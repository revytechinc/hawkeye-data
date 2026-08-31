---
id: rc-enable-missing
title: rc.conf enable=YES but script or binary missing
when_to_use: Boot or `exit` from single-user prints that a service is enabled but the rc.d script is gone, the daemon binary is gone, or rcorder/rc.conf has a syntax error. Classic after pkg delete, a partial upgrade, or /usr not mounted. This is not Hawkeye self-health.
requires_rw: no
requires_net: no
requires_zfs: no
requires_ufs: no
preconditions: {"rw":false,"net":false,"zfs":false,"ufs":false,"rescue_ok":true,"single_user_ok":true}
danger_flags: ["Do not start or restart any service from this playbook until the apply gate (hawkeye apply --yes). Inspect only.","A missing binary with *_enable=YES will fail again if you start it anyway.","sh -n /etc/rc.conf does not prove the rest of rc.d is sane; still read rcorder errors.","Do not run service /etc/rc.d start from an LLM plan; operator apply --yes only."]
rollback_notes: Leave the service stopped. After a writable root and apply --yes, set foo_enable=NO or restore the missing package/script. reboot if rc is still wedged.
---

# rc.conf YES, script or binary missing

`rc.conf` `*_enable=YES` (or `YES`/`true`/`on`) only means rc will **try**. If `/etc/rc.d/foo` or `/usr/local/etc/rc.d/foo` is gone, or the `command=` binary is gone, boot complains and that service never runs.

**Apply gate:** the `## Commands` block is inspect-only. Hawkeye apply defaults to dry-run. Do **not** `service foo start`, `/etc/rc.d/foo start`, or `onestart` until the operator confirms (`hawkeye apply --yes`) **and** the script and binary both exist.

`sysrc` is often missing from `/rescue`; `grep` and `ls` are the rescue-safe tools.

## Commands

```sh
export PATH=/rescue:/sbin:/bin:/usr/sbin:/usr/bin
sh -n /etc/rc.conf
sh -n /etc/rc.conf.local 2>/dev/null
grep -E '_enable=' /etc/rc.conf /etc/rc.conf.local /etc/rc.conf.d/* 2>/dev/null
ls /etc/rc.d
ls /usr/local/etc/rc.d 2>/dev/null
rcorder /etc/rc.d/* 2>&1
rcorder /etc/rc.d/* /usr/local/etc/rc.d/* 2>&1
```

## One service (replace foo)

```sh
SVC=foo
grep -E "${SVC}_enable=" /etc/rc.conf /etc/rc.conf.local /etc/rc.conf.d/* 2>/dev/null
ls -l /etc/rc.d/"$SVC" /usr/local/etc/rc.d/"$SVC"
# If the script exists, syntax-check it and find the daemon path:
sh -n /etc/rc.d/"$SVC" 2>/dev/null
sh -n /usr/local/etc/rc.d/"$SVC" 2>/dev/null
grep -E '^(command|procname)=' /etc/rc.d/"$SVC" /usr/local/etc/rc.d/"$SVC" 2>/dev/null
# ls the command= path you just read (do not guess a Linux path).
```

A `*_enable=YES` line with **no** matching file under `/etc/rc.d` or `/usr/local/etc/rc.d` is a leftover (pkg gone, `/usr` not mounted — see `fstab-mounts`). A script that exists but `command=` points at a missing binary is a broken install or a BE that does not match the package set (`bectl-rollback`).

`rcorder` lines like `requirement 'bar' not found` mean a `REQUIRE:` is unsatisfied (missing script), not that you should start something.

## Apply-gated start or disable

Only after inspect, a writable root if you will edit rc.conf, and `hawkeye apply --yes`:

```sh
# Start is allowed only when both the rc.d script and the command= binary exist.
#   /etc/rc.d/foo start
#   /usr/local/etc/rc.d/foo start
# To stop the boot noise instead of starting:
#   mount -u -o rw /     # or zfs-remount-rw
#   then set foo_enable=NO in /etc/rc.conf at the console
# Do not paste production rc.conf into an LLM.
```

## Notes

- `checkyesno` accepts `YES`, `yes`, `true`, `on`, `1`. A typo (`sshd_enble`) is just a dead line.
- `/etc/rc.conf.d/foo` overrides pieces of rc.conf for that service.
- This is **not** a Hawkeye `doctor` playbook. Do not treat a missing `hawkeye` rc.d script as the host's boot failure.
- `service(8)` lives under `/usr/sbin` and may be absent in rescue; call the script path you `ls`'d.
