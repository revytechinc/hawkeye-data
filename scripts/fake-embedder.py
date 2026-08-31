#!/usr/bin/env python3
"""llama.cpp-style stub embedder for tests. No GGUF, no network.

Copyright (c) 2026, REVYTECH, Inc.  BSD 3-Clause.

Accepts the argv Hawkeye / embed.py use:

  fake-embedder.py -m MODEL --embedding -p TEXT --no-display-prompt \\
      -ngl 0 --embd-output-format array

Prints a JSON array of 8 floats derived from sha256(TEXT).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Same algorithm as embed.fake_embed (import without pulling sqlite).
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from embed import fake_embed  # noqa: E402


def _prompt(argv: list[str]) -> str:
    out = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-p", "--prompt") and i + 1 < len(argv):
            out.append(argv[i + 1])
            i += 2
            continue
        i += 1
    if not out:
        print("fake-embedder: missing -p TEXT", file=sys.stderr)
        sys.exit(2)
    return " ".join(out)


def main(argv: list[str]) -> int:
    text = _prompt(argv[1:])
    vec = fake_embed(text)
    sys.stdout.write(json.dumps(vec) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
