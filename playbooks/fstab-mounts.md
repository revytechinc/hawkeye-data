---
id: fstab-mounts
title: Compare fstab to mounted filesystems
when_to_use: Boot dropped to single-user, /usr never appeared, or a mountpoint is empty because /etc/fstab does not match what is actually mounted. Typical after a disk swap, a renamed GPT/UFS label, a missing device node, a leftover noauto line, or a ZFS dataset that is canmount=off / mountpoint=legacy while fstab still lists it.
requires_rw: no
requires_net: no
requires_zfs: no
requires_ufs: no
preconditions: {"rw":false,"net":false,"zfs":false,"ufs":false,"rescue_ok":true,"single_user_ok":true}
danger_flags: ["Do not fsck a ZFS pool or dataset; dump/pass in fstab is for UFS/dump(8) only.","Mounting the wrong device onto /usr or /var can hide the real tree.","Editing fstab is a persistent change; needs a writable root and the apply gate (hawkeye apply --yes).","A missing /dev/gpt or /dev/ufs node usually means the label or disk is gone, not that you should invent a new name."]
rollback_notes: umount MOUNTPOINT for anything you mounted by hand. Restore /etc/fstab from backup or a ZFS BE if you edited it. Reboot if mounts are in a confused state.
---

# fstab versus what is mounted

FreeBSD `fstab(5)` is six fields: device, mountpoint, type, options, dump, pass. Compare that file to live mounts before you change anything. This playbook is **inspect first**. Do not edit `/etc/fstab` or `mount` extra filesystems until the operator confirms apply (`hawkeye apply --yes`).

ZFS datasets with a real `mountpoint=` are usually mounted by ZFS itself, not by fstab. A leftover fstab line for a dataset is a common false alarm; a missing `/dev/gpt/LABEL` after a disk swap is a real one.

## Commands

```sh
export PATH=/rescue:/sbin:/bin:/usr/sbin:/usr/bin
cat /etc/fstab
mount -p
df -T
gpart show -l
glabel status
ls /dev/gpt /dev/ufs /dev/label /dev/gptid 2>/dev/null
# ZFS (ignore errors on a UFS-only box):
zfs list -o name,mounted,mountpoint,canmount 2>/dev/null
# fstab lines that are not comments (device mountpoint type options dump pass):
grep -v '^#' /etc/fstab | grep -v '^$'
```

## Read the six fields

- **device** — `/dev/gpt/NAME`, `/dev/ufs/NAME`, `/dev/ada0p2`, a gptid, or a ZFS dataset (`POOL/fs`). The node must exist for GEOM/UFS. Names come from **this** box (`gpart show -l`, `glabel status`), never from an example.
- **type** — `ufs`, `zfs`, `swap`, `tmpfs`, `nullfs`, `nfs`. If `df -T /` says `zfs` but fstab still lists UFS for `/`, you are looking at the wrong story.
- **options** — `rw`, `ro`, `noauto` (will **not** mount at boot; that is expected), `late`, `nosuid`. `noauto` is not a failure.
- **dump** — `dump(8)` frequency. `0` means dump skips it. Not a mount flag.
- **pass** — `fsck(8)` order at boot. `0` skip, `1` root (UFS), `2+` the rest. **Never** give a ZFS dataset a non-zero pass; never `fsck` ZFS (playbook `fsck` is UFS only).

## Missing device

```sh
# For each fstab device that is not a ZFS dataset and not "noauto":
#   ls -l /dev/gpt/NAME
# If ls fails: disk not attached, geli not attached (playbook geli-attach),
# label renamed, or gptid changed after a replacement.
gpart show
gpart show -l
glabel status
```

A ZFS dataset in fstab with `type` `zfs` still needs the pool imported (`zpool-import`). `canmount=off` or `mountpoint=legacy` plus a bad fstab line is a common upgrade leftover.

## Apply-gated mount or fstab edit

Hawkeye apply defaults to dry-run. Do **not** mount or rewrite fstab until the operator runs `hawkeye apply --yes` (or types the command at the console). Root must be writable first (`ufs-mount-rw` or `zfs-remount-rw`).

```sh
# Only after apply --yes, and only for a device you just confirmed exists:
#   mount /usr
#   mount /var
# Persistent fix is an /etc/fstab edit (comment the bad line, or fix the label).
#   mount -u -o rw /
#   then edit /etc/fstab at the console; do not paste production fstab into an LLM.
```

## Notes

- Single-user often has `/` mounted and nothing else. An empty `/usr` with a `/usr` fstab line is this playbook, not a missing world package.
- Swap lines (`type` `swap`) never appear in `mount -p`.
- NFS/nullfs/tmpfs are out of scope here except to skip them when comparing local disks.
- After a label fix, reboot or `exit` from single-user so `rc` remounts in order.
