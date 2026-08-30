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
| `embeddings` | Optional FLOAT32 (or sqlite-vec) blobs; **empty** in the default kit |

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

`embeddings(target_table, target_id, model, dim, vector)` is created so Hawkeye can fill it later. Tier 0 must work when this table has zero rows and when no embedder/GPU is present. Do not require the sqlite-vec extension on rescue media.
