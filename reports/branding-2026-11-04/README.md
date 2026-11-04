# Read Docs 0.7.2 branding release

Cody selected the rd monogram on November 4, 2026 and authorized rebuilding and
publishing the three desktop downloads. Release source is
85e0982f5aa9eccb364ba8d701ae894eef02908f.

The original artwork is preserved in assets/read-docs-source.png. Platform
exports trim its outer generation fringe while preserving the monogram and
mineral glass image. icon-delivery.png shows the actual ICNS and ICO at large
size and 16, 32 and 64 pixels. Mac bundle and Windows shortcut names are Read
Docs. Existing bundle ID, Windows installer AppId, executable names and data
locations stay compatible. Windows upgrades migrate owned legacy shortcuts and
preserve unrelated shortcuts with the same legacy name.

## Verification

- 100 local Python tests pass with four platform skips; native capture,
  readback, clipboard and obsolete-profile import checks pass. The initial
  native run used Apple's old system Python, which lacks PYTHONSAFEPATH; the
  authoritative rerun used the supported interpreter. Both native architectures
  compile, JavaScript process tests pass, and npm packaging includes the assets.
- GitHub Desktop installers run 41903554892 and Test run 41903556751 pass at the
  exact release source. Both Mac architectures and Windows run actual offline
  Kokoro synthesis and Whisper transcription. Windows additionally renders the
  packaged Qt window, installs into a clean destination, and verifies upgrade
  shortcut migration and preservation of an unrelated shortcut.
- Final Mac release wrappers were rebuilt locally using the verified 0.7.1
  third-party runtime cache with unchanged dependency requirements. First-party
  source and assets were replaced completely. Read-only DMG checks verify all
  bundled Python source, icon PNGs, architecture, version, signatures and 37
  bundled model hashes, then run actual offline speech on both architectures.
- Apple accepted notarization ccdc3521-22bf-4704-9203-c6bb101db047 (Apple silicon)
  and 084d2b15-d456-4587-a6d8-27caf387bbb6 (Intel). Both distribution DMGs have
  stapled tickets and pass Gatekeeper. The locally installed app also has its
  own current stapled ticket. Distribution follows Apple's outer-container
  notarization and stapling workflow:
  https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution
- The installed Mac uses a fresh Read Docs.app bundle, with the previous verified
  user-installed bundle retained in the canonical release cache for rollback.
  Its native window was inspected. All 5,593 library/document/audio/history
  files and saved preferences are preserved; only derived analysis and volatile
  microphone status fields changed. The shared speech process and its existing
  Kokoro, Whisper, Pocket and Kitten configuration remained running.

The Windows download remains an unsigned preview. Automated audio and GUI checks
do not replace the user's physical microphone, speakers, global shortcut,
text-insertion, OS permission and sleep/wake checks on each device. The setup
wizard's real-device confirmations remain user controlled.

## Publication and scope

Published release: https://github.com/SproutSeeds/doc-reader/releases/tag/v0.7.2.
Live downloads: https://frg.earth/read-docs. Production deployment
dpl_GDj5NFrnm2f8Mo8V43ThW5SPSMh4 is verified. All three anonymous download
streams match SHA256. The site passes 382 tests and eight live viewport checks;
all unrelated production source bytes and 1,029 local files are preserved.
Publishing the tag retriggered two identical CI runs; those redundant runs were
cancelled after the original exact-source runs succeeded. Website
changes are scoped to the Read Docs manifest, HTML and two app-icon PNGs. Sharing
keeps the existing wordmark image, title Read Docs and empty descriptions.
The source npm package is not republished; this is a desktop branding release.

Resume disposition: evidence only, no canonical or public resume change. This
is a bounded branding and installer polish patch to the already recorded
standalone desktop release (doc-reader-standalone-2026-11-04-r1), rather than a
separate new accomplishment. The existing public resume is a preservation check
in the narrow website deployment.

Worktree: this release's source is committed separately. Existing design studies
and older report artifacts remain classified local evidence. Preserve those
buckets for regression comparison; do not sweep them into the release commit.
Release caches are under /Volumes/Code_2TB/.agent-tmp/doc-reader/release-0.7.2;
private library snapshots and rollback copies remain outside the repository.
