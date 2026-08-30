---
id: fsck
title: Run fsck on UFS (never on ZFS)
when_to_use: UFS/FFS is dirty, will not remount RW, or the box dropped to single-user after an unclean shutdown. Not for ZFS pools.
requires_rw: no
requires_net: no
requires_zfs: no
requires_ufs: yes
preconditions: {"rw":false,"net":false,"zfs":false,"ufs":true,"rescue_ok":true,"single_user_ok":true}
danger_flags: ["NEVER fsck a ZFS pool or dataset; use zpool status / zpool import.","NEVER fsck a UFS filesystem that is mounted read-write.","fsck -y updates the filesystem; have a reason, not a habit.","Running the wrong device node can damage an unrelated disk."]
rollback_notes: There is no undo of a repairing fsck. Restore from backup or a ZFS BE (if this was not UFS). Pre-repair: fsck -n (no write) to inspect.
---

# fsck (UFS/FFS only)

Identify the filesystem type first. If `/` is ZFS, stop.

## Commands

```sh
export PATH=/rescue:/sbin:/bin:/usr/sbin:/usr/bin
df -T /
mount -p
sysctl vfs.mounts 2>/dev/null
gpart show
glabel status
# Confirm UFS and that it is NOT mounted RW:
SPEC=$(mount -p | awk '$2=="/" {print $1}')
mount -p | awk '$2=="/" {print}'
# Inspect only (no writes):
fsck -t ufs -n "$SPEC"
# Repair only after you intend to write (still not RW-mounted):
fsck -t ufs -y "$SPEC"
# Then remount (playbook ufs-mount-rw):
mount -u -o rw /
```

## Unmounted additional filesystem

```sh
fsck -t ufs -n /dev/gpt/LABEL
fsck -t ufs /dev/gpt/LABEL
```

## Notes

- FreeBSD: `fsck -t ufs` dispatches to `fsck_ufs` / `fsck_ffs`.
- Journaled soft updates: `fsck` may replay; read the output before `-y` on a failing disk.
- For ZFS: `zpool status`, `zpool clear` (clearing error counters, not a repair hammer), and restore from snapshots/BEs. There is no `fsck.zfs` in this kit.
