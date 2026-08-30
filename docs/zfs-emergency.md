---
id: zfs-emergency
title: ZFS emergency cheat sheet
category: cheatsheet
---

# ZFS emergency cheat sheet

- `zpool import` — discover exported pools
- Safe inspect: `zpool import -o readonly=on -N POOL`
- Status: `zpool status -v POOL` (not `fsck`)
- Dataset RO vs pool RO: `zfs get readonly` vs `zpool get readonly`
- Remount dataset: `zfs mount -u DATASET` or `mount -u -o rw /`
- Keys: `zfs get -r keystatus,keylocation` then `zfs load-key` at the console
- BEs: `bectl list` / `bectl activate`
- Missing module: `kldload /boot/kernel/zfs.ko` (and `opensolaris.ko` on older trees)
- `zpool clear` clears error **counters** after you fix the cause; it is not a repair tool
- Do not `zpool import -F` / rewind unless you understand lost transactions; out of scope for the default playbooks
