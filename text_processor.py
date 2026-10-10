"""
text_processor.py - rule-based text processing for AccessLens AI.

IMPORTANT: this is NOT a trained AI model. It uses simple, transparent rules:
  1. Word/phrase replacement from a small built-in dictionary
  2. Splitting very long sentences at conjunctions and semicolons
  3. Regular expressions to highlight dates, numbers, deadlines, warnings, keywords
  4. A readability score (Flesch Reading Ease) calculated with a syllable heuristic
"""

import html
import re

MAX_WORDS = 20  # sentences longer than this are split where possible

# Longer phrases are replaced by plainer ones.
PHRASES = {
    "in order to": "to",
    "due to the fact that": "because",
    "in the event that": "if",
    "with regard to": "about",
    "with respect to": "about",
    "prior to": "before",
    "subsequent to": "after",
    "in addition to": "besides",
    "in addition": "also",
    "a number of": "several",
    "at this point in time": "now",
    "for the purpose of": "for",
    "in accordance with": "following",
    "pursuant to": "under",
    "as a result of": "because of",
    "in spite of the fact that": "although",
    "is able to": "can",
    "are able to": "can",
    "has the ability to": "can",
    "on a daily basis": "daily",
    "in the near future": "soon",
}

# Single words (and a few common forms) are replaced by simpler ones.
# Words like "required" are deliberately left alone so the highlighter can flag them.
WORDS = {
    "utilize": "use", "utilise": "use", "utilizes": "uses", "utilized": "used",
    "commence": "start", "commences": "starts", "commenced": "started",
    "commencement": "start",
    "terminate": "end", "terminates": "ends", "terminated": "ended",
    "obtain": "get", "obtains": "gets", "obtained": "got",
    "approximately": "about", "sufficient": "enough", "additional": "more",
    "demonstrate": "show", "demonstrates": "shows", "demonstrated": "showed",
    "indicate": "show", "indicates": "shows", "indicated": "showed",
    "modify": "change", "modifies": "changes", "modified": "changed",
    "facilitate": "help", "facilitates": "helps", "subsequently": "later",
    "endeavor": "try", "endeavour": "try", "numerous": "many",
    "regarding": "about", "individuals": "people", "remainder": "rest",
    "commencing": "starting", "nevertheless": "still", "assistance": "help",
    "frequently": "often", "residing": "living", "purchased": "bought",
}

