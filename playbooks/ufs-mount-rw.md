---
id: ufs-mount-rw
title: Remount UFS root read-write
when_to_use: Root is UFS/FFS and is mounted read-only (typical in single-user). You need a writable slash to edit /etc, replace files, or complete fsck-then-mount.
requires_rw: no
requires_net: no
requires_zfs: no
requires_ufs: yes
preconditions: {"rw":false,"net":false,"zfs":false,"ufs":true,"rescue_ok":true,"single_user_ok":true}
danger_flags: ["Never fsck a UFS filesystem that is mounted read-write.","If fsck reports serious damage, copying off the box may be safer than a write remount.","Soft updates / journaled soft updates: follow fsck(8); do not guess flags."]
rollback_notes: mount -u -o ro /   — returns the root filesystem to read-only.
---

# Remount UFS root read-write

FreeBSD single-user often mounts `/` read-only. The usual unlock is `mount -u -o rw /`.

If remount fails, the filesystem may be dirty. Unmount is not possible for `/`; run `fsck` on the block device while it is still RO, then remount (see playbook `fsck`).

## Commands

```sh
export PATH=/rescue:/sbin:/bin:/usr/sbin:/usr/bin
mount -p
df -T /
ROOTSPEC=$(mount -p | awk '$2=="/" {print $1}')
echo "root spec: $ROOTSPEC"
mount -u -o rw /
mount -p | awk '$2=="/" {print}'
```

## If remount refuses

```sh
# Still RO. Inspect; fsck only while not RW-mounted.
fsck -t ufs -n "$ROOTSPEC"
# See playbook fsck before running a repair (fsck -y).
```

## Notes

- This is **not** a ZFS procedure. If `df -T /` shows `zfs`, use `zfs-remount-rw` instead.
- `mount -u` updates the existing mount (do not `umount /`).
