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

## fstab versus mounts

- `cat /etc/fstab` then `mount -p` / `df -T` (`fstab-mounts`)
- Labels: `gpart show -l`, `glabel status`, `ls /dev/gpt /dev/ufs`
- `noauto` is expected not to mount; dump/pass are UFS `dump(8)` / `fsck(8)` fields
- Missing `/dev/gpt/NAME`: disk, geli, or a renamed label — do not invent names
- Never `fsck` ZFS; a ZFS fstab line still needs the pool imported

## rc.conf enabled but missing

- `grep _enable= /etc/rc.conf`; `ls /etc/rc.d /usr/local/etc/rc.d` (`rc-enable-missing`)
- `rcorder /etc/rc.d/*`; `sh -n /etc/rc.conf` and `sh -n` the rc.d script
- Do **not** start the service until apply `--yes` and both script and `command=` binary exist

## Root full / inodes

- `df -h /` and `df -i /` (`root-full`) — blocks vs UFS inodes
- Classic fillers: `/var/log`, `/var/cache/pkg`, `/var/crash`
- Reclaim is apply-gated; do not empty `/var/db/pkg`

## Network and modules

- `kldload /boot/kernel/MODULE.ko` (`kldload-boot-kernel`)
- `ifconfig IF up` / `dhclient IF` / `service netif restart` (`network-ifconfig`)
- NIC UP but `status: no carrier`, no `default` in `netstat -rn`, or empty `resolv.conf` (`network-no-route`)

## sshd after upgrade

- `sshd_enable=YES` but not listening: `ls /etc/rc.d/sshd /usr/sbin/sshd`, `sshd -t`, `sockstat` (`sshd-not-running`)
- Do not start sshd until apply `--yes` and `sshd -t` is clean

## PATH and runlevel

- `export PATH=/rescue:/sbin:/bin:/usr/sbin:/usr/bin` (`rescue-path`)
- single-user: `boot -s` or `shutdown now`; `exit` continues to multi-user (`single-user`)

## Where this kit lives

- Rescue: `/boot/hawkeye/knowledge.sqlite`
- pkg: `/usr/local/share/hawkeye/knowledge.sqlite`
