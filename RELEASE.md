# Release Checklist

## 0.1.1

`0.1.1` is the first macOS-first native-wrapper release.

## 0.1.2

`0.1.2` improves the install-time error when Apple's Command Line Tools are
missing. Users are told to run `xcode-select --install` and then retry
`read-docs install`.

## 0.2.0

`0.2.0` promotes Doc Reader from a native-wrapper reader into the local-first
DocReader app suite. It adds the canonical local web UI, persistent reading and
dictation cards, pause/resume history, strict private 4090 Kokoro playback,
Mac-local Kokoro fallback, 4090 Whisper dictation, microphone selection,
one-key Option dictation, one-key Right Command selected-text readback, and
managed app/status controls for the installed macOS helper.

## 0.2.1

`0.2.1` cleans up the macOS web-agent restart path so an expected transient
`launchctl bootstrap` retry does not print a scary error when the agent still
starts successfully.

## 0.2.2

`0.2.2` fixes the macOS menu-bar `Resume Web Reading` control so it resumes the
paused web reading card instead of sending another pause request.

## 0.2.3

`0.2.3` makes pause/resume resume inside the current reading chunk instead of
starting that chunk from the beginning. The web reader now persists the current
chunk start position and trims the resumed narration to the approximate paused
word position.

## 0.3.0

`0.3.0` presents Doc Reader as the local GPU speech workspace it has become. It
updates the README animation and package metadata around strict 4090 Kokoro TTS,
4090 Whisper dictation, unified Library cards, local Signal Map analysis, and the
native recording HUD cancel control. OpenAI remains available as an explicit
optional backend instead of the primary operating path.

## 0.3.1

`0.3.1` tightens the README and npm animation so the Mac shortcuts are explicit:
highlighted text plus Right Command triggers Kokoro TTS readback, and holding
ALT for about 1.5 seconds turns on the Whisper STT microphone path. It also
adds spacing around the recording HUD and keeps the local GPU workflow copy
inside the visible cards.

## 0.3.2

`0.3.2` hardens the installed macOS helper and local GPU STT path. The recording
HUD now has an x cancel button that stays above other windows, Esc can cancel a
stuck recording, and stale recordings are surfaced instead of silently latching.
The web app serves Doc Reader favicon, Apple touch icon, and web manifest
metadata for saved web shortcuts. Local 4090 STT is enabled by default, Umbra
preloads Whisper after service start, and interactive dictation uses a faster
single-beam Whisper decode while keeping `large-v3` as the default model.
Selected-text readback also accepts Command-L in addition to the Right Command
gesture and legacy control chords.

## 0.3.3

`0.3.3` fixes strict 4090 Kokoro TTS after the `0.3.2` Whisper preload change.
The Umbra sidecar now preloads Kokoro before Whisper and starts with Torch's CUDA
DLL directory ahead of ctranslate2's bundled cuDNN DLL. This keeps the app on the
strict 4090 Kokoro path while avoiding the Windows CUDA symbol crash that reset
speech requests during Kokoro load.

Before publishing:

```bash
node --check bin/read-docs.js
bash -n build-macos-app enable-startup disable-startup install-context-menu-service uninstall-context-menu-service run-doc-reader read-selection-service.sh
PYTHONPYCACHEPREFIX=/tmp/doc-reader-pyc .venv/bin/python -m compileall doc_reader
./build-macos-app /tmp/doc-reader-native-build
npm pack --dry-run --json
```

Manual checks:

- `read-docs status` reports a native shell path after `read-docs install` or `read-docs restart`.
- LaunchAgent program is `~/Applications/Doc Reader.app/Contents/MacOS/DocReader`.
- The app shows in the menu bar, opens the canonical web page, and does not create a Python Dock tile.
- `~/Applications/Doc Reader.app` is created with the Doc Reader icon, registered with Launch Services, and usable from Applications, Spotlight, and the Dock.
- `read-docs install` and `read-docs restart` start the web app agent as part of the normal app lifecycle.
- `read-docs tailscale` starts the web app agent and exposes `127.0.0.1:8766` on the tailnet.
- `read-docs tts-umbra-install` provisions `DocReaderTTS` on Umbra and reports the RTX 4090 health endpoint.
- The Umbra health endpoint reports `whisper.enabled=true` after `read-docs tts-umbra-install`.
- The web app can enable `Hold Option for 4090 dictation`, and `/api/transcribe` creates a copyable `Dictation` card with no OpenAI key.
- Dictation settings list native macOS input devices, save the selected microphone, and show Microphone, Accessibility, and Input Monitoring permission state.
- The web app detects when the native hotkey helper is offline and can kickstart it without leaving the page.
- Native dictation inserts returned text into the active text field and preserves the clipboard when Accessibility permission is available.
- `read-docs tts-mac-start` provisions the Mac-local Kokoro sidecar and reports the local health endpoint.
- `read-docs tts-bench` writes Chatterbox/Kokoro/macOS speech samples and a benchmark JSON report.
- `Read Clipboard in DocReader`, pause, and stop call the web app instead of a separate native reader.
- Library cards persist across app restarts, and playing one card pauses any active card first.
- Pause and Resume restore the saved chunk for a document or text card.
- Default app playback uses strict private 4090 Kokoro with no API fallback.
- Local fallback mode prefers private 4090 Kokoro, then Mac Kokoro, then 4090 Chatterbox, then macOS system speech.
- Neural sidecar input is cleaned and split before synthesis to keep Markdown-heavy selections from drifting into repeated nonsense.
- OpenAI text-to-speech works only when explicitly selected with an environment, Doc Reader Keychain, or ORP Keychain key.
- The package contains no real API keys or local env files.

Publish:

```bash
npm publish
npm view read-docs version
```

Upgrade path for existing users:

```bash
npm install -g read-docs@latest
read-docs restart
```

Install path for new users:

```bash
npm install -g read-docs
read-docs install
```

Current caveat: the native app is compiled locally during install, so users need
Apple Command Line Tools (`xcode-select --install`). A later release should ship a
signed and notarized prebuilt app bundle.
