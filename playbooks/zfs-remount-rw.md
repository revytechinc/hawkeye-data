---
id: zfs-remount-rw
title: Remount ZFS root read-write
when_to_use: Root is a ZFS dataset and is mounted read-only (single-user, panic remount, zfs readonly=on, or a readonly pool import). You need to edit files, write logs, or run tools that create files.
requires_rw: no
requires_net: no
requires_zfs: yes
requires_ufs: no
preconditions: {"rw":false,"net":false,"zfs":true,"ufs":false,"rescue_ok":true,"single_user_ok":true}
danger_flags: ["Writing while disks are failing can destroy the last good copy of data.","If the pool was imported with readonly=on, dataset-level zfs set readonly=off is not enough; export and re-import without readonly (see zpool-import).","Do not force writes for forensic capture; stay readonly in that case."]
rollback_notes: zfs set readonly=on $ROOTDS; mount -u -o ro /   — or export the pool and re-import with -o readonly=on.
---

# Remount ZFS root read-write

Use this when `/` is ZFS and `mount` shows `read-only`, or `zfs get readonly` is `on` for the dataset mounted on `/`.

This playbook does **not** load encryption keys. If `zfs get keystatus` is `unavailable`, stop and use `zfs-load-key` (keys never go through an LLM).

## Commands

```sh
export PATH=/rescue:/sbin:/bin:/usr/sbin:/usr/bin
mount -p
df -T /
zfs list -o name,mounted,mountpoint,readonly,canmount
ROOTDS=$(mount -p | awk '$2=="/" {print $1}')
echo "root dataset: $ROOTDS"
zfs get -o property,value name,readonly,mounted,encryption,keystatus "$ROOTDS"
zpool get readonly "$(echo "$ROOTDS" | awk -F/ '{print $1}')"
zfs set readonly=off "$ROOTDS"
zfs mount -u "$ROOTDS"
mount -u -o rw /
mount -p | awk '$2=="/" {print}'
```

## Notes

- `zfs set readonly=off` changes the dataset property. `zfs mount -u` remounts it. `mount -u -o rw /` is the generic remount.
- If `zpool get readonly` is `on`, the pool was imported read-only. Dataset `readonly=off` will not make it writable. See playbook `zpool-import`: export, then import **without** `-o readonly=on`.
- Prefer `/rescue` on the PATH when `/usr` is missing so you are not calling dynamically linked `/sbin` against a missing `/lib`.
