"""Mixed-language segmentation and sentence splitting for long TTS text.

Adapted from the edge-tts reference implementation: split long text into
segments (split -> synth each -> concatenate output). Supports zh/ja/en/auto.
"""
import re

_EN_RE = re.compile(r"[A-Za-z\uFF21-\uFF3A\uFF41-\uFF5A]")
_KANA_RE = re.compile(r"[\u3040-\u309F\u30A0-\u30FF\u31F0-\u31FF\uFF66-\uFF9D]")
_CJK_RE = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]")
_STRONG_PUNCT = set("。！？!?…")
_CLAUSE_BREAK = set("。！？!?…，、；：,;:\n")


def _classify(ch: str) -> str:
    if _EN_RE.match(ch):
        return "en"
    if _KANA_RE.match(ch):
        return "kana"
    if _CJK_RE.match(ch):
        return "cjk"
    return "neutral"


def detect_language(text: str) -> str:
    """Lightweight detection: kana -> ja; hanzi -> zh; otherwise en."""
    if not text:
        return "en"
    if re.search(r"[\u3040-\u309f\u30a0-\u30ff\uff66-\uff9f]", text):
        return "ja"
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    return "en"


def split_language_segments(text: str, merge_en_with_cjk: bool = True) -> list[tuple[str, str]]:
    """Split mixed text into [(lang, text), ...], lang in {'zh','ja','en'}."""
    if not text or not text.strip():
        return []

    runs = []
    for ch in text:
        cls = _classify(ch)
        if runs and runs[-1][0] == cls and not runs[-1][2] and not runs[-1][3]:
            runs[-1] = (cls, runs[-1][1] + ch, False, False)
        else:
            runs.append((cls, ch, False, False))

    merged = []
    for cls, chars, _, _ in runs:
        if cls == "neutral":
            if merged:
                c, t, pf, sf_ = merged[-1]
                merged[-1] = (c, t + chars, pf, True)
            else:
                merged.append((cls, chars, False, False))
        else:
            merged.append((cls, chars, False, False))

    if merged and merged[0][0] == "neutral":
        _cls, chars, _, _ = merged[0]
        if len(merged) >= 2:
            c2, t2, _, sf2 = merged[1]
            merged[1] = (c2, chars + t2, True, sf2)
            merged.pop(0)
        else:
            return []

    n = len(merged)
    bounds = [False] * (n + 1)
    for i in range(n - 1):
        cls_l, t_l, _, _ = merged[i]
        cls_r, _, _, _ = merged[i + 1]
        if cls_l == "en" or cls_r == "en":
            bounds[i + 1] = True
        if t_l and t_l[-1] in _STRONG_PUNCT:
            bounds[i + 1] = True

    langs: list[str | None] = [None] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and not bounds[j + 1]:
            j += 1
        kana_idx = [k for k in range(i, j + 1) if merged[k][0] == "kana"]
        for k in range(i, j + 1):
            cls = merged[k][0]
            if cls == "kana":
                langs[k] = "ja"
            elif cls == "en":
                langs[k] = "en"
            elif cls == "cjk":
                if not kana_idx:
                    langs[k] = "zh"
                    continue
                nearest = min(kana_idx, key=lambda ki: abs(ki - k))
                lo, hi = (k, nearest) if k < nearest else (nearest, k)
                span = "".join(merged[m][1] for m in range(lo, hi + 1))
                broken = any(ch in _CLAUSE_BREAK for ch in span)
                langs[k] = "zh" if broken else "ja"
        i = j + 1

    if merge_en_with_cjk:
        changed = True
        while changed:
            changed = False
            for i in range(n):
                if langs[i] != "en":
                    continue
                _cls, chars, pf, sf_ = merged[i]
                if i > 0 and not merged[i - 1][3] and not pf and langs[i - 1] != "en":
                    c2, t2, pf2, _sf2 = merged[i - 1]
                    merged[i - 1] = (c2, t2 + chars, pf2, True)
                    merged.pop(i)
                    langs.pop(i)
                    n -= 1
                    changed = True
                    break
                if i + 1 < n and not sf_ and not merged[i + 1][2] and langs[i + 1] != "en":
                    c2, t2, _pf2, sf2 = merged[i + 1]
                    merged[i + 1] = (c2, chars + t2, True, sf2)
                    merged.pop(i)
                    langs.pop(i)
                    n -= 1
                    changed = True
                    break

    segments: list[tuple[str, str]] = []
    for i in range(n):
        lang, (_cls, chars, _, _) = langs[i], merged[i]
        if segments and segments[-1][0] == lang:
            segments[-1] = (lang, segments[-1][1] + chars)
        else:
            segments.append((lang or "zh", chars))
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


# Map our language codes to qwen_tts language argument strings.
QWEN_LANG_MAP = {
    "zh": "Chinese",
    "ja": "Japanese",
    "en": "English",
    "auto": "Auto",
}


def build_segments(text: str, language: str, max_chars: int = 120) -> list[dict]:
    """Build the ordered synthesis plan: [{lang, text, index}, ...].

    - auto: split by language first, then chunk each language run.
    - fixed language: chunk the whole text by sentence.
    """
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
