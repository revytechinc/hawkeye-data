---
id: schema
title: knowledge.sqlite schema (FTS mandatory, vectors optional)
category: schema
---

# knowledge.sqlite schema

Source of truth: `schema/knowledge.sql`.

## Tables

| Object | Role |
|---|---|
| `meta` | `schema_version` (2), `built_at`, counts, `source`, `git_rev`, `collected_at` |
| `documents` | Cheat sheets + harvested FreeBSD doc (`category`, `source`, `git_rev`, `collected_at`) |
| `playbooks` | Deterministic procedures (skills) |
| `skills` | VIEW alias of `playbooks` |
| `documents_fts` | FTS5 external-content over `documents` |
| `playbooks_fts` | FTS5 external-content over `playbooks` |
| `embeddings` | Optional little-endian FLOAT32 blobs; **may be populated** by the builder when a local embedder is configured; **empty** is valid (Tier 0 uses FTS5) |

## Playbook columns

`id`, `title`, `when_to_use`, `preconditions` (JSON), `commands` (JSON array), `danger_flags` (JSON array), `rollback_notes`, `body`, `requires_rw`, `requires_net`, `requires_zfs`, `requires_ufs`, `path`.

## Documents columns

`id`, `title`, `category` (e.g. `docs`, `freebsd-handbook`, `freebsd-man8`), `path`, `body`, `source` (git id or `hawkeye`), `git_rev`, `collected_at`.

`user_version` 2 added `source`, `git_rev`, `collected_at`. FTS5 still indexes `title`, `category`, `body` only.

## Open read-only / immutable

The builder uses `PRAGMA journal_mode=DELETE` and `VACUUM`. Copy the single file onto rescue media.

```
sqlite3 'file:/boot/hawkeye/knowledge.sqlite?mode=ro&immutable=1'
sqlite3 'file:/usr/local/share/hawkeye/knowledge.sqlite?mode=ro&immutable=1'
```

C API: `sqlite3_open_v2(path, &db, SQLITE_OPEN_READONLY, NULL)` or the URI above.

`immutable=1` means the process will not create a `-wal` sidecar and will not write. The file must not be mid-write; the shipped DB is frozen after `VACUUM`.

## FTS (Tier 0)

```
SELECT p.id, p.title
  FROM playbooks AS p
 WHERE p.rowid IN (
   SELECT rowid FROM playbooks_fts
    WHERE playbooks_fts MATCH 'zfs readonly'
 );
```

Tokenizer is `unicode61` (no Porter) so tokens like `zfs`, `geli`, and `bectl` stay intact.

## Vectors (optional)

`embeddings(target_table, target_id, model, dim, vector)` holds little-endian FLOAT32 blobs (Hawkeye `PackF32`). sqlite-vec is not required at build or on rescue media.

The builder (`scripts/embed.py`, hooked from assemble / finalize) **can** populate playbook rows (and documents when the estimated blob size stays reasonable) when a **local** llama.cpp-style embedder is configured:

```
HAWKEYE_EMBED_BIN=/usr/local/bin/llama-cli
HAWKEYE_EMBED_MODEL=/path/to/local-embed.gguf
make db
```

`HAWKEYE_LLM_BIN` is accepted as a fallback for the binary path (same name the Hawkeye binary reads). Tests use `HAWKEYE_EMBED_FAKE=1` (deterministic dim-8, no GGUF, no network).

If those env vars are unset, the harvest stays FTS-only and **must not fail**. An empty table is valid. Hawkeye may also `FillEmbeddings` at runtime on a writable copy. Do not commit GGUF files, API keys, or embeddings from a hosted API.

```
SELECT COUNT(*) FROM embeddings;           -- 0 is fine
SELECT target_id, model, dim, length(vector) FROM embeddings
 WHERE target_table = 'playbooks';
```

Tier 0 consult must work when this table has zero rows and when no embedder/GPU is present.
