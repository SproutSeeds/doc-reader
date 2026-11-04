# Read Docs desktop and first run

The app opens in its own native window, with the existing local workspace inside
WebKit on Mac and Qt WebEngine on Windows. The browser remains an optional source
installation interface. Installed apps carry Python, audio dependencies, Kokoro
English voices and the multilingual Whisper model.

Considered a compact utility panel, a split-pane setup checklist, and a centered
four-step sequence. Chosen: the centered sequence, with a quiet progress rail and
one decision at a time. The reading workspace keeps its generous document canvas.
Type uses the system sans for controls and the existing serif for the main prompt.
Glass groups the keyboard demonstration; ordinary actions remain plain text.

Sequence: speech readiness, permissions, shortcuts, try it. A visible Back control
and Escape return one step. Set up later preserves partial progress. Only a
successful explicit completion marks setup complete. Settings can reopen it.

Recommended shortcuts: hold Left Option/Alt to dictate; tap Right Command/Windows
alone to read highlighted text. Key combinations retain normal behavior. Provide
a conventional alternate shortcut for keyboards without a right Windows key.
Saved custom shortcuts survive upgrades until the user changes them.

Verification must include real native window launches, isolated keyboard-state
tests, keyboard/focus and narrow-window UI checks, and offline speech from bundled
weights. Automated speech and key routing do not establish physical microphone,
speaker, permission-prompt or Windows-device acceptance.
