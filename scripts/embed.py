#!/usr/bin/env python3
"""Fill knowledge.sqlite embeddings from a local embedder.

Copyright (c) 2026, REVYTECH, Inc.  BSD 3-Clause.

The embeddings table is optional. This tool:

  * skips (exit 0) when no local embedder is configured, so the default
    harvest stays FTS-only;
  * writes deterministic dim-8 FLOAT32 blobs when HAWKEYE_EMBED_FAKE=1
    (CI / tests — no GGUF, no network);
  * invokes a llama.cpp-style binary when HAWKEYE_EMBED_BIN and
    HAWKEYE_EMBED_MODEL are set (local only; never a hosted API).
    llama-embedding (basename) omits --embedding and --no-display-prompt
    (llama-cpp-9426 rejects both) and defaults --pooling mean plus
    --embd-separator '<#sep#>'. No wrap script. HAWKEYE_EMBED_ARGS
    still appends/overrides.

Vectors are little-endian FLOAT32 blobs, matching Hawkeye PackF32 /
sqlite-vec. sqlite-vec is not required at build time.

Do not commit GGUF files, API keys, or cloud embeddings.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shlex
import sqlite3
import struct
import subprocess
import sys
from pathlib import Path

FAKE_DIM = 8
FAKE_MODEL = "fake-dim8"
TEXT_CAP = 8192
# llama-embedding default newline separator exploded dim (tens of
# thousands). Jail-proven token; must not appear in playbook text.
DEFAULT_EMBD_SEPARATOR = "<#sep#>"
# Documents are opt-in. A nomic-embed 768-d row is 3 KiB; 1261 handbook
# documents would add ~4 MiB to a 17 MiB rescue kit. Playbooks (16 rows,
# ~50 KiB) always fill when an embedder is configured.
DEFAULT_DOC_CAP = 8 * 1024 * 1024


def getenv(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def pack_f32(vec: list[float]) -> bytes:
    """Little-endian FLOAT32 blob (Hawkeye PackF32 / sqlite-vec)."""
    return struct.pack("<" + "f" * len(vec), *[float(x) for x in vec])


def unpack_f32(blob: bytes) -> list[float]:
    if not blob or len(blob) % 4 != 0:
        return []
    return list(struct.unpack("<" + "f" * (len(blob) // 4), blob))


def parse_embedding(text: str) -> list[float]:
    """Parse llama.cpp --embd-output-format array (JSON) or loose floats."""
    s = (text or "").strip()
    if not s:
        raise ValueError("empty embedding output")
    i = s.find("[")
    j = s.rfind("]")
    if i >= 0 and j > i:
        try:
            raw = json.loads(s[i : j + 1])
            if isinstance(raw, list) and raw and all(isinstance(x, (int, float)) for x in raw):
                return [float(x) for x in raw]
        except json.JSONDecodeError:
            pass
    out: list[float] = []
    tok: list[str] = []

    def flush() -> None:
        if not tok:
            return
        word = "".join(tok)
        tok.clear()
        try:
            out.append(float(word))
        except ValueError:
            return

    for ch in s:
        if ch.isdigit() or ch in ".-+eE":
            tok.append(ch)
        else:
            flush()
    flush()
    if not out:
        raise ValueError("no embedding floats parsed")
    return out


def fake_embed(text: str) -> list[float]:
    """Stable dim-8 unit vector from sha256(text). No model file."""
    digest = hashlib.sha256(text.encode("utf-8", errors="replace")).digest()
    vals = []
    for n in range(FAKE_DIM):
        u = int.from_bytes(digest[n * 4 : (n + 1) * 4], "little")
        vals.append((u / 4294967295.0) * 2.0 - 1.0)
    norm = math.sqrt(sum(x * x for x in vals)) or 1.0
    return [x / norm for x in vals]


def chunk_text(table: str, title: str, when: str, body: str) -> str:
    """Same concatenation Hawkeye FillEmbeddings uses."""
    if table == "playbooks":
        raw = f"{title}\n{when}\n{body}"
    else:
        raw = f"{title}\n{body}"
    raw = raw.strip()
    if len(raw) > TEXT_CAP:
        raw = raw[:TEXT_CAP]
    return raw


def resolve_backend() -> tuple[str, str, str]:
    """Return (kind, bin_or_empty, model). kind is fake|llama|skip."""
    if getenv("HAWKEYE_EMBED_FAKE") in ("1", "yes", "true", "TRUE", "Yes"):
        return "fake", "", FAKE_MODEL
    bin_path = getenv("HAWKEYE_EMBED_BIN") or getenv("HAWKEYE_LLM_BIN")
    model = getenv("HAWKEYE_EMBED_MODEL")
    if bin_path and model:
        return "llama", bin_path, model
    return "skip", "", ""


def model_label(model: str) -> str:
    """Store the GGUF basename, not a jail-specific path."""
    name = Path(model).name if model else ""
    return name or FAKE_MODEL


def _is_llama_embedding(bin_path: str) -> bool:
    """True when HAWKEYE_EMBED_BIN basename is llama-embedding."""
    return Path(bin_path).name.lower() == "llama-embedding"


def _flag_present(args: list[str], flag: str) -> bool:
    """True if flag is already in argv (bare or --flag=value)."""
    eq = flag + "="
    return any(a == flag or a.startswith(eq) for a in args)


def llama_argv(bin_path: str, model: str, text: str) -> list[str]:
    """Build llama.cpp argv. llama-embedding omits flags it rejects.

    llama-cli --embedding is invalid on llama-cpp-9426. llama-embedding
    also rejects --no-display-prompt. Defaults --pooling mean and
    --embd-separator (see DEFAULT_EMBD_SEPARATOR). HAWKEYE_EMBED_ARGS
    still appends and can override those defaults. A wrap script that
    strips flags is not required.
    """
    prefix: list[str] = []
    if bin_path.endswith(".py") and not os.access(bin_path, os.X_OK):
        prefix = [sys.executable]
    extra: list[str] = []
    raw = getenv("HAWKEYE_EMBED_ARGS")
    if raw:
        extra = shlex.split(raw)
    llama_embedding = _is_llama_embedding(bin_path)
    base = Path(bin_path).name.lower()
    # llama-embedding, and other *embedding* bins that are not *cli*.
    embedding_flag = [] if llama_embedding or (
        "embedding" in base and "cli" not in base
    ) else ["--embedding"]
    display_prompt_flag = [] if llama_embedding else ["--no-display-prompt"]
    pooling: list[str] = []
    separator: list[str] = []
    if llama_embedding:
        if not _flag_present(extra, "--pooling"):
            pooling = ["--pooling", "mean"]
        if not _flag_present(extra, "--embd-separator"):
            separator = ["--embd-separator", DEFAULT_EMBD_SEPARATOR]
    return [
        *prefix,
        bin_path,
        "-m",
        model,
        *embedding_flag,
        "-p",
        text,
        *display_prompt_flag,
        "-ngl",
        "0",
        "--embd-output-format",
        "array",
        *pooling,
        *separator,
        *extra,
    ]


def llama_embed(bin_path: str, model: str, text: str) -> list[float]:
    argv = llama_argv(bin_path, model, text)
    try:
        r = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except FileNotFoundError as e:
        raise SystemExit(f"embed.py: HAWKEYE_EMBED_BIN not found: {bin_path}") from e
    except subprocess.TimeoutExpired as e:
        raise SystemExit(f"embed.py: embedder timed out: {bin_path}") from e
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        raise SystemExit(f"embed.py: embedder exit {r.returncode}: {err[:400]}")
    try:
        return parse_embedding(r.stdout or "")
    except ValueError:
        # some builds print the array on stderr
        return parse_embedding((r.stdout or "") + "\n" + (r.stderr or ""))


def docs_wanted(n_docs: int, dim: int) -> bool:
    """Documents are opt-in. Playbooks always fill.

    HAWKEYE_EMBED_DOCS=1 forces document rows when estimated bytes stay
    under HAWKEYE_EMBED_MAX_DOC_BYTES (default 8 MiB).
    """
    flag = getenv("HAWKEYE_EMBED_DOCS")
    if flag not in ("1", "yes", "true", "YES"):
        return False
    cap = int(getenv("HAWKEYE_EMBED_MAX_DOC_BYTES") or DEFAULT_DOC_CAP)
    est = n_docs * max(dim, 1) * 4
    return est <= cap


def fill_connection(conn: sqlite3.Connection, vacuum: bool = False) -> dict:
    """Insert embeddings. No-op dict when no embedder is configured."""
    kind, bin_path, model = resolve_backend()
    if kind == "skip":
        return {"status": "skip", "count": 0, "model": "", "kind": kind}

    play = list(
        conn.execute(
            "SELECT id, title, COALESCE(when_to_use, ''), body FROM playbooks ORDER BY id"
        )
    )
    docs = list(
        conn.execute("SELECT id, title, body FROM documents ORDER BY id")
    )

    def embed_one(text: str) -> list[float]:
        if kind == "fake":
            return fake_embed(text)
        return llama_embed(bin_path, model, text)

    n = 0
    dim = 0
    stored_model = model_label(model) if kind != "fake" else FAKE_MODEL

    def write_row(table: str, tid: str, vec: list[float]) -> None:
        nonlocal n, dim
        if not vec:
            return
        dim = len(vec)
        conn.execute(
            """INSERT OR REPLACE INTO embeddings
               (target_table, target_id, model, dim, vector)
               VALUES (?, ?, ?, ?, ?)""",
            (table, tid, stored_model, dim, pack_f32(vec)),
        )
        n += 1

    for pid, title, when, body in play:
        text = chunk_text("playbooks", title or "", when or "", body or "")
        if not text:
            continue
        write_row("playbooks", pid, embed_one(text))

    if docs and docs_wanted(len(docs), dim or FAKE_DIM):
        for did, title, body in docs:
            text = chunk_text("documents", title or "", "", body or "")
            if not text:
                continue
            write_row("documents", did, embed_one(text))
    elif docs:
        print(
            f"embed: skip {len(docs)} documents (playbooks-only; HAWKEYE_EMBED_DOCS=1 to include)",
            file=sys.stderr,
        )

    if vacuum:
        conn.execute("PRAGMA journal_mode = DELETE")
        conn.commit()
        conn.execute("VACUUM")
    else:
        conn.commit()

    return {
        "status": "populated" if n else "empty",
        "count": n,
        "model": stored_model,
        "kind": kind,
        "dim": dim,
    }


def fill_path(db_path: Path, vacuum: bool = True) -> dict:
    conn = sqlite3.connect(str(db_path))
    try:
        return fill_connection(conn, vacuum=vacuum)
    finally:
        conn.close()


def cmd_self_test() -> int:
    vec = fake_embed("zfs-remount-rw")
    if len(vec) != FAKE_DIM:
        print(f"self-test: dim {len(vec)} != {FAKE_DIM}", file=sys.stderr)
        return 1
    blob = pack_f32(vec)
    if len(blob) != FAKE_DIM * 4:
        print("self-test: blob length", file=sys.stderr)
        return 1
    back = unpack_f32(blob)
    if len(back) != FAKE_DIM:
        print("self-test: unpack", file=sys.stderr)
        return 1
    parsed = parse_embedding(json.dumps(vec))
    if len(parsed) != FAKE_DIM:
        print("self-test: parse json", file=sys.stderr)
        return 1
    parsed2 = parse_embedding(" ".join(str(x) for x in vec))
    if len(parsed2) != FAKE_DIM:
        print("self-test: parse loose", file=sys.stderr)
        return 1
    a, b = fake_embed("alpha"), fake_embed("beta")
    if a == b:
        print("self-test: vectors not distinct", file=sys.stderr)
        return 1
    if model_label("/boot/hawkeye/models/nomic-embed-text-v1.5.Q8_0.gguf") != (
        "nomic-embed-text-v1.5.Q8_0.gguf"
    ):
        print("self-test: model_label", file=sys.stderr)
        return 1
    saved_args = os.environ.pop("HAWKEYE_EMBED_ARGS", None)
    try:
        argv = llama_argv("/usr/local/bin/llama-embedding", "m.gguf", "hi")
        if "--embedding" in argv:
            print("self-test: llama-embedding should omit --embedding", file=sys.stderr)
            return 1
        if "--no-display-prompt" in argv:
            print(
                "self-test: llama-embedding should omit --no-display-prompt",
                file=sys.stderr,
            )
            return 1
        try:
            i = argv.index("--pooling")
        except ValueError:
            print("self-test: llama-embedding should pass --pooling mean", file=sys.stderr)
            return 1
        if i + 1 >= len(argv) or argv[i + 1] != "mean":
            print("self-test: llama-embedding --pooling should be mean", file=sys.stderr)
            return 1
        if "--embd-separator" not in argv:
            print("self-test: llama-embedding should pass --embd-separator", file=sys.stderr)
            return 1
        sep_i = argv.index("--embd-separator")
        if sep_i + 1 >= len(argv) or argv[sep_i + 1] != DEFAULT_EMBD_SEPARATOR:
            print("self-test: embd-separator token", file=sys.stderr)
            return 1
        argv2 = llama_argv("/usr/local/bin/llama-cli", "m.gguf", "hi")
        if "--embedding" not in argv2:
            print("self-test: llama-cli should pass --embedding", file=sys.stderr)
            return 1
        os.environ["HAWKEYE_EMBED_ARGS"] = "--pooling cls --threads 1"
        argv3 = llama_argv("/usr/local/bin/llama-embedding", "m.gguf", "hi")
        if argv3.count("--pooling") != 1 or argv3[argv3.index("--pooling") + 1] != "cls":
            print("self-test: HAWKEYE_EMBED_ARGS should override --pooling", file=sys.stderr)
            return 1
        if "--threads" not in argv3 or argv3[argv3.index("--threads") + 1] != "1":
            print("self-test: HAWKEYE_EMBED_ARGS should append extras", file=sys.stderr)
            return 1
        if "--no-display-prompt" in argv3 or "--embedding" in argv3:
            print("self-test: extras must not restore rejected flags", file=sys.stderr)
            return 1
    finally:
        if saved_args is None:
            os.environ.pop("HAWKEYE_EMBED_ARGS", None)
        else:
            os.environ["HAWKEYE_EMBED_ARGS"] = saved_args
    print(f"self-test: ok dim={FAKE_DIM} model={FAKE_MODEL}")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Fill knowledge.sqlite embeddings (local only)")
    p.add_argument("db", nargs="?", help="path to knowledge.sqlite")
    p.add_argument("--no-vacuum", action="store_true", help="skip VACUUM (caller will)")
    p.add_argument("--self-test", action="store_true", help="pack/parse/fake checks, no sqlite")
    args = p.parse_args(argv[1:])
    if args.self_test:
        return cmd_self_test()
    if not args.db:
        print("usage: embed.py [--no-vacuum] knowledge.sqlite", file=sys.stderr)
        return 2
    db = Path(args.db)
    if not db.is_file():
        print(f"embed.py: not a file: {db}", file=sys.stderr)
        return 1
    info = fill_path(db, vacuum=not args.no_vacuum)
    if info["status"] == "skip":
        print("embed: skip (no HAWKEYE_EMBED_BIN+HAWKEYE_EMBED_MODEL or HAWKEYE_EMBED_FAKE)")
        return 0
    print(
        f"embed: {info['status']} count={info['count']} "
        f"dim={info.get('dim') or 0} model={info['model']} kind={info['kind']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
