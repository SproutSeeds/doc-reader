from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from .config import NarrationStyle, ReadMode

STOPWORDS = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "am",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "can",
    "did",
    "do",
    "does",
    "doing",
    "down",
    "during",
    "each",
    "few",
    "for",
    "from",
    "further",
    "had",
    "has",
    "have",
    "having",
    "he",
    "her",
    "here",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "itself",
    "just",
    "me",
    "more",
    "most",
    "my",
    "myself",
    "no",
    "nor",
    "not",
    "now",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "our",
    "ours",
    "ourselves",
    "out",
    "over",
    "own",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "with",
    "would",
    "you",
    "your",
    "yours",
    "yourself",
    "yourselves",
}

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")
URL_RE = re.compile(r"https?://\S+")


@dataclass
class PreparedNarration:
    index: int
    source_words: int
    spoken_words: int
    text: str


class SmartNarrator:
    def __init__(self, *, mode: ReadMode, style: NarrationStyle) -> None:
        self.mode = mode
        self.style = style
        self.term_counts: Counter[str] = Counter()

    def prepare(self, chunk_text: str, index: int) -> PreparedNarration:
        source_words = _word_count(chunk_text)

        if self.mode == "full":
            spoken_text = _make_spoken_friendly(chunk_text)
        else:
            spoken_text = self._summarize(chunk_text, index)

        spoken_words = _word_count(spoken_text)
        return PreparedNarration(
            index=index,
            source_words=source_words,
            spoken_words=spoken_words,
            text=spoken_text,
        )

    def _summarize(self, text: str, _index: int) -> str:
        sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]
        if not sentences:
            return ""

        self.term_counts.update(_keywords(text))
        theme_terms = {term for term, _ in self.term_counts.most_common(40)}

        scored_sentences: list[tuple[float, int, str]] = []
        for i, sentence in enumerate(sentences):
            score = _sentence_score(sentence, i, theme_terms)
            scored_sentences.append((score, i, sentence))

        scored_sentences.sort(key=lambda item: item[0], reverse=True)

        take_n = {
            "concise": 1,
            "balanced": 2,
            "detailed": 3,
        }[self.style]
        take_n = min(take_n, len(scored_sentences))

        chosen = sorted(scored_sentences[:take_n], key=lambda item: item[1])
        summary = " ".join(sentence for _, _, sentence in chosen)

        if _word_count(summary) < 30 and len(sentences) > take_n:
            remaining = sorted(scored_sentences[take_n:], key=lambda item: item[0], reverse=True)
            if remaining:
                summary = f"{summary} {remaining[0][2]}".strip()

        summary = _make_spoken_friendly(summary)

        return summary


def _sentence_score(sentence: str, position: int, theme_terms: set[str]) -> float:
    if _looks_like_reference(sentence):
        return -2.5

    words = _keywords(sentence)
    if not words:
        return -1.0

    score = 0.0
    score += min(len(words), 20) * 0.6
    score += sum(1.0 for word in words if word in theme_terms)

    if any(char.isdigit() for char in sentence):
        score += 1.0
    if "important" in sentence.lower() or "key" in sentence.lower():
        score += 1.0

    # Slightly favor earlier sentences, which usually introduce context.
    score += max(0.0, 1.5 - (position * 0.15))

    if len(sentence) < 35:
        score -= 0.8
    if len(sentence) > 280:
        score -= 0.5

    return score


def _looks_like_reference(sentence: str) -> bool:
    lower = sentence.lower().strip()
    if lower.startswith("copyright"):
        return True
    if lower.startswith("all rights reserved"):
        return True
    if re.search(r"\bdoi\b", lower):
        return True
    if re.search(r"\bpage\s+\d+\b", lower):
        return True
    if re.fullmatch(r"\(?\d{4}\)?", lower):
        return True
    return False


def _keywords(text: str) -> list[str]:
    words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9'-]{2,}\b", text.lower())
    return [word for word in words if word not in STOPWORDS]


def _make_spoken_friendly(text: str) -> str:
    text = URL_RE.sub("a web link", text)
    text = text.replace("|", ", ")
    text = text.replace("/", " or ")
    text = text.replace("&", " and ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)

    # Remove markdown and code-like punctuation noise.
    text = text.replace("`", "")
    text = text.replace("###", "")
    text = text.replace("##", "")
    text = text.replace("#", "")

    return text.strip()


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))
