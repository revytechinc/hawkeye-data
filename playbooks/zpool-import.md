---
id: zpool-import
title: Import a ZFS pool (readonly first, then unlock)
when_to_use: The pool is not imported (new boot, missing cache, other host, disks returned). You need to inspect or mount datasets, including a root pool from rescue or live media.
requires_rw: no
requires_net: no
requires_zfs: yes
requires_ufs: no
preconditions: {"rw":false,"net":false,"zfs":true,"ufs":false,"rescue_ok":true,"single_user_ok":true}
danger_flags: ["zpool import -f rewrites pool state; only if you are sure no other host has the pool imported.","Importing read-write on a damaged pool can make recovery worse; start with -o readonly=on.","Do not import a pool that is still imported on another machine.","Encryption keys and passphrases must be typed at the console; they never go through an LLM, log, or chat."]
rollback_notes: zpool export POOL   — or keep the readonly import and do not re-import read-write.
---

# Import a ZFS pool

Default path: **list**, **import readonly** (no mounts if you want extra caution), **inspect**, **load keys** if encrypted (see `zfs-load-key`), **mount**. Only then, if you must write, export and re-import without `readonly=on`.

## Commands

```sh
export PATH=/rescue:/sbin:/bin:/usr/sbin:/usr/bin
zpool import
zpool import -o readonly=on -N POOL
zpool status POOL
zpool get health,readonly,altroot POOL
zfs list -o name,mounted,mountpoint,encroot,keystatus,readonly -r POOL
# If keystatus=unavailable: stop. Operator loads the key at the console (playbook zfs-load-key).
# After keys (if any) are loaded:
zfs mount -a
# To go read-write later (destroys the readonly import guarantee):
zpool export POOL
zpool import POOL
```

## Other-host / missing cache / altroot

```sh
zpool import -f -o readonly=on -N POOL
zpool import -o readonly=on -R /mnt POOL
zpool import -d /dev/gpt -o readonly=on -N POOL
zpool import -c /etc/zfs/zpool.cache
```

## Notes

- `-N` imports without mounting datasets. Useful until keys are loaded.
- `-o readonly=on` is the safe inspect import. Dataset `zfs set readonly=off` will **not** override a readonly pool; you must export and import again without that option.
- `-R /mnt` sets `altroot` so mounts land under `/mnt` (rescue media, not the running root).
- `-f` is for a last-imported-host mismatch, not a substitute for a missing device.
- After a writable import of a root pool from live media, do not reuse that pool as `/` until you understand `bootfs` and BE names (`bectl-rollback`).
