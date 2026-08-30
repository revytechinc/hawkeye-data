---
id: network-ifconfig
title: Bring up a NIC with ifconfig, dhclient, or service netif
when_to_use: The box has no usable network (wrong if, down NIC, missing module, no lease) and you need a link for pkg, NFS, or remote recovery. Skip if the failure is disks, not packets.
requires_rw: no
requires_net: no
requires_zfs: no
requires_ufs: no
preconditions: {"rw":false,"net":false,"zfs":false,"ufs":false,"rescue_ok":true,"single_user_ok":true}
danger_flags: ["dhclient overwrites address state on that interface.","service netif restart drops all NICs briefly.","Do not point default route at an untrusted network without noticing.","Wireless/wpa is out of scope here; this playbook is wired DHCP/static."]
rollback_notes: ifconfig IF down; ifconfig IF inet 0.0.0.0 delete; service netif restart   — or reboot if /etc was not changed.
---

# ifconfig, dhclient, service netif

Works from `/rescue` with a present driver. If `ifconfig -a` shows no physical NIC, load the module first (playbook `kldload-boot-kernel`).

Interface names are host-specific (`em0`, `igb0`, `ix0`, `re0`, `vtnet0`). Read them from `ifconfig -a`; do not copy example names blindly.

## Commands

```sh
export PATH=/rescue:/sbin:/bin:/usr/sbin:/usr/bin
ifconfig -a
kldstat
# If the NIC is missing, kldload the driver from /boot/kernel (see kldload-boot-kernel).
IF=em0
ifconfig "$IF" up
dhclient "$IF"
ifconfig "$IF"
netstat -rn
```

## rc(8) services (when /etc and userland exist)

```sh
service netif restart
service routing restart
service dhclient start em0
```

## Static addressing (no dhclient)

```sh
ifconfig em0 inet 192.0.2.10/24 up
route add default 192.0.2.1
```

The `192.0.2.0/24` block is documentation-only (RFC 5737). Use this host's real addresses; never paste production addressing into an LLM.

## Notes

- Single-user may lack `dhclient` in `/rescue`. Then use static `ifconfig`/`route`, or `service` after mounting a writable userland.
- `/etc/rc.conf` edits need a writable root (`ufs-mount-rw` or `zfs-remount-rw`) and are a persistent change; prefer runtime ifconfig for a one-shot rescue.
