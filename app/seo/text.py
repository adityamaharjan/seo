"""Text extraction, tokenization and keyword extraction helpers.

Salvaged and refined from the prototype's ``AsyncSEOAnalyzer`` so the logic is
reusable across checks and independently testable.
"""
import re
import string

from bs4 import BeautifulSoup

from app.seo.constants import STOP_WORDS

_NON_CONTENT_TAGS = ["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]
_PUNCT_RE = re.compile(f"[{re.escape(string.punctuation)}]")


def extract_clean_text(soup: BeautifulSoup) -> str:
    """Visible body text with chrome/boilerplate tags removed.

    Operates on a copy so the caller's soup keeps its full structure.
    """
    clone = BeautifulSoup(str(soup), "lxml")
    for tag in clone(_NON_CONTENT_TAGS):
        tag.extract()
    return clone.get_text(separator=" ")


def tokenize(text: str) -> list[str]:
    text = _PUNCT_RE.sub(" ", text.lower())
    return [
        w
        for w in text.split()
        if w not in STOP_WORDS and w.isalpha() and len(w) > 2
    ]


def stopword_density(raw_text: str) -> float:
    words = re.findall(r"\w+", raw_text.lower())
    if not words:
        return 0.0
    stops = sum(1 for w in words if w in STOP_WORDS)
    return round((stops / len(words)) * 100, 1)
