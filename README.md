# whisper-dictate

Universal push-to-talk dictation for macOS (Apple Silicon) using `faster-whisper`.
Hold **Right Option**, speak, release — the transcribed text is pasted into
whichever window is focused. A floating status pill at the top of your screen
shows **Recording…** (red) while you speak and **Transcribing…** (blue) while
the model processes — then disappears once the text is pasted.

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
- Ctrl+C in the terminal to quit

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
