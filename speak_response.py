#!/usr/bin/env python3
"""Speak response text from a selection, clipboard, argument, or stdin."""

from __future__ import annotations

import argparse
import sys
import threading

import pyperclip

from voice_output import VoiceOutput


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="Text to speak.")
    source.add_argument(
        "--clipboard",
        action="store_true",
        help="Speak the current clipboard contents.",
    )
    source.add_argument(
        "--stdin",
        action="store_true",
        help="Read response text from standard input.",
    )
    args = parser.parse_args()

    if args.text is not None:
        text = args.text
    elif args.clipboard:
        text = pyperclip.paste()
    else:
        text = sys.stdin.read()

    finished = threading.Event()
    voice = VoiceOutput()
    print(voice.startup_message())
    if not voice.speak(text, on_done=finished.set):
        return 1

    try:
        finished.wait()
    except KeyboardInterrupt:
        voice.stop()
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
