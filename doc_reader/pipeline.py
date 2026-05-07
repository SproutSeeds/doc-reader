from __future__ import annotations

import queue
import re
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path

from .chunking import ChunkInputBlock, chunk_blocks_stream
from .config import ReaderConfig
from .extract import iter_document_blocks_with_meta
from .smart_narration import PreparedNarration, SmartNarrator
from .speech import Speaker

WORD_RE = re.compile(r"\b\w+\b")


class _EndOfStream:
    pass


@dataclass
class _ErrorWrapper:
    error: Exception


@dataclass
class _PreparedChunk:
    prepared: PreparedNarration
    page_number: int | None = None


@dataclass
class ReaderStats:
    chunks_spoken: int = 0
    source_words: int = 0
    spoken_words: int = 0
    startup_latency_seconds: float = 0.0


class StreamingReader:
    def __init__(self, config: ReaderConfig) -> None:
        self.config = config
        self._queue: queue.Queue[_PreparedChunk | _EndOfStream | _ErrorWrapper] = queue.Queue(
            maxsize=config.queue_size
        )

    def run(self, speaker: Speaker) -> ReaderStats:
        stats = ReaderStats()
        producer = threading.Thread(target=self._produce, args=(speaker,), daemon=True)

        start_time = time.perf_counter()
        producer.start()

        first_item = self._queue.get()
        stats.startup_latency_seconds = time.perf_counter() - start_time

        if isinstance(first_item, _EndOfStream):
            producer.join(timeout=1.0)
            speaker.close()
            return stats
        if isinstance(first_item, _ErrorWrapper):
            raise first_item.error
        self._speak_prepared(first_item, speaker, stats)

        while True:
            item = self._queue.get()
            if isinstance(item, _EndOfStream):
                break
            if isinstance(item, _ErrorWrapper):
                raise item.error
            self._speak_prepared(item, speaker, stats)

        producer.join(timeout=1.0)
        speaker.close()
        return stats

    def _produce(self, speaker: Speaker) -> None:
        try:
            narrator = SmartNarrator(mode=self.config.mode, style=self.config.style)
            blocks = iter_document_blocks_with_meta(
                Path(self.config.source_path),
                preserve_all=self.config.mode == "full",
            )
            chunks = chunk_blocks_stream(
                (
                    ChunkInputBlock(text=block.text, page_number=block.page_number)
                    for block in blocks
                ),
                first_chunk_words=self.config.first_chunk_words,
                chunk_words=self.config.chunk_words,
            )

            elapsed_seconds = 0.0
            start_seconds = max(0.0, self.config.start_seconds)
            for index, chunk in enumerate(chunks):
                if self.config.max_chunks is not None and index >= self.config.max_chunks:
                    break
                prepared = narrator.prepare(chunk.text, index)
                if prepared.text:
                    chunk_seconds = self._estimate_chunk_seconds(prepared.spoken_words)
                    if index < max(0, int(self.config.start_chunk_index)):
                        continue
                    if elapsed_seconds + chunk_seconds <= start_seconds:
                        elapsed_seconds += chunk_seconds
                        continue
                    if start_seconds > elapsed_seconds:
                        prepared = self._trim_prepared_for_resume(
                            prepared,
                            offset_seconds=start_seconds - elapsed_seconds,
                            chunk_seconds=chunk_seconds,
                        )
                        if not prepared.text:
                            elapsed_seconds += chunk_seconds
                            continue
                    speaker.prefetch(prepared.text, prepared.index)
                    self._queue.put(
                        _PreparedChunk(
                            prepared=prepared,
                            page_number=chunk.page_number,
                        )
                    )
                    elapsed_seconds += chunk_seconds

            self._queue.put(_EndOfStream())
        except Exception as exc:  # noqa: BLE001
            self._queue.put(_ErrorWrapper(exc))

    def _estimate_chunk_seconds(self, spoken_words: int) -> float:
        words = max(1, spoken_words)
        rate = max(60, self.config.speech_rate)
        return (words / rate) * 60.0

    def _trim_prepared_for_resume(
        self,
        prepared: PreparedNarration,
        *,
        offset_seconds: float,
        chunk_seconds: float,
    ) -> PreparedNarration:
        if offset_seconds <= 0 or chunk_seconds <= 0:
            return prepared
        ratio = min(0.98, max(0.0, offset_seconds / chunk_seconds))
        offset_words = int(prepared.spoken_words * ratio)
        trimmed_text = _trim_text_by_word_offset(prepared.text, offset_words)
        return replace(
            prepared,
            source_words=_word_count(trimmed_text),
            spoken_words=_word_count(trimmed_text),
            text=trimmed_text,
        )

    def _speak_prepared(
        self,
        item: _PreparedChunk,
        speaker: Speaker,
        stats: ReaderStats,
    ) -> None:
        prepared = item.prepared
        if self.config.verbose and item.page_number is not None:
            print(
                f"[doc-reader] page number={item.page_number} chunk={prepared.index}"
            )
        if self.config.verbose:
            print(f"[doc-reader] chunk-start index={prepared.index}")
        speaker.speak(prepared.text, prepared.index)
        if self.config.verbose:
            print(f"[doc-reader] chunk-done index={prepared.index}")
        stats.chunks_spoken += 1
        stats.source_words += prepared.source_words
        stats.spoken_words += prepared.spoken_words


def _trim_text_by_word_offset(text: str, offset_words: int) -> str:
    if offset_words <= 0:
        return text
    matches = list(WORD_RE.finditer(text))
    if not matches:
        return text
    if offset_words >= len(matches):
        return ""
    return text[matches[offset_words].start() :].lstrip()


def _word_count(text: str) -> int:
    return len(WORD_RE.findall(text))
