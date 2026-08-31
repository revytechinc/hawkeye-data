#!/usr/bin/env python3
"""Extract FreeBSD adoc/mdoc into a corpus, chunk it, and assemble sqlite documents.

Subcommands:
  extract   cache/ -> corpus/collected/*.md
  chunk     corpus + playbooks + docs -> dist/chunks/*.jsonl.gz + dist/manifest.json
  load      insert corpus/collected into an existing sqlite DB
  assemble  dist/chunks (+ playbooks via SQL from caller) -> documents in sqlite
  finalize  FTS rebuild, optional embed fill, meta, VACUUM

Copyright (c) 2026, REVYTECH, Inc.  BSD 3-Clause.
"""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GITHUB_CHUNK_MAX = 41943040  # 40 MiB
GITHUB_CHUNK_WARN = 41943040
GITHUB_FILE_FAIL = 94371840  # 90 MiB
GITHUB_SQLITE_SKIP = 52428800  # 50 MiB: still build, do not commit

SKIP_DOC_NAMES = {"TEST-EVIDENCE.md", "test-evidence.md"}


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_revisions(root: Path) -> dict:
    p = root / "cache" / "revisions.json"
    if p.is_file():
        return load_json(p)
    return {"collected_at": "", "sources": {}}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# AsciiDoc
# ---------------------------------------------------------------------------

FRONT_MATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.S)
YAML_TITLE_RE = re.compile(r"^title:\s*(.+)$", re.M)
ADOC_TITLE_RE = re.compile(r"^={1,3}\s+(.+)$", re.M)
ATTR_RE = re.compile(r"^:[^:\n]+:[^\n]*$", re.M)
IFDEF_RE = re.compile(r"^ifn?def::[^\n]*$", re.M)
ENDIF_RE = re.compile(r"^endif::[^\n]*$", re.M)
INCLUDE_RE = re.compile(r"^include::[^\n]*$", re.M)
TOC_RE = re.compile(r"^toc::[^\n]*$", re.M)


def parse_front_matter(text: str) -> tuple[dict, str]:
    meta: dict = {}
    m = FRONT_MATTER_RE.match(text)
    if not m:
        return meta, text
    fm = m.group(1)
    body = text[m.end():]
    for line in fm.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip().strip("\"'")
        if k and not k.startswith(" ") and k not in ("authors", "tags", "trademarks"):
            # skip nested yaml lists dumped as "- foo"
            if k.startswith("-"):
                continue
            meta[k] = v
    return meta, body


def adoc_to_text(src: str) -> tuple[str, str]:
    meta, body = parse_front_matter(src)
    title = meta.get("title") or ""
    # drop hugo/asciidoctor chrome that is not prose
    lines = []
    skip_block = False  # leftover; keep simple
    for line in body.splitlines():
        if ATTR_RE.match(line) or IFDEF_RE.match(line) or ENDIF_RE.match(line):
            continue
        if INCLUDE_RE.match(line) or TOC_RE.match(line):
            continue
        if line.strip() in ("ifdef::[]", "ifndef::[]", "endif::[]"):
            continue
        lines.append(line)
    body2 = "\n".join(lines)
    body2 = re.sub(r"\[\[.*?\]\]\s*", "", body2)
    body2 = re.sub(r"\[source,[^\]]*\]\s*", "", body2)
    body2 = re.sub(r"\[NOTE\]|\[WARNING\]|\[TIP\]|\[IMPORTANT\]|\[CAUTION\]", "", body2)
    body2 = body2.replace("....", "")
    body2 = re.sub(r"\[\.filename\]#([^#]+)#", r"`\1`", body2)
    body2 = re.sub(r"man:([a-zA-Z0-9._-]+)\[(\d+)\]", r"\1(\2)", body2)
    body2 = re.sub(r"crossref:[^\[]+\[([^\]]*)\]", r"\1", body2)
    body2 = re.sub(r"link:[^\[]+\[([^\]]*)\]", r"\1", body2)
    body2 = re.sub(r"https?://\S+\[([^\]]+)\]", r"\1", body2)
    body2 = re.sub(r"<<[^,>]+,([^>]+)>>", r"\1", body2)
    body2 = re.sub(r"<<([^>]+)>>", r"\1", body2)
    if not title:
        m = ADOC_TITLE_RE.search(body2)
        if m:
            title = m.group(1).strip()
    title = title.strip()
    body2 = body2.strip() + "\n"
    return title, body2


# ---------------------------------------------------------------------------
# mdoc -> rough plaintext (good enough for FTS; no mandoc on this host)
# ---------------------------------------------------------------------------

COMMENT_RE = re.compile(r'^\.\\"')
SO_RE = re.compile(r"^\.so\s+(\S+)")


