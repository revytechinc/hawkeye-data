#!/bin/sh
# Reconstruct share/knowledge.sqlite from dist/chunks + playbooks/ + docs/.
# Used on a fresh clone (corpus/collected is gitignored) and at install time
# if the assembled sqlite was too large to commit.
# Finalize also runs scripts/embed.py when a local embedder is configured.
# Copyright (c) 2026, REVYTECH, Inc.  BSD 3-Clause.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OUT=${1:-"$ROOT/share/knowledge.sqlite"}
command -v python3 >/dev/null 2>&1 || { echo "assemble.sh: need python3" >&2; exit 1; }
command -v sqlite3 >/dev/null 2>&1 || { echo "assemble.sh: need sqlite3" >&2; exit 1; }
mkdir -p "$(dirname -- "$OUT")"
exec python3 "$ROOT/scripts/corpus.py" assemble "$OUT"
