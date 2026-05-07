#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="$HOME/Library/Logs/doc-reader-service.log"

log_event() {
  mkdir -p "$(dirname "$LOG_FILE")"
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')" "$*" >> "$LOG_FILE"
}

is_blank() {
  [[ -z "${1//[[:space:]]/}" ]]
}

post_to_web_app() {
  local selection_text="$1"
  local py="$HOME/.doc-reader-managed/.venv/bin/python"
  if [[ ! -x "$py" ]]; then
    py="$(command -v python3 || true)"
  fi
  if [[ -z "$py" ]]; then
    return 1
  fi

  "$py" - "$selection_text" <<'PY'
import json
import sys
import urllib.error
import urllib.request

text = sys.argv[1]
payload = json.dumps({"label": "Highlighted Text", "text": text}).encode("utf-8")
request = urllib.request.Request(
    "http://127.0.0.1:8766/api/text",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(request, timeout=2.0) as response:
        if response.status < 200 or response.status >= 300:
            raise SystemExit(1)
except (OSError, urllib.error.URLError):
    raise SystemExit(1)
PY
}

capture_frontmost_selection() {
  if [[ "$(uname -s)" != "Darwin" ]] || [[ ! -x /usr/bin/osascript ]]; then
    return 0
  fi

  /usr/bin/osascript 2>/dev/null <<'APPLESCRIPT' || true
set previousClipboard to missing value
set hadPrevious to true
try
    set previousClipboard to the clipboard
on error
    set hadPrevious to false
end try

set marker to "__DOC_READER_NO_SELECTION__" & (random number from 100000 to 999999) as text
set the clipboard to marker

tell application "System Events"
    keystroke "c" using command down
end tell

delay 0.18

set selectedText to ""
try
    set selectedText to the clipboard as text
end try

if hadPrevious then
    set the clipboard to previousClipboard
else
    set the clipboard to ""
end if

if selectedText is marker then
    return ""
end if

return selectedText
APPLESCRIPT
}

selection="$(cat)"
source="service"

copied_selection="$(capture_frontmost_selection)"
if ! is_blank "$copied_selection"; then
  if is_blank "$selection" || [[ "${#copied_selection}" -gt "${#selection}" ]]; then
    selection="$copied_selection"
    source="copy-fallback"
  fi
fi

if is_blank "$selection"; then
  log_event "no usable selected text received"
  exit 0
fi

if post_to_web_app "$selection"; then
  chars="$(printf '%s' "$selection" | wc -c | tr -d '[:space:]')"
  words="$(printf '%s' "$selection" | wc -w | tr -d '[:space:]')"
  log_event "posted selected text to web app source=$source chars=$chars words=$words"
  exit 0
fi

launchctl kickstart "gui/$(id -u)/com.docreader.web" >/dev/null 2>&1 || true
sleep 0.35
if post_to_web_app "$selection"; then
  chars="$(printf '%s' "$selection" | wc -c | tr -d '[:space:]')"
  words="$(printf '%s' "$selection" | wc -w | tr -d '[:space:]')"
  log_event "posted selected text to web app after kickstart source=$source chars=$chars words=$words"
  exit 0
fi

inbox="$HOME/.doc-reader-managed/service-inbox"
mkdir -p "$inbox"

tmp_item="$(mktemp "$inbox/selection.XXXXXX")"
item="$tmp_item.txt"
printf '%s\n' "$selection" > "$tmp_item"
mv "$tmp_item" "$item"
chars="$(printf '%s' "$selection" | wc -c | tr -d '[:space:]')"
words="$(printf '%s' "$selection" | wc -w | tr -d '[:space:]')"
log_event "queued selected text source=$source chars=$chars words=$words item=$(basename "$item")"

# Ensure an installed reader agent gets a chance to consume queue items.
launchctl kickstart "gui/$(id -u)/com.docreader.web" >/dev/null 2>&1 || true
launchctl kickstart "gui/$(id -u)/com.docreader.tray" >/dev/null 2>&1 || true
