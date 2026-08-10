#!/usr/bin/env python3
"""
Push-to-talk dictation with faster-whisper.

Usage:
    Hold RIGHT OPTION key -> record
    Release RIGHT OPTION  -> transcribe + paste into focused window
    CTRL+SHIFT+S          -> speak the currently selected response

Works anywhere on macOS: Discord desktop, Telegram desktop, browsers,
Claude, terminal — whatever window is focused when you release the key.

Quit with Ctrl+C in this terminal.
"""
import os
import sys
import threading
import time

import numpy as np
import sounddevice as sd
import AppKit
import pyperclip
from pynput import keyboard
from pynput.keyboard import Controller, Key
from faster_whisper import WhisperModel

from overlay import Overlay
from response_capture import capture_selected_text, capture_ax_app_text, extract_last_response
from voice_output import VoiceOutput



# ---------- Config ----------
MODEL_SIZE   = "small.en"   # tiny.en | base.en | small.en | medium.en
COMPUTE_TYPE = "int8"       # int8 is fast on Apple Silicon CPU
SAMPLE_RATE  = 16000
HOTKEY       = Key.alt_r    # Right Option. Use Key.alt_l for Left Option.
AUTO_PASTE   = True         # If False, text is only copied to clipboard.
LANGUAGE     = "en"         # set to None for autodetect
MIN_SECONDS  = 0.3          # ignore blips shorter than this
SPEAK_HOTKEY = os.getenv("SPEAK_HOTKEY", "<ctrl>+<shift>+s")
# ----------------------------

print(f"Loading faster-whisper model '{MODEL_SIZE}' (compute_type={COMPUTE_TYPE})...")
print("(first run will download the model, ~100-500 MB depending on size)")
model = WhisperModel(MODEL_SIZE, device="cpu", compute_type=COMPUTE_TYPE)
print("Ready. Hold RIGHT OPTION to dictate. Ctrl+C to quit.\n")

kbd = Controller()
overlay = Overlay()
voice_output = VoiceOutput()
print(voice_output.startup_message())
print(f"Select a response and press {SPEAK_HOTKEY} to hear it.\n")

_recording = False
_frames: list = []
_lock = threading.Lock()

# ---------- Armed Response Reader State ----------
_armed_until: float = 0.0
_last_dictated_text: str = ""
_last_seen_clipboard: str = ""
RESPONSE_TIMEOUT_SECONDS = 90.0
# -------------------------------------------------


def _clipboard_watcher():
    """Monitor clipboard for new response text, ONLY while armed after dictation."""
    global _armed_until, _last_seen_clipboard
    try:
        _last_seen_clipboard = pyperclip.paste()
    except Exception:
        _last_seen_clipboard = ""

    while True:
        time.sleep(0.3)
        now = time.time()

        if now > _armed_until:
            continue

        try:
            current = pyperclip.paste()
        except Exception:
            continue

        if current and current != _last_seen_clipboard:
            _last_seen_clipboard = current

            # Ignore if clipboard is identical to the prompt the user just dictated
            if current.strip() == _last_dictated_text.strip():
                continue

            # Ignore temporary selection markers from response_capture
            if "__WHISPER_DICTATE_SELECTION_" in current:
                continue

            # Disarm immediately so subsequent copies are ignored
            _armed_until = 0.0
            print(f"[voice] Response captured from clipboard ({len(current)} chars). Speaking...")
            voice_output.speak(
                current,
                on_start=overlay.show_speaking,
                on_done=overlay.hide,
            )


def _auto_read_worker(app_pid: int, prompt_text: str):
    """Hands-free background worker that watches for the AI response in the target app."""
    global _armed_until

    start_time = time.time()
    last_ax_text = capture_ax_app_text(app_pid) or ""

    # Poll accessibility tree & clipboard for up to 30 seconds
    while time.time() - start_time < 30.0:
        time.sleep(0.5)

        # 1. Try Accessibility API text from the target application window
        ax_text = capture_ax_app_text(app_pid)
        if ax_text and ax_text != last_ax_text and ax_text.strip() != prompt_text.strip():
            clean_response = extract_last_response(ax_text, prompt_text)
            if clean_response:
                print(f"[voice] Hands-free auto-detected response from app ({len(clean_response)} chars). Speaking...")
                _armed_until = 0.0
                voice_output.speak(
                    clean_response,
                    on_start=overlay.show_speaking,
                    on_done=overlay.hide,
                )
                return


        # 2. Check if clipboard received the response automatically
        try:
            clip = pyperclip.paste()
            if (
                clip
                and clip != _last_seen_clipboard
                and clip.strip() != prompt_text.strip()
                and "__WHISPER_DICTATE_SELECTION_" not in clip
            ):
                print(f"[voice] Auto-detected response from clipboard ({len(clip)} chars). Speaking...")
                _armed_until = 0.0
                voice_output.speak(
                    clip,
                    on_start=overlay.show_speaking,
                    on_done=overlay.hide,
                )
                return
        except Exception:
            pass




