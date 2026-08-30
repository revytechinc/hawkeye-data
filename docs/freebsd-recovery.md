---
id: freebsd-recovery
title: FreeBSD recovery cheat sheet
category: cheatsheet
---

# FreeBSD recovery cheat sheet

Short hits for FTS and a human at a RO console. Procedures live in `playbooks/`.

## Identify the root filesystem

- `df -T /` — `ufs` vs `zfs`
- `mount -p` — device/dataset, mountpoint, type, options (`ro`/`rw`)
- `zfs get readonly,mounted,encroot,keystatus` on the `/` dataset
- `gpart show` / `glabel status` — partition labels

## Make `/` writable

- UFS: `mount -u -o rw /` (`ufs-mount-rw`)
- ZFS dataset: `zfs set readonly=off $ROOTDS` then `zfs mount -u` / `mount -u -o rw /` (`zfs-remount-rw`)
- ZFS pool imported `readonly=on`: export, re-import without that option (`zpool-import`)

## Dirty UFS

- `fsck -t ufs -n $SPEC` inspect; `-y` repair only while **not** RW-mounted (`fsck`)
- Never `fsck` ZFS

## Pools

- `zpool import` list; `zpool import -o readonly=on -N POOL` inspect (`zpool-import`)
- Encrypted: `zfs load-key` at the **console** (`zfs-load-key`)
- geli: `geli attach` at the **console** (`geli-attach`)

## Boot environments

- `bectl list` / `bectl activate GOOD_BE` / reboot (`bectl-rollback`)

## Network and modules

- `kldload /boot/kernel/MODULE.ko` (`kldload-boot-kernel`)
- `ifconfig IF up` / `dhclient IF` / `service netif restart` (`network-ifconfig`)

## PATH and runlevel

- `export PATH=/rescue:/sbin:/bin:/usr/sbin:/usr/bin` (`rescue-path`)
- single-user: `boot -s` or `shutdown now`; `exit` continues to multi-user (`single-user`)

## Where this kit lives

- Rescue: `/boot/hawkeye/knowledge.sqlite`
- pkg: `/usr/local/share/hawkeye/knowledge.sqlite`
