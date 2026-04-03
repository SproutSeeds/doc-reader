# doc-reader

Maintained by SproutSeeds. Research stewardship: Fractal Research Group ([frg.earth](https://frg.earth)).

A local-first streaming document reader for `.pdf`, `.docx`, `.txt`, and `.md` files.

It is designed to start speaking quickly from the first chunk, then keep playback continuous by preparing later chunks in the background.

## Why this exists

- Avoids user-provided ElevenLabs keys.
- Uses local text-to-speech by default (`say` on macOS, with optional `pyttsx3` fallback).
- Reads with understanding in `smart` mode instead of spelling every character.
- Prefetches chunks so playback remains continuous.
- Supports optional ElevenLabs speech output when you want cloud voices.

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies.
3. Run the reader.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m doc_reader /path/to/file.pdf --mode smart --style balanced --verbose
```

## One-command launch

From the repo root:

```bash
./run-doc-reader
```

This command will:

- Create `.venv` if needed
- Install/update dependencies when `requirements.txt` changes
- Launch the menu-bar app

Optional fallback TTS engine:

```bash
./.venv/bin/python -m pip install pyttsx3
```

## ElevenLabs (optional)

CLI with environment variables:

```bash
export ELEVENLABS_API_KEY=\"your_api_key_here\"
export ELEVENLABS_VOICE_ID=\"your_voice_id_here\"
./run-doc-reader --speech-backend elevenlabs
```

CLI with explicit flags:

```bash
./run-doc-reader \
  --speech-backend elevenlabs \
  --elevenlabs-voice-id your_voice_id_here \
  --elevenlabs-model-id eleven_multilingual_v2 \
  --elevenlabs-output-format mp3_44100_128
```

Tray app usage:

- Open the panel from the menu bar icon.
- Set `ELEVENLABS_API_KEY` in your shell/session before launching the tray app.
- Use the single voice dropdown to pick either an OS voice or an ElevenLabs voice.
- Click `Start` (or pick/drop a file to auto-start).

## macOS menu-bar GUI

You can run a top-bar widget (system tray icon on macOS):

```bash
python -m doc_reader.tray
```

What it gives you:

- Click the menu-bar icon to open the reader panel.
- Click `Browse...` for a classic file picker.
- Drag and drop a supported file onto the panel.
- Paste plain text directly into the text box and click `Start`.
- Choose from one voice dropdown with grouped options:
  - `Operating System Voices`
  - `ElevenLabs Voices` (when `ELEVENLABS_API_KEY` is available)
- Enter your ElevenLabs API key in the panel and press Enter:
  - shows a green check on successful validation
  - stores it locally for this computer across restarts
- Built-in library for dropped/browsed files:
  - auto-saves progress while reading
  - shows saved books in a `Library` dropdown
  - click `Resume` to continue from the saved spot
- Chapter jump (best-effort detection):
  - file headings like `Chapter 1`, `Part II`, `Introduction`, etc. are detected
  - pick a chapter in the `Chapter` dropdown, then press `Start` to jump there
  - if already playing, changing chapter jumps playback immediately
- Live current-page indicator for PDFs (`Current page: N`) while speaking.
- Tray playback uses full reading mode (not summary mode) to avoid dropping content.
- Pause/Resume and Library resume use exact chunk-position restart (no content skip; may repeat a little).
- File starts reading immediately after selection or drop.
- Global selection hotkey (macOS): highlight text anywhere and press `Control+Option+Command+R`.
  - This copies the current selection into the paste box and starts reading immediately.
  - First use may prompt for macOS Accessibility/Automation permissions.
- Playback controls:
  - `Start`
  - `Pause` / `Resume`
  - `Back 15s` (approximate rewind)
  - `Stop`

Optional: customize the hotkey before launch with `DOC_READER_SELECTION_SHORTCUT`
(pynput format), for example `export DOC_READER_SELECTION_SHORTCUT='<ctrl>+<alt>+<cmd>+s'`.
The default hotkey remains active as a fallback for context-menu integration.

## Right-click menu (macOS Services)

Install a native `Services` entry so highlighted text can be read from right-click menus:

```bash
./install-context-menu-service
```

Then in any app:

1. Highlight text.
2. Right click.
3. Choose `Services -> Read with Doc Reader`.

This Services flow does not use synthetic keystrokes.

Remove it later with:

```bash
./uninstall-context-menu-service
```

## Auto-start at login (macOS)

Enable startup once:

```bash
./enable-startup
```

This installs a managed startup copy at `~/.doc-reader-managed` and registers a LaunchAgent.
Run `./enable-startup` again after code changes to refresh that managed copy.

Disable later:

```bash
./disable-startup
```

## Modes

- `--mode smart`: Speaks key ideas from each chunk (default).
- `--mode full`: Speaks cleaned source text.

## Detail styles

- `--style concise`: very short key points
- `--style balanced`: moderate detail (default)
- `--style detailed`: more context per chunk

## Continuous playback strategy

Pipeline architecture:

1. Extract text progressively from the input file.
2. Chunk text into early-small then steady-sized segments.
3. Prepare speech-ready narration for each chunk.
4. Queue prepared chunks while the current chunk is being spoken.

The first chunk target is smaller (`--first-chunk-words`) so audio starts quickly; later chunks use `--chunk-words` for steadier flow.

## Useful CLI options

```bash
python -m doc_reader file.docx \
  --mode smart \
  --style detailed \
  --speech-backend auto \
  --rate 190 \
  --voice Samantha \
  --first-chunk-words 95 \
  --chunk-words 240 \
  --queue-size 10
```

Dry-run without speaking:

```bash
python -m doc_reader notes.md --dry-run --verbose
```

## Notes

- `.doc` (legacy Word) is not supported yet; convert to `.docx` first.
- PDF quality depends on extractable text in the file (scanned PDFs need OCR first).

## Contributing

Contributions are welcome. Please see [CONTRIBUTING.md](CONTRIBUTING.md) for setup, PR guidelines, and security reporting.
