---
id: root-full
title: Root filesystem full or inodes exhausted
when_to_use: pkg, newsyslog, editors, or freebsd-update fail with "No space left on device", or df shows / at 100% capacity or 100% inodes. Classic UFS inode exhaustion and /var/log or pkg cache filling the root. Not a ZFS checksum/pool-health problem.
requires_rw: no
requires_net: no
requires_zfs: no
requires_ufs: no
preconditions: {"rw":false,"net":false,"zfs":false,"ufs":false,"rescue_ok":true,"single_user_ok":true}
danger_flags: ["Deleting the wrong tree (especially /var/db/pkg or /etc) makes the box worse than full.","Truncating logs loses evidence; copy off first if you still need the files.","ZFS snapshots hold space after you rm; df will not drop until the snapshot is gone (out of scope here).","Reclaim writes need a writable root and the apply gate (hawkeye apply --yes)."]
rollback_notes: Deleted or truncated files are gone. Restore from backup or a ZFS BE. If you only inspected, there is nothing to roll back.
---

# Root 100% full or out of inodes

Two different failures look like "disk full":

- **Blocks:** `df -h /` shows `Capacity` 100%. pkg extract, logging, and `freebsd-update` die.
- **Inodes:** `df -i /` shows `iused` at the limit while `df -h` still has free space. Classic UFS with millions of small files (mail queues, `/tmp`, leftover pkg). ZFS almost never runs out of inodes this way.

Inspect first. Do not `rm` or truncate until the operator confirms apply (`hawkeye apply --yes`) and `/` is writable (`ufs-mount-rw` or `zfs-remount-rw`).

## Commands

```sh
export PATH=/rescue:/sbin:/bin:/usr/sbin:/usr/bin
df -h /
df -i /
df -T /
df -h / /var /tmp /usr /usr/local 2>/dev/null
df -i / /var /tmp /usr 2>/dev/null
mount -p
du -xhd 1 /
du -xhd 1 /var 2>/dev/null
du -xhd 1 /var/log /var/cache /var/db /var/crash /tmp /usr/local 2>/dev/null
ls -l /var/log
ls /var/cache/pkg /var/db/freebsd-update 2>/dev/null
```

## What you are looking at

- `/var/log` growing (`messages`, `maillog`, `debug.log`) — newsyslog never ran or a daemon is looping.
- `/var/cache/pkg` — pkg cache after a large install or a failed upgrade.
- `/var/crash` — kernel dumps.
- `/tmp` or `/var/tmp` — leftover extract trees.
- `/var/db/freebsd-update` — leftover upgrade work; do not delete blindly.
- **Do not** empty `/var/db/pkg` to free space; that is the package database.

On ZFS, also `zfs list -o name,used,avail,refer` and `zpool list`. A dataset can be full while the pool still has space (quota) or the pool can be full because snapshots still reference deleted files.

## Apply-gated reclaim

Hawkeye apply defaults to dry-run. Only after you identified **one** tree and `hawkeye apply --yes`:

```sh
# Writable slash first (playbooks ufs-mount-rw or zfs-remount-rw).
# Truncate a log you named from ls (example name only):
#   : > /var/log/messages
# Cached packages (pkg binary must exist; this is not a network fetch):
#   pkg clean -a
# Then:
df -h /
df -i /
```

Do not paste `rm -rf` of `/var` or `/usr` into a plan. If the root is a ruined upgrade, activate another BE (`bectl-rollback`) instead of deleting userland.

## Notes

- `df` and `du` are on typical `/rescue` images. `pkg` is not; skip `pkg clean` until `/usr` is mounted.
- `No space left on device` during `pkg install` or `pkg upgrade` is this playbook, not a broken mirror.
- After reclaim, logging and pkg can write again; you still need to fix whatever filled the disk.
