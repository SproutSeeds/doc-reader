# Read Docs 0.6.2 app refinement

The shared Mac/Windows web workspace now uses a centered reading canvas,
on-demand Library/Import/Voice/Speed/Settings dialogs and one glass playback bar.
Text controls replace decorative icons and arrows. Settings retains dictation,
shortcuts, microphone selection, speech status and library analysis. Existing
storage keys, model choices, data paths and API routes are retained.

## Verification

- 92 Python tests passed with four platform-specific skips.
- Native capture and selected-text readback regression checks passed, including
  full 156,393-character capture, clipboard preservation and cancellation.
- Mac native wrapper compiled and signed locally for compilation validation.
- Two Node process-target tests passed; CLI syntax and npm package dry run passed.
- `tests/workspace-browser.mjs` passed against the temporary-library server in
  `tests/serve_workspace_preview.py`: draft reload, saved editing, imports,
  keyboard filters, modal dismissal/focus, voice preview cleanup, speed changes,
  request-error recovery and playback transitions. Seven size/theme variants
  cover 320–1920 px and a short landscape window; screenshots were inspected.
- Axe WCAG A/AA checks passed on the canvas, all five panels and dark canvas.
  This automated audit does not establish full assistive-technology acceptance.

Browser speech and transcription are simulated. No personal library, microphone,
global shortcut or real speech service was used for these browser checks.
Packaged speech and distribution verification are recorded separately.

## Published release

Release source is `0ff4899281c9576094f4abf5e2d6f9349efbe3d8`, tagged `v0.6.2`.
[Read Docs 0.6.2](https://github.com/SproutSeeds/doc-reader/releases/tag/v0.6.2)
is public, and [the download page](https://frg.earth/read-docs) serves its three
platform assets. GitHub installer run `41776604509` passed actual Kokoro/Whisper
audio on Apple silicon, Intel Mac and Windows x64, plus clean Windows install.
The separate cross-platform test workflow passed too.

Both Mac DMGs are Developer ID signed, Apple-notarized and stapled. Gatekeeper
accepts the apps and images. Read-only mounted imports, FFmpeg/eSpeak and
isolated service health passed; every bundled Python source matches the release
commit. Windows remains an unsigned preview. The three public downloads were
streamed completely and matched their local sizes and SHA-256 checksums.

Website deployment `dpl_7KeUgxY2PDccTgviHP7GmNFENCF1` changes only the release
manifest and release-notes link in its 781-file source manifest. All other
source bytes and checked public routes, including the resume PDF, are preserved.
Live browser checks passed at 1440, 390 and 320 px, including each platform URL,
unsigned-Windows label, release version, Info dismissal and focus restoration.
The FRG repository retains its separately classified preexisting dirty buckets.

## Installed Mac app

Updated the existing managed installation through its restart command after
confirming that no reading, recording or transcription was active. The previous
managed source exactly matched historical commit `5f09a20`; there were no
uncommitted runtime source edits to overwrite. The live page now matches the
new workspace bytes. All 1,679 preexisting history/document/text files retain
their hashes. Speech health, 28 voices and the native helper are ready; macOS
reports microphone, Accessibility and Input Monitoring permissions granted.
These are status checks, not physical microphone or hotkey acceptance.

`local-data-before.json` is private preservation metadata. Keep it local; do not
include it in public source or release assets.

## Source and workspace disposition

Commit only the app source, scoped native labels, version/release documentation,
design note, preview harness, browser checks, README screenshot and this receipt.
Other preexisting `reports/` artifacts remain a classified canonical evidence
bucket. Current screenshots and JSON/log receipts are local QA evidence, retained
for the next coordinated evidence checkpoint. Ignored prototype helpers under
`build/app-design-20261103/` are superseded by the committed preview/test tools.

## Resume decision

Evidence-only, no new resume claim: this is an interface and accessibility
refinement of the Read Docs desktop release already captured by
`doc-reader-desktop-release-2026-11-03-r1`. Platform delivery, speech architecture
and contributor attribution are unchanged. A separate accomplishment or resume
publication would duplicate that verified milestone. Canonical/public resume
sources and outputs were not edited for this refinement.
