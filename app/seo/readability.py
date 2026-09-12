"""Readability metrics (Flesch Reading Ease & Flesch-Kincaid Grade).

Self-contained syllable estimation so the engine has no heavy NLP deps.
"""
import re
from dataclasses import dataclass

_VOWEL_GROUPS = re.compile(r"[aeiouy]+")
_SENTENCE_SPLIT = re.compile(r"[.!?]+")
_WORD = re.compile(r"[A-Za-z]+")


def count_syllables(word: str) -> int:
    word = word.lower().strip()
    if not word:
        return 0
    groups = _VOWEL_GROUPS.findall(word)
    count = len(groups)
    # Silent trailing 'e' (but never reduce below 1).
    if word.endswith("e") and not word.endswith(("le", "ee", "ie")) and count > 1:
        count -= 1
    return max(count, 1)


@dataclass
class Readability:
    flesch_reading_ease: float
    flesch_kincaid_grade: float
    sentence_count: int
    word_count: int
    avg_words_per_sentence: float
    avg_syllables_per_word: float

    @property
    def interpretation(self) -> str:
        e = self.flesch_reading_ease
        if e >= 70:
            return "easy to read"
        if e >= 50:
            return "fairly difficult to read"
        return "difficult to read"


def analyze_readability(text: str) -> Readability:
    sentences = [s for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    words = _WORD.findall(text)
    n_sentences = max(len(sentences), 1)
    n_words = len(words)
    if n_words == 0:
        return Readability(0.0, 0.0, 0, 0, 0.0, 0.0)

    syllables = sum(count_syllables(w) for w in words)
    words_per_sentence = n_words / n_sentences
    syllables_per_word = syllables / n_words

    ease = 206.835 - 1.015 * words_per_sentence - 84.6 * syllables_per_word
    grade = 0.39 * words_per_sentence + 11.8 * syllables_per_word - 15.59

    return Readability(
        flesch_reading_ease=round(max(0.0, min(100.0, ease)), 1),
        flesch_kincaid_grade=round(max(0.0, grade), 1),
        sentence_count=len(sentences),
        word_count=n_words,
        avg_words_per_sentence=round(words_per_sentence, 1),
        avg_syllables_per_word=round(syllables_per_word, 2),
    )
