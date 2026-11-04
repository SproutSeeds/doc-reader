"""Locate the immutable speech assets shipped beside the desktop runtime."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def models_root() -> Path | None:
    configured = os.getenv("DOC_READER_MODELS_DIR")
    candidate = Path(configured) if configured else Path(sys.prefix).parent / "models"
    if configured and not (candidate / "manifest.json").is_file():
        raise RuntimeError("The bundled speech models are missing. Reinstall Read Docs.")
    return candidate if (candidate / "manifest.json").is_file() else None


def model_manifest() -> dict:
    root = models_root()
    return json.loads((root / "manifest.json").read_text(encoding="utf-8")) if root else {}


def whisper_path(fallback: str) -> str:
    root = models_root()
    if root:
        name = model_manifest()["whisper"]["name"]
        candidate = root / f"whisper-{name}"
        if not (candidate / "model.bin").is_file():
            raise RuntimeError("The bundled dictation model is missing. Reinstall Read Docs.")
        return str(candidate)
    return fallback
