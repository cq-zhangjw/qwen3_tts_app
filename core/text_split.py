"""Mixed-language segmentation and sentence splitting for long TTS text.

Language strategy (sentence-based, robust):
  - Split text into sentences on strong punctuation (。！？!?… newline).
  - A sentence that contains ANY kana (hiragana/katakana) is Japanese,
    INCLUDING all kanji in that sentence. Real Japanese sentences always
    carry kana (particles / inflections), so kanji near kana are never zh.
  - A sentence with CJK hanzi but no kana is Chinese.
  - A sentence with Latin letters but no kana/hanzi is English.
Long runs are further chunked by sentence boundary to stay within limits.
"""
import re

_EN_RE = re.compile(r"[A-Za-z\uFF21-\uFF3A\uFF41-\uFF5A]")
_KANA_RE = re.compile(r"[\u3040-\u309F\u30A0-\u30FF\u31F0-\u31FF\uFF66-\uFF9D]")
_CJK_RE = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]")

# split-off punctuation (kept attached to the sentence before it)
_SENT_SPLIT_RE = re.compile(r"(?<=[。！？!?…\n；;])")


def detect_language(text: str) -> str:
    """Lightweight detection: kana -> ja; hanzi -> zh; otherwise en."""
    if not text:
        return "en"
    if _KANA_RE.search(text):
        return "ja"
    if _CJK_RE.search(text):
        return "zh"
    return "en"


def _classify_sentence(s: str) -> str:
    has_kana = bool(_KANA_RE.search(s))
    has_cjk = bool(_CJK_RE.search(s))
    has_en = bool(_EN_RE.search(s))
    if has_kana:
        return "ja"
    if has_cjk:
        return "zh"
    if has_en:
        return "en"
    return "neutral"


def split_language_segments(text: str, merge_en_with_cjk: bool = True) -> list[tuple[str, str]]:
    """Split mixed text into [(lang, text), ...], lang in {'zh','ja','en'}.

    Sentence-based: kana anywhere in a sentence makes the whole sentence ja,
    so Japanese kanji are no longer misclassified as Chinese.
    """
    if not text or not text.strip():
        return []

    raw = _SENT_SPLIT_RE.split(text)
    segments: list[tuple[str, str]] = []
    for part in raw:
        s = part.strip()
        if not s:
            continue
        lang = _classify_sentence(s)
        if lang == "neutral":
            # pure punctuation / whitespace: fold into previous segment
            if segments:
                prev_lang, prev_text = segments[-1]
                segments[-1] = (prev_lang, prev_text + s)
            continue
        if segments and segments[-1][0] == lang:
            segments[-1] = (lang, segments[-1][1] + s)
        else:
            segments.append((lang, s))
    return [(lang, t.strip()) for lang, t in segments if t.strip()]


def split_text(text: str, max_chars: int = 120) -> list[str]:
    """Split long text on sentence boundaries into <= max_chars chunks."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    parts: list[str] = []
    buf = ""
    for ch in text:
        buf += ch
        if ch in "。！？；…\n.!?;":
            if len(buf) >= max_chars * 0.4:
                if buf.strip():
                    parts.append(buf.strip())
                buf = ""
        elif len(buf) >= max_chars:
            parts.append(buf.strip())
            buf = ""
    if buf.strip():
        parts.append(buf.strip())

    merged: list[str] = []
    for part in parts:
        if merged and len(merged[-1]) + len(part) <= max_chars:
            merged[-1] += part
        else:
            merged.append(part)
    return merged or [text]


QWEN_LANG_MAP = {
    "zh": "Chinese",
    "ja": "Japanese",
    "en": "English",
    "auto": "Auto",
}


def build_segments(text: str, language: str, max_chars: int = 120) -> list[dict]:
    """Build the ordered synthesis plan: [{lang, text, index}, ...]."""
    if language == "auto":
        lang_runs = split_language_segments(text)
        if not lang_runs:
            lang_runs = [(detect_language(text), text)]
    else:
        lang_runs = [(language, text)]

    plan: list[dict] = []
    for lang, run in lang_runs:
        for chunk in split_text(run, max_chars):
            plan.append({"lang": lang, "text": chunk, "index": len(plan)})
    return plan
