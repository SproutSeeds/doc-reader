"""Fetch pinned public weights at BUILD time; installers never download models."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from huggingface_hub import hf_hub_download
from doc_reader.kokoro_voices import english_voices
import shutil

KOKORO = ("hexgrad/Kokoro-82M", "f3ff3571791e39611d31c381e3a41a3af07b4987")
WHISPER = {
    "base": ("Systran/faster-whisper-base", "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66"),
    "small": ("Systran/faster-whisper-small", "536b0662742c02347bc0e980a01041f333bce120"),
}


def bundle(destination: Path, whisper: str) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": 1, "kokoro": {"repo": KOKORO[0], "revision": KOKORO[1]},
                "whisper": {"name": whisper, "repo": WHISPER[whisper][0], "revision": WHISPER[whisper][1]}, "files": {}}
    for directory, repo, revision, files in (
        ("kokoro", *KOKORO, ["config.json", "kokoro-v1_0.pth", "README.md", "VOICES.md"] +
         [f"voices/{voice['id']}.pt" for voice in english_voices()]),
        (f"whisper-{whisper}", *WHISPER[whisper], ["config.json", "model.bin", "tokenizer.json", "vocabulary.txt", "README.md"]),
    ):
        for filename in files:
            source = hf_hub_download(repo, filename, revision=revision)
            target = destination / directory / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            with target.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            manifest["files"][f"{directory}/{filename}"] = {"sha256": digest, "bytes": target.stat().st_size}
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Bundled Kokoro, {len(english_voices())} English voices and multilingual Whisper {whisper}.", flush=True)


if __name__ == "__main__":
    bundle(Path(sys.argv[1]), "small" if sys.platform == "win32" else "base")
