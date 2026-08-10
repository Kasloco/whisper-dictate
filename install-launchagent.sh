#!/bin/bash
# Install whisper-dictate as a macOS LaunchAgent so it starts at login
# and restarts automatically if it ever crashes.
set -e

PLIST_SRC="$(cd "$(dirname "$0")" && pwd)/com.jonathan.whisperdictate.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.jonathan.whisperdictate.plist"
LABEL="com.jonathan.whisperdictate"

if [ ! -f "$PLIST_SRC" ]; then
  echo "Cannot find $PLIST_SRC"
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents"

# Unload if already loaded, ignore errors
launchctl unload "$PLIST_DST" 2>/dev/null || true

cp "$PLIST_SRC" "$PLIST_DST"
echo "Copied plist to $PLIST_DST"

launchctl load -w "$PLIST_DST"
echo "Loaded LaunchAgent: $LABEL"

sleep 1
if launchctl list | grep -q "$LABEL"; then
  echo
  echo "==> Running. It will now start at every login."
  echo "    Logs:   ~/whisper-dictate/dictate.log"
  echo "            ~/whisper-dictate/dictate.err.log"
  echo
  echo "NOTE: macOS will likely pop up a NEW Accessibility prompt for"
  echo "      the Python binary the first time this runs in the"
  echo "      background, because launchd is a different parent process"
  echo "      than Terminal. Grant it in:"
  echo "      System Settings -> Privacy & Security -> Accessibility"
  echo
  echo "      After granting, restart the agent with:"
  echo "        ./restart-launchagent.sh"
else
  echo "Agent did not appear in launchctl list. Check the logs."
  exit 1
fi
