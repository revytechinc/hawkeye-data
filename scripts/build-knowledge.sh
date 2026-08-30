#!/bin/sh
# Build knowledge.sqlite from markdown sources.
# POSIX sh + sqlite3(1). No Python, no Go.
# Copyright (c) 2026, REVYTECH, Inc.  BSD 3-Clause.
set -eu

usage() {
	echo "usage: build-knowledge.sh [output.sqlite]" >&2
	exit 2
}

[ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ] && usage

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OUT=${1:-"$ROOT/share/knowledge.sqlite"}
SCHEMA="$ROOT/schema/knowledge.sql"
PLAYBOOKS="$ROOT/playbooks"
DOCS="$ROOT/docs"

need() {
	command -v "$1" >/dev/null 2>&1 || {
		echo "build-knowledge.sh: missing required command: $1" >&2
		exit 1
	}
}
need sqlite3
need awk
need sed
need date

if [ ! -f "$SCHEMA" ]; then
	echo "build-knowledge.sh: schema not found: $SCHEMA" >&2
	exit 1
fi

sql_quote() {
	# stdin -> SQL string literal (including surrounding quotes)
	printf "'"
	sed "s/'/''/g"
	printf "'"
}

yn_to_int() {
	case "${1:-}" in
	yes|true|True|YES|Y|1) printf '1' ;;
	*) printf '0' ;;
	esac
}

json_bool() {
	if [ "$1" -eq 1 ]; then
		printf 'true'
	else
		printf 'false'
	fi
}

# First YAML front-matter scalar: "key: rest of line"
fm_get() {
	_file=$1
	_key=$2
	awk -v key="$_key" '
		BEGIN { in_fm = 0 }
		NR == 1 && $0 == "---" { in_fm = 1; next }
		in_fm && $0 == "---" { exit }
		in_fm {
			p = key ":"
			if ($0 == p) { exit }
			if (index($0, p) == 1) {
				rest = substr($0, length(p) + 1)
				sub(/^[[:space:]]+/, "", rest)
				print rest
				exit
			}
		}
	' "$_file"
}

body_get() {
	awk '
		BEGIN { n = 0 }
		$0 == "---" { n++; next }
		n >= 2 { print }
	' "$1"
}

