# TEST-EVIDENCE

Captured: `2026-08-30T20:18:46Z` UTC
Database: `share/knowledge.sqlite` (147456 bytes)
Open: `file:...?...mode=ro&immutable=1` integrity_check=ok journal_mode=delete

## FTS query: `zfs readonly`

Matches: 4

```
id              title                                          
--------------  -----------------------------------------------
single-user     Single-user versus multi-user                  
zfs-load-key    Load ZFS encryption keys at the console        
zfs-remount-rw  Remount ZFS root read-write                    
zpool-import    Import a ZFS pool (readonly first, then unlock)
```

## meta

```
built_at=2026-08-30T20:18:46Z
corpus_id=hawkeye-data
document_count=5
embeddings=optional-empty
fts=mandatory
playbook_count=11
schema_version=1
```

## embeddings

rows=0 (optional table; empty in the default kit)

## result

PASS: FTS hit at least one playbook (zfs-remount-rw) for "zfs readonly"; DB opens immutable/RO.
