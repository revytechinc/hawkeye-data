---
id: network-no-route
title: NIC up but no carrier, default route, or DNS
when_to_use: ifconfig shows the interface UP (maybe even with an address) but nothing routes off-box — status no carrier, empty netstat -rn default, or /etc/resolv.conf has no nameserver. Skip if the NIC itself is missing (kldload-boot-kernel) or you already know you need a bring-up (network-ifconfig).
requires_rw: no
requires_net: no
requires_zfs: no
requires_ufs: no
preconditions: {"rw":false,"net":false,"zfs":false,"ufs":false,"rescue_ok":true,"single_user_ok":true}
danger_flags: ["dhclient and route add change live addressing; apply gate (hawkeye apply --yes) before those.","Do not point default at an untrusted gateway just to 'get a route'.","Editing resolv.conf is persistent; do it at the console, not through an LLM.","This playbook is wired Ethernet; wpa/wireless is out of scope."]
rollback_notes: ifconfig IF inet 0.0.0.0 delete; route delete default; ifconfig IF down   — or reboot if /etc was not changed.
---

# NIC up, no carrier / no default / no DNS

Three stacked failures. Walk them in order; do not skip to `dhclient` if `ifconfig` says `status: no carrier`.

1. **Carrier** — the NIC is administratively up but the link is dead (cable, switch, VLAN, or driver).
2. **Default route** — you have an address (or you do not) and `netstat -rn` has no `default`.
3. **DNS** — packets might route, but `/etc/resolv.conf` has no `nameserver`.

There is no Linux `/proc/net`. Use `ifconfig`, `netstat -rn`, and `route`.

## Commands

```sh
export PATH=/rescue:/sbin:/bin:/usr/sbin:/usr/bin
ifconfig -a
netstat -rn
netstat -rn -f inet
route -n get default
cat /etc/resolv.conf
ls /var/db/dhclient.leases.* 2>/dev/null
```

Interface names are host-specific (`em0`, `igb0`, `ix0`, `re0`, `vtnet0`). Read them from `ifconfig -a`.

```sh
IF=em0
ifconfig "$IF"
# Look for: UP, RUNNING, status: no carrier | status: active, inet ...
```

## How to read it

- `status: no carrier` (and often no `RUNNING`) — layer 1. Cable, switch port, or the driver is wrong. Load the module only if `ifconfig -a` has no physical NIC (`kldload-boot-kernel`). Do not run `dhclient` yet.
- `status: active` but no `inet` — no address. Bring-up is playbook `network-ifconfig` (apply-gated `dhclient` / static).
- `inet` present, `netstat -rn` has no `default` — DHCP never installed a router, or static config omitted `defaultrouter`.
- `default` present, `resolv.conf` empty or has no `nameserver` — DNS only. `dhclient` usually writes this; a hand-edited empty file is common after a restore.

`/rescue` may lack `dhclient`. `ifconfig` and `netstat` are the rescue-safe pair.

## Apply-gated addressing

Hawkeye apply defaults to dry-run. Do **not** run `dhclient`, `route add`, or rewrite `resolv.conf` until `hawkeye apply --yes`. Prefer playbook `network-ifconfig` for the actual bring-up.

```sh
# After apply --yes, and only if status is active:
#   dhclient "$IF"
#   ifconfig "$IF" inet 192.0.2.10/24 up
#   route add default 192.0.2.1
# 192.0.2.0/24 is documentation-only (RFC 5737). Use this host's addresses.
# resolv.conf: edit at the console; do not paste customer nameservers into an LLM.
```

## Notes

- Single-user usually has no `routing`/`netif` rc; a missing default is expected until you add one.
- `service netif restart` drops every NIC; that is a mutating apply, not an inspect step.
- IPv6: `netstat -rn -f inet6` and `ifconfig` `inet6`. Same carrier rule.
