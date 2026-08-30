---
id: secrets-policy
title: Secrets never enter the Hawkeye corpus
category: policy
---

# Secrets policy

This kit is a public, shippable knowledge corpus. It must remain useful on a USB stick and on a RO root.

**Never store in this repository, the sqlite file, playbooks, or docs:**

- SSH private keys, `authorized_keys` samples that look real, or host keys
- Passwords, passphrases, `htpasswd` lines, or API tokens
- geli passphrases, ZFS wrapping keys, or key-file bytes
- Real MAC addresses, production hostnames, or customer paths that identify a deployment

**Runtime rule for Hawkeye (the binary):**

- Playbooks `zfs-load-key` and `geli-attach` tell the operator to type secrets at the console.
- The assistant may print the command name (`zfs load-key DATASET`) and must not accept the secret as a parameter to "run this for me".
- Redaction: if a log is later ingested, drop lines that look like PEM, `BEGIN OPENSSH`, `crypt$`, `keylocation=file://` contents, and `Authorization:` headers. Prefer dropping the whole line to "fake" examples.

This file exists so FTS queries such as "password", "key", and "geli" still hit **policy**, not samples.
