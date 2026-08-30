---
id: bectl-rollback
title: List, activate, or roll back a ZFS boot environment
when_to_use: The current boot environment is broken (failed upgrade, bad pkg, unbootable userland) and you have another BE. You are on a ZFS root with bectl(8)/be(8).
requires_rw: no
requires_net: no
requires_zfs: yes
requires_ufs: no
preconditions: {"rw":false,"net":false,"zfs":true,"ufs":false,"rescue_ok":true,"single_user_ok":true}
danger_flags: ["bectl activate changes the next reboot; a wrong BE can still fail to boot.","bectl destroy is permanent for that BE; this playbook does not destroy.","Temporary activate (-t) lasts one boot; forgetting that can surprise you on the following reboot.","Do not activate a BE from a different pool or ABI you do not understand."]
rollback_notes: bectl activate PREVIOUS_BE; reboot   — or bectl activate -t PREVIOUS_BE for a one-shot test boot.
---

# Boot environment list / activate / rollback

`bectl` manages ZFS boot environments (typically `zroot/ROOT/...`). Rollback here means **activate a known-good BE and reboot**, not `zfs rollback` of an arbitrary snapshot (that is a different, more dangerous operation).

## Commands

```sh
export PATH=/rescue:/sbin:/bin:/usr/sbin:/usr/bin
bectl list
zfs list -o name,used,referenced,canmount,mountpoint -r $(zfs list -H -o name | awk -F/ '/\/ROOT$/{print;exit}')
# Activate a known-good BE for the next reboot (persistent):
bectl activate GOOD_BE
# Or one reboot only:
bectl activate -t GOOD_BE
reboot
```

## From the loader (if userland bectl is missing)

```sh
# At the loader prompt, BE selection is typically in the boot menu.
# Or set:
#   vfs.root.mountfrom="zfs:zroot/ROOT/GOOD_BE"
# Names MUST come from this machine (zfs list / zpool get bootfs), not from examples.
```

## Notes

- You often **do not** need a writable current root to activate another BE; `bectl activate` updates `bootfs` / dataset properties. If the tool refuses, import the pool read-write (see `zpool-import`) from rescue media.
- After activate, **reboot**. Do not expect `/` to switch in place.
- `bectl create`, `bectl rename`, and `bectl destroy` are out of scope here.
