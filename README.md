# whisper-dictate

Universal push-to-talk dictation and response voice for macOS (Apple Silicon).
Local `faster-whisper` handles input; ElevenLabs (with a free macOS fallback)
can read selected assistant responses back to you.

Hold **Right Option**, speak, release — the transcribed text is pasted into
whichever window is focused. Select a response anywhere and press
**Ctrl+Shift+S** to hear it. A floating status pill shows **Recording…**,
**Transcribing…**, or **Speaking…** while the tool works.

Works with Discord desktop, Telegram desktop, Claude, browsers, terminal,
anywhere. No special integration required — just focus the chat and talk.

## One-time install

Clone the repo and run setup:

```bash
git clone https://github.com/Kasloco/whisper-dictate ~/whisper-dictate
cd ~/whisper-dictate
chmod +x setup.sh run.sh whisper-dictate.command
./setup.sh
```

### macOS permissions

On first run, macOS will prompt for two permissions. Grant both in
**System Settings → Privacy & Security**:

1. **Microphone** — required to capture audio.
2. **Accessibility** — required by `pynput` to watch for the Option key and
   simulate the Cmd+V paste. Add **Terminal** (or whatever app you launch
   `run.sh` from) to the Accessibility list.

If you don't grant Accessibility, the script still works but won't auto-paste —
text will only land on your clipboard, and you'll need to press Cmd+V yourself.

## Running it

```bash
./run.sh
```

First launch downloads the `small.en` model (~460 MB). Subsequent launches
are instant.

Usage:

- Focus any text field (Discord message box, Telegram, Claude, etc.)
- **Hold Right Option**, speak
- **Release** — text appears in the field
- Select an assistant response and press **Ctrl+Shift+S** to hear it
- Ctrl+C in the terminal to quit

## Speaking responses

The response feature is intentionally selection-based so it works across apps
without scraping private application APIs. After an assistant responds:

1. Select the response text.
2. Press **Ctrl+Shift+S**.
3. The selection is copied temporarily, sent to ElevenLabs, and then your
   previous clipboard contents are restored.

When no ElevenLabs key is configured, the same workflow uses macOS `say`
locally. When ElevenLabs is configured, the selected text leaves the Mac and
is sent to the ElevenLabs Text to Speech API. The local `voice-usage.log`
contains only provider, model, character count, and timestamp—not response
text.

The output layer can also be used by other integrations:

```bash
python speak_response.py --clipboard
printf '%s' "Response text" | python speak_response.py --stdin
```

### ElevenLabs setup

For a terminal session, set the key directly:

```bash
export ELEVENLABS_API_KEY="your-api-key"
```

You can also copy `.env.example` to `.env` and fill in the values. `.env` is
ignored by Git.

For LaunchAgent or login-started use, store it in the macOS Keychain so it is
available without putting the secret in this repository:

```bash
security add-generic-password \
  -s whisper-dictate-elevenlabs \
  -a "$USER" \
  -w "$ELEVENLABS_API_KEY" \
  -U
```

Optional configuration:

| Setting | Default | Notes |
|---|---|---|
| `ELEVENLABS_VOICE_ID` | `JBFqnCBsd6RMkjVDRZzb` | Set this to a voice from your ElevenLabs library. |
| `ELEVENLABS_MODEL_ID` | `eleven_flash_v2_5` | Fast model suitable for conversational playback. |
| `ELEVENLABS_OUTPUT_FORMAT` | `mp3_44100_128` | Audio format passed to the streaming endpoint. |
| `SPEAK_HOTKEY` | `<ctrl>+<shift>+s` | `pynput` hotkey syntax for reading a selection. |
| `MAX_SPOKEN_CHARS` | `4000` | Bounds accidental long selections and TTS cost. |
| `VOICE_FALLBACK_TO_SAY` | `True` | Use macOS speech if ElevenLabs is unavailable. |

## Configuration

Edit the top of `dictate.py`:

| Setting | Default | Notes |
|---|---|---|
| `MODEL_SIZE` | `small.en` | `tiny.en` (fastest, less accurate), `base.en`, `small.en` (good balance), `medium.en` (slow on CPU) |
| `COMPUTE_TYPE` | `int8` | Fastest on Apple Silicon CPU. Try `int8_float32` if accuracy feels low. |
| `HOTKEY` | `Key.alt_r` | Change to `Key.alt_l` for Left Option, or any other `pynput` key. |
| `AUTO_PASTE` | `True` | Set `False` to only copy to clipboard. |
| `LANGUAGE` | `"en"` | Set to `None` for autodetect (multilingual — requires a non-`.en` model like `small`). |

## Model picks for talking to agents

For openclaw / hermes dictation where you want fast + accurate:

- **`small.en`** — sweet spot on M-series. ~1-2s latency for a normal sentence.
- **`base.en`** — if `small.en` feels slow, drop to this. Slightly worse on
  technical words and names.
- **`medium.en`** — noticeably more accurate on jargon but too slow for
  conversational push-to-talk on CPU.

## Auto-start at login

Double-click `whisper-dictate.command` to run it from Terminal, or add it to
**System Settings → General → Login Items → Open at Login** so it starts
automatically at every login. Terminal already has the necessary Microphone and
Accessibility grants, so it just works.

## Troubleshooting

- **"portaudio.h not found" during pip install** — `brew install portaudio`
  then re-run `./setup.sh`.
- **No paste happens, only clipboard** — Accessibility permission missing.
  System Settings → Privacy & Security → Accessibility → add Terminal.
- **Wrong key triggers it** — `Key.alt_r` on some keyboards maps to a
  different physical key. Run `python -c "from pynput import keyboard; \
  keyboard.Listener(on_press=print).start(); input()"`, press your desired
  key, and copy the reported key constant into `HOTKEY`.
- **Garbled or empty transcripts** — check Input device is the right mic:
  `python -c "import sounddevice as sd; print(sd.query_devices())"`.
