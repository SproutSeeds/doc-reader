from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Iterator

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")


@dataclass(frozen=True)
class ChunkInputBlock:
    text: str
    page_number: int | None = None


@dataclass(frozen=True)
class ChunkOutput:
    text: str
    page_number: int | None = None


def chunk_text_stream(
    blocks: Iterable[str],
    *,
    first_chunk_words: int = 110,
    chunk_words: int = 220,
) -> Iterator[str]:
    wrapped = (ChunkInputBlock(text=block, page_number=None) for block in blocks)
    for chunk in chunk_blocks_stream(
        wrapped,
        first_chunk_words=first_chunk_words,
        chunk_words=chunk_words,
    ):
        yield chunk.text


def chunk_blocks_stream(
    blocks: Iterable[ChunkInputBlock],
    *,
    first_chunk_words: int = 110,
    chunk_words: int = 220,
) -> Iterator[ChunkOutput]:
    if first_chunk_words < 40:
        first_chunk_words = 40
    if chunk_words < first_chunk_words:
        chunk_words = first_chunk_words

    current_sentences: list[str] = []
    current_words = 0
    chunk_index = 0
    current_page: int | None = None

    for block in blocks:
        block_text = block.text.strip()
        if not block_text:
            continue

        block_page = block.page_number
        if (
            current_sentences
            and block_page is not None
            and current_page is not None
            and block_page != current_page
        ):
            target_words = first_chunk_words if chunk_index == 0 else chunk_words
            min_page_split_words = max(60, min(target_words, max(40, target_words // 2)))
            if current_words >= min_page_split_words:
                yield ChunkOutput(text=" ".join(current_sentences), page_number=current_page)
                current_sentences = []
                current_words = 0
                chunk_index += 1
                current_page = None

        if block_page is not None and current_page is None:
            current_page = block_page

        for sentence in _iter_sentences(block_text):
            sentence_words = _word_count(sentence)
            if sentence_words == 0:
                continue

            target_words = first_chunk_words if chunk_index == 0 else chunk_words

            if current_words >= target_words and current_sentences:
                yield ChunkOutput(text=" ".join(current_sentences), page_number=current_page)
                current_sentences = []
                current_words = 0
                chunk_index += 1
                target_words = chunk_words

            current_sentences.append(sentence)
            current_words += sentence_words

            if current_words >= target_words:
                yield ChunkOutput(text=" ".join(current_sentences), page_number=current_page)
                current_sentences = []
                current_words = 0
                chunk_index += 1

    if current_sentences:
        yield ChunkOutput(text=" ".join(current_sentences), page_number=current_page)


def _iter_sentences(block: str) -> Iterator[str]:
    block = block.strip()
    if not block:
        return

    if _word_count(block) <= 18:
        yield block
        return

    parts = SENTENCE_SPLIT_RE.split(block)
    if len(parts) == 1:
        yield block
        return

    for part in parts:
        part = part.strip()
        if part:
            yield part


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))
