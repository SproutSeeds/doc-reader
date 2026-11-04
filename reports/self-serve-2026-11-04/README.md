# Read Docs 0.7.1 independent setup

The user asked for a download and setup experience people can finish without
Cody helping, plus a minimal share preview titled only Read Docs.

App changes: automatic speech preparation and actionable retry; explicit model
preparation works with old disabled-warmup settings and queues behind startup;
macOS Accessibility registers the app when Allow is selected; microphone choice
and contextual help live inside setup; shortcut diagrams and trial instructions
follow selected keys; Back and Continue remain visible at small window sizes.
A desktop-only guide avoids sending new users through npm instructions.

Verified: 100 Python tests (four platform skips), native capture/readback/import
regressions, native app build and WKWebView rendering; real bundled offline
Kokoro/Whisper with background warmup disabled; Mac/Windows setup browser
flows, failed-start recovery, custom keys, microphone control, help, navigation,
responsive layouts and accessibility. Browser permissions/audio are simulated.
The built-in browser connection failed; the existing Playwright harness used
installed Chrome with GPU disabled to avoid a headless screenshot tiling defect.

Release delivery is in progress. Physical microphone, speakers, keyboard,
Windows security prompts and sleep/wake remain target-device checks.

Resume disposition: no new accomplishment. This is a bounded readiness patch
to the native-window, guided-setup and bundled-model milestone already included
under doc-reader-standalone-2026-11-04-r1. Preserve that certificate and public
resume; retain this patch's evidence here without duplicating the accomplishment.

Worktree: source changes and this report belong to the 0.7.1 patch. Existing
report buckets remain classified and untouched; their disposition is recorded
in reports/standalone-2026-11-04/README.md. Final installer/provider receipts and
selected screenshots will be checkpointed after delivery.
