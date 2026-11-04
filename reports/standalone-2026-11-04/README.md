# Read Docs 0.7.0 standalone release evidence

Scope: native Mac/Windows windows, first-run setup, prominent side-specific
shortcuts, bundled offline speech, and installer/download delivery.

Verified locally before packaging:

- 98 Python tests, four platform skips; native capture and selected-text suites.
- Actual WKWebView window renders the app and opens first-run setup.
- Actual bundled Kokoro speech transcribed by bundled Whisper with HF and
  Transformers offline flags and an empty cache. Relocated long-path eSpeak
  initialization is included in this check.
- Existing workspace browser suite and two-platform setup suite, including
  permission/readiness gates, custom-choice preservation, recommended defaults,
  Escape/Back/focus, partial progress, completion, responsive themes and axe.
- Two Node process ownership tests; source whitespace checks.

Setup browser permission state and audio are simulated. These checks do not
establish physical microphone, speakers, keyboard combinations, OS permission
prompts, Windows Start-menu behavior or sleep/wake acceptance. The Try it step
requires the user's own confirmation rather than marking those checks passed.

The three-platform bundled-runtime CI run 41783003403 passed at dfab59e.
Installed-upgrade verification then exposed obsolete npm source shadowing the
bundle. Commit e36c710 enables Python safe-path imports and adds a native
regression; Mac and Windows test CI 41785475710 passed. Both Mac launchers were
rebuilt locally from that commit for arm64 and x86_64, preserving the verified
CI runtime and models. The Windows payload is byte-identical to the passing CI
artifact because this follow-up changes only Mac Swift and native tests.

Both final Mac disk images passed source/model hash checks, read-only service
startup and real offline Kokoro-to-Whisper speech. Apple accepted their final
notarization submissions. The published final assets and all three anonymous download streams match their
SHA256 receipts. The current npm publication remains the
existing source release; naming/source discovery did not authorize an npm publish.

Worktree: all preexisting reports remain classified evidence. New source and
tests are scoped to this desktop objective. Screenshots, logs, checksums and
provider receipts stay in this report directory. Personal library/settings data
must not be committed. Prior report buckets are preserved.

Published delivery:

- [Read Docs downloads](https://frg.earth/read-docs) and [v0.7.0 preview](https://github.com/SproutSeeds/doc-reader/releases/tag/v0.7.0).
- Website production `dpl_6z9g93zpxdnQRJYDEZ6tuGd4WQEt` changes only the landing HTML and release manifest in the existing 781-file deployment. All 382 site tests, eight-size local/live browser checks, exact bytes and download hashes pass. Other routes and the public resume are preserved.
- Final Apple silicon notary submission `e4f0bb96-55d7-4059-bf8f-29be6f9d8545`; Intel `1a43b1b2-556f-488a-850a-ae8ec29d68ed`. Both accepted, stapled and Gatekeeper verified. `notary-final-*`, `native-final-*` and `runtime-final-*` are the final receipts; earlier files without `final` describe superseded candidates.
- The existing Mac app is updated, and the native first-run window was inspected with both Kokoro and Whisper ready. All 5,573 library/document/audio/history files and saved user choices were preserved. Only volatile status and derived analysis fields refreshed. The existing shared speech service retains Pocket, Kitten and its extended model cache; Whisper warmup is enabled for setup. Fresh installers independently pass offline checks with their bundled runtime/models.
- The qualified milestone completed canonical and phone-free public resume intake `doc-reader-standalone-2026-11-04-r1`. All 22 rendered pages, text, links, privacy and live delivery were verified; the writer reservation is released.

Final source and evidence are checkpointed on main. The v0.7.0 tag remains at
`e36c710`, the source used for the release; the later checkpoint contains only
documentation and verification evidence.

Retained local evidence buckets and next actions:

- `reports/standalone-2026-11-04/`: final receipts and selected setup screenshots are committed. Responsive workspace captures, superseded candidates and local artifact-path receipts remain classified local evidence for future regression comparison; never publish the private library snapshot, which lives outside the repo.
- `reports/app-design-2026-11-03/`, `reports/desktop-release-2026-11-03/`, `reports/doc-reader-audit-2026-09-08/`, `reports/readback-audit-2026-09-25/`, `reports/release-2026-09-25/` and `reports/windows-contribution-2026-09-22/`: preserved preexisting evidence, including locally private snapshots. Leave them in place; review privacy and historical relevance before any separate archival checkpoint.
- The FRG checkout remains intentionally dirty with its existing classified buckets; the two download source files and publication evidence await its next coordinated source checkpoint. No broad site commit or checkout deployment occurred.

Final ORP hygiene reports no unclassified dirty paths. Physical user acceptance
remains explicitly separate from these automated and visual checks.
