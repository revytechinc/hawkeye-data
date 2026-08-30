---
id: boot-and-loader
title: FreeBSD loader and boot cheat sheet
category: cheatsheet
---

# Loader and boot cheat sheet

- Boot menu: select kernel, single-user (`boot -s`), or a ZFS BE when the menu offers one.
- Loader prompt (`OK`): `lsdev`, `lsmod`, `show`, `set vfs.root.mountfrom=...`, `boot -s`.
- Root from ZFS: `vfs.root.mountfrom=zfs:POOL/ROOT/BE` — names from **this** pool (`zpool get bootfs`, `zfs list`), never invented.
- `currdev` / `load` paths point at `/boot` on the boot pool. If `/boot` is on a different dataset than `/usr`, a missing `/usr` can still leave `/boot/hawkeye` reachable.
- `geom_eli` passphrase is prompted by the loader or early kernel — same secret rule: not through an LLM.
- After a bad upgrade, prefer `bectl activate` plus reboot over hand-editing `vfs.root.mountfrom` unless `bectl` is unavailable.
