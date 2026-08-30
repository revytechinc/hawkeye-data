# Hawkeye knowledge kit. POSIX make. sqlite3(1) required to rebuild.
# Copyright (c) 2026, REVYTECH, Inc.  BSD 3-Clause.
#
# Two install prefixes:
#   pkg/share  -> $(PREFIX)/share/hawkeye   (default PREFIX=/usr/local)
#   rescue/boot -> /boot/hawkeye            (available when /usr is missing)
#
# Harvest pipeline (official FreeBSD doc, license-clean):
#   make collect   # network: sparse git fetch into cache/
#   make extract   # adoc/mdoc -> corpus/collected
#   make chunk     # content-addressed dist/chunks (GitHub 40MiB)
#   make db        # assemble share/knowledge.sqlite
#   make test
#   make harvest   # collect extract chunk db test

.POSIX:

PREFIX = /usr/local
DESTDIR =
SHAREDIR = $(PREFIX)/share/hawkeye
BOOTDIR = /boot/hawkeye
DB = share/knowledge.sqlite
GITHUB_CHUNK_MAX = 41943040

.PHONY: all db assemble collect extract chunk test harvest clean distclean \
	install install-boot

all: db

collect:
	sh scripts/collect.sh

extract:
	sh scripts/extract.sh

chunk:
	GITHUB_CHUNK_MAX=$(GITHUB_CHUNK_MAX) sh scripts/chunk.sh

# Prefer local corpus (after extract). Else reconstruct from committed chunks.
db:
	@if [ -d corpus/collected ] && [ -n "`find corpus/collected -name '*.md' 2>/dev/null | sed -n 1p`" ]; then \
		sh scripts/build-knowledge.sh $(DB); \
	elif [ -f dist/manifest.json ]; then \
		sh scripts/assemble.sh $(DB); \
	else \
		sh scripts/build-knowledge.sh $(DB); \
	fi

assemble:
	sh scripts/assemble.sh $(DB)

test: db
	sh scripts/test-knowledge.sh $(DB)

harvest: collect extract chunk db test

clean:
	rm -f share/knowledge.sqlite share/knowledge.sqlite-journal \
		share/knowledge.sqlite-wal share/knowledge.sqlite-shm \
		share/knowledge.sqlite.load.sql

distclean: clean
	rm -rf cache corpus/collected

install: db
	mkdir -p $(DESTDIR)$(SHAREDIR)/playbooks \
		$(DESTDIR)$(SHAREDIR)/schema \
		$(DESTDIR)$(SHAREDIR)/docs \
		$(DESTDIR)$(SHAREDIR)/notices \
		$(DESTDIR)$(SHAREDIR)/dist
	cp $(DB) $(DESTDIR)$(SHAREDIR)/knowledge.sqlite
	cp schema/knowledge.sql $(DESTDIR)$(SHAREDIR)/schema/knowledge.sql
	cp README.md $(DESTDIR)$(SHAREDIR)/README.md
	cp SOURCES.md $(DESTDIR)$(SHAREDIR)/SOURCES.md 2>/dev/null || true
	cp playbooks/*.md $(DESTDIR)$(SHAREDIR)/playbooks/
	cp docs/*.md $(DESTDIR)$(SHAREDIR)/docs/
	cp notices/* $(DESTDIR)$(SHAREDIR)/notices/ 2>/dev/null || true
	if [ -f dist/manifest.json ]; then \
		cp dist/manifest.json $(DESTDIR)$(SHAREDIR)/dist/; \
		mkdir -p $(DESTDIR)$(SHAREDIR)/dist/chunks; \
		cp dist/chunks/chunk-* $(DESTDIR)$(SHAREDIR)/dist/chunks/ 2>/dev/null || true; \
	fi

# Compact rescue copy: sqlite + playbook markdown only (no extra docs tree).
install-boot: db
	mkdir -p $(DESTDIR)$(BOOTDIR)/playbooks
	cp $(DB) $(DESTDIR)$(BOOTDIR)/knowledge.sqlite
	cp playbooks/*.md $(DESTDIR)$(BOOTDIR)/playbooks/
	cp README.md $(DESTDIR)$(BOOTDIR)/README.md