# JSON array of command lines from the first fenced block after "## Commands".
commands_json() {
	awk '
		BEGIN { in_cmd = 0; want = 0; first = 1; printf "[" }
		/^##[ \t]*Commands/ { want = 1; next }
		want && /^```/ {
			if (in_cmd) { in_cmd = 0; want = 0; next }
			in_cmd = 1
			next
		}
		in_cmd {
			line = $0
			if (line == "") next
			gsub(/\\/, "\\\\", line)
			gsub(/"/, "\\\"", line)
			gsub(/\t/, "\\t", line)
			if (!first) printf ","
			first = 0
			printf "\"%s\"", line
		}
		END { printf "]" }
	' "$1"
}

mkdir -p "$(dirname -- "$OUT")"
rm -f "$OUT" "$OUT-journal" "$OUT-wal" "$OUT-shm"

sqlite3 "$OUT" < "$SCHEMA"

load_sql="$OUT.load.sql"
: > "$load_sql"

n_play=0
for f in "$PLAYBOOKS"/*.md; do
	[ -f "$f" ] || continue
	id=$(fm_get "$f" id)
	title=$(fm_get "$f" title)
	when=$(fm_get "$f" when_to_use)
	rollback=$(fm_get "$f" rollback_notes)
	danger=$(fm_get "$f" danger_flags)
	pre=$(fm_get "$f" preconditions)
	rw=$(yn_to_int "$(fm_get "$f" requires_rw)")
	net=$(yn_to_int "$(fm_get "$f" requires_net)")
	zfs=$(yn_to_int "$(fm_get "$f" requires_zfs)")
	ufs=$(yn_to_int "$(fm_get "$f" requires_ufs)")
	if [ -z "$id" ] || [ -z "$title" ] || [ -z "$when" ]; then
		echo "build-knowledge.sh: $f needs id, title, when_to_use" >&2
		exit 1
	fi
	[ -n "$danger" ] || danger='[]'
	[ -n "$rollback" ] || rollback=''
	cmds=$(commands_json "$f")
	if [ -z "$pre" ]; then
		pre=$(printf '{"rw":%s,"net":%s,"zfs":%s,"ufs":%s}' \
			"$(json_bool "$rw")" "$(json_bool "$net")" \
			"$(json_bool "$zfs")" "$(json_bool "$ufs")")
	fi
	rel="playbooks/$(basename -- "$f")"
	{
		printf "INSERT INTO playbooks (id, title, when_to_use, preconditions, commands, danger_flags, rollback_notes, body, requires_rw, requires_net, requires_zfs, requires_ufs, path) VALUES ("
		printf '%s' "$id" | sql_quote
		printf ', '
		printf '%s' "$title" | sql_quote
		printf ', '
		printf '%s' "$when" | sql_quote
		printf ', '
		printf '%s' "$pre" | sql_quote
		printf ', '
		printf '%s' "$cmds" | sql_quote
		printf ', '
		printf '%s' "$danger" | sql_quote
		printf ', '
		printf '%s' "$rollback" | sql_quote
		printf ', '
		body_get "$f" | sql_quote
		printf ', %s, %s, %s, %s, ' "$rw" "$net" "$zfs" "$ufs"
		printf '%s' "$rel" | sql_quote
		printf ");\n"
	} >> "$load_sql"
	n_play=$((n_play + 1))
done

n_doc=0
for f in "$DOCS"/*.md; do
	[ -f "$f" ] || continue
	base=$(basename -- "$f")
	case "$base" in
	TEST-EVIDENCE.md|test-evidence.md) continue ;;
	esac
	id=$(fm_get "$f" id)
	title=$(fm_get "$f" title)
	category=$(fm_get "$f" category)
	if [ -z "$id" ] || [ -z "$title" ]; then
		echo "build-knowledge.sh: skip (no front matter): $rel" >&2
		# Allow schema.md etc. without front matter by synthesizing.
		id=$(printf '%s' "$base" | sed 's/\.md$//')
		title=$id
		category=${category:-docs}
		rel="docs/$base"
		{
			printf "INSERT INTO documents (id, title, category, path, body) VALUES ("
			printf '%s' "$id" | sql_quote
			printf ', '
			printf '%s' "$title" | sql_quote
			printf ', '
			printf '%s' "$category" | sql_quote
			printf ', '
			printf '%s' "$rel" | sql_quote
			printf ', '
			# whole file is the body when there is no front matter
			sql_quote < "$f"
			printf ");\n"
		} >> "$load_sql"
		n_doc=$((n_doc + 1))
		continue
	fi
	[ -n "$category" ] || category=docs
	rel="docs/$base"
	{
		printf "INSERT INTO documents (id, title, category, path, body) VALUES ("
		printf '%s' "$id" | sql_quote
		printf ', '
		printf '%s' "$title" | sql_quote
		printf ', '
		printf '%s' "$category" | sql_quote
		printf ', '
		printf '%s' "$rel" | sql_quote
		printf ', '
		body_get "$f" | sql_quote
		printf ");\n"
	} >> "$load_sql"
	n_doc=$((n_doc + 1))
done

if [ "$n_play" -lt 1 ]; then
	echo "build-knowledge.sh: no playbooks found in $PLAYBOOKS" >&2
	exit 1
fi

sqlite3 "$OUT" < "$load_sql"

# Rebuild FTS from external content, then freeze the file for RO/immutable.
built=${SOURCE_DATE_EPOCH:-}
if [ -n "$built" ]; then
	built=$(date -u -d "@$built" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)
else
	built=$(date -u +%Y-%m-%dT%H:%M:%SZ)
fi

sqlite3 "$OUT" <<SQL
INSERT INTO playbooks_fts(rowid, title, when_to_use, body, commands, danger_flags)
  SELECT rowid, title, when_to_use, body, commands, danger_flags FROM playbooks;
INSERT INTO documents_fts(rowid, title, category, body)
  SELECT rowid, title, category, body FROM documents;
INSERT INTO meta(key, value) VALUES
  ('schema_version', '1'),
  ('corpus_id', 'hawkeye-data'),
  ('built_at', '$(printf '%s' "$built")'),
  ('playbook_count', '$(printf '%s' "$n_play")'),
  ('document_count', '$(printf '%s' "$n_doc")'),
  ('fts', 'mandatory'),
  ('embeddings', 'optional-empty');
INSERT INTO playbooks_fts(playbooks_fts) VALUES('optimize');
INSERT INTO documents_fts(documents_fts) VALUES('optimize');
PRAGMA journal_mode = DELETE;
VACUUM;
PRAGMA integrity_check;
SQL

rm -f "$load_sql"

echo "built $OUT ($n_play playbooks, $n_doc documents)"
