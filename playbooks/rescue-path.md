---
id: rescue-path
title: Use /rescue when dynamic userland is missing
when_to_use: /bin or /sbin fail (missing /lib, missing /usr, truncated root) or you are on install/mfs media. /rescue holds statically linked copies of the critical tools.
requires_rw: no
requires_net: no
requires_zfs: no
requires_ufs: no
preconditions: {"rw":false,"net":false,"zfs":false,"ufs":false,"rescue_ok":true,"single_user_ok":true}
danger_flags: ["/rescue is a small tool set; not every flag from GNU or full userland exists.","Mixing /rescue and broken dynamic binaries on PATH can call the broken one first if you put /rescue last."]
rollback_notes: Restore PATH from a known-good profile, or reboot. /rescue itself is not modified by this playbook.
---

# /rescue PATH

`/rescue` is intended to work when `/usr` is gone and when shared libraries under `/lib` are gone. Put it **first** on `PATH`.

## Commands

```sh
export PATH=/rescue:/sbin:/bin:/usr/sbin:/usr/bin
echo "$PATH"
ls /rescue
# Sanity: these should be static and runnable
/rescue/sh -c 'echo rescue-ok'
/rescue/mount -p
/rescue/ifconfig -a
# ZFS tools are present on typical FreeBSD /rescue builds:
/rescue/zfs version 2>/dev/null || /rescue/zpool status
```

## Notes

- After `PATH=/rescue:...`, the rest of the playbooks can run even if `/usr/local` (Hawkeye pkg copy) is missing. The knowledge file should be under `/boot/hawkeye/`.
- If `/rescue` itself is missing, boot install media or another BE (`bectl-rollback`).
- Do not copy secrets into scripts under `/rescue`; it is a binary directory, not a scratch area.
