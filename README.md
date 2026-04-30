# read-docs

<p align="center">
  <img src="https://raw.githubusercontent.com/SproutSeeds/doc-reader/main/docs/readme-animation.svg" alt="Animated read-docs terminal workflow showing selected text and the Read with Doc Reader service" width="760">
</p>

Maintained by SproutSeeds. Research stewardship: Fractal Research Group ([frg.earth](https://frg.earth)).

A macOS-first, local-first streaming document reader for `.pdf`, `.docx`, `.txt`,
and `.md` files.

It is designed to start speaking quickly from the first chunk, then keep playback continuous by preparing later chunks in the background.

## Why this exists

- Does not ship a shared ElevenLabs key; cloud voices are opt-in per user.
- Uses local text-to-speech by default (`say` on macOS, with optional `pyttsx3` fallback for the CLI).
- Reads with understanding in `smart` mode instead of spelling every character.
- Prefetches chunks so playback remains continuous.
- Supports optional ElevenLabs speech output when you want cloud voices.

## Platform support

The app experience is macOS-first. The menu-bar app, login agent, global selection
hotkey, and right-click Services integration are macOS features.

The document reader engine is still a Python CLI and may work on Linux or Windows
with compatible speech dependencies, but the packaged app workflow is supported on
macOS.

## Quick start: macOS app

Install the npm bootstrapper, then install the managed macOS app agent:

```bash
npm install -g read-docs
read-docs install
read-docs status
```

`read-docs install` copies the runtime into `~/.doc-reader-managed`, prepares its
Python environment, registers a LaunchAgent, starts the menu-bar app, and installs
the `Read with Doc Reader` Services item for highlighted text.

Current native-wrapper builds require Apple's Command Line Tools because the app
bundle is compiled locally during install:

```bash
xcode-select --install
```

Useful app commands:

```bash
read-docs start
read-docs stop
read-docs restart
read-docs status
read-docs uninstall
```

## Quick start: source checkout

1. Create and activate a virtual environment.
2. Install dependencies.
3. Run the reader.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m doc_reader /path/to/file.pdf --mode smart --style balanced --verbose
```

## npm package

This repository is configured for the public npm package `read-docs`.
The unscoped `doc-reader` package name is already owned by another maintainer, so the
official SproutSeeds package uses the available global npm name `read-docs`.

The npm package is a bootstrapper and control surface for the managed app. Running
`read-docs` with no arguments shows the available app and CLI commands; it does not
directly run the Python tray from the package install location.

Install globally:

```bash
npm install -g read-docs
```

Pass a document path to use the command-line reader instead of the menu-bar app:

```bash
read-docs /path/to/file.pdf --mode smart --style balanced --verbose
```

## Development launch

From the repo root:

```bash
./run-doc-reader
```

This command will:

- Create `.venv` if needed
- Install/update dependencies when `requirements.txt` changes
- Launch the menu-bar app directly from the source checkout

Optional fallback TTS engine:

```bash
./.venv/bin/python -m pip install pyttsx3
```

## ElevenLabs (optional)

The package does not include an ElevenLabs API key. For cloud voices, provide your
own key with `ELEVENLABS_API_KEY` or paste it into the tray panel. Keys entered in
the tray are stored only in local OS settings for that computer; clear the field
and press Enter to remove the saved key.

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

App usage:

- Open the panel from the menu bar icon.
- Choose a document, read clipboard text, or paste text into the reader window.
- Open `Settings...` to choose system speech or ElevenLabs.
- Paste an ElevenLabs API key into settings and load voices if you want cloud voices.
- Click `Stop Reading` from the menu bar item to stop active playback.

## macOS menu-bar app

The supported app path is:

```bash
read-docs install
```

For local development, you can also run the Python menu-bar module directly:

```bash
python -m doc_reader.tray
```

What it gives you:

- Native menu-bar app shell (`Doc Reader.app`) instead of a Python Dock app.
- `Open Doc Reader` for pasted text reading.
- `Choose Document...` for `.pdf`, `.docx`, `.txt`, `.md`, and `.markdown`.
- `Read Clipboard` for quick text playback.
- `Stop Reading` for active playback.
- `Settings...` for full/smart mode, system speech, and ElevenLabs voice setup.
- ElevenLabs API keys stored in the macOS Keychain.
- Right-click Services integration for highlighted text.

The older PySide tray module remains in the source tree as a development fallback,
but the npm app path uses the native macOS wrapper.

## Right-click menu (macOS Services)

Install a native `Services` entry so highlighted text can be read from right-click menus:

```bash
read-docs install
```

If the app agent is already installed and you only need to refresh the Services
entry, run `read-docs install-service`.

Then in any app:

1. Highlight text.
2. Right click.
3. Choose `Services -> Read with Doc Reader`.

This Services flow does not use synthetic keystrokes.

Remove it later with:

```bash
read-docs uninstall-service
```

## Auto-start at login (macOS)

The app agent is registered by:

```bash
read-docs install
```

This installs a managed app copy at `~/.doc-reader-managed` and registers a
LaunchAgent. Run `read-docs restart` after package updates to refresh that managed
copy and restart the app.

Disable later:

```bash
read-docs disable-startup
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
