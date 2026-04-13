#!/bin/bash
# One-shot installer for whisper-dictate on macOS (Apple Silicon).
set -e
cd "$(dirname "$0")"

echo "==> Checking Homebrew..."
if ! command -v brew &>/dev/null; then
  echo "Homebrew not found. Install from https://brew.sh and re-run this script."
  exit 1
fi

echo "==> Ensuring portaudio is installed (needed by sounddevice)..."
if ! brew list portaudio &>/dev/null; then
  brew install portaudio
else
  echo "    portaudio already installed."
fi

echo "==> Creating Python venv (.venv)..."
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "==> Upgrading pip..."
pip install --upgrade pip >/dev/null

echo "==> Installing Python dependencies..."
pip install -r requirements.txt

echo
echo "==> Setup complete. Run it with: ./run.sh"
echo "    On first launch macOS will prompt for Microphone and Accessibility permissions."
