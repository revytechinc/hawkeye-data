---
id: zfs-load-key
title: Load ZFS encryption keys at the console
when_to_use: zfs get keystatus shows unavailable and datasets will not mount. The operator has the passphrase or key file. Hawkeye must not see the secret.
requires_rw: no
requires_net: no
requires_zfs: yes
requires_ufs: no
preconditions: {"rw":false,"net":false,"zfs":true,"ufs":false,"rescue_ok":true,"single_user_ok":true,"secrets_at_console_only":true}
danger_flags: ["KEYS NEVER GO THROUGH AN LLM, chat, log, screenshot, or Hawkeye prompt.","A wrong keylocation or wrapping key can look like 'unavailable' forever; do not cycle guesses into the assistant.","keyfile paths are secrets if the file contains key material; do not paste paths that embed passphrases.","load-key does not by itself mount; mount after keystatus=available."]
rollback_notes: zfs unload-key DATASET   — or zfs unload-key -a. Then zfs unmount if you mounted.
---

# Load ZFS encryption keys

**Secret rule:** the operator types the passphrase or points `zfs` at a key file **on the console**. Hawkeye prints this playbook and stops. Do not paste keys, key files, or `echo`-piped passphrases into the assistant.

## Commands

```sh
export PATH=/rescue:/sbin:/bin:/usr/sbin:/usr/bin
zfs get -o name,property,value -r encryption,keystatus,keyformat,keylocation,pbkdf2iters POOL
# Operator, at the console, NOT via Hawkeye:
zfs load-key DATASET
# or all unloaded keys that can prompt:
zfs load-key -a
zfs get -r keystatus POOL
zfs mount DATASET
```

## Key file (still not via LLM)

If `keylocation` is `file://...` and that file is present (for example on `/boot` or a USB key the operator inserted):

```sh
zfs get keylocation DATASET
# Operator confirms the path. Hawkeye must not ingest the file contents.
zfs load-key DATASET
```

## Notes

- `prompt://` means a tty prompt. That tty must be the physical or serial console, not a model context window.
- After `keystatus=available`, mount (`zfs mount` or `zfs mount -a`). If the pool is `readonly=on`, mounts stay read-only (see `zpool-import` and `zfs-remount-rw`).
- Never invent `keylocation` values. Read them from `zfs get`.
