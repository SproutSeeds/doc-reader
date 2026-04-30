# Release Checklist

## 0.1.1

`0.1.1` is the first macOS-first native-wrapper release.

## 0.1.2

`0.1.2` improves the install-time error when Apple's Command Line Tools are
missing. Users are told to run `xcode-select --install` and then retry
`read-docs install`.

Before publishing:

```bash
node --check bin/read-docs.js
bash -n build-macos-app enable-startup disable-startup install-context-menu-service uninstall-context-menu-service run-doc-reader read-selection-service.sh
PYTHONPYCACHEPREFIX=/tmp/doc-reader-pyc .venv/bin/python -m compileall doc_reader
./build-macos-app /tmp/doc-reader-native-build
npm pack --dry-run --json
```

Manual checks:

- `read-docs status` reports a native shell path after `read-docs install` or `read-docs restart`.
- LaunchAgent program is `~/.doc-reader-managed/Doc Reader.app/Contents/MacOS/DocReader`.
- The app shows in the menu bar and does not create a Python Dock tile.
- `Read Clipboard`, `Choose Document...`, and `Stop Reading` work.
- ElevenLabs voice loading works with a user-provided key.
- The package contains no real API keys or local env files.

Publish:

```bash
npm publish
npm view read-docs version
```

Upgrade path for existing users:

```bash
npm install -g read-docs@latest
read-docs restart
```

Install path for new users:

```bash
npm install -g read-docs
read-docs install
```

Current caveat: the native app is compiled locally during install, so users need
Apple Command Line Tools (`xcode-select --install`). A later release should ship a
signed and notarized prebuilt app bundle.
