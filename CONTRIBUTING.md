# Contributing to doc-reader

Thanks for taking the time to contribute.

## Ways to help

- Report bugs
- Suggest features and UX improvements
- Improve docs
- Submit code fixes or enhancements

## Before you start

1. Search existing issues and pull requests first.
2. Open an issue for non-trivial changes so we can align on direction.
3. Keep changes focused and small when possible.

## Local setup

```bash
git clone https://github.com/SproutSeeds/doc-reader.git
cd doc-reader
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the tray app:

```bash
./run-doc-reader
```

Run the CLI:

```bash
python -m doc_reader /path/to/file.pdf --mode smart --style balanced --verbose
```

## Pull request guidelines

1. Fork the repo and create a branch with a clear name.
2. Make your change with docs updates when needed.
3. Verify behavior locally (startup, file reading, and any touched flow).
4. Open a PR with:
   - clear summary
   - motivation
   - testing notes
   - screenshots/log snippets for UI or behavior changes

## Coding notes

- Target Python 3.11+.
- Keep functions focused and readable.
- Avoid adding heavy dependencies unless strongly justified.
- Preserve cross-platform behavior (macOS-first tray support, CLI fallback elsewhere).
- Never commit secrets (API keys, tokens, local env files).

## Reporting security issues

Please avoid posting sensitive vulnerabilities in public issues. Open a private security advisory on GitHub instead.
