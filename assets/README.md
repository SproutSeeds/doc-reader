# Read Docs branding

Cody approved the rd concept on November 4, 2026. `read-docs-source.png` is the
original generated artwork, retained without changes. Its source and reference
roles are documented in docs/design-notes/icon-studies-2026-11-04/prompts.json.

The platform export crops inside the original tile and applies a rounded alpha
boundary to remove generation fringe. It preserves the monogram and glass image.

Rebuild the delivery formats on macOS:

```sh
swift packaging/export_icons.swift assets/read-docs-source.png doc_reader/icons
python3 packaging/export_windows_icon.py
```

The Mac build resamples doc_reader/icons/read-docs-1024.png into its ICNS.
The ICO packs the 16, 32, 48, 64, 128 and 256 pixel PNGs without re-rendering them.
