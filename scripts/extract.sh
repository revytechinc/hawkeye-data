#!/bin/sh
# adoc/mdoc in cache/ -> corpus/collected documents (YAML + body).
# Copyright (c) 2026, REVYTECH, Inc.  BSD 3-Clause.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
command -v python3 >/dev/null 2>&1 || { echo "extract.sh: need python3" >&2; exit 1; }
exec python3 "$ROOT/scripts/corpus.py" extract
