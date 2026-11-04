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

Release source: `eca0d5970609d23dc8864a7761cda8cd0122bc00`. Desktop CI
`41852049569` passed all three targets, including actual offline speech,
the packaged Windows window and a clean-profile Windows installation.
Both final Mac disk images passed read-only runtime, source/model hash and
offline speech checks. Apple accepted submissions
`db508036-3a7b-426d-be29-04bae4612880` (Apple silicon) and
`d0c2024d-9ccc-4b80-bfb3-9f89e090c8c6` (Intel); both are stapled and pass
Gatekeeper.

The initial Mac test job could not acquire a hosted runner and ended before
any test ran. Its capacity annotation and the queued retry are retained.
Commit `d8a67ed` first tried the explicit Apple silicon packaging runner;
`41855663270` was also queued without a runner. Commit `4eda339` uses the Intel
packaging runner while hosted arm64 capacity is constrained. Only the workflow
file differs from the release commit; application and test source remain
identical. Desktop CI separately builds and exercises both Mac architectures,
and the local Apple silicon Python/native suites also pass.

The existing Mac app is updated and visually inspected. All 5,573 existing
library/document/audio/history files and saved preferences are preserved.
Both shared Kokoro and Whisper models are loaded; optional Pocket and Kitten
and the extended model cache remain available. Merging the old app bundle
initially retained 150 obsolete packaged bytecode/dependency metadata files;
the signature check caught them. Removing only those proven extra runtime
files restored the exact signed bundle, which passes signature, stapler and
Gatekeeper checks. Personal data lives outside the app and was preserved.

The Intel test job also ended without acquiring a hosted runner. The release
uses the passing full local Mac suite, successful three-platform packaging CI,
signed disk-image runtime checks and passing hosted Windows suite. The extra
hosted Mac unit/native job remains unexecuted; no application test failure was
waived. See `release-verification-decision.json` and the original GitHub capacity
annotations for this explicit limit.

Published: [Read Docs](https://frg.earth/read-docs) and
[v0.7.1 preview](https://github.com/SproutSeeds/doc-reader/releases/tag/v0.7.1).
All three public installer streams match their final SHA256 receipts. Mac
downloads are signed and Apple-notarized; Windows remains an unsigned preview.
The npm publication is unchanged.

Website production `dpl_41mYymcfYmrPLGYWMPNyQyr9M3gj` serves the verified 0.7.1
manifest and desktop guide. The share image matches the landing page; title is
Read Docs and all description fields are empty. Local and live eight-size
browser checks, sharing-crawler responses, exact public bytes and unrelated
route preservation pass. All 382 site tests pass. Messaging clients retain
control over their own preview layout and cache refresh timing.

Physical microphone, speakers, keyboard, Windows security prompts and
sleep/wake remain target-device checks. Setup does not mark those checks
complete on the user's behalf.

Resume disposition: no new accomplishment. This is a bounded readiness patch
to the native-window, guided-setup and bundled-model milestone already included
under doc-reader-standalone-2026-11-04-r1. Preserve that certificate and public
resume; retain this patch's evidence here without duplicating the accomplishment.

Worktree: source, final release receipts and selected screenshots are
checkpointed for the 0.7.1 patch. Remaining responsive screenshots, intermediate
draft receipts and local-path asset lists stay in this report directory for
future regression comparison. Private library/settings baselines remain in
the canonical release cache outside the repository and must not be published.
Existing report buckets remain classified and untouched; their disposition is
recorded in `reports/standalone-2026-11-04/README.md`. The FRG checkout retains
its existing unrelated dirty work; the three Read Docs source files, design
note and final publication receipts await its next coordinated checkpoint.