_REPLACEMENTS = {**PHRASES, **WORDS}
_REPLACE_RE = re.compile(
    r"\b(?:" + "|".join(sorted(map(re.escape, _REPLACEMENTS), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_SPLIT_RE = re.compile(r";\s+|,\s+(?:and|but|so|whereas|which)\s+", re.IGNORECASE)


def _match_case(original, replacement):
    """Keep the capitalisation of the word being replaced."""
    if original.isupper() and len(original) > 1:
        return replacement.upper()
    if original[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement


def _replace_vocab(text):
    """Swap complex words/phrases for simpler ones using the dictionaries above."""
    return _REPLACE_RE.sub(lambda m: _match_case(m.group(0), _REPLACEMENTS[m.group(0).lower()]), text)


def split_long_sentence(sentence):
    """
    Split a long sentence near its middle at a semicolon or a conjunction
    (", and" / ", but" / ", so" / ", whereas" / ", which"). Repeats until the
    pieces are short or no good split point exists.
    """
    words = sentence.split()
    if len(words) <= MAX_WORDS:
        return [sentence]

    best = None  # (how far from the middle, regex match)
    for m in _SPLIT_RE.finditer(sentence):
        left = len(sentence[: m.start()].split())
        right = len(words) - left
        if left < 5 or right < 5:  # avoid creating tiny fragments
            continue
        gap = abs(left - right)
        if best is None or gap < best[0]:
            best = (gap, m)
    if best is None:
        return [sentence]

    m = best[1]
    joiner = re.sub(r"[;,\s]", "", m.group(0)).lower()
    prefix = {"but": "But ", "whereas": "But ", "so": "So ", "which": "This "}.get(joiner, "")
    first = sentence[: m.start()].rstrip(" ,;") + "."
    rest = sentence[m.end():]
    rest = prefix + rest if prefix else rest[:1].upper() + rest[1:]
    return split_long_sentence(first) + split_long_sentence(rest)


def simplify_text(text):
    """Simplify text paragraph by paragraph (blank lines are preserved)."""
    paragraphs = re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip())
    output = []
    for paragraph in paragraphs:
        paragraph = re.sub(r"\s+", " ", paragraph).strip()
        if not paragraph:
            continue
        paragraph = _replace_vocab(paragraph)
        pieces = []
        for sentence in _SENTENCE_RE.split(paragraph):
            pieces.extend(split_long_sentence(sentence))
        output.append(" ".join(pieces))
    return "\n\n".join(output)


# ------------------------------------------------------------- readability
def count_syllables(word):
    """Rough English syllable estimate: count groups of vowels."""
    word = re.sub(r"[^a-z]", "", word.lower())
    if not word:
        return 1
    count = len(re.findall(r"[aeiouy]+", word))
    if word.endswith("e") and not word.endswith(("le", "ee")) and count > 1:
        count -= 1  # silent final e
    return max(count, 1)


def analyse(text):
    """Return word count, average sentence length and Flesch Reading Ease (0-100, higher = easier)."""
    words = re.findall(r"[A-Za-z0-9'\u2019-]+", text)
    sentences = [s for s in _SENTENCE_RE.split(text.strip()) if s.strip()]
    if not words:
        return {"words": 0, "sentences": 0, "avg_sentence": 0.0, "ease": 0.0}
    avg_sentence = len(words) / max(len(sentences), 1)
    syllables = sum(count_syllables(w) for w in words)
    ease = 206.835 - 1.015 * avg_sentence - 84.6 * (syllables / len(words))
    return {
        "words": len(words),
        "sentences": len(sentences),
        "avg_sentence": round(avg_sentence, 1),
        "ease": round(max(0.0, min(100.0, ease)), 1),
    }


# ------------------------------------------------------------ highlighting
_MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December|"
    "Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec"
)

# Order matters: earlier categories win when two patterns could match the same text.
_PATTERNS = [
    ("date", rf"\b(?:{_MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?\b"
             rf"|\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTHS})\.?(?:,?\s+\d{{4}})?\b"
             r"|\b\d{1,4}[/-]\d{1,2}[/-]\d{1,4}\b"),
    ("deadline", r"\b(?:deadline|no later than|due(?!\s+to\b)|expires?|expiry|overdue|"
                 r"within\s+\d+\s+(?:hours?|days?|weeks?|months?))\b"),
    ("warning", r"\b(?:warning|caution|danger|dangerous|risk|penalty|penalties|must not|do not|"
                r"never|prohibited|forbidden|illegal|fail(?:ure)? to)\b"),
    ("keyword", r"\b(?:important|required|mandatory|urgent|essential|critical|note|notice|"
                r"must|immediately)\b"),
    ("number", r"[$\u00a3\u20ac\u20b9]\s?\d[\d,]*(?:\.\d+)?|\b\d[\d,]*(?:\.\d+)?%?"),
]
_HIGHLIGHT_RE = re.compile("|".join(f"(?P<{n}>{p})" for n, p in _PATTERNS), re.IGNORECASE)
LABELS = {"date": "Date", "deadline": "Deadline", "warning": "Warning",
          "keyword": "Key term", "number": "Number"}


def highlight_html(text):
    """
    Return (safe_html, counts). The text is HTML-escaped first, then matches are
    wrapped in <mark> tags, so user input can never inject HTML.
    """
    escaped = html.escape(text, quote=False)
    counts = {name: 0 for name, _ in _PATTERNS}

    def wrap(match):
        kind = match.lastgroup
        counts[kind] += 1
        return f'<mark class="hl hl-{kind}" title="{LABELS[kind]}">{match.group(0)}</mark>'

    return _HIGHLIGHT_RE.sub(wrap, escaped), counts


def process(text):
    """Full pipeline: simplify, measure before/after, count highlights."""
    simplified = simplify_text(text)
    _, counts = highlight_html(simplified)
    return {
        "simplified": simplified,
        "before": analyse(text),
        "after": analyse(simplified),
        "highlight_count": sum(counts.values()),
    }
