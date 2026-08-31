---
id: single-user
title: Single-user versus multi-user
when_to_use: You need to know how you got a root shell with a RO filesystem, how to reach single-user, or how to continue to multi-user after a repair.
requires_rw: no
requires_net: no
requires_zfs: no
requires_ufs: no
preconditions: {"rw":false,"net":false,"zfs":false,"ufs":false,"rescue_ok":true,"single_user_ok":true}
danger_flags: ["exit from single-user starts the rest of rc; a broken rc will fail again (see rc-enable-missing).","Single-user is not a security boundary on an insecure console.","Do not 'kill 1' as if this were a SysV Linux box."]
rollback_notes: reboot   — or shutdown -r now. To stay in single-user, do not exit.
---

# Single-user vs multi-user

FreeBSD single-user: `init` gives a root shell, typically **before** most of `rc`. `/` is often **read-only**. Networking and daemons are usually down. This is the intended environment for `fsck`, `zfs-remount-rw`, `ufs-mount-rw`, and `bectl-rollback`.

## Reach single-user

```sh
# From a running multi-user system:
shutdown now
# From the loader (boot menu / ok prompt):
#   boot -s
# From an already-booted kernel that asked mountroot: follow that prompt; -s is loader-side.
```

## Work in single-user

```sh
export PATH=/rescue:/sbin:/bin:/usr/sbin:/usr/bin
mount -p
# Make / writable only if you intend to edit (see ufs-mount-rw or zfs-remount-rw):
#   mount -u -o rw /
#   or zfs set readonly=off $ROOTDS && zfs mount -u $ROOTDS
```

## Continue to multi-user

```sh
# From the single-user shell, after repairs:
exit
# That continues init's multi-user path (rc).
# To reboot instead:
reboot
```

## Notes

- Console secure flag in `ttys(5)` controls whether single-user asks for the root password.
- Single-user is **not** the same as `/rescue`. You can be multi-user with a broken `/usr` and still want `/rescue` on `PATH` (playbook `rescue-path`).
- There is no portable `init 1` / `telinit` workflow here; use `shutdown now` or `boot -s`.
- If `exit` dies on a missing rc.d script or `*_enable=YES` leftover, playbook `rc-enable-missing` (do not start services without apply `--yes`).
- If `exit` dies on a missing fstab device, playbook `fstab-mounts`.
