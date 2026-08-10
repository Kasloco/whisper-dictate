#!/usr/bin/env python3
"""Universal response capture helpers.

The user can select an answer in any accessible macOS application and press
the configured speak hotkey.  This module copies the selection temporarily,
returns its text, and restores the previous clipboard contents afterward.
That makes the feature work across apps without scraping private app APIs.
"""

from __future__ import annotations

import time
import uuid
from typing import Optional

import pyperclip
from pynput.keyboard import Controller, Key


def capture_selected_text(
    keyboard_controller: Controller,
    *,
    release_delay: float = 0.12,
    copy_delay: float = 0.14,
) -> Optional[str]:
    """Copy the active selection, then restore the user's clipboard.

    Returns ``None`` when there is no active text selection or the selected
    application does not expose a readable clipboard value.
    """

    # Give the modifier keys from the global speak shortcut time to release
    # before sending Cmd+C to the focused application.
    time.sleep(release_delay)
    previous_clipboard = pyperclip.paste()
    marker = f"__WHISPER_DICTATE_SELECTION_{uuid.uuid4().hex}__"
    selected = ""

    try:
        pyperclip.copy(marker)
        with keyboard_controller.pressed(Key.cmd):
            keyboard_controller.press("c")
            keyboard_controller.release("c")
        time.sleep(copy_delay)
        selected = pyperclip.paste()
    finally:
        pyperclip.copy(previous_clipboard)

    if not selected or selected == marker or not selected.strip():
        return None
    return selected


def capture_ax_app_text(pid: int) -> Optional[str]:
    """Extract text from the given process using macOS Accessibility APIs."""
    try:
        import ApplicationServices  # type: ignore

        ax_app = ApplicationServices.AXUIElementCreateApplication(pid)

        def _get_attr(el, attr):
            err, val = ApplicationServices.AXUIElementCopyAttributeValue(
                el, attr, None,
            )
            return val if err == 0 else None

        # Check focused UI element first
        focused = _get_attr(ax_app, "AXFocusedUIElement")
        if focused:
            val = _get_attr(focused, "AXValue")
            if val and isinstance(val, str) and val.strip():
                return val.strip()

        # Fallback to main window
        win = _get_attr(ax_app, "AXMainWindow")
        if win:
            val = _get_attr(win, "AXValue")
            if val and isinstance(val, str) and val.strip():
                return val.strip()
    except Exception:
        pass
    return None

