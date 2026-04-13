#!/bin/bash
# Remove the whisper-dictate LaunchAgent.
set -e
PLIST_DST="$HOME/Library/LaunchAgents/com.jonathan.whisperdictate.plist"

if [ -f "$PLIST_DST" ]; then
  launchctl unload "$PLIST_DST" 2>/dev/null || true
  rm "$PLIST_DST"
  echo "Uninstalled LaunchAgent. whisper-dictate will no longer start at login."
else
  echo "No LaunchAgent installed at $PLIST_DST"
fi
