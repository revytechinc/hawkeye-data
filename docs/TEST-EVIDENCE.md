# TEST-EVIDENCE

Captured: `2026-08-30T21:43:19Z` UTC
Database: `share/knowledge.sqlite` (17985536 bytes)
Open: `file:...?...mode=ro&immutable=1` integrity_check=ok journal_mode=delete user_version=2

## FTS query: `zfs readonly` (playbooks)

Matches: 4

```
      id                             title
--------------  -----------------------------------------------
single-user     Single-user versus multi-user
zfs-load-key    Load ZFS encryption keys at the console
zfs-remount-rw  Remount ZFS root read-write
zpool-import    Import a ZFS pool (readonly first, then unlock)
```

## FTS query: `ZFS` (documents, after harvest)

Matches: 154

```
                      id                              category                                            title
----------------------------------------------  ---------------------  ----------------------------------------------------------------------------
boot-and-loader                                 cheatsheet             FreeBSD loader and boot cheat sheet
freebsd-recovery                                cheatsheet             FreeBSD recovery cheat sheet
zfs-emergency                                   cheatsheet             ZFS emergency cheat sheet
freebsd-doc:books/arch-handbook/boot/_index     freebsd-arch-handbook  Chapter 1. Bootstrapping and Kernel Initialization
freebsd-doc:articles/committers-guide/_index    freebsd-articles       Committer's Guide
freebsd-doc:articles/license-guide/_index       freebsd-articles       FreeBSD Licensing Policy
freebsd-doc:articles/linux-emulation/_index     freebsd-articles       Linux® emulation in FreeBSD
freebsd-doc:articles/remote-install/_index      freebsd-articles       Remote Installation of the FreeBSD Operating System Without a Remote Console
freebsd-doc:articles/vinum/_index               freebsd-articles       The vinum Volume Manager
freebsd-doc:books/faq/_index                    freebsd-faq            Frequently Asked Questions for FreeBSD
freebsd-doc:books/handbook/basics/_index        freebsd-handbook       Chapter 3. FreeBSD Basics
freebsd-doc:books/handbook/bibliography/_index  freebsd-handbook       Appendix B. Bibliography
```

## FTS query: `jails` (documents, after harvest)

Matches: 42

```
                       id                                category                        title
-------------------------------------------------  ---------------------  ------------------------------------
freebsd-doc:books/arch-handbook/jail/_index        freebsd-arch-handbook  Chapter 4. The Jail Subsystem
freebsd-doc:books/arch-handbook/smp/_index         freebsd-arch-handbook  Chapter 8. SMPng Design Document
freebsd-doc:articles/building-products/_index      freebsd-articles       Building Products with FreeBSD
freebsd-doc:articles/committers-guide/_index       freebsd-articles       Committer's Guide
freebsd-doc:articles/freebsd-update-server/_index  freebsd-articles       Build Your Own FreeBSD Update Server
freebsd-doc:articles/rc-scripting/_index           freebsd-articles       Practical rc.d scripting in BSD
freebsd-doc:books/handbook/bibliography/_index     freebsd-handbook       Appendix B. Bibliography
freebsd-doc:books/handbook/bsdinstall/_index       freebsd-handbook       Chapter 2. Installing FreeBSD
```

## meta

```
built_at=2026-08-30T21:43:16Z
collected_at=2026-08-30T21:42:10Z
corpus_id=hawkeye-data
document_count=1261
embeddings=optional-empty
fts=mandatory
git_rev={"freebsd-doc": "72442dc9c2971d5a056eb7f6e1056672a546e85e", "freebsd-src": "a311bd18a6fb57c6d3a19ab5bb53bb6f1c5fd056"}
playbook_count=11
schema_version=2
source=freebsd-doc,freebsd-src,hawkeye
```

## embeddings

rows=0 (optional table; empty in the default kit)

## chunks

manifest ok: 10 chunks, sha256+bytes verified; second run sha256s unchanged

## result

PASS: FTS hit playbook zfs-remount-rw for "zfs readonly"; FTS also hit harvested FreeBSD docs for "ZFS"; DB opens immutable/RO.
