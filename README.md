# hawkeye-data

Offline **knowledge kit** for [Hawkeye](https://github.com/revytechinc/hawkeye) — trench-warfare medicine for FreeBSD. Meatball surgery on servers and desktops, not people.

This repository is **data and knowledge only**. Binaries live in
[revytechinc/hawkeye](https://github.com/revytechinc/hawkeye). The website lives in
[revytechinc/hawkeye-www](https://github.com/revytechinc/hawkeye-www).

Copyright (c) 2026, REVYTECH, Inc. Licensed under the BSD 3-Clause License (see `LICENSE`).
FreeBSD Handbook, FAQ, articles, and related AsciiDoc are under the
[FreeBSD Documentation License](https://www.freebsd.org/copyright/freebsd-doc-license/)
(see `notices/FREEBSD-DOC-LICENSE.txt` and `SOURCES.md`). Redistributions of AsciiDoc
must retain that notice.

## Why this exists

Hawkeye should still help when:

- there is **no network**
- the root filesystem is **read-only**
- **`/usr` is missing** (so the pkg copy is gone)
- the **GPU / LLM / embedder is down**

Tier 0 is a compact `knowledge.sqlite` plus markdown playbooks. Retrieval is **FTS5** first. Embeddings are optional: the kit builder can ship precomputed little-endian FLOAT32 rows so sqlite-vec ranking works on a box with no GGUF, and Hawkeye can still `FillEmbeddings` at runtime if an embedder exists. An empty `embeddings` table is valid — consult falls back to FTS.

## What Hawkeye consumes

The Hawkeye binary opens **one sqlite file** read-only and runs FTS queries (and, later, optional vector search). It does not compile this repo. Chunks in `dist/` are how this repository stays under GitHub's 100MB file limit; Hawkeye never opens a chunk directly.

Search order (typical):

1. `HAWKEYE_KNOWLEDGE_PATH` if set (URI or filesystem path)
2. `/boot/hawkeye/knowledge.sqlite` — rescue/boot copy, survives a missing `/usr`
3. `/usr/local/share/hawkeye/knowledge.sqlite` — pkg copy (`PREFIX` may differ)

Open so the file stays usable on RO media:

```sh
sqlite3 'file:/boot/hawkeye/knowledge.sqlite?mode=ro&immutable=1'
```

or `sqlite3_open_v2(..., SQLITE_OPEN_READONLY)`. The shipped DB uses `journal_mode=DELETE` and is `VACUUM`ed so there is no `-wal` sidecar.

**Playbooks** (`playbooks` table, also view `skills`) are deterministic procedures: `id`, `title`, `when_to_use`, `preconditions`, `commands`, `danger_flags`, `rollback_notes`. Hawkeye should print them as-is. An LLM, if present, may rank or explain; it must not invent replacement commands for disk/key operations.

**Documents** are cheat sheets **plus** extracted official FreeBSD documentation (handbook chapters, articles, rescue-relevant mdoc, `UPDATING`). Categories include `freebsd-handbook`, `freebsd-articles`, `freebsd-man8`, etc.

Schema: `schema/knowledge.sql` (`user_version` 2: `documents.source`, `git_rev`, `collected_at`) and `docs/schema.md`.

## Collect pipeline

Official, license-clean sources only. Registry: `collect/sources.json`.

```
make collect    # sparse git fetch -> cache/ (gitignored)
make extract    # adoc/mdoc -> corpus/collected (gitignored)
make chunk      # gzip JSONL -> dist/chunks + dist/manifest.json (committed)
make db         # assemble share/knowledge.sqlite (committed if < 50MB)
make test
make harvest    # collect extract chunk db test
```

`scripts/collect.sh` uses `git clone --filter=blob:none --sparse --depth 1` (never a full freebsd-src clone). Sparse paths and collected revision SHAs are listed in `SOURCES.md`.

### Sources in

- https://github.com/freebsd/freebsd-doc — English AsciiDoc:
  `documentation/content/en/books/{handbook,faq,porters-handbook,developers-handbook,arch-handbook,fdp-primer,accessibility,design-44bsd,dev-model}`
  and `documentation/content/en/articles`. Skip `*.po`.
- https://github.com/freebsd/freebsd-src — sparse only:
  `UPDATING`, `RELNOTES` (if present), English mdoc under `share/man/man{4,5,7,8}`,
  OpenZFS man pages, rescue-relevant colocated pages (geli/geom, bectl, fsck, zfs, jail, loader, …).
  Not every `usr.bin` toy man page.
- Existing Hawkeye `playbooks/` and `docs/` cheat sheets.

### Sources out (do not scrape)

- Copyrighted books (Absolute FreeBSD, etc.)
- forums.freebsd.org, Reddit, Stack Overflow
- wiki.freebsd.org (mixed license)
- Whole ports tree / every pkg-descr

### Chunking (GitHub 100MB file limit)

Do **not** binary-split sqlite (useless for incremental updates). Chunk by source grouping (handbook, other books, articles, man8, man4, …; playbooks stay small).

Each chunk is gzipped JSONL of documents `{id,title,category,path,body,source,git_rev}` (playbooks include extra fields). `dist/manifest.json` lists `sha256` and byte sizes. `scripts/chunk.sh` only rewrites a chunk file when its content hash changed.
If `corpus/collected` is missing (gitignored on a fresh clone), only the
`playbooks` and `hawkeye-docs` chunks are rebuilt; harvested handbook/man
chunks are kept.

Limits: warn at 40MiB (`GITHUB_CHUNK_MAX=41943040`), never commit a single file ≥ 50MB, hard-fail at 90MB.

If assembled `share/knowledge.sqlite` grows past 50MB, still commit `dist/chunks`; skip committing the sqlite and reconstruct at install with `make db` / `scripts/assemble.sh`. Hawkeye still opens **one** sqlite file after assemble.

`cache/` and `corpus/collected/` are gitignored. `dist/chunks/` and `dist/manifest.json` are the git artifact.

## Two install prefixes

| Copy | Path | When |
|---|---|---|
| Rescue / boot | `/boot/hawkeye/` | `/usr` missing, early boot, broken pkg db |
| pkg | `/usr/local/share/hawkeye/` | normal installed system (`DESTDIR`/`PREFIX` apply) |

Keep the tree small enough that a `/boot` copy is realistic: compact sqlite + playbook markdown. Extra docs ship with the pkg copy.

```sh
make          # rebuild share/knowledge.sqlite (sqlite3 + python3)
make test     # FTS "zfs readonly" must hit a playbook; fake embedder must fill embeddings
make install          # DESTDIR/PREFIX/share/hawkeye
make install-boot     # DESTDIR/boot/hawkeye
```

`share/knowledge.sqlite` is **committed** (when under 50MB) so rescue media can copy a file without a builder host. Rebuild from `playbooks/*.md`, `docs/*.md`, and `corpus/collected` with `scripts/build-knowledge.sh`, or from `dist/chunks` with `scripts/assemble.sh`.

### Precomputed embeddings (optional)

The default harvest **does not require** a model. If `HAWKEYE_EMBED_BIN` and `HAWKEYE_EMBED_MODEL` point at a local llama.cpp-style embedder (nomic-embed GGUF on the jail/builder, not in git), `scripts/embed.py` fills **playbook** rows only. That is enough for rescue ranking and keeps the ~17 MiB kit compact (16 × 768-d FLOAT32 ≈ 50 KiB). Documents stay FTS-only unless you set `HAWKEYE_EMBED_DOCS=1`. Tests use `HAWKEYE_EMBED_FAKE=1` (stable dim-8, no GGUF, no network) and require every playbook id to have a row.

```
HAWKEYE_EMBED_BIN=/usr/local/bin/llama-embedding \
HAWKEYE_EMBED_MODEL=/usr/local/share/hawkeye/models/nomic-embed-text-v1.5.Q8_0.gguf \
make db
# or, after assemble: make embed
# optional override: HAWKEYE_EMBED_ARGS='--threads 4'
```

On llama-cpp-9426, `llama-cli --embedding` is invalid and `llama-embedding` rejects `--no-display-prompt`. `embed.py` detects the `llama-embedding` basename, omits those flags, and defaults `--pooling mean --embd-separator '<#sep#>'` so a wrap script is not required. `HAWKEYE_EMBED_ARGS` still appends/overrides. A newline separator explodes the vector dim.

Do **not** commit GGUF files, API keys, or cloud embeddings. Local only. `make test` still passes when no embedder is on the builder.

A FreeBSD port skeleton lives in `ports/sysutils/hawkeye-data` (sibling of `sysutils/hawkeye`). See that directory's `pkg-message`.

## No secrets in the corpus

Do not add SSH keys, passwords, tokens, `htpasswd` lines, geli/ZFS key bytes, or anything that looks like a real secret.

Playbooks `zfs-load-key` and `geli-attach` require the operator to type secrets **at the console**. Keys never go through an LLM. See `docs/secrets-policy.md`.

## Layout

```
collect/sources.json          # registry: git urls, sparse paths, license
collect/man-pages.txt         # rescue-relevant man basenames
cache/                        # gitignored sparse clones
corpus/collected/             # gitignored extracted plaintext
dist/manifest.json            # chunk list: id, path, sha256, bytes, git_rev
dist/chunks/chunk-*.jsonl.gz  # ~40MiB max, content-addressed
notices/FREEBSD-DOC-LICENSE.txt
SOURCES.md                    # git URLs, sparse paths, collected SHAs
schema/knowledge.sql          # tables + FTS5 + optional embeddings
scripts/collect.sh extract.sh chunk.sh assemble.sh build-knowledge.sh
scripts/embed.py              # optional local/fake FLOAT32 fill
scripts/test-embeddings.sh    # fake embedder: COUNT(*) > 0, playbook ids match
playbooks/*.md                # emergency procedures (YAML front matter)
docs/*.md                     # cheat sheets + schema + TEST-EVIDENCE
share/knowledge.sqlite        # assembled kit Hawkeye opens (committed if < 50MB)
ports/sysutils/hawkeye-data/  # port skeleton
```

## Emergency playbooks (first kit)

`zfs-remount-rw`, `ufs-mount-rw`, `zpool-import`, `zfs-load-key`, `geli-attach`, `bectl-rollback`, `fsck`, `network-ifconfig`, `kldload-boot-kernel`, `single-user`, `rescue-path`, plus operator-complaint kits: `fstab-mounts`, `rc-enable-missing`, `root-full`, `network-no-route`, `sshd-not-running`.
