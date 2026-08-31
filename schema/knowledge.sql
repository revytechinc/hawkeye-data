-- Hawkeye knowledge.sqlite schema (Tier 0).
-- Copyright (c) 2026, REVYTECH, Inc.  BSD 3-Clause.
--
-- This database is data/knowledge only. Open it read-only in production:
--   sqlite3 'file:/boot/hawkeye/knowledge.sqlite?mode=ro&immutable=1'
--   sqlite3 'file:/usr/local/share/hawkeye/knowledge.sqlite?mode=ro&immutable=1'
--
-- FTS5 is mandatory so Hawkeye still works with no embedder, no GPU, and
-- no network. The embeddings table is optional and may be empty (Tier 0
-- then uses FTS5 only). The builder MAY populate it when a local embedder
-- is configured; the default harvest with no model must still succeed.
--
-- Builder always uses journal_mode=DELETE and VACUUM so the file can be
-- copied onto rescue media and opened immutable (no -wal sidecar required).

PRAGMA journal_mode = DELETE;
PRAGMA synchronous = FULL;
PRAGMA foreign_keys = ON;
PRAGMA user_version = 2;
PRAGMA application_id = 0x484B5945; -- 'HKYE'

CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE documents (
    rowid         INTEGER PRIMARY KEY,
    id            TEXT    NOT NULL UNIQUE,
    title         TEXT    NOT NULL,
    category      TEXT,
    path          TEXT,
    body          TEXT    NOT NULL,
    source        TEXT,
    git_rev       TEXT,
    collected_at  TEXT
);

-- Playbooks (also known as skills): deterministic recovery procedures.
CREATE TABLE playbooks (
    rowid           INTEGER PRIMARY KEY,
    id              TEXT    NOT NULL UNIQUE,
    title           TEXT    NOT NULL,
    when_to_use     TEXT    NOT NULL,
    preconditions   TEXT    NOT NULL DEFAULT '{}', -- JSON object
    commands        TEXT    NOT NULL DEFAULT '[]', -- JSON array of strings
    danger_flags    TEXT    NOT NULL DEFAULT '[]', -- JSON array of strings
    rollback_notes  TEXT    NOT NULL DEFAULT '',
    body            TEXT    NOT NULL,
    requires_rw     INTEGER NOT NULL DEFAULT 0 CHECK (requires_rw IN (0, 1)),
    requires_net    INTEGER NOT NULL DEFAULT 0 CHECK (requires_net IN (0, 1)),
    requires_zfs    INTEGER NOT NULL DEFAULT 0 CHECK (requires_zfs IN (0, 1)),
    requires_ufs    INTEGER NOT NULL DEFAULT 0 CHECK (requires_ufs IN (0, 1)),
    path            TEXT
);

-- Skills is an alias: Hawkeye may query either name.
CREATE VIEW skills AS SELECT * FROM playbooks;

-- FTS5 (mandatory). unicode61 keeps tokens such as zfs, geli, bectl intact.
-- External-content tables: rebuild FTS from the base tables after load.
CREATE VIRTUAL TABLE documents_fts USING fts5(
    title,
    category,
    body,
    content  = 'documents',
    content_rowid = 'rowid',
    tokenize = 'unicode61'
);

CREATE VIRTUAL TABLE playbooks_fts USING fts5(
    title,
    when_to_use,
    body,
    commands,
    danger_flags,
    content  = 'playbooks',
    content_rowid = 'rowid',
    tokenize = 'unicode61'
);

-- Optional vector table. scripts/embed.py fills it when a local embedder
-- is configured (HAWKEYE_EMBED_BIN + HAWKEYE_EMBED_MODEL, or
-- HAWKEYE_EMBED_FAKE=1 for tests). The default harvest with no model
-- leaves this empty. Hawkeye binaries (https://github.com/revytechinc/hawkeye)
-- MAY also FillEmbeddings at runtime. Tier 0 MUST ignore an empty table
-- and use FTS5 instead. Do not require sqlite-vec at build or on rescue.
--
-- vector is a little-endian blob of dim FLOAT32 values (Hawkeye PackF32),
-- or a format understood by a sqlite-vec virtual table if that extension
-- is loaded.
CREATE TABLE embeddings (
    id           INTEGER PRIMARY KEY,
    target_table TEXT    NOT NULL CHECK (target_table IN ('documents', 'playbooks')),
    target_id    TEXT    NOT NULL,
    model        TEXT    NOT NULL,
    dim          INTEGER NOT NULL CHECK (dim > 0),
    vector       BLOB,
    UNIQUE (target_table, target_id, model)
);

CREATE INDEX embeddings_target ON embeddings (target_table, target_id);
