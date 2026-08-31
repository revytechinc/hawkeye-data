---
id: sshd-not-running
title: sshd enabled but not running after upgrade
when_to_use: sshd_enable=YES after freebsd-update, a pkg upgrade, or a BE switch, but nothing is listening and ssh from the network fails. You are on the console. Not for Hawkeye MCP/self-health, and not for forgotten firewall rules as the first guess.
requires_rw: no
requires_net: no
requires_zfs: no
requires_ufs: no
preconditions: {"rw":false,"net":false,"zfs":false,"ufs":false,"rescue_ok":true,"single_user_ok":true}
danger_flags: ["Do not start sshd until the apply gate (hawkeye apply --yes) and sshd -t is clean.","Do not paste ssh_host_* keys, authorized_keys, or sshd_config into an LLM.","Starting sshd with a broken ListenAddress or missing host keys fails again or exposes a bad config.","/usr/sbin/sshd is not in /rescue; if /usr is unmounted this is fstab-mounts first."]
rollback_notes: Leave sshd stopped. After a writable root and apply --yes, fix config or host keys at the console, or bectl activate a BE that still has a working sshd. reboot if you cannot get a clean sshd -t.
---

# sshd enabled, not running

After an upgrade the usual story is: `sshd_enable=YES` is still in rc.conf, `/etc/rc.d/sshd` still exists, but `/usr/sbin/sshd` is missing, `sshd_config` fails `sshd -t`, or host keys were not regenerated. `sockstat` then shows nothing on 22.

**Apply gate:** inspect only below. Do **not** `/etc/rc.d/sshd start` until `hawkeye apply --yes` and the binary, config, and host keys all check out.

## Commands

```sh
export PATH=/rescue:/sbin:/bin:/usr/sbin:/usr/bin
grep -E 'sshd_enable=' /etc/rc.conf /etc/rc.conf.local /etc/rc.conf.d/* 2>/dev/null
ls -l /etc/rc.d/sshd /usr/sbin/sshd
/etc/rc.d/sshd rcvar
/etc/rc.d/sshd status
ls /etc/ssh/ssh_host_*_key 2>/dev/null
sshd -t
sockstat -4 -l -P tcp 2>/dev/null
sockstat -46 -l -P tcp 2>/dev/null
netstat -an -p tcp 2>/dev/null
```

`sockstat` lives in `/usr/bin` and is often missing from `/rescue`; `netstat -an -p tcp` is the fallback. Look for `*.22` in `LISTEN` state, not for a process table rumour.

## What failed

- **`/usr/sbin/sshd` missing** — `/usr` not mounted (`fstab-mounts`), incomplete world, or you are in a BE that does not match the upgrade (`bectl-rollback`).
- **`/etc/rc.d/sshd` missing** — base is truncated; this is not a pkg `openssh-portable` path (that would be `/usr/local/etc/rc.d/openssh`).
- **`sshd -t` errors** — leftover `sshd_config` merge after `freebsd-update` / `etcupdate`. Fix at the console; do not paste the file into an assistant.
- **No `ssh_host_*_key` files** — sshd refuses to start. Generate keys at the console after apply (`ssh-keygen -A`). Never dump key bytes into Hawkeye.
- **`status` says not running, `sshd -t` is clean, keys exist** — it simply never started after the upgrade. Start is apply-gated.

`rc-enable-missing` if `sshd_enable=YES` but the rc.d script itself is gone.

## Apply-gated start

Hawkeye apply defaults to dry-run. Only after `sshd -t` is quiet, the binary exists, and `hawkeye apply --yes`:

```sh
# /etc/rc.d/sshd start
# /etc/rc.d/sshd status
# sockstat -4 -l -P tcp
```

If `sshd_enable` is not YES, `onestart` is a one-shot; still apply-gated, still not an LLM exec.

## Notes

- Console-only for keys and config. Playbook `geli-attach` / `zfs-load-key` secret rule applies to host keys too.
- A working sshd on the box does not prove the firewall or `ListenAddress` matches the NIC you think (`network-no-route`).
- `/rescue` has no sshd. You cannot start it until `/usr` is there.
