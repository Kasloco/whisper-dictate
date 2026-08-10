#!/usr/bin/env python3
"""ElevenLabs voice output for whisper-dictate.

This module deliberately has no dependency on the transcription model.  It
accepts response text, turns it into audio with ElevenLabs, and plays the
result through macOS.  If ElevenLabs is not configured (or the request fails),
macOS ``say`` is used as a local fallback.

API keys are read from ``ELEVENLABS_API_KEY`` first and then from the macOS
Keychain service ``whisper-dictate-elevenlabs``.  No response text is written
to the usage log; only provider, model, character count, and timestamp are
recorded.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"
KEYCHAIN_SERVICE = "whisper-dictate-elevenlabs"
DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"
DEFAULT_MODEL_ID = "eleven_flash_v2_5"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"
DEFAULT_MAX_CHARS = 4000


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _load_local_env() -> None:
    """Load simple KEY=value pairs without adding a dotenv dependency."""

    env_path = Path(__file__).with_name(".env")
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def prepare_speech_text(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """Make selected assistant text pleasant and bounded for speech.

    Markdown decoration and fenced code are generally poor speech input.  A
    hard character cap prevents an accidentally selected document from
    creating an unexpectedly large TTS request.
    """

    text = text.strip()
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_~]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text

    clipped = text[:max_chars].rsplit(" ", 1)[0].rstrip(" ,;:")
    return f"{clipped} … response truncated"


def _keychain_api_key() -> Optional[str]:
    """Read the optional API key from the logged-in user's macOS Keychain."""

    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


class VoiceOutput:
    """Generate and play one response at a time, with cancellation support."""

    def __init__(self) -> None:
        _load_local_env()
        self.api_key = os.getenv("ELEVENLABS_API_KEY", "").strip() or _keychain_api_key()
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID).strip()
        self.model_id = os.getenv("ELEVENLABS_MODEL_ID", DEFAULT_MODEL_ID).strip()
        self.output_format = os.getenv(
            "ELEVENLABS_OUTPUT_FORMAT", DEFAULT_OUTPUT_FORMAT,
        ).strip()
        self.max_chars = _env_int("MAX_SPOKEN_CHARS", DEFAULT_MAX_CHARS)
        self.fallback_to_say = _env_bool("VOICE_FALLBACK_TO_SAY", True)
        try:
            timeout_seconds = float(os.getenv("ELEVENLABS_TIMEOUT_SECONDS", "60"))
        except ValueError:
            timeout_seconds = 60.0
        self.timeout_seconds = max(10.0, timeout_seconds)
        self.usage_log = Path(__file__).with_name("voice-usage.log")

        self._lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._active_process: Optional[subprocess.Popen] = None
        self._active_response = None

    @property
    def provider_name(self) -> str:
        return "ElevenLabs" if self.api_key else "macOS say"

    def startup_message(self) -> str:
        if self.api_key:
            return (
                "Voice output: ElevenLabs enabled "
                f"(model={self.model_id}, voice={self.voice_id})."
            )
        return "Voice output: ElevenLabs key not found; using macOS say fallback."

    def stop(self) -> None:
        """Cancel an in-flight request and stop currently playing audio."""

        with self._lock:
            self._cancel_event.set()
            process = self._active_process
            response = self._active_response
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass
        if response is not None:
            try:
                response.close()
            except OSError:
                pass

    def speak(
        self,
        text: str,
        *,
        on_start: Optional[Callable[[], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
    ) -> bool:
        """Speak text asynchronously and return whether it was accepted."""

        prepared = prepare_speech_text(text, self.max_chars)
        if not prepared:
            print("[voice] Nothing to speak.")
            return False

        self.stop()
        cancel_event = threading.Event()
        with self._lock:
            self._cancel_event = cancel_event

        if on_start is not None:
            on_start()

        threading.Thread(
            target=self._speak_worker,
            args=(prepared, cancel_event, on_done),
            daemon=True,
        ).start()
        return True

    def _speak_worker(
        self,
        text: str,
        cancel_event: threading.Event,
        on_done: Optional[Callable[[], None]],
    ) -> None:
        temp_path: Optional[str] = None
        try:
            if self.api_key:
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as audio:
                    temp_path = audio.name
                self._download_elevenlabs(text, temp_path, cancel_event)
                if not cancel_event.is_set():
                    self._record_usage("elevenlabs", text)
                    self._play_file(temp_path, cancel_event)
            elif self.fallback_to_say:
                self._speak_with_macos(text, cancel_event)
                self._record_usage("macos-say", text)
            else:
                print(
                    "[voice] Set ELEVENLABS_API_KEY or enable "
                    "VOICE_FALLBACK_TO_SAY.",
                )
        except (HTTPError, URLError, OSError, RuntimeError, ValueError) as exc:
            if cancel_event.is_set():
                return
            print(f"[voice] ElevenLabs unavailable: {exc}")
            if self.fallback_to_say:
                try:
                    self._speak_with_macos(text, cancel_event)
                    self._record_usage("macos-say-fallback", text)
                except (OSError, RuntimeError) as fallback_exc:
                    print(f"[voice] macOS fallback unavailable: {fallback_exc}")
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except FileNotFoundError:
                    pass
            if on_done is not None and not cancel_event.is_set():
                on_done()

    def _download_elevenlabs(
        self,
        text: str,
        destination: str,
        cancel_event: threading.Event,
    ) -> None:
        voice_id = quote(self.voice_id, safe="")
        output_format = quote(self.output_format, safe="")
        url = (
            f"{ELEVENLABS_API_URL}/{voice_id}/stream"
            f"?output_format={output_format}"
        )
        payload = json.dumps({"text": text, "model_id": self.model_id}).encode("utf-8")
        request = Request(
            url,
            data=payload,
            headers={
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.api_key or "",
            },
            method="POST",
        )

        try:
            response_context = urlopen(request, timeout=self.timeout_seconds)
        except HTTPError as exc:
            detail = exc.read(400).decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(str(exc.reason)) from exc

        with self._lock:
            self._active_response = response_context
        try:
            with response_context as response, open(destination, "wb") as audio:
                while not cancel_event.is_set():
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    audio.write(chunk)
        finally:
            with self._lock:
                if self._active_response is response_context:
                    self._active_response = None

    def _play_file(self, path: str, cancel_event: threading.Event) -> None:
        process = subprocess.Popen(
            ["afplay", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        with self._lock:
            self._active_process = process
        try:
            process.wait()
            if process.returncode != 0 and not cancel_event.is_set():
                detail = (process.stderr.read() if process.stderr else "").strip()
                raise RuntimeError(detail or "afplay failed")
        finally:
            with self._lock:
                if self._active_process is process:
                    self._active_process = None

    def _speak_with_macos(
        self,
        text: str,
        cancel_event: threading.Event,
    ) -> None:
        if cancel_event.is_set():
            return
        process = subprocess.Popen(
            ["say", text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        with self._lock:
            self._active_process = process
        try:
            process.wait()
            if process.returncode != 0 and not cancel_event.is_set():
                detail = (process.stderr.read() if process.stderr else "").strip()
                raise RuntimeError(detail or "say failed")
        finally:
            with self._lock:
                if self._active_process is process:
                    self._active_process = None

    def _record_usage(self, provider: str, text: str) -> None:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "model": self.model_id if provider == "elevenlabs" else None,
            "characters": len(text),
        }
        try:
            with self.usage_log.open("a", encoding="utf-8") as log:
                log.write(json.dumps(event) + "\n")
        except OSError as exc:
            print(f"[voice] Could not write usage log: {exc}")
