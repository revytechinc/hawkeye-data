#!/bin/sh
# Pack corpus + playbooks + hawkeye docs into content-addressed gzip JSONL chunks.
# Skip rewrite when sha256 is unchanged. Max ~40MiB (GITHUB_CHUNK_MAX).
# Copyright (c) 2026, REVYTECH, Inc.  BSD 3-Clause.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
command -v python3 >/dev/null 2>&1 || { echo "chunk.sh: need python3" >&2; exit 1; }
exec python3 "$ROOT/scripts/corpus.py" chunk
