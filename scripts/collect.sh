#!/bin/sh
# Sparse-fetch official FreeBSD sources into cache/. Record revision SHAs.
# POSIX sh + git. Does NOT vendor freebsd-src or freebsd-doc history.
# Copyright (c) 2026, REVYTECH, Inc.  BSD 3-Clause.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SOURCES="$ROOT/collect/sources.json"
CACHE="$ROOT/cache"
REVFILE="$CACHE/revisions.json"
SOURCES_MD="$ROOT/SOURCES.md"

need() {
	command -v "$1" >/dev/null 2>&1 || {
		echo "collect.sh: missing required command: $1" >&2
		exit 1
	}
}
need git
need python3
export GIT_TERMINAL_PROMPT=0
export GIT_CONFIG_NOSYSTEM=1

if [ ! -f "$SOURCES" ]; then
	echo "collect.sh: missing $SOURCES" >&2
	exit 1
fi

mkdir -p "$CACHE"

# Parse sources.json with python (jq also fine; python keeps one dependency story).
python3 - "$SOURCES" "$CACHE" "$REVFILE" "$SOURCES_MD" "$ROOT" << 'PY'
import json, os, subprocess, sys, datetime

sources_path, cache_root, revfile, sources_md, root = sys.argv[1:]
cfg = json.load(open(sources_path, encoding="utf-8"))

def run(cmd, cwd=None, check=True):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=cwd, check=check)

revisions = {}
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

for src in cfg["sources"]:
    sid = src["id"]
    url = src["git_url"]
    dest = os.path.join(root, src["cache_dir"])
    paths = src.get("sparse_paths") or []
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    if not os.path.isdir(os.path.join(dest, ".git")):
        run([
            "git", "clone",
            "--filter=blob:none",
            "--sparse",
            "--depth", "1",
            "--no-checkout",
            url,
            dest,
        ])
        # cone: repo-root files (UPDATING, RELNOTES) come along automatically
        run(["git", "sparse-checkout", "init", "--cone"], cwd=dest)
        if paths:
            run(["git", "sparse-checkout", "set", *paths], cwd=dest)
        run(["git", "checkout", "--force"], cwd=dest)
    else:
        # Incremental: update sparse paths then deepen fetch
        if paths:
            run(["git", "sparse-checkout", "init", "--cone"], cwd=dest)
            run(["git", "sparse-checkout", "set", *paths], cwd=dest)
        run(["git", "fetch", "--depth", "1", "--filter=blob:none", "origin"], cwd=dest)
        # Prefer origin/main, then origin/HEAD
        r = subprocess.run(
            ["git", "rev-parse", "--verify", "origin/main"],
            cwd=dest, capture_output=True, text=True,
        )
        ref = "origin/main" if r.returncode == 0 else "FETCH_HEAD"
        run(["git", "checkout", "--force", ref], cwd=dest)

    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=dest, text=True
    ).strip()
    branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=dest, text=True
    ).strip()
    revisions[sid] = {
        "id": sid,
        "git_url": url,
        "git_rev": sha,
        "branch": branch,
        "cache_dir": src["cache_dir"],
        "sparse_paths": paths,
        "license": src.get("license", ""),
        "collected_at": now,
    }
    print(f"collect: {sid} {sha}", flush=True)

os.makedirs(os.path.dirname(revfile), exist_ok=True)
with open(revfile, "w", encoding="utf-8") as f:
    json.dump({"collected_at": now, "sources": revisions}, f, indent=2)
    f.write("\n")

lines = []
lines.append("# Sources")
lines.append("")
lines.append("Hawkeye knowledge harvest. Official, license-clean FreeBSD documentation only.")
lines.append("")
lines.append(f"Collected at: `{now}` UTC")
lines.append("")
lines.append("Redistributions of AsciiDoc (and compiled forms derived from it) must retain")
lines.append("the FreeBSD Documentation License notice. See `notices/FREEBSD-DOC-LICENSE.txt`")
lines.append("(text from https://www.freebsd.org/copyright/freebsd-doc-license/).")
lines.append("")
lines.append("## In (collected)")
lines.append("")
for sid, rec in revisions.items():
    lines.append(f"### `{sid}`")
    lines.append("")
    lines.append(f"- git: `{rec['git_url']}`")
    lines.append(f"- revision: `{rec['git_rev']}`")
    lines.append(f"- license: {rec['license']}")
    lines.append("- sparse paths:")
    for p in rec["sparse_paths"]:
        lines.append(f"  - `{p}`")
    if sid == "freebsd-src":
        lines.append("- also: repo-root `UPDATING` and `RELNOTES` if present (cone sparse includes root files)")
        lines.append("- OpenZFS mdoc: `sys/contrib/openzfs/man`")
        lines.append("- rescue-relevant colocated mdoc under listed `sbin/` / `usr.sbin/` / `stand/man`")
        lines.append("- English mdoc under `share/man/man{4,5,7,8}` (not usr.bin toys, except crontab)")
    if sid == "freebsd-doc":
        lines.append("- include: `*.adoc` / `_index.adoc` (skip `*.po` translations)")
        lines.append("- books: handbook, faq, porters-handbook, developers-handbook, arch-handbook,")
        lines.append("  fdp-primer, accessibility, design-44bsd, dev-model")
        lines.append("- articles: `documentation/content/en/articles`")
    lines.append("")

lines.append("## Out (not collected)")
lines.append("")
lines.append("- Copyrighted books (Absolute FreeBSD, etc.)")
lines.append("- forums.freebsd.org, Reddit, Stack Overflow")
lines.append("- wiki.freebsd.org (mixed license)")
lines.append("- Whole ports tree / every pkg-descr")
lines.append("- Full `freebsd-src` history or non-sparse tree (too large)")
lines.append("- Translation `*.po` files")
lines.append("")
lines.append("## Hawkeye originals")
lines.append("")
lines.append("- `playbooks/` emergency procedures (BSD 3-Clause, REVYTECH)")
lines.append("- `docs/` cheat sheets (except TEST-EVIDENCE)")
lines.append("")

with open(sources_md, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"wrote {revfile}")
print(f"wrote {sources_md}")
PY
