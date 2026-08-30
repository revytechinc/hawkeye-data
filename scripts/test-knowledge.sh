#!/bin/sh
# Tiny Tier 0 test: build (or reuse) knowledge.sqlite, FTS-query "zfs readonly",
# assert a playbook hits, and verify the file opens immutable/RO.
# POSIX sh + sqlite3(1).
# Copyright (c) 2026, REVYTECH, Inc.  BSD 3-Clause.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DB=${1:-"$ROOT/share/knowledge.sqlite"}
EVIDENCE=${2:-"$ROOT/docs/TEST-EVIDENCE.md"}

need() {
	command -v "$1" >/dev/null 2>&1 || {
		echo "test-knowledge.sh: missing $1" >&2
		exit 1
	}
}
need sqlite3

if [ ! -f "$DB" ]; then
	sh "$ROOT/scripts/build-knowledge.sh" "$DB"
fi

fail() {
	echo "FAIL: $*" >&2
	exit 1
}

uri_ro="file:${DB}?mode=ro"
uri_imm="file:${DB}?mode=ro&immutable=1"

n=$(sqlite3 "$uri_ro" "SELECT COUNT(*) FROM playbooks_fts WHERE playbooks_fts MATCH 'zfs readonly';")
[ "$n" -ge 1 ] || fail "FTS 'zfs readonly' matched $n playbook rows (want >= 1)"

hits=$(sqlite3 -header -column "$uri_ro" \
	"SELECT p.id, p.title
	 FROM playbooks AS p
	 WHERE p.rowid IN (
	   SELECT rowid FROM playbooks_fts WHERE playbooks_fts MATCH 'zfs readonly'
	 )
	 ORDER BY p.id;")

echo "$hits" | grep -q 'zfs-remount-rw' || fail "expected playbook id zfs-remount-rw in FTS hits"

# Immutable open (no writes, no -wal). Query meta + integrity via RO URI.
meta=$(sqlite3 "$uri_imm" "SELECT key || '=' || value FROM meta ORDER BY key;")
ic=$(sqlite3 "$uri_imm" "PRAGMA integrity_check;")
[ "$ic" = "ok" ] || fail "integrity_check=$ic"

pc=$(sqlite3 "$uri_imm" "SELECT value FROM meta WHERE key='playbook_count';")
[ "$pc" -ge 11 ] || fail "playbook_count=$pc (want >= 11 required emergency playbooks)"

# Confirm embeddings table exists and is empty (optional, not required for Tier 0).
ec=$(sqlite3 "$uri_imm" "SELECT COUNT(*) FROM embeddings;")
[ "$ec" -eq 0 ] || fail "embeddings should be empty in the default kit (got $ec)"

# Confirm WAL is not in use (DELETE journal) so a copy onto /boot is a single file.
jm=$(sqlite3 "$uri_imm" "PRAGMA journal_mode;")
# RO/immutable may report "delete" or the file's mode; accept delete.
case "$jm" in
delete|DELETE) ;;
*) fail "journal_mode=$jm (want delete, for a sidecar-free rescue copy)" ;;
esac

bytes=$(wc -c < "$DB" | tr -d ' ')
now=$(date -u +%Y-%m-%dT%H:%M:%SZ)

{
	echo "# TEST-EVIDENCE"
	echo
	echo "Captured: \`$now\` UTC"
	echo "Database: \`$DB\` ($bytes bytes)"
	echo "Open: \`file:...?...mode=ro&immutable=1\` integrity_check=$ic journal_mode=$jm"
	echo
	echo "## FTS query: \`zfs readonly\`"
	echo
	echo "Matches: $n"
	echo
	echo '```'
	echo "$hits"
	echo '```'
	echo
	echo "## meta"
	echo
	echo '```'
	echo "$meta"
	echo '```'
	echo
	echo "## embeddings"
	echo
	echo "rows=$ec (optional table; empty in the default kit)"
	echo
	echo "## result"
	echo
	echo "PASS: FTS hit at least one playbook (zfs-remount-rw) for \"zfs readonly\"; DB opens immutable/RO."
} > "$EVIDENCE"

echo "PASS: FTS 'zfs readonly' -> $n hit(s)"
echo "evidence: $EVIDENCE"
