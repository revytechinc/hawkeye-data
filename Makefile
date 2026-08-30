# Hawkeye knowledge kit. POSIX make. sqlite3(1) required to rebuild.
# Copyright (c) 2026, REVYTECH, Inc.  BSD 3-Clause.
#
# Two install prefixes:
#   pkg/share  -> $(PREFIX)/share/hawkeye   (default PREFIX=/usr/local)
#   rescue/boot -> /boot/hawkeye            (available when /usr is missing)

.POSIX:

PREFIX = /usr/local
DESTDIR =
SHAREDIR = $(PREFIX)/share/hawkeye
BOOTDIR = /boot/hawkeye
DB = share/knowledge.sqlite

.PHONY: all db test clean install install-boot

all: db

db:
	mkdir -p share
	sh scripts/build-knowledge.sh $(DB)

test: db
	sh scripts/test-knowledge.sh $(DB)

clean:
	rm -f share/knowledge.sqlite share/knowledge.sqlite-journal \
		share/knowledge.sqlite-wal share/knowledge.sqlite-shm \
		share/knowledge.sqlite.load.sql

install: db
	mkdir -p $(DESTDIR)$(SHAREDIR)/playbooks \
		$(DESTDIR)$(SHAREDIR)/schema \
		$(DESTDIR)$(SHAREDIR)/docs
	cp $(DB) $(DESTDIR)$(SHAREDIR)/knowledge.sqlite
	cp schema/knowledge.sql $(DESTDIR)$(SHAREDIR)/schema/knowledge.sql
	cp README.md $(DESTDIR)$(SHAREDIR)/README.md
	cp playbooks/*.md $(DESTDIR)$(SHAREDIR)/playbooks/
	cp docs/*.md $(DESTDIR)$(SHAREDIR)/docs/

# Compact rescue copy: sqlite + playbook markdown only (no extra docs tree).
install-boot: db
	mkdir -p $(DESTDIR)$(BOOTDIR)/playbooks
	cp $(DB) $(DESTDIR)$(BOOTDIR)/knowledge.sqlite
	cp playbooks/*.md $(DESTDIR)$(BOOTDIR)/playbooks/
	cp README.md $(DESTDIR)$(BOOTDIR)/README.md