def _mdoc_unescape(s: str) -> str:
    s = s.replace(r"\&", "")
    s = s.replace(r"\-", "-")
    s = s.replace(r"\(em", "—")
    s = s.replace(r"\(en", "–")
    s = s.replace(r"\(lq", '"')
    s = s.replace(r"\(rq", '"')
    s = s.replace(r"\(aq", "'")
    s = s.replace(r"\(dq", '"')
    s = s.replace(r"\.", ".")
    s = s.replace(r"\e", "\\")
    s = re.sub(r"\\f[BIRP]", "", s)
    s = re.sub(r"\\s[+-]?\d+", "", s)
    s = re.sub(r"\\\(.[^)]*\)", "", s)
    s = re.sub(r"\\\[.*?\]", "", s)
    return s


def _split_mdoc_args(s: str) -> list[str]:
    # very small: keep quoted phrases together
    out = []
    buf = []
    in_q = False
    for ch in s:
        if ch == '"':
            in_q = not in_q
            continue
        if ch.isspace() and not in_q:
            if buf:
                out.append("".join(buf))
                buf = []
            continue
        buf.append(ch)
    if buf:
        out.append("".join(buf))
    return out


HEADING_MACROS = {"Sh", "SH", "Ss", "SS"}
BREAK_MACROS = {"Pp", "PP", "Lp", "sp", "D1", "Dl"}
SKIP_MACROS = {
    "Dd", "Dt", "Os", "Bk", "Ek", "Bd", "Ed", "Bl", "El", "It",
    "Rs", "Re", "%A", "%T", "%O", "%D", "%B", "%I", "%N", "%J", "%P", "%U", "%Q",
    "Xr",  # handled specially
}


def _strip_overstrike(s: str) -> str:
    # mandoc -Tutf8 uses backspace overstrike for bold/underline
    while "\x08" in s:
        s = re.sub(r".\x08", "", s)
    s = s.replace("\x08", "")
    return s


