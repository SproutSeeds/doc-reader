# Read Docs Windows signing and verification

Published Windows 0.7.3 at
[GitHub](https://github.com/SproutSeeds/doc-reader/releases/tag/v0.7.3-windows).
The live [download page](https://frg.earth/read-docs) selects the signed Windows
asset, shows per-platform versions and keeps the existing Mac 0.7.2 links. FRG
deployment `dpl_E1b3yZY1CMRYfyX1r58kFqwUZCiu` changes only the Read Docs HTML,
JavaScript and release manifest; all 784 production source references match the
scoped manifest and unrelated route bytes are preserved.
The final Windows 11 installation passes upgrade, uninstall, clean installation,
all 799 installed PE signatures, exact payload hashes, the full EXE lifecycle and
real offline speech. Its default user profile and the pre-existing shared speech
process are unchanged. Read Docs is installed in the per-user Programs folder
with its Start menu shortcut, ready for an interactive setup trial.

The public installer is 1,325,624,920 bytes, SHA-256
`60b2e0de636ec36644b125bc4838993bf9a9d27ed8be1832587ca14423eb7a67`.
An anonymous complete HTTP 200 download and published checksums match the
signature-verified Windows bytes. The first Python streaming attempt timed out;
the complete curl retry succeeded in 17.27 seconds.

Both [tests](https://github.com/SproutSeeds/doc-reader/actions/runs/41916595058)
and the fresh [Windows build](https://github.com/SproutSeeds/doc-reader/actions/runs/41916638117)
pass on source `780e7e1e9c30832ee64c83a97ed59f19f9739adc`. The earlier failed
build `41916356404` exposed the inherited PowerShell module-path issue and is
superseded by this verified build. Mac installers remain on 0.7.2.

Requested November 4, 2026: explain the unsigned Windows download and verify
Windows behavior. The previous release workflow had no signing step or CI signing
credentials. An existing Microsoft Artifact Signing public-trust profile was
active and the authorized Windows host could use it through Azure CLI. No new
subscription, credential, identity validation or role assignment was created.

## Findings and corrections

- The actual installed 0.7.2 EXE started correctly but a restricted system PATH
  prevented process ownership lookup through PowerShell, allowing duplicate
  helpers and preventing owned shutdown. The OS PowerShell path now resolves
  directly. The new installed-EXE smoke verifies launch, duplicate open, saved
  preferences, restart and shutdown with an isolated profile and no developer
  tools on PATH.
- The pinned stripped Python distribution contained four vendor libraries with
  malformed certificate data. Signing refused these files. The builder restores
  the four original files from the matching unstripped archive, verifies its
  pinned SHA-256 and original Microsoft/Python signatures, and preserves them.
  The upstream issue is [python-build-standalone #855](https://github.com/astral-sh/python-build-standalone/issues/855).
- The signing script preserves valid vendor signatures, fails on invalid ones,
  timestamps new signatures and signs the installer, inner setup copies and
  uninstaller through Inno. Unsigned CI artifacts have UNSIGNED in their names.
- PowerShell vendor verification uses its own module defaults, avoiding the
  incompatible PowerShell 7 module path inherited by the Windows CI builder.

## Evidence and limits

The physical host runs Windows 11 Pro 10.0.26200 x64. SSH-driven checks run in
session 0; their native rendering and synthetic audio checks establish no
interactive microphone, loudspeaker, global shortcut, cross-app insertion,
SmartScreen-download UI or sleep/wake acceptance. Those remain user setup checks.
Microphone capture was disabled throughout the automated lifecycle tests.

Pre-signing checks passed 100 Python tests (one Mac-only skip), bundled imports,
FFmpeg/eSpeak and isolated service health, native Qt setup-window rendering,
actual offline Kokoro synthesis and Whisper transcription, and the installed EXE
lifecycle. Local Mac checks passed 100 tests (four Windows-only skips), both Node
process-target tests and npm dry-run packaging. See the final release receipt for
signed installed-byte checks, CI and publication evidence.

The release reuses the previously hash-verified 0.7.2 Windows dependency/model
payload (installer SHA-256 dc256302f354f415019d98091529badc536ec1e4a29f860fde517f2b052f8b6c).
Desktop requirements and models are unchanged. App sources and package metadata
are refreshed, the launcher is recompiled, the four vendor libraries are restored
from the pinned upstream archive, and executable signatures are added. The final
installed runtime is tested again. A fresh CI build independently exercises the
same source and vendor-restoration path.

Raw provider/SSH logs and staging installers stay in the task's ignored release
cache. Public evidence contains hashes, status and the public publisher identity.
Existing Windows shared speech and other Python applications are preserved.

Resume disposition: evidence-only, no canonical or public resume change. This is
release hardening and regression repair for the already recorded standalone
desktop milestone, doc-reader-standalone-2026-11-04-r1. It adds verification to
that work rather than a separate product accomplishment. The website publication
checks the unchanged public resume bytes.

Worktree disposition: checkpoint scoped source and sanitized final receipts.
Retain older reports and icon studies as classified local evidence. Do not sweep
unrelated artifacts into the release commit. Keep this task's logs/cache for
release recovery; preserve the existing user speech service and profile.
