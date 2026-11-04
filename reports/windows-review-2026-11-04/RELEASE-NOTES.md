Read Docs 0.7.3 for Windows adds verified publisher signatures to the installer,
app and executable dependencies. The publisher is FRACTAL RESEARCH GROUP LLC.
The installer also signs its uninstaller and temporary setup components.

This update fixes duplicate helpers and incomplete shutdown when PowerShell is
absent from the command search path. The release checks now launch the actual
installed EXE, reopen it, preserve settings, restart it and stop its services.
The bundled Python runtime retains the original vendor signatures on four
libraries that the upstream stripped distribution had altered.

Windows 11 checks cover installation, upgrade, uninstall, native setup rendering,
offline Kokoro speech and Whisper transcription. Microphone, speaker, global
shortcut and cross-app insertion checks remain part of the hands-on setup trial.
Signed new releases may still receive a SmartScreen reputation warning.

[Download](https://frg.earth/read-docs). Mac downloads remain on the signed,
Apple-notarized [0.7.2 release](https://github.com/SproutSeeds/doc-reader/releases/tag/v0.7.2).
Source and contributor credit remain in the repository; the npm package is unchanged.
