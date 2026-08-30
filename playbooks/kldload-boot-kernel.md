---
id: kldload-boot-kernel
title: kldload a module from /boot/kernel
when_to_use: A driver or geom class is missing (no NIC, no geli, no zfs.ko) and /usr may be gone. Modules still live under /boot/kernel or /boot/modules.
requires_rw: no
requires_net: no
requires_zfs: no
requires_ufs: no
preconditions: {"rw":false,"net":false,"zfs":false,"ufs":false,"rescue_ok":true,"single_user_ok":true}
danger_flags: ["Loading the wrong ABI module (wrong kernel/module pair) can panic.","kldload is not a substitute for a matching kernel.","Some modules are already compiled in; loading a duplicate can fail or confuse diagnostics."]
rollback_notes: kldunload MODULE   — only if nothing is using it. A panic requires a reboot; there is no unload then.
---

# kldload from /boot/kernel

When `/usr` is missing, `kldload if_em` may still fail if module search path points at `/boot/modules` plus `/boot/kernel` incorrectly, or if those paths are on a filesystem that is not mounted. Prefer the **absolute path**.

## Commands

```sh
export PATH=/rescue:/sbin:/bin:/usr/sbin:/usr/bin
kldstat
ls /boot/kernel
ls /boot/modules
sysctl kern.module_path
# Example: Intel em(4). Replace with the module this host needs.
kldload /boot/kernel/if_em.ko
kldstat
```

## Common rescue modules (verify the file exists first)

```sh
kldload /boot/kernel/zfs.ko
kldload /boot/kernel/geom_eli.ko
kldload /boot/kernel/if_igb.ko
kldload /boot/kernel/if_vtnet.ko
kldload /boot/kernel/opensolaris.ko
```

Not every kernel ships every `.ko` (it may be static). `ls` the directory; do not assume.

## Notes

- `MODULE_PATH` / `kern.module_path` defaults include `/boot/kernel` and `/boot/modules`.
- If `/boot` itself is missing, you are past this playbook: boot a different kernel/BE or install media.
- After `if_*.ko`, continue with playbook `network-ifconfig`. After `geom_eli.ko`, playbook `geli-attach`. After `zfs.ko`, playbook `zpool-import`.
