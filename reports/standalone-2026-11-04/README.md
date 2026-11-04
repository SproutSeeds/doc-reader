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

Release and live-download verification will be recorded after platform builds,
signing/notarization and publication. The current npm publication remains the
existing source release; naming/source discovery did not authorize an npm publish.

Worktree: all preexisting reports remain classified evidence. New source and
tests are scoped to this desktop objective. Screenshots, logs, checksums and
provider receipts stay in this report directory. Personal library/settings data
must not be committed. Prior report buckets are preserved.
