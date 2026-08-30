# hawkeye-data

Offline **knowledge kit** for [Hawkeye](https://github.com/revytechinc/hawkeye) — a doctor for FreeBSD.

This repository is **data and knowledge only**. Binaries live in
[revytechinc/hawkeye](https://github.com/revytechinc/hawkeye). The website lives in
[revytechinc/hawkeye-www](https://github.com/revytechinc/hawkeye-www).

Copyright (c) 2026, REVYTECH, Inc. Licensed under the BSD 3-Clause License (see `LICENSE`).

## Why this exists

Hawkeye should still help when:

- there is **no network**
- the root filesystem is **read-only**
- **`/usr` is missing** (so the pkg copy is gone)
- the **GPU / LLM / embedder is down**

Tier 0 is a compact `knowledge.sqlite` plus markdown playbooks. Retrieval is **FTS5**, not vectors. Embeddings are optional and generated later by the binary if an embedder exists.

## What Hawkeye consumes

The Hawkeye binary opens **one sqlite file** read-only and runs FTS queries (and, later, optional vector search). It does not compile this repo.

Search order (typical):

1. `HAWKEYE_KNOWLEDGE` if set (URI or filesystem path)
2. `/boot/hawkeye/knowledge.sqlite` — rescue/boot copy, survives a missing `/usr`
3. `/usr/local/share/hawkeye/knowledge.sqlite` — pkg copy (`PREFIX` may differ)

Open so the file stays usable on RO media:

```sh
sqlite3 'file:/boot/hawkeye/knowledge.sqlite?mode=ro&immutable=1'
```

or `sqlite3_open_v2(..., SQLITE_OPEN_READONLY)`. The shipped DB uses `journal_mode=DELETE` and is `VACUUM`ed so there is no `-wal` sidecar.

**Playbooks** (`playbooks` table, also view `skills`) are deterministic procedures: `id`, `title`, `when_to_use`, `preconditions`, `commands`, `danger_flags`, `rollback_notes`. Hawkeye should print them as-is. An LLM, if present, may rank or explain; it must not invent replacement commands for disk/key operations.

**Documents** are short cheat sheets so FTS still hits phrases like "single-user", "geli", or "boot environment".

Schema: `schema/knowledge.sql` and `docs/schema.md`.

## Two install prefixes

| Copy | Path | When |
|---|---|---|
| Rescue / boot | `/boot/hawkeye/` | `/usr` missing, early boot, broken pkg db |
| pkg | `/usr/local/share/hawkeye/` | normal installed system (`DESTDIR`/`PREFIX` apply) |

Keep the tree small enough that a `/boot` copy is realistic: compact sqlite + playbook markdown. Extra docs ship with the pkg copy.

```sh
make          # rebuild share/knowledge.sqlite (sqlite3 required)
make test     # FTS "zfs readonly" must hit a playbook
make install          # DESTDIR/PREFIX/share/hawkeye
make install-boot     # DESTDIR/boot/hawkeye
```

`share/knowledge.sqlite` is **committed** so rescue media can copy a file without a builder host. Rebuild from `playbooks/*.md` and `docs/*.md` with `scripts/build-knowledge.sh` (POSIX sh + `sqlite3`; no Python, no Go).

A FreeBSD port skeleton lives in `ports/sysutils/hawkeye-data` (sibling of `sysutils/hawkeye`). See that directory's `pkg-message`.

## No secrets in the corpus

Do not add SSH keys, passwords, tokens, `htpasswd` lines, geli/ZFS key bytes, or anything that looks like a real secret.

Playbooks `zfs-load-key` and `geli-attach` require the operator to type secrets **at the console**. Keys never go through an LLM. See `docs/secrets-policy.md`.

## Layout

```
schema/knowledge.sql          # tables + FTS5 + optional embeddings
scripts/build-knowledge.sh    # markdown -> sqlite
scripts/test-knowledge.sh     # FTS smoke test
playbooks/*.md                # emergency procedures (YAML front matter)
docs/*.md                     # cheat sheets + schema + TEST-EVIDENCE
share/knowledge.sqlite        # built kit (committed)
ports/sysutils/hawkeye-data/  # port skeleton
```

## Emergency playbooks (first kit)

`zfs-remount-rw`, `ufs-mount-rw`, `zpool-import`, `zfs-load-key`, `geli-attach`, `bectl-rollback`, `fsck`, `network-ifconfig`, `kldload-boot-kernel`, `single-user`, `rescue-path`.
