# whisper-dictate

Universal push-to-talk dictation for macOS (Apple Silicon) using `faster-whisper`.
Hold **Right Option**, speak, release — the transcribed text is pasted into
whichever window is focused. Works with Discord desktop, Telegram desktop,
Claude, browsers, terminal, anywhere.

## One-time install

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
2. **Accessibility** — required by `pynput` to watch for the Option key and simulate Cmd+V paste. Add **Terminal** to the Accessibility list.

## Running it

```bash
./run.sh
```

First launch downloads the `small.en` model (~460 MB). Subsequent launches are instant.

- Focus any text field
- **Hold Right Option**, speak
- **Release** — text appears in the field
- Ctrl+C to quit

## Auto-start at login

Double-click `whisper-dictate.command`, or add it to
**System Settings → General → Login Items → Open at Login**.

## Configuration

Edit the top of `dictate.py`:

| Setting | Default | Notes |
|---|---|---|
| `MODEL_SIZE` | `small.en` | `tiny.en`, `base.en`, `small.en`, `medium.en` |
| `COMPUTE_TYPE` | `int8` | Fastest on Apple Silicon CPU |
| `HOTKEY` | `Key.alt_r` | Change to `Key.alt_l` for Left Option |
| `AUTO_PASTE` | `True` | Set `False` to only copy to clipboard |
| `LANGUAGE` | `"en"` | Set to `None` for autodetect |

## Troubleshooting

- **"portaudio.h not found"** — `brew install portaudio` then re-run `./setup.sh`
- **No paste, only clipboard** — Accessibility permission missing for Terminal
- **Garbled transcripts** — check mic: `python -c "import sounddevice as sd; print(sd.query_devices())"`
