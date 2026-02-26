#!/usr/bin/env bash
set -euo pipefail

selection="$(cat)"

if [[ -z "${selection//[[:space:]]/}" ]]; then
  exit 0
fi

inbox="$HOME/.doc-reader-managed/service-inbox"
mkdir -p "$inbox"

item="$(mktemp "$inbox/selection.XXXXXX.txt")"
printf '%s\n' "$selection" > "$item"

# Ensure the tray agent is started (if installed) so it can consume queue items.
launchctl kickstart "gui/$(id -u)/com.docreader.tray" >/dev/null 2>&1 || true
