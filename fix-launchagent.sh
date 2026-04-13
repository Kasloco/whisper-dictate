#!/bin/bash
# Repair the LaunchAgent: swap in the new plist that uses framework Python
# directly (so Accessibility permissions line up), then reload.
set -e
cd "$(dirname "$0")"

SRC="$(pwd)/com.jonathan.whisperdictate.plist"
DST="$HOME/Library/LaunchAgents/com.jonathan.whisperdictate.plist"

if [ ! -f "$SRC" ]; then
  echo "Cannot find plist at: $SRC"
  exit 1
fi

echo "==> Verifying framework Python exists..."
FRAMEWORK_PY="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13"
if [ ! -x "$FRAMEWORK_PY" ]; then
  echo "Framework Python not found at $FRAMEWORK_PY"
  echo "Looking for alternatives..."
  ls -l /Library/Frameworks/Python.framework/Versions/ 2>/dev/null || true
  which -a python3.13 python3 2>/dev/null || true
  exit 1
fi
echo "    OK: $FRAMEWORK_PY"

echo "==> Clearing old logs so we can see fresh output..."
: > dictate.log
: > dictate.err.log

echo "==> Installing updated plist..."
cp "$SRC" "$DST"
plutil -lint "$DST"

echo "==> Unloading old agent..."
launchctl unload "$DST" 2>/dev/null || true

echo "==> Loading new agent..."
launchctl load -w "$DST"

sleep 2

echo
echo "==> Status:"
launchctl list | grep whisperdictate || echo "    (not running)"
echo
echo "==> Last 10 log lines:"
echo "--- dictate.log ---"
tail -n 10 dictate.log 2>/dev/null || echo "(empty)"
echo "--- dictate.err.log ---"
tail -n 10 dictate.err.log 2>/dev/null || echo "(empty)"
echo
echo "If you see 'Ready. Hold RIGHT OPTION to dictate.' in dictate.log"
echo "and NO 'not trusted' error in dictate.err.log, you're set."
echo "Try dictating into any window to confirm."
