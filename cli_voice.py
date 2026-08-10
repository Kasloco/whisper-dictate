#!/usr/bin/env python3
"""
cli_voice.py - Automated Voice Output Wrapper for CLI AI Tools.

Usage:
    python3 cli_voice.py "your-cli-command"

Example:
    python3 cli_voice.py "codex"
    python3 cli_voice.py "ollama run llama3.2"

Runs your interactive CLI session, displays all output on screen, and
automatically speaks every AI response using ElevenLabs!
"""

import sys
import os
import pty
import select
import threading
from voice_output import VoiceOutput, prepare_speech_text

voice_output = VoiceOutput()
print(voice_output.startup_message())


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 cli_voice.py <command>")
        print("Example: python3 cli_voice.py codex")
        sys.exit(1)

    cmd = sys.argv[1]
    print(f"==> Launching CLI with automated ElevenLabs voice output: {cmd}\n")

    master_fd, slave_fd = pty.openpty()
    process = subprocess.Popen(
        cmd,
        shell=True,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
    )
    os.close(slave_fd)

    buffer = []

    def speak_buffer(text_block):
        prepared = prepare_speech_text(text_block)
        if prepared:
            print(f"\n[voice] Speaking CLI response ({len(prepared)} chars)...")
            voice_output.speak(prepared)

    try:
        while process.poll() is None:
            r, _, _ = select.select([master_fd, sys.stdin], [], [], 0.1)
            if master_fd in r:
                try:
                    data = os.read(master_fd, 1024)
                    if not data:
                        break
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                    text = data.decode("utf-8", errors="replace")
                    buffer.append(text)

                    # If a complete line / paragraph ended
                    if "\n\n" in text or "\n" in text:
                        full_chunk = "".join(buffer).strip()
                        if len(full_chunk) > 20:
                            threading.Thread(
                                target=speak_buffer,
                                args=(full_chunk,),
                                daemon=True,
                            ).start()
                            buffer.clear()
                except OSError:
                    break

            if sys.stdin in r:
                try:
                    user_input = os.read(sys.stdin.fileno(), 1024)
                    if not user_input:
                        break
                    os.write(master_fd, user_input)
                    buffer.clear()
                except OSError:
                    break
    except KeyboardInterrupt:
        pass
    finally:
        voice_output.stop()
        print("\nExited CLI voice wrapper.")


if __name__ == "__main__":
    import subprocess
    main()
