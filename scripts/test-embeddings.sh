#!/bin/sh
# Red-green: a fake/deterministic embedder must populate embeddings without
# a GGUF, network, or sqlite-vec. Default harvest with no embedder stays
# FTS-only (empty table) and must still pass.
# POSIX sh + sqlite3(1) + python3.
# Copyright (c) 2026, REVYTECH, Inc.  BSD 3-Clause.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
EVIDENCE=${1:-"$ROOT/docs/TEST-EVIDENCE.md"}

need() {
	command -v "$1" >/dev/null 2>&1 || {
		echo "test-embeddings.sh: missing $1" >&2
		exit 1
	}
}
need sqlite3
need python3

fail() {
	echo "FAIL: $*" >&2
	exit 1
}

TMP=$(mktemp -d "${TMPDIR:-/tmp}/hawkeye-embed.XXXXXX")
trap 'rm -rf "$TMP"' EXIT

# Inherit nothing from the operator environment.
unset HAWKEYE_EMBED_FAKE HAWKEYE_EMBED_BIN HAWKEYE_EMBED_MODEL HAWKEYE_LLM_BIN
unset HAWKEYE_EMBED_DOCS

EMPTY="$TMP/empty.sqlite"
FAKE="$TMP/fake.sqlite"
BINDB="$TMP/bin.sqlite"

# --- red case without this feature: builder leaves embeddings empty ---
sh "$ROOT/scripts/build-knowledge.sh" "$EMPTY" >/tmp/hawkeye-embed-empty.log 2>&1 \
	|| fail "default build-knowledge.sh failed (see /tmp/hawkeye-embed-empty.log)"

empty_n=$(sqlite3 "file:${EMPTY}?mode=ro&immutable=1" "SELECT COUNT(*) FROM embeddings;")
[ "$empty_n" -eq 0 ] || fail "default build (no embedder) should leave embeddings empty (got $empty_n)"

empty_fts=$(sqlite3 "file:${EMPTY}?mode=ro" \
	"SELECT COUNT(*) FROM playbooks_fts WHERE playbooks_fts MATCH 'zfs readonly';")
[ "$empty_fts" -ge 1 ] || fail "FTS broken on default (no-embedder) kit"

empty_jm=$(sqlite3 "file:${EMPTY}?mode=ro&immutable=1" "PRAGMA journal_mode;")
case "$empty_jm" in
delete|DELETE) ;;
*) fail "journal_mode=$empty_jm on default kit (want delete)" ;;
esac

# --- green: HAWKEYE_EMBED_FAKE writes stable dim-8 blobs, no GGUF ---
HAWKEYE_EMBED_FAKE=1 sh "$ROOT/scripts/build-knowledge.sh" "$FAKE" \
	>/tmp/hawkeye-embed-fake.log 2>&1 \
	|| fail "HAWKEYE_EMBED_FAKE=1 build failed (see /tmp/hawkeye-embed-fake.log)"

fake_n=$(sqlite3 "file:${FAKE}?mode=ro&immutable=1" "SELECT COUNT(*) FROM embeddings;")
[ "$fake_n" -gt 0 ] || fail "SELECT COUNT(*) FROM embeddings is $fake_n after fake embedder (want > 0)"

