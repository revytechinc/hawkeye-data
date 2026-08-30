# Sources

Hawkeye knowledge harvest. Official, license-clean FreeBSD documentation only.

Collected at: `2026-08-30T21:42:10Z` UTC

Redistributions of AsciiDoc (and compiled forms derived from it) must retain
the FreeBSD Documentation License notice. See `notices/FREEBSD-DOC-LICENSE.txt`
(text from https://www.freebsd.org/copyright/freebsd-doc-license/).

## In (collected)

### `freebsd-doc`

- git: `https://github.com/freebsd/freebsd-doc.git`
- revision: `72442dc9c2971d5a056eb7f6e1056672a546e85e`
- license: FreeBSD Documentation License
- sparse paths:
  - `documentation/content/en/books/handbook`
  - `documentation/content/en/books/faq`
  - `documentation/content/en/books/porters-handbook`
  - `documentation/content/en/books/developers-handbook`
  - `documentation/content/en/books/arch-handbook`
  - `documentation/content/en/books/fdp-primer`
  - `documentation/content/en/books/accessibility`
  - `documentation/content/en/books/design-44bsd`
  - `documentation/content/en/books/dev-model`
  - `documentation/content/en/articles`
- include: `*.adoc` / `_index.adoc` (skip `*.po` translations)
- books: handbook, faq, porters-handbook, developers-handbook, arch-handbook,
  fdp-primer, accessibility, design-44bsd, dev-model
- articles: `documentation/content/en/articles`

### `freebsd-src`

- git: `https://github.com/freebsd/freebsd-src.git`
- revision: `a311bd18a6fb57c6d3a19ab5bb53bb6f1c5fd056`
- license: BSD-2-Clause (src); man pages may include IEEE Std 1003.1 excerpts — see notices/FREEBSD-DOC-LICENSE.txt
- sparse paths:
  - `share/man/man4`
  - `share/man/man5`
  - `share/man/man7`
  - `share/man/man8`
  - `sys/contrib/openzfs/man`
  - `sbin/geli`
  - `sbin/geom`
  - `sbin/bectl`
  - `sbin/fsck`
  - `sbin/fsck_ffs`
  - `sbin/newfs`
  - `sbin/mount`
  - `sbin/umount`
  - `sbin/mdconfig`
  - `sbin/ifconfig`
  - `sbin/route`
  - `sbin/kldload`
  - `sbin/kldstat`
  - `sbin/sysctl`
  - `sbin/ipfw`
  - `sbin/dhclient`
  - `sbin/nvmecontrol`
  - `sbin/camcontrol`
  - `sbin/pfctl`
  - `sbin/dump`
  - `sbin/restore`
  - `sbin/shutdown`
  - `sbin/reboot`
  - `sbin/init`
  - `usr.sbin/jail`
  - `usr.sbin/jexec`
  - `usr.sbin/jls`
  - `usr.sbin/bhyve`
  - `usr.sbin/bhyvectl`
  - `usr.sbin/periodic`
  - `usr.sbin/syslogd`
  - `usr.sbin/newsyslog`
  - `usr.bin/crontab`
  - `usr.sbin/cron`
  - `stand/man`
  - `stand/defaults`
  - `lib/geom`
  - `usr.bin/gpart`
- also: repo-root `UPDATING` and `RELNOTES` if present (cone sparse includes root files)
- OpenZFS mdoc: `sys/contrib/openzfs/man`
- rescue-relevant colocated mdoc under listed `sbin/` / `usr.sbin/` / `stand/man`
- English mdoc under `share/man/man{4,5,7,8}` (not usr.bin toys, except crontab)

## Out (not collected)

- Copyrighted books (Absolute FreeBSD, etc.)
- forums.freebsd.org, Reddit, Stack Overflow
- wiki.freebsd.org (mixed license)
- Whole ports tree / every pkg-descr
- Full `freebsd-src` history or non-sparse tree (too large)
- Translation `*.po` files

## Hawkeye originals

- `playbooks/` emergency procedures (BSD 3-Clause, REVYTECH)
- `docs/` cheat sheets (except TEST-EVIDENCE)
