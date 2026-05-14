from __future__ import annotations

import json
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
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")
MIN_RUNTIME_RATE = 60
MAX_RUNTIME_RATE = 500
RATE_CONTROL_KEYS = ("read_rate", "readRate", "rate", "speech_rate", "speechRate")
SEGMENT_KEY_STRIDE = 10_000


class _EndOfStream:
    pass


@dataclass
class _ErrorWrapper:
    error: Exception


@dataclass
class _PreparedChunk:
    prepared: PreparedNarration
    speech_segments: tuple[str, ...] = ()
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
                    runtime_rate = self._apply_runtime_rate(speaker)
                    chunk_seconds = self._estimate_chunk_seconds(
                        prepared.spoken_words,
                        rate=runtime_rate,
                    )
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
                    speech_segments = tuple(
                        _iter_speech_segments(
                            prepared.text,
                            target_words=self.config.speech_segment_words,
                        )
                    )
                    if not speech_segments:
                        elapsed_seconds += chunk_seconds
                        continue
                    self._apply_runtime_rate(speaker)
                    speaker.prefetch(
                        speech_segments[0],
                        _speech_segment_key(prepared.index, 0),
                    )
                    self._queue.put(
                        _PreparedChunk(
                            prepared=prepared,
                            speech_segments=speech_segments,
                            page_number=chunk.page_number,
                        )
                    )
                    elapsed_seconds += chunk_seconds

            self._queue.put(_EndOfStream())
        except Exception as exc:  # noqa: BLE001
            self._queue.put(_ErrorWrapper(exc))

    def _runtime_rate(self) -> int:
        rate = self.config.speech_rate
        path = self.config.rate_control_path
        if path:
            try:
                raw = path.read_text(encoding="utf-8").strip()
            except OSError:
                raw = ""
            if raw:
                try:
                    payload: object = json.loads(raw)
                except ValueError:
                    payload = raw

                value: object | None = payload
                if isinstance(payload, dict):
                    value = None
                    for key in RATE_CONTROL_KEYS:
                        if key in payload:
                            value = payload[key]
                            break

                if value is not None:
                    try:
                        rate = int(round(float(str(value).strip())))
                    except (TypeError, ValueError):
                        rate = self.config.speech_rate
        return max(MIN_RUNTIME_RATE, min(MAX_RUNTIME_RATE, int(rate)))

    def _apply_runtime_rate(self, speaker: Speaker) -> int:
        rate = self._runtime_rate()
        setter = getattr(speaker, "set_rate", None)
        if callable(setter):
            setter(rate)
        return rate

    def _estimate_chunk_seconds(self, spoken_words: int, *, rate: int | None = None) -> float:
        words = max(1, spoken_words)
        effective_rate = max(MIN_RUNTIME_RATE, rate or self.config.speech_rate)
        return (words / effective_rate) * 60.0

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
        speech_segments = item.speech_segments or tuple(
            _iter_speech_segments(
                prepared.text,
                target_words=self.config.speech_segment_words,
            )
        )
        for segment_index, segment in enumerate(speech_segments):
            self._apply_runtime_rate(speaker)
            next_index = segment_index + 1
            if next_index < len(speech_segments):
                speaker.prefetch(
                    speech_segments[next_index],
                    _speech_segment_key(prepared.index, next_index),
                )
            speaker.speak(segment, _speech_segment_key(prepared.index, segment_index))
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


def _iter_speech_segments(text: str, *, target_words: int) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []

    target = max(12, int(target_words or 0))
    sentences = SENTENCE_SPLIT_RE.split(cleaned)
    segments: list[str] = []
    current: list[str] = []
    current_words = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        sentence_words = _word_count(sentence)
        if sentence_words > target * 2:
            if current:
                segments.append(" ".join(current))
                current = []
                current_words = 0
            segments.extend(_split_long_sentence(sentence, target_words=target))
            continue
        if current and current_words + sentence_words > target:
            segments.append(" ".join(current))
            current = []
            current_words = 0
        current.append(sentence)
        current_words += sentence_words

    if current:
        segments.append(" ".join(current))
    return segments or [cleaned]


def _split_long_sentence(sentence: str, *, target_words: int) -> list[str]:
    words = sentence.split()
    if not words:
        return []
    target = max(12, target_words)
    return [
        " ".join(words[index : index + target])
        for index in range(0, len(words), target)
    ]


def _speech_segment_key(chunk_index: int, segment_index: int) -> int:
    return ((max(0, int(chunk_index)) + 1) * SEGMENT_KEY_STRIDE) + max(0, int(segment_index))


def _word_count(text: str) -> int:
    return len(WORD_RE.findall(text))
