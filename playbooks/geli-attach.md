---
id: geli-attach
title: Attach a geli provider at the console
when_to_use: A geli-encrypted partition is detached (no /dev/*.eli). You need the provider before mount, zpool import, or swap. The operator has the passphrase or key file. Hawkeye must not see the secret.
requires_rw: no
requires_net: no
requires_zfs: no
requires_ufs: no
preconditions: {"rw":false,"net":false,"zfs":false,"ufs":false,"rescue_ok":true,"single_user_ok":true,"secrets_at_console_only":true}
danger_flags: ["KEYS NEVER GO THROUGH AN LLM, chat, log, screenshot, or Hawkeye prompt.","Attaching with the wrong key is a failed attach, not a format; still do not brute-force via the assistant.","Do not geli init, geli setkey, or geli kill unless that is the explicit goal of a different procedure.","Swap geli providers: attaching is not the same as enabling swap."]
rollback_notes: geli detach /dev/PROVIDER.eli   — or geli detach PROVIDER (see geli(8)). Unmount filesystems first.
---

# Attach a geli provider

**Secret rule:** passphrase and key files stay on the console. Hawkeye lists devices and flags; it never accepts the secret as input.

## Commands

```sh
export PATH=/rescue:/sbin:/bin:/usr/sbin:/usr/bin
geli list
geli status
ls -l /dev/*.eli /dev/gpt/* /dev/ada* /dev/nvme* /dev/da* 2>/dev/null
# Identify the encrypted provider (NOT the .eli node). Example name only:
#   /dev/gpt/disk0p3
# Operator, at the console, NOT via Hawkeye:
geli attach PROVIDER
geli status
```

## Key file (still not via LLM)

```sh
# Operator supplies the key file path. Do not paste key bytes.
geli attach -k /path/to/keyfile PROVIDER
```

## After attach

- UFS: `fsck` if needed, then `mount` (playbooks `fsck`, `ufs-mount-rw`).
- ZFS: `zpool import` (playbook `zpool-import`). A pool on geli typically needs the `.eli` providers present first.
- If the geli device is `/` itself, this usually happens from the boot loader (`geom_eli` + passphrase prompt), not from this late playbook.

## Notes

- Provider names are host-specific. Use `geli status`, `gpart show`, and `glabel status` on **this** box. Never copy device names from examples into production without checking.
- Dummy key material is not included in this kit on purpose.