def audio_callback(indata, frames_count, time_info, status):
    if status:
        # non-fatal stream warnings
        print(f"[audio] {status}", file=sys.stderr)
    if _recording:
        _frames.append(indata.copy())


stream = sd.InputStream(
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype="float32",
    callback=audio_callback,
    blocksize=0,
)
stream.start()


def transcribe_and_paste():
    global _frames, _armed_until, _last_dictated_text, _last_seen_clipboard
    with _lock:
        chunks = _frames
        _frames = []
    if not chunks:
        overlay.hide()
        return
    audio = np.concatenate(chunks, axis=0).flatten().astype(np.float32)
    duration = len(audio) / SAMPLE_RATE
    if duration < MIN_SECONDS:
        print(f"  (too short: {duration:.2f}s — skipped)")
        overlay.hide()
        return
    print(f"  transcribing {duration:.1f}s ...")
    segments, _info = model.transcribe(
        audio,
        language=LANGUAGE,
        beam_size=1,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
    )
    text = " ".join(seg.text.strip() for seg in segments).strip()
    if not text:
        print("  (no speech detected)")
        overlay.hide()
        return
    print(f"  > {text}")
    pyperclip.copy(text)
    if AUTO_PASTE:
        # small delay so modifier key release is registered
        time.sleep(0.08)
        with kbd.pressed(Key.cmd):
            kbd.press("v")
            kbd.release("v")

    # Arm response watcher and launch hands-free auto-read worker
    _last_dictated_text = text
    _last_seen_clipboard = text
    _armed_until = time.time() + RESPONSE_TIMEOUT_SECONDS
    print("  [voice] Dictation finished. Armed for response (watching for reply).")
    overlay.hide()

    try:
        front_app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
        if front_app:
            pid = front_app.processIdentifier()
            threading.Thread(target=_auto_read_worker, args=(pid, text), daemon=True).start()
    except Exception:
        pass




def speak_selected_response():
    """Read the active text selection without permanently changing clipboard."""

    selected = capture_selected_text(kbd)
    if not selected:
        print("[voice] No selected text found. Select the response first.")
        overlay.hide()
        return

    print(f"[voice] speaking selected response ({len(selected)} chars)...")
    accepted = voice_output.speak(
        selected,
        on_start=overlay.show_speaking,
        on_done=overlay.hide,
    )
    if not accepted:
        overlay.hide()


def on_speak_hotkey():
    # Do not block the keyboard listener while copying or generating audio.
    threading.Thread(target=speak_selected_response, daemon=True).start()


def on_press(key):
    global _recording
    if key == HOTKEY:
        # Speaking should stop as soon as the user starts a new dictation.
        voice_output.stop()
        with _lock:
            if _recording:
                return
            _recording = True
            _frames.clear()
        print("● recording...", flush=True)
        overlay.show_recording()


def on_release(key):
    global _recording
    if key == HOTKEY:
        with _lock:
            if not _recording:
                return
            _recording = False
        overlay.show_transcribing()
        threading.Thread(target=transcribe_and_paste, daemon=True).start()


def _listen():
    """Run the keyboard listener (blocks until interrupted)."""
    threading.Thread(target=_clipboard_watcher, daemon=True).start()

    speak_hotkey = keyboard.HotKey(
        keyboard.HotKey.parse(SPEAK_HOTKEY),
        on_speak_hotkey,
    )


    def press(key):
        speak_hotkey.press(listener.canonical(key))
        on_press(key)

    def release(key):
        speak_hotkey.release(listener.canonical(key))
        on_release(key)

    with keyboard.Listener(on_press=press, on_release=release) as listener:
        listener.join()


def main():
    try:
        overlay.run(on_ready=_listen)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass
        voice_output.stop()
        print("\nExiting.")


if __name__ == "__main__":
    main()
