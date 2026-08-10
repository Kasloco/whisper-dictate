#!/bin/bash
# Quickly restart the whisper-dictate LaunchAgent (after granting permissions
# or editing dictate.py).
set -e
PLIST_DST="$HOME/Library/LaunchAgents/com.jonathan.whisperdictate.plist"
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load   -w "$PLIST_DST"
echo "Restarted. Tail logs with:"
echo "  tail -f ~/whisper-dictate/dictate.log ~/whisper-dictate/dictate.err.log"
