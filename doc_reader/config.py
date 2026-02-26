from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ReadMode = Literal["smart", "full"]
NarrationStyle = Literal["concise", "balanced", "detailed"]


@dataclass
class ReaderConfig:
    source_path: Path
    mode: ReadMode = "smart"
    style: NarrationStyle = "balanced"
    speech_rate: int = 180
    voice_hint: str | None = None
    queue_size: int = 8
    first_chunk_words: int = 110
    chunk_words: int = 220
    max_chunks: int | None = None
    start_chunk_index: int = 0
    start_seconds: float = 0.0
    verbose: bool = False
