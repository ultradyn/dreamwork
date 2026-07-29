#!/usr/bin/env bash
# Bundled reference — vendored, not authored here. Copied from the
# `subagent-protocols` skill so a dreamwork install carries the monitor
# helper the handshake documents. Upstream source:
# ~/.claude/skills/subagent-protocols/watch-file.sh, sha256
# e4d0f3c09bdb2d8d16c3f25757c05630b79e5224fd9ecb6a3780fde11cf702bf
# (2026-07-29). Re-sync on the docs-freshness rotation if upstream
# changes the script, and bump the sha. Body below is verbatim.
#
# watch-file.sh <file> [grep-extra] — stream each NEW non-blank, non-comment line
# appended to <file>, one per line, for use as a Monitor command:
#     Monitor("watch-file.sh ~/.cache/agent-comms/agent-to-coord.md")
# Each new line becomes a notification. Creates the file if missing so tail won't
# fail, follows across truncation/rotation (-F), and line-buffers so events arrive
# immediately. Skips blank lines and '#' comment/header lines. Runs until killed
# (use as a persistent Monitor; TaskStop to end).
set -u
f="${1:?usage: watch-file.sh <file> [extra-grep-filter]}"
extra="${2:-}"
mkdir -p "$(dirname "$f")" 2>/dev/null || true
[ -e "$f" ] || : > "$f"
if [ -n "$extra" ]; then
  tail -n 0 -F "$f" 2>/dev/null | grep --line-buffered -vE '^[[:space:]]*$|^#' | grep --line-buffered -E "$extra"
else
  tail -n 0 -F "$f" 2>/dev/null | grep --line-buffered -vE '^[[:space:]]*$|^#'
fi
