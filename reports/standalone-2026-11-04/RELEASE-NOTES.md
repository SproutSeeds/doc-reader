Read Docs 0.7.0 opens in its own desktop window on macOS and Windows. The first-run setup guides you through speech readiness, permissions, shortcuts and a short hands-on check.

- Hold Left Option on Mac or Left Alt on Windows to dictate. Tap Right Command or Right Windows to read highlighted text. Setup offers these defaults and keeps existing custom choices until you choose to change them. A fallback is available for keyboards without a right Windows key.
- The installers include Python, the speech runtime, FFmpeg, eSpeak, Kokoro with 28 English voices, and multilingual Whisper. English speech works offline without installing developer tools or downloading models on first launch.
- Mac upgrades load the bundled application code even when an older npm installation exists.
- Shortcut guides remain visible in the workspace. Setup can be resumed or reopened from Settings.
- Normal modifier-key combinations are preserved. Windows selection reading requires a fresh selection rather than reusing old clipboard text.

Download the Apple Silicon or Intel Mac DMG, or the Windows x64 Setup EXE, at https://frg.earth/read-docs. Mac packages are Developer ID signed, notarized and stapled. Windows remains an unsigned preview; Windows may show an unknown-publisher warning.

All three platform builds passed actual offline Kokoro synthesis and Whisper transcription. Verification also covers service startup, packaged Windows window rendering, native Mac window rendering, setup navigation, accessibility and saved preferences. Automated tests do not establish physical microphone, keyboard, permission-prompt or sleep/wake acceptance on every device; the final setup step asks you to try speech and both shortcuts.

Kokoro is Apache-2.0 and Whisper is MIT licensed; model cards, licenses and pinned model revisions are included. The existing npm package remains available as a separate source installation path.