def mdoc_via_mandoc(src_path: Path) -> tuple[str, str] | None:
    mandoc = shutil.which("mandoc")
    if not mandoc or not src_path.is_file():
        return None
    try:
        r = subprocess.run(
            [mandoc, "-T", "utf8", str(src_path)],
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0 or not r.stdout:
        return None
    text = _strip_overstrike(r.stdout.decode("utf-8", errors="replace"))
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    if len(text) < 40:
        return None
    title = ""
    m = re.search(r"^(?:NAME|Name)\n\s+(.+)$", text, re.M)
    if m:
        title = m.group(1).strip()
    if not title:
        m = re.search(r"^([A-Z0-9._-]+)\(\d+\)", text)
        if m:
            title = m.group(1)
    if not title:
        title = src_path.stem
    return title, text


def mdoc_to_text(src: str, src_path: Path | None = None) -> tuple[str, str]:
    if src_path is not None:
        via = mdoc_via_mandoc(src_path)
        if via:
            return via
    # Follow .so if the target exists next to us (or relative)
    lines_in = src.splitlines()
    if lines_in:
        mso = SO_RE.match(lines_in[0].strip())
        if mso and src_path is not None:
            target = (src_path.parent / mso.group(1)).resolve()
            if not target.is_file():
                # man8/foo.8 style from share/man
                alt = src_path.parent / Path(mso.group(1)).name
                if alt.is_file():
                    target = alt
            if target.is_file():
                try:
                    src = target.read_text(encoding="utf-8", errors="replace")
                    src_path = target
                except OSError:
                    pass

    title = ""
    out: list[str] = []
    name_bits: list[str] = []
    in_name = False

    for raw in src.splitlines():
        if COMMENT_RE.match(raw) or raw.startswith(".\\\""):
            continue
        raw = _mdoc_unescape(raw)
        if not raw.startswith("."):
            if raw.strip():
                out.append(raw)
            elif out and out[-1] != "":
                out.append("")
            continue
        # macro line
        rest = raw[1:]
        if not rest.strip():
            continue
        parts = rest.split(None, 1)
        macro = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        argv = _split_mdoc_args(args)

        if macro in ("Dt",):
            if argv and not title:
                title = " ".join(argv)
            continue
        if macro in ("Nd",):
            name_bits.append(" ".join(argv))
            continue
        if macro in ("Nm",) and in_name:
            name_bits.append(" ".join(argv) if argv else "")
            continue
        if macro in HEADING_MACROS:
            heading = " ".join(argv) if argv else ""
            in_name = heading.upper() == "NAME"
            level = "##" if macro in ("Sh", "SH") else "###"
            out.append("")
            out.append(f"{level} {heading}".rstrip())
            out.append("")
            continue
        if macro in BREAK_MACROS:
            if out and out[-1] != "":
                out.append("")
            if argv:
                out.append(" ".join(argv))
            continue
        if macro == "It":
            bullet = " ".join(argv).strip()
            out.append(f"- {bullet}" if bullet else "-")
            continue
        if macro == "Xr":
            if len(argv) >= 2:
                out.append(f"{argv[0]}({argv[1]})")
            elif argv:
                out.append(argv[0])
            continue
        if macro in ("Fl",):
            flags = " ".join("-" + a if not a.startswith("-") else a for a in argv)
            out.append(flags)
            continue
        if macro in SKIP_MACROS:
            if argv:
                out.append(" ".join(argv))
            continue
        # default: keep arguments (Nm, Cm, Ar, Pa, Va, ...)
        if argv:
            out.append(" ".join(argv))
        elif macro == "Nm" and title:
            out.append(title.split()[0])

    body = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"
    if not title:
        # first .Nm
        m = re.search(r"^\.Nm\s+(\S+)", src, re.M)
        if m:
            title = m.group(1)
        else:
            title = src_path.stem if src_path else "untitled"
    if name_bits:
        nd = " ".join(x for x in name_bits if x).strip()
        if nd and nd not in title:
            title = f"{title} — {nd}" if "—" not in title and " - " not in title else title
    return title.strip(), body


# ---------------------------------------------------------------------------
# Path -> category / chunk group
# ---------------------------------------------------------------------------

BOOK_CAT = {
    "handbook": "freebsd-handbook",
    "faq": "freebsd-faq",
    "porters-handbook": "freebsd-porters-handbook",
    "developers-handbook": "freebsd-developers-handbook",
    "arch-handbook": "freebsd-arch-handbook",
    "fdp-primer": "freebsd-fdp-primer",
    "accessibility": "freebsd-accessibility",
    "design-44bsd": "freebsd-design-44bsd",
    "dev-model": "freebsd-dev-model",
}


def classify_adoc(rel: str) -> tuple[str, str]:
    """Return (category, chunk_group). rel uses posix slashes from cache root."""
    parts = rel.split("/")
    # documentation/content/en/books/<book>/...
    if "books" in parts:
        i = parts.index("books")
        book = parts[i + 1] if i + 1 < len(parts) else "book"
        cat = BOOK_CAT.get(book, f"freebsd-{book}")
        if book == "handbook":
            return cat, "handbook"
        return cat, "books-other"
    if "articles" in parts:
        return "freebsd-articles", "articles"
    return "freebsd-doc", "freebsd-doc"


def classify_mdoc(rel: str) -> tuple[str, str]:
    name = Path(rel).name
    if rel in ("UPDATING", "RELNOTES") or name in ("UPDATING", "RELNOTES"):
        return "freebsd-updating", "updating"
    # section from filename
    m = re.search(r"\.(\d)(?:\.in)?$", name)
    sec = m.group(1) if m else ""
    if "openzfs" in rel.replace("\\", "/"):
        cat = f"freebsd-man{sec}" if sec else "freebsd-man8"
        return cat, "man8" if sec in ("", "8") else f"man{sec}"
    if sec == "8" or "/man8/" in rel:
        return "freebsd-man8", "man8"
    if sec == "4" or "/man4/" in rel:
        return "freebsd-man4", "man4"
    if sec == "5" or "/man5/" in rel:
        return "freebsd-man5", "man5"
    if sec == "7" or "/man7/" in rel:
        return "freebsd-man7", "man7"
    return "freebsd-man", "man-other"


def glob_match(path: str, pattern: str) -> bool:
    """Minimal glob: ** / * only, posix paths."""
    import fnmatch
    if pattern.startswith("**/"):
        # match anywhere
        tail = pattern[3:]
        if fnmatch.fnmatch(path, tail) or fnmatch.fnmatch(os.path.basename(path), tail):
            return True
        if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, "*/*/" + tail):
            return True
        # any prefix
        parts = path.split("/")
        for i in range(len(parts)):
            if fnmatch.fnmatch("/".join(parts[i:]), tail) or fnmatch.fnmatch(parts[i], tail):
                return True
            if fnmatch.fnmatch(parts[i], tail.replace("**/", "")):
                return True
        return fnmatch.fnmatch(path, pattern)
    return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(os.path.basename(path), pattern)


def matches_globs(rel: str, include: list[str], exclude: list[str]) -> bool:
    if any(glob_match(rel, g) for g in exclude):
        return False
    if not include:
        return True
    return any(glob_match(rel, g) for g in include)


def doc_id(source_id: str, rel: str) -> str:
    rel = rel.replace("\\", "/")
    rel = re.sub(r"^documentation/content/en/", "", rel)
    rel = re.sub(r"\.(adoc|mdoc|8\.in|5\.in|4\.in|7\.in|4|5|7|8|md|txt)$", "", rel)
    rel = rel.strip("/")
    return f"{source_id}:{rel}"