missing=$(sqlite3 "file:${FAKE}?mode=ro&immutable=1" \
	"SELECT p.id FROM playbooks AS p
	 LEFT JOIN embeddings AS e
	   ON e.target_table = 'playbooks' AND e.target_id = p.id
	 WHERE e.target_id IS NULL
	 ORDER BY p.id;")
[ -z "$missing" ] || fail "playbook ids missing from embeddings: $missing"

extra_pb=$(sqlite3 "file:${FAKE}?mode=ro&immutable=1" \
	"SELECT e.target_id FROM embeddings AS e
	 LEFT JOIN playbooks AS p ON p.id = e.target_id
	 WHERE e.target_table = 'playbooks' AND p.id IS NULL
	 ORDER BY e.target_id;")
[ -z "$extra_pb" ] || fail "embeddings playbook target_id not in playbooks: $extra_pb"

bad=$(sqlite3 "file:${FAKE}?mode=ro&immutable=1" \
	"SELECT COUNT(*) FROM embeddings
	 WHERE dim <= 0 OR vector IS NULL OR length(vector) = 0;")
[ "$bad" -eq 0 ] || fail "fake embeddings has $bad rows with dim<=0 or empty vector"

fake_dim=$(sqlite3 "file:${FAKE}?mode=ro&immutable=1" \
	"SELECT dim FROM embeddings WHERE target_table='playbooks' LIMIT 1;")
[ "$fake_dim" -gt 0 ] || fail "dim=$fake_dim (want > 0)"

# FLOAT32 blob: 4 bytes per dim
want_bytes=$((fake_dim * 4))
blob_len=$(sqlite3 "file:${FAKE}?mode=ro&immutable=1" \
	"SELECT length(vector) FROM embeddings WHERE target_table='playbooks' LIMIT 1;")
[ "$blob_len" -eq "$want_bytes" ] || \
	fail "vector blob length=$blob_len (want $want_bytes for dim=$fake_dim)"

fake_fts=$(sqlite3 "file:${FAKE}?mode=ro" \
	"SELECT COUNT(*) FROM playbooks_fts WHERE playbooks_fts MATCH 'zfs readonly';")
[ "$fake_fts" -ge 1 ] || fail "FTS broken after fake embed fill"

fake_jm=$(sqlite3 "file:${FAKE}?mode=ro&immutable=1" "PRAGMA journal_mode;")
case "$fake_jm" in
delete|DELETE) ;;
*) fail "journal_mode=$fake_jm after embed fill (want delete, no WAL sidecar)" ;;
esac

# --- assemble.sh path (same finalize hook) ---
ASM="$TMP/assembled.sqlite"
if [ -f "$ROOT/dist/manifest.json" ]; then
	HAWKEYE_EMBED_FAKE=1 sh "$ROOT/scripts/assemble.sh" "$ASM" \
		>/tmp/hawkeye-embed-assemble.log 2>&1 \
		|| fail "HAWKEYE_EMBED_FAKE=1 assemble.sh failed (see /tmp/hawkeye-embed-assemble.log)"
	asm_n=$(sqlite3 "file:${ASM}?mode=ro&immutable=1" "SELECT COUNT(*) FROM embeddings;")
	[ "$asm_n" -gt 0 ] || fail "assemble + fake embedder left embeddings empty"
	asm_missing=$(sqlite3 "file:${ASM}?mode=ro&immutable=1" \
		"SELECT p.id FROM playbooks AS p
		 LEFT JOIN embeddings AS e
		   ON e.target_table = 'playbooks' AND e.target_id = p.id
		 WHERE e.target_id IS NULL;")
	[ -z "$asm_missing" ] || fail "assemble missing playbook embeddings: $asm_missing"
	asm_jm=$(sqlite3 "file:${ASM}?mode=ro&immutable=1" "PRAGMA journal_mode;")
	case "$asm_jm" in
	delete|DELETE) ;;
	*) fail "assemble journal_mode=$asm_jm (want delete)" ;;
	esac
	asm_note="assemble.sh + fake: embeddings=$asm_n journal_mode=$asm_jm"
else
	asm_note="no dist/manifest.json (assemble path not exercised)"
fi

# --- llama.cpp-style BIN+MODEL path, still no GGUF (stub binary) ---
if [ -x "$ROOT/scripts/fake-embedder.py" ] || [ -f "$ROOT/scripts/fake-embedder.py" ]; then
	HAWKEYE_EMBED_BIN="$ROOT/scripts/fake-embedder.py" \
	HAWKEYE_EMBED_MODEL=fake-dim8 \
	HAWKEYE_EMBED_DOCS=0 \
		sh "$ROOT/scripts/build-knowledge.sh" "$BINDB" \
		>/tmp/hawkeye-embed-bin.log 2>&1 \
		|| fail "HAWKEYE_EMBED_BIN stub build failed (see /tmp/hawkeye-embed-bin.log)"
	bin_n=$(sqlite3 "file:${BINDB}?mode=ro&immutable=1" "SELECT COUNT(*) FROM embeddings;")
	[ "$bin_n" -gt 0 ] || fail "BIN+MODEL stub left embeddings empty"
	bin_missing=$(sqlite3 "file:${BINDB}?mode=ro&immutable=1" \
		"SELECT p.id FROM playbooks AS p
		 LEFT JOIN embeddings AS e
		   ON e.target_table = 'playbooks' AND e.target_id = p.id
		 WHERE e.target_id IS NULL;")
	[ -z "$bin_missing" ] || fail "BIN stub missing playbook embeddings: $bin_missing"
	bin_note="BIN+MODEL stub wrote $bin_n rows (playbooks)"
else
	bin_note="no scripts/fake-embedder.py (BIN path not exercised)"
fi

pb_n=$(sqlite3 "file:${FAKE}?mode=ro&immutable=1" \
	"SELECT COUNT(*) FROM embeddings WHERE target_table='playbooks';")
doc_n=$(sqlite3 "file:${FAKE}?mode=ro&immutable=1" \
	"SELECT COUNT(*) FROM embeddings WHERE target_table='documents';")
model=$(sqlite3 "file:${FAKE}?mode=ro&immutable=1" \
	"SELECT model FROM embeddings LIMIT 1;")

now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
{
	echo
	echo "## embeddings fill (fake embedder, no GGUF / no network)"
	echo
	echo "Captured: \`$now\` UTC"
	echo
	echo "- default harvest (no embedder): embeddings=$empty_n (FTS-only, journal_mode=$empty_jm)"
	echo "- HAWKEYE_EMBED_FAKE=1: embeddings=$fake_n (playbooks=$pb_n documents=$doc_n dim=$fake_dim model=\`$model\`)"
	echo "- $asm_note"
	echo "- $bin_note"
	echo
	echo "PASS: fake embedder populated embeddings; playbook ids match; dim>0; vector blob non-empty; FTS intact; journal_mode=DELETE."
} >> "$EVIDENCE"

echo "PASS: default build embeddings=$empty_n (FTS-only)"
echo "PASS: fake embedder embeddings=$fake_n playbooks=$pb_n dim=$fake_dim"
echo "PASS: $bin_note"
