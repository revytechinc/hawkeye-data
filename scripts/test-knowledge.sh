#!/bin/sh
# Tier 0 tests: FTS "zfs readonly" hits playbook zfs-remount-rw;
# after harvest, FTS also hits handbook (ZFS / jails);
# chunk.sh is idempotent; manifest lists sha256 + sizes.
# POSIX sh + sqlite3(1) + python3.
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

meta=$(sqlite3 "$uri_imm" "SELECT key || '=' || value FROM meta ORDER BY key;")
ic=$(sqlite3 "$uri_imm" "PRAGMA integrity_check;")
[ "$ic" = "ok" ] || fail "integrity_check=$ic"

uv=$(sqlite3 "$uri_imm" "PRAGMA user_version;")
[ "$uv" -ge 1 ] || fail "user_version=$uv"

pc=$(sqlite3 "$uri_imm" "SELECT value FROM meta WHERE key='playbook_count';")
[ "$pc" -ge 11 ] || fail "playbook_count=$pc (want >= 11 required emergency playbooks)"

ec=$(sqlite3 "$uri_imm" "SELECT COUNT(*) FROM embeddings;")
[ "$ec" -eq 0 ] || fail "embeddings should be empty in the default kit (got $ec)"

jm=$(sqlite3 "$uri_imm" "PRAGMA journal_mode;")
case "$jm" in
delete|DELETE) ;;
*) fail "journal_mode=$jm (want delete, for a sidecar-free rescue copy)" ;;
esac

# Handbook / collected FreeBSD docs (present after harvest).
hb_n=0
hb_hits=""
jail_n=0
jail_hits=""
if sqlite3 "$uri_ro" "SELECT COUNT(*) FROM documents WHERE category LIKE 'freebsd-%';" | grep -vq '^0$'; then
	hb_n=$(sqlite3 "$uri_ro" "SELECT COUNT(*) FROM documents_fts WHERE documents_fts MATCH 'ZFS';")
	[ "$hb_n" -ge 1 ] || fail "harvested corpus present but FTS 'ZFS' matched $hb_n document rows"
	hb_hits=$(sqlite3 -header -column "$uri_ro" \
		"SELECT d.id, d.category, d.title
		 FROM documents AS d
		 WHERE d.rowid IN (
		   SELECT rowid FROM documents_fts WHERE documents_fts MATCH 'ZFS'
		 )
		 ORDER BY d.category, d.id
		 LIMIT 12;")
	echo "$hb_hits" | grep -qi 'handbook\|man8\|freebsd' || \
		fail "expected a handbook or man page among FTS 'ZFS' document hits"
	jail_n=$(sqlite3 "$uri_ro" "SELECT COUNT(*) FROM documents_fts WHERE documents_fts MATCH 'jails';")
	jail_hits=$(sqlite3 -header -column "$uri_ro" \
		"SELECT d.id, d.category, d.title
		 FROM documents AS d
		 WHERE d.rowid IN (
		   SELECT rowid FROM documents_fts WHERE documents_fts MATCH 'jails'
		 )
		 ORDER BY d.category, d.id
		 LIMIT 8;")
fi

# Chunk manifest + idempotency.
chunk_note="no dist/manifest.json (playbooks-only kit)"
if [ -f "$ROOT/dist/manifest.json" ]; then
	need python3
	chunk_note=$(python3 - "$ROOT" << 'PY'
import json, hashlib, gzip, sys
from pathlib import Path
root = Path(sys.argv[1])
man = json.loads((root / "dist" / "manifest.json").read_text(encoding="utf-8"))
chunks = man.get("chunks") or []
if not chunks:
    print("FAIL: manifest has no chunks")
    sys.exit(1)
bad = []
for c in chunks:
    for k in ("id", "path", "sha256", "bytes"):
        if k not in c:
            bad.append(f"{c.get('id')}: missing {k}")
    p = root / c["path"]
    if not p.is_file():
        bad.append(f"{c.get('id')}: missing file {p}")
        continue
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    if h != c["sha256"]:
        bad.append(f"{c.get('id')}: sha256 mismatch file={h} manifest={c['sha256']}")
    n = p.stat().st_size
    if n != int(c["bytes"]):
        bad.append(f"{c.get('id')}: size mismatch file={n} manifest={c['bytes']}")
    if n >= 94371840:
        bad.append(f"{c.get('id')}: file {n} bytes >= 90MB hard fail")
if bad:
    print("FAIL: " + "; ".join(bad))
    sys.exit(1)
print(f"manifest ok: {len(chunks)} chunks, sha256+bytes verified")
PY
)
	# Idempotency: second chunk.sh must not change chunk file hashes.
	before=$(python3 -c "import json,pathlib; m=json.loads(pathlib.Path('$ROOT/dist/manifest.json').read_text()); print({c['id']:c['sha256'] for c in m['chunks']})")
	sh "$ROOT/scripts/chunk.sh" >/tmp/hawkeye-chunk-idempotent.log 2>&1 || fail "chunk.sh second run failed"
	after=$(python3 -c "import json,pathlib; m=json.loads(pathlib.Path('$ROOT/dist/manifest.json').read_text()); print({c['id']:c['sha256'] for c in m['chunks']})")
	[ "$before" = "$after" ] || fail "chunk.sh not idempotent: sha256s changed with unchanged sources"
	chunk_note="$chunk_note; second run sha256s unchanged"
fi

bytes=$(wc -c < "$DB" | tr -d ' ')
now=$(date -u +%Y-%m-%dT%H:%M:%SZ)

{
	echo "# TEST-EVIDENCE"
	echo
	echo "Captured: \`$now\` UTC"
	echo "Database: \`$DB\` ($bytes bytes)"
	echo "Open: \`file:...?...mode=ro&immutable=1\` integrity_check=$ic journal_mode=$jm user_version=$uv"
	echo
	echo "## FTS query: \`zfs readonly\` (playbooks)"
	echo
	echo "Matches: $n"
	echo
	echo '```'
	echo "$hits"
	echo '```'
	echo
	echo "## FTS query: \`ZFS\` (documents, after harvest)"
	echo
	echo "Matches: $hb_n"
	echo
	if [ -n "$hb_hits" ]; then
		echo '```'
		echo "$hb_hits"
		echo '```'
		echo
	fi
	echo "## FTS query: \`jails\` (documents, after harvest)"
	echo
	echo "Matches: $jail_n"
	echo
	if [ -n "$jail_hits" ]; then
		echo '```'
		echo "$jail_hits"
		echo '```'
		echo
	fi
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
	echo "## chunks"
	echo
	echo "$chunk_note"
	echo
	echo "## result"
	echo
	if [ "$hb_n" -ge 1 ]; then
		echo "PASS: FTS hit playbook zfs-remount-rw for \"zfs readonly\"; FTS also hit harvested FreeBSD docs for \"ZFS\"; DB opens immutable/RO."
	else
		echo "PASS: FTS hit at least one playbook (zfs-remount-rw) for \"zfs readonly\"; DB opens immutable/RO. (No harvested freebsd-* documents in this DB.)"
	fi
} > "$EVIDENCE"

echo "PASS: FTS 'zfs readonly' -> $n hit(s)"
if [ "$hb_n" -ge 1 ]; then
	echo "PASS: FTS 'ZFS' documents -> $hb_n hit(s)"
fi
echo "evidence: $EVIDENCE"