def write_corpus_md(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = [
        "---",
        f"id: {rec['id']}",
        f"title: {json.dumps(rec['title'], ensure_ascii=False)}",
        f"category: {rec['category']}",
        f"path: {rec['path']}",
        f"source: {rec['source']}",
        f"git_rev: {rec.get('git_rev') or ''}",
        f"collected_at: {rec.get('collected_at') or ''}",
        f"chunk_group: {rec.get('chunk_group') or ''}",
        "---",
        "",
        rec["body"].rstrip(),
        "",
    ]
    path.write_text("\n".join(fm), encoding="utf-8")


def read_corpus_md(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta, body = parse_front_matter(text)
    if not meta.get("id"):
        return None
    title = meta.get("title") or path.stem
    if len(title) >= 2 and title[0] == '"' and title[-1] == '"':
        title = json.loads(title)
    return {
        "kind": "document",
        "id": meta["id"],
        "title": title,
        "category": meta.get("category") or "",
        "path": meta.get("path") or str(path),
        "body": body,
        "source": meta.get("source") or "",
        "git_rev": meta.get("git_rev") or "",
        "collected_at": meta.get("collected_at") or "",
        "chunk_group": meta.get("chunk_group") or "",
    }


# ---------------------------------------------------------------------------
# extract
# ---------------------------------------------------------------------------

def cmd_extract(root: Path) -> int:
    cfg = load_json(root / "collect" / "sources.json")
    revs = load_revisions(root)
    collected_at = revs.get("collected_at") or utcnow()
    out_root = root / "corpus" / "collected"
    out_root.mkdir(parents=True, exist_ok=True)

    n = 0
    skipped = 0
    for src in cfg["sources"]:
        sid = src["id"]
        cache = root / src["cache_dir"]
        if not cache.is_dir():
            print(f"extract: skip {sid}: cache missing {cache}", file=sys.stderr)
            continue
        git_rev = (revs.get("sources") or {}).get(sid, {}).get("git_rev") or ""
        include = src.get("include_globs") or []
        exclude = src.get("exclude_globs") or []
        kind = src.get("kind") or "text"
        dest_src = out_root / sid
        if dest_src.exists():
            # rebuild this source tree
            import shutil
            shutil.rmtree(dest_src)

        files = []
        for dirpath, dirnames, filenames in os.walk(cache):
            # skip .git
            dirnames[:] = [d for d in dirnames if d != ".git"]
            for fn in filenames:
                if fn.endswith(".po"):
                    skipped += 1
                    continue
                full = Path(dirpath) / fn
                rel = full.relative_to(cache).as_posix()
                if not matches_globs(rel, include, exclude):
                    # root UPDATING/RELNOTES explicitly
                    if fn in ("UPDATING", "RELNOTES") and "/" not in rel:
                        pass
                    else:
                        continue
                files.append((full, rel))

        for full, rel in files:
            try:
                raw = full.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                print(f"extract: cannot read {full}: {e}", file=sys.stderr)
                continue
            if kind == "adoc":
                if not rel.endswith(".adoc"):
                    continue
                title, body = adoc_to_text(raw)
                category, group = classify_adoc(rel)
            elif kind == "mdoc":
                title, body = mdoc_to_text(raw, full)
                category, group = classify_mdoc(rel)
            else:
                title = full.stem
                body = raw
                category, group = "freebsd-src", "src-other"

            if len(body.strip()) < 40:
                skipped += 1
                continue
            rec = {
                "id": doc_id(sid, rel),
                "title": title or full.stem,
                "category": category,
                "path": rel,
                "body": body,
                "source": sid,
                "git_rev": git_rev,
                "collected_at": collected_at,
                "chunk_group": group,
            }
            outp = dest_src / (rel + ".md")
            write_corpus_md(outp, rec)
            n += 1

        print(f"extract: {sid} {n} documents so far")

    print(f"extract: wrote {n} documents ({skipped} skipped) -> {out_root}")
    return 0


# ---------------------------------------------------------------------------
# playbooks / hawkeye docs as chunk records
# ---------------------------------------------------------------------------

def fm_get_all(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return parse_front_matter(text)


def yn_to_int(v: str) -> int:
    return 1 if str(v).strip().lower() in ("yes", "true", "y", "1") else 0


def playbook_commands(body: str) -> str:
    lines = body.splitlines()
    want = False
    in_cmd = False
    cmds = []
    for line in lines:
        if re.match(r"^##\s*Commands", line):
            want = True
            continue
        if want and line.startswith("```"):
            if in_cmd:
                break
            in_cmd = True
            continue
        if in_cmd:
            if line == "":
                continue
            cmds.append(line)
    return json.dumps(cmds, ensure_ascii=False)


def load_playbooks(root: Path) -> list[dict]:
    out = []
    pb = root / "playbooks"
    if not pb.is_dir():
        return out
    for f in sorted(pb.glob("*.md")):
        meta, body = fm_get_all(f)
        if not meta.get("id"):
            continue
        rw = yn_to_int(meta.get("requires_rw", "no"))
        net = yn_to_int(meta.get("requires_net", "no"))
        zfs = yn_to_int(meta.get("requires_zfs", "no"))
        ufs = yn_to_int(meta.get("requires_ufs", "no"))
        pre = meta.get("preconditions") or json.dumps(
            {"rw": bool(rw), "net": bool(net), "zfs": bool(zfs), "ufs": bool(ufs)}
        )
        rec = {
            "kind": "playbook",
            "id": meta["id"],
            "title": meta.get("title") or meta["id"],
            "when_to_use": meta.get("when_to_use") or "",
            "preconditions": pre,
            "commands": playbook_commands(body),
            "danger_flags": meta.get("danger_flags") or "[]",
            "rollback_notes": meta.get("rollback_notes") or "",
            "body": body,
            "requires_rw": rw,
            "requires_net": net,
            "requires_zfs": zfs,
            "requires_ufs": ufs,
            "path": f"playbooks/{f.name}",
            "category": "playbook",
            "source": "hawkeye",
            "git_rev": "",
            "collected_at": "",
            "chunk_group": "playbooks",
        }
        out.append(rec)
    return out


def load_hawkeye_docs(root: Path) -> list[dict]:
    out = []
    docs = root / "docs"
    if not docs.is_dir():
        return out
    for f in sorted(docs.glob("*.md")):
        if f.name in SKIP_DOC_NAMES:
            continue
        meta, body = fm_get_all(f)
        if not meta.get("id"):
            rec = {
                "kind": "document",
                "id": f.stem,
                "title": f.stem,
                "category": "docs",
                "path": f"docs/{f.name}",
                "body": f.read_text(encoding="utf-8", errors="replace"),
                "source": "hawkeye",
                "git_rev": "",
                "collected_at": "",
                "chunk_group": "hawkeye-docs",
            }
            out.append(rec)
            continue
        rec = {
            "kind": "document",
            "id": meta["id"],
            "title": meta.get("title") or meta["id"],
            "category": meta.get("category") or "docs",
            "path": f"docs/{f.name}",
            "body": body if body.strip() else f.read_text(encoding="utf-8", errors="replace"),
            "source": "hawkeye",
            "git_rev": "",
            "collected_at": "",
            "chunk_group": "hawkeye-docs",
        }
        out.append(rec)
    return out


def load_collected(root: Path) -> list[dict]:
    out = []
    base = root / "corpus" / "collected"
    if not base.is_dir():
        return out
    for p in sorted(base.rglob("*.md")):
        rec = read_corpus_md(p)
        if rec:
            rec["kind"] = "document"
            out.append(rec)
    return out


def record_to_chunk_obj(rec: dict) -> dict:
    if rec.get("kind") == "playbook":
        keys = [
            "kind", "id", "title", "when_to_use", "preconditions", "commands",
            "danger_flags", "rollback_notes", "body", "requires_rw", "requires_net",
            "requires_zfs", "requires_ufs", "path", "category", "source", "git_rev",
        ]
    else:
        keys = ["kind", "id", "title", "category", "path", "body", "source", "git_rev"]
    obj = {k: rec.get(k) for k in keys}
    if "kind" not in obj or not obj["kind"]:
        obj["kind"] = "document"
    return obj


def dumps_jsonl(records: list[dict]) -> bytes:
    # stable order: sort by id
    records = sorted(records, key=lambda r: (r.get("kind") or "", r.get("id") or ""))
    lines = []
    for rec in records:
        obj = record_to_chunk_obj(rec)
        lines.append(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    blob = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
    return gzip.compress(blob, mtime=0, compresslevel=9)


def split_if_needed(group: str, records: list[dict], max_bytes: int) -> list[tuple[str, list[dict], bytes]]:
    """Return list of (chunk_id, records, gzip_bytes). Split if gzip would exceed max."""
    payload = dumps_jsonl(records)
    if len(payload) <= max_bytes:
        return [(group, records, payload)]
    # split by walking until gzip would exceed
    parts: list[tuple[str, list[dict], bytes]] = []
    batch: list[dict] = []
    idx = 0
    for rec in sorted(records, key=lambda r: r.get("id") or ""):
        trial = batch + [rec]
        trial_gz = dumps_jsonl(trial)
        if batch and len(trial_gz) > max_bytes:
            parts.append((f"{group}-{idx:02d}", batch, dumps_jsonl(batch)))
            idx += 1
            batch = [rec]
        else:
            batch = trial
    if batch:
        parts.append((f"{group}-{idx:02d}", batch, dumps_jsonl(batch)))
    return parts


def cmd_chunk(root: Path) -> int:
    cfg = load_json(root / "collect" / "sources.json")
    max_b = int(os.environ.get("GITHUB_CHUNK_MAX") or cfg.get("github_chunk_max") or GITHUB_CHUNK_MAX)
    warn_b = int(cfg.get("github_chunk_warn") or GITHUB_CHUNK_WARN)
    fail_b = int(cfg.get("github_file_fail") or GITHUB_FILE_FAIL)

    revs = load_revisions(root)
    collected = load_collected(root)
    playbooks = load_playbooks(root)
    docs = load_hawkeye_docs(root)
    # corpus/collected is gitignored. A checkout without extract must not
    # treat handbook/man chunks as stale — only rebuild live hawkeye groups.
    live_only = not collected

    groups: dict[str, list[dict]] = defaultdict(list)
    for rec in collected:
        g = rec.get("chunk_group") or "misc"
        groups[g].append(rec)
    for rec in playbooks:
        groups["playbooks"].append(rec)
    for rec in docs:
        groups["hawkeye-docs"].append(rec)

    dist = root / "dist"
    chunks_dir = dist / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    old_manifest_path = dist / "manifest.json"
    old = {}
    if old_manifest_path.is_file():
        try:
            old = load_json(old_manifest_path)
        except json.JSONDecodeError:
            old = {}
    old_by_id = {c["id"]: c for c in old.get("chunks") or []}

    new_chunks = []
    source_ids = sorted({r.get("source") or "" for r in collected if r.get("source")})
    git_revs = {
        sid: (revs.get("sources") or {}).get(sid, {}).get("git_rev")
        for sid in source_ids
    }
    if live_only:
        # Keep harvested source ids/revs from the last full chunk.
        source_ids = sorted(set(source_ids) | set(old.get("source_ids") or []) - {""})
        for sid, rev in (old.get("git_rev") or {}).items():
            if rev and not git_revs.get(sid):
                git_revs[sid] = rev
        print("chunk: no corpus/collected; rebuilding playbooks/hawkeye-docs only")

    # stable group order
    order = [
        "playbooks", "hawkeye-docs", "handbook", "books-other", "articles",
        "man8", "man7", "man5", "man4", "man-other", "updating",
    ]
    group_names = [g for g in order if g in groups] + sorted(g for g in groups if g not in order)

    written = 0
    reused = 0
    keep_names = set()

    for g in group_names:
        recs = groups[g]
        if not recs:
            continue
        for cid, batch, payload in split_if_needed(g, recs, max_b):
            digest = sha256_bytes(payload)
            nbytes = len(payload)
            fname = f"chunk-{cid}.jsonl.gz"
            fpath = chunks_dir / fname
            rel = f"dist/chunks/{fname}"
            keep_names.add(fname)

            if nbytes >= fail_b:
                print(f"chunk: FAIL {fname} is {nbytes} bytes (>= {fail_b})", file=sys.stderr)
                return 1
            if nbytes >= warn_b:
                print(f"chunk: WARN {fname} is {nbytes} bytes (warn at {warn_b})", file=sys.stderr)

            prev = old_by_id.get(cid)
            if prev and prev.get("sha256") == digest and fpath.is_file() and sha256_file(fpath) == digest:
                reused += 1
                action = "reuse"
            else:
                fpath.write_bytes(payload)
                written += 1
                action = "write"
                print(f"chunk: {action} {fname} {nbytes} bytes sha256={digest}")

            srcs = sorted({r.get("source") or "" for r in batch if r.get("source")})
            new_chunks.append({
                "id": cid,
                "path": rel,
                "sha256": digest,
                "bytes": nbytes,
                "count": len(batch),
                "source_ids": srcs,
                "git_rev": {s: git_revs.get(s) for s in srcs if git_revs.get(s)},
            })

    if live_only:
        live_ids = {c["id"] for c in new_chunks}
        for prev in old.get("chunks") or []:
            cid = prev.get("id")
            if not cid or cid in live_ids:
                continue
            fname = Path(prev.get("path") or f"dist/chunks/chunk-{cid}.jsonl.gz").name
            fpath = chunks_dir / fname
            if not fpath.is_file():
                print(f"chunk: skip missing harvested {fname}", file=sys.stderr)
                continue
            if prev.get("sha256") and sha256_file(fpath) != prev["sha256"]:
                print(f"chunk: skip {fname}: sha256 mismatch vs manifest", file=sys.stderr)
                continue
            keep_names.add(fname)
            new_chunks.append(prev)
            reused += 1

    # remove stale chunk files not in new manifest
    for existing in chunks_dir.glob("chunk-*"):
        if existing.name not in keep_names:
            print(f"chunk: remove stale {existing.name}")
            existing.unlink()

    out_sources = list(source_ids)
    if "hawkeye" not in out_sources:
        out_sources.append("hawkeye")
    manifest = {
        "format": "hawkeye-chunks-v1",
        "chunk_max": max_b,
        "built_at": utcnow(),
        "source_ids": out_sources,
        "git_rev": git_revs,
        "chunks": new_chunks,
    }
    # stable json
    old_bytes = old_manifest_path.read_bytes() if old_manifest_path.is_file() else b""
    new_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    # built_at always changes; compare chunks only for "idempotent sha of chunk files"
    if old_bytes != new_bytes:
        # If only built_at differs, still rewrite (manifest is tiny). Chunk files already reused.
        old_manifest_path.write_bytes(new_bytes)

    print(f"chunk: {len(new_chunks)} chunks ({written} written, {reused} reused)")
    return 0


# ---------------------------------------------------------------------------
# sqlite load / assemble
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "2"


def apply_schema(conn: sqlite3.Connection, schema_sql: str) -> None:
    conn.executescript(schema_sql)


def insert_document(conn: sqlite3.Connection, rec: dict) -> None:
    conn.execute(
        """INSERT INTO documents (id, title, category, path, body, source, git_rev, collected_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             title=excluded.title,
             category=excluded.category,
             path=excluded.path,
             body=excluded.body,
             source=excluded.source,
             git_rev=excluded.git_rev,
             collected_at=excluded.collected_at
        """,
        (
            rec.get("id"),
            rec.get("title") or rec.get("id"),
            rec.get("category") or "",
            rec.get("path") or "",
            rec.get("body") or "",
            rec.get("source") or "",
            rec.get("git_rev") or "",
            rec.get("collected_at") or "",
        ),
    )


def insert_playbook(conn: sqlite3.Connection, rec: dict) -> None:
    conn.execute(
        """INSERT INTO playbooks (
             id, title, when_to_use, preconditions, commands, danger_flags,
             rollback_notes, body, requires_rw, requires_net, requires_zfs, requires_ufs, path
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             title=excluded.title,
             when_to_use=excluded.when_to_use,
             preconditions=excluded.preconditions,
             commands=excluded.commands,
             danger_flags=excluded.danger_flags,
             rollback_notes=excluded.rollback_notes,
             body=excluded.body,
             requires_rw=excluded.requires_rw,
             requires_net=excluded.requires_net,
             requires_zfs=excluded.requires_zfs,
             requires_ufs=excluded.requires_ufs,
             path=excluded.path
        """,
        (
            rec.get("id"),
            rec.get("title") or rec.get("id"),
            rec.get("when_to_use") or "",
            rec.get("preconditions") or "{}",
            rec.get("commands") or "[]",
            rec.get("danger_flags") or "[]",
            rec.get("rollback_notes") or "",
            rec.get("body") or "",
            int(rec.get("requires_rw") or 0),
            int(rec.get("requires_net") or 0),
            int(rec.get("requires_zfs") or 0),
            int(rec.get("requires_ufs") or 0),
            rec.get("path") or "",
        ),
    )


def _fill_embeddings(conn: sqlite3.Connection) -> dict:
    """Optional local-embedder fill. No-op when no embedder is configured."""
    path = Path(__file__).resolve().parent / "embed.py"
    if not path.is_file():
        return {"status": "skip", "count": 0, "model": ""}
    spec = importlib.util.spec_from_file_location("hawkeye_embed", path)
    if spec is None or spec.loader is None:
        return {"status": "skip", "count": 0, "model": ""}
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.fill_connection(conn, vacuum=False)


def rebuild_fts_and_meta(conn: sqlite3.Connection, extra_meta: dict) -> None:
    # External-content FTS5: rebuild from base tables (keeps FTS in sync after schema v2).
    conn.execute("INSERT INTO playbooks_fts(playbooks_fts) VALUES('rebuild')")
    conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
    # Precomputed embeddings when a local embedder is configured. Skip (empty
    # table) is the default harvest; Tier 0 still uses FTS5.
    emb = _fill_embeddings(conn)
    n_play = conn.execute("SELECT COUNT(*) FROM playbooks").fetchone()[0]
    n_doc = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    n_emb = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    meta = {
        "schema_version": SCHEMA_VERSION,
        "corpus_id": "hawkeye-data",
        "built_at": utcnow(),
        "playbook_count": str(n_play),
        "document_count": str(n_doc),
        "fts": "mandatory",
        "embeddings": "populated" if n_emb else "optional-empty",
    }
    if n_emb:
        meta["embed_count"] = str(n_emb)
        if emb.get("model"):
            meta["embed_model"] = emb["model"]
    meta.update(extra_meta)
    # Caller extra_meta must not wipe the embeddings status if it omitted it.
    if "embeddings" not in extra_meta:
        meta["embeddings"] = "populated" if n_emb else "optional-empty"
    conn.execute("DELETE FROM meta")
    conn.executemany("INSERT INTO meta(key, value) VALUES (?, ?)", list(meta.items()))
    conn.execute("INSERT INTO playbooks_fts(playbooks_fts) VALUES('optimize')")
    conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('optimize')")
    conn.execute("PRAGMA journal_mode = DELETE")
    conn.commit()
    conn.execute("VACUUM")
    ic = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if ic != "ok":
        raise SystemExit(f"integrity_check={ic}")


def extra_from_revs_or_manifest(root: Path, conn: sqlite3.Connection | None = None) -> dict:
    """meta.source / git_rev / collected_at. Fall back to dist/manifest when cache/ is gone."""
    revs = load_revisions(root)
    sources = set((revs.get("sources") or {}).keys())
    git_rev = {
        k: v.get("git_rev") for k, v in (revs.get("sources") or {}).items() if v.get("git_rev")
    }
    collected_at = revs.get("collected_at") or ""
    man = root / "dist" / "manifest.json"
    if man.is_file() and (not sources or not git_rev):
        spec = load_json(man)
        sources |= {s for s in (spec.get("source_ids") or []) if s}
        for k, v in (spec.get("git_rev") or {}).items():
            if v and not git_rev.get(k):
                git_rev[k] = v
    if conn is not None:
        if not git_rev:
            for src, rev in conn.execute(
                "SELECT DISTINCT source, git_rev FROM documents "
                "WHERE source != '' AND git_rev != ''"
            ):
                sources.add(src)
                if rev:
                    git_rev[src] = rev
        if not collected_at:
            row = conn.execute(
                "SELECT collected_at FROM documents WHERE collected_at != '' LIMIT 1"
            ).fetchone()
            if row:
                collected_at = row[0]
    if not collected_at:
        sources_md = root / "SOURCES.md"
        if sources_md.is_file():
            m = re.search(r"Collected at:\s*`([^`]+)`", sources_md.read_text(encoding="utf-8"))
            if m:
                collected_at = m.group(1)
    sources.add("hawkeye")
    sources.discard("")
    return {
        "source": ",".join(sorted(sources)),
        "git_rev": json.dumps(git_rev, sort_keys=True),
        "collected_at": collected_at,
    }


def cmd_load_corpus(root: Path, db_path: Path) -> int:
    """Insert corpus/collected documents into existing DB (playbooks already loaded)."""
    conn = sqlite3.connect(str(db_path))
    recs = load_collected(root)
    for rec in recs:
        insert_document(conn, rec)
    conn.commit()
    print(f"load-corpus: {len(recs)} documents into {db_path}")
    conn.close()
    return 0


def iter_chunk_records(root: Path):
    man = root / "dist" / "manifest.json"
    if not man.is_file():
        return
    spec = load_json(man)
    for ch in spec.get("chunks") or []:
        p = root / ch["path"]
        if not p.is_file():
            print(f"assemble: missing chunk {p}", file=sys.stderr)
            continue
        with gzip.open(p, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)


def cmd_assemble(root: Path, db_path: Path) -> int:
    schema = (root / "schema" / "knowledge.sql").read_text(encoding="utf-8")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    apply_schema(conn, schema)

    n_doc = n_play = 0
    # Prefer live playbooks/ markdown so Hawkeye originals stay canonical.
    live_pb = {r["id"] for r in load_playbooks(root)}
    live_docs = {r["id"] for r in load_hawkeye_docs(root)}
    for rec in load_playbooks(root):
        insert_playbook(conn, rec)
        n_play += 1
    for rec in load_hawkeye_docs(root):
        insert_document(conn, rec)
        n_doc += 1

    for rec in iter_chunk_records(root):
        kind = rec.get("kind") or "document"
        if kind == "playbook":
            if rec.get("id") in live_pb:
                continue
            insert_playbook(conn, rec)
            n_play += 1
        else:
            if rec.get("id") in live_docs:
                continue
            insert_document(conn, rec)
            n_doc += 1

    extra = extra_from_revs_or_manifest(root, conn)
    rebuild_fts_and_meta(conn, extra)
    conn.close()
    nbytes = db_path.stat().st_size
    print(f"assemble: {db_path} ({n_play} playbooks, {n_doc}+chunk documents, {nbytes} bytes)")
    if nbytes >= GITHUB_SQLITE_SKIP:
        print(
            f"assemble: sqlite is {nbytes} bytes (>= 50MB); do not commit the DB, "
            "install via `make db` / scripts/assemble.sh from dist/chunks.",
            file=sys.stderr,
        )
    return 0


def cmd_finalize(root: Path, db_path: Path) -> int:
    """After POSIX playbook/doc load + load-corpus, rebuild FTS/meta/vacuum."""
    conn = sqlite3.connect(str(db_path))
    extra = extra_from_revs_or_manifest(root, conn)
    rebuild_fts_and_meta(conn, extra)
    conn.close()
    nbytes = db_path.stat().st_size
    n_play = sqlite3.connect(str(db_path)).execute("SELECT COUNT(*) FROM playbooks").fetchone()[0]
    n_doc = sqlite3.connect(str(db_path)).execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    print(f"finalize: {db_path} ({n_play} playbooks, {n_doc} documents, {nbytes} bytes)")
    if nbytes >= GITHUB_SQLITE_SKIP:
        print(
            f"finalize: sqlite is {nbytes} bytes (>= 50MB); keep chunks as the git artifact.",
            file=sys.stderr,
        )
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print("usage: corpus.py extract|chunk|load-corpus|assemble|finalize [db]", file=sys.stderr)
        print("  finalize/assemble also run embed.py when a local embedder is set", file=sys.stderr)
        return 2
    cmd = argv[1]
    root = ROOT
    if cmd == "extract":
        return cmd_extract(root)
    if cmd == "chunk":
        return cmd_chunk(root)
    if cmd == "load-corpus":
        db = Path(argv[2]) if len(argv) > 2 else root / "share" / "knowledge.sqlite"
        return cmd_load_corpus(root, db)
    if cmd == "assemble":
        db = Path(argv[2]) if len(argv) > 2 else root / "share" / "knowledge.sqlite"
        return cmd_assemble(root, db)
    if cmd == "finalize":
        db = Path(argv[2]) if len(argv) > 2 else root / "share" / "knowledge.sqlite"
        return cmd_finalize(root, db)
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
