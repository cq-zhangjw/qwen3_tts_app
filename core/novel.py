"""Novel dubbing: character analysis, line splitting, per-line dubbing, assembly."""
from __future__ import annotations

import logging
import os
import re
import uuid

import numpy as np
import soundfile as sfx

from core.config import settings
from core.database import db, now_iso
from core.tts_engine import PRESET_VOICES, engine
from core.text_split import build_segments

logger = logging.getLogger(__name__)

NARRATOR_ID = "c_narrator"
PALETTE = ["#6366f1", "#ec4899", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444", "#14b8a6"]

# quoted dialogue forms: "..."  "..." 「...」
_DIALOGUE_RE = re.compile(r"[“\"]([^”\"]{1,200})[”\"]")
# clause boundary + 2-3 char subject + (within 18 chars) a speech cue
_SPEAKER_RE = re.compile(
    r"(?:[。！？!?\n，、：]|^)\s*([一-龥]{2,3})[一-龥，。！？、]{0,18}?"
    r"(?:说道|笑道|说|道|问|开口|念道|念|嘟囔|笑|轻声|低声)"
)
_STOP_NAMES = {"我们", "你们", "他们", "她们", "自己", "这个", "那个", "什么", "怎么",
               "缓缓", "微微", "低声", "轻声", "大声", "小声", "于是", "然后", "忽然",
               "突然", "原来", "终于", "此时", "这时", "于是", "因为", "所以", "但是",
               "一个", "两个", "三个", "先生捋", "林清", "婉儿", "Suzanne"}
# environment / onomatopoeia markers
_SFX_RE = re.compile(r"(敲门声|沙沙声|砰砰砰|轰隆|哗啦|滴答|吱呀|叮咚|哐当)")


def _new_char(name: str, color: str, voice_id: str | None = None, instruct: str | None = None, gender: str | None = None) -> dict:
    return {
        "id": f"c_{uuid.uuid4().hex[:8]}",
        "name": name,
        "color": color,
        "voice_id": voice_id or "preset:novel_m_uncle",
        "instruct": instruct,
        "gender": gender,
    }


def _chunk_text(text: str, max_chars: int = 2500) -> list[str]:
    """Split long text into chunk-sized pieces on sentence boundaries."""
    parts = re.split(r"(?<=[。！？!?…\n])", text)
    chunks, buf = [], ""
    for p in parts:
        if len(buf) + len(p) > max_chars and buf:
            chunks.append(buf)
            buf = p
        else:
            buf += p
    if buf.strip():
        chunks.append(buf)
    return chunks


def analyze_characters_llm(text: str) -> list[dict]:
    """Step 2: LLM extract characters only (chunked)."""
    try:
        from utils.llm_util import llm_analyze_chunk
        chunks = _chunk_text(text)
        char_map: dict[str, dict] = {}
        for ch in chunks:
            result = llm_analyze_chunk(ch, known_characters=list(char_map.keys()) or None)
            for c in result.get("characters", []):
                name = c.get("name", "").strip()
                if name and name not in char_map:
                    char_map[name] = c
        out = []
        for i, (name, c) in enumerate(char_map.items()):
            is_narr = name == "旁白"
            out.append({
                "id": NARRATOR_ID if is_narr else f"c_{uuid.uuid4().hex[:8]}",
                "name": name,
                "color": "#64748b" if is_narr else PALETTE[i % len(PALETTE)],
                "voice_id": "preset:novel_m_uncle",
                "instruct": "用平稳舒缓、清晰的叙述语气朗读" if is_narr else None,
                "gender": c.get("gender"),
            })
        # narrator always present
        if not any(x["name"] == "旁白" for x in out):
            out.append({
                "id": NARRATOR_ID, "name": "旁白", "color": "#64748b",
                "voice_id": "preset:novel_m_uncle",
                "instruct": "用平稳舒缓、清晰的叙述语气朗读", "gender": None,
            })
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM analyze failed, fallback: %s", exc)
        return analyze_characters(text)


def split_lines_llm(text: str, characters: list[dict]) -> list[dict]:
    """Step 3: LLM split lines, assigning to known characters."""
    try:
        from utils.llm_util import llm_analyze_chunk
        known = [c["name"] for c in characters]
        name_to_id = {c["name"]: c["id"] for c in characters}
        chunks = _chunk_text(text)
        raw_lines: list[dict] = []
        for ch in chunks:
            result = llm_analyze_chunk(ch, known_characters=known)
            raw_lines.extend(result.get("lines", []))
        out = []
        for i, l in enumerate(raw_lines, 1):
            speaker = (l.get("speaker") or "旁白").strip()
            cid = name_to_id.get(speaker, NARRATOR_ID)
            ltype = l.get("type", "narration")
            if ltype not in ("narration", "dialogue", "sfx"):
                ltype = "narration"
            out.append({
                "id": f"L{i:04d}",
                "text": (l.get("text") or "").strip(),
                "character_id": cid,
                "type": ltype,
                "instruct": l.get("instruct") or None,
                "status": "pending",
                "audio_url": None,
                "duration_sec": None,
                "error": None,
            })
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM split failed, fallback: %s", exc)
        return split_lines(text, characters)


def analyze_and_split_llm(text: str) -> tuple[list[dict], list[dict]]:
    """LLM-driven: returns (characters, lines). Chunks long text; falls back
    to rule-based on any error."""
    try:
        from utils.llm_util import llm_analyze_chunk
        chunks = _chunk_text(text)
        char_map: dict[str, dict] = {}
        all_lines: list[dict] = []
        known = None
        for ch in chunks:
            result = llm_analyze_chunk(ch, known_characters=list(char_map.keys()) or None)
            for c in result.get("characters", []):
                name = c.get("name", "").strip()
                if name and name not in char_map:
                    char_map[name] = c
            known = list(char_map.keys())
            for l in result.get("lines", []):
                speaker = (l.get("speaker") or "旁白").strip()
                if speaker not in char_map:
                    char_map[speaker] = {"name": speaker, "gender": "unknown"}
                ltype = l.get("type", "narration")
                if ltype not in ("narration", "dialogue", "sfx"):
                    ltype = "narration"
                all_lines.append({
                    "text": l.get("text", "").strip(),
                    "speaker": speaker,
                    "type": ltype,
                    "instruct": l.get("instruct") or None,
                })
        # build character objects
        characters = [{
            "id": NARRATOR_ID if n == "旁白" else f"c_{uuid.uuid4().hex[:8]}",
            "name": n,
            "color": "#64748b" if n == "旁白" else PALETTE[len(chars_list) % len(PALETTE)],
            "voice_id": "preset:novel_m_uncle",
            "instruct": "用平稳舒缓、清晰的叙述语气朗读" if n == "旁白" else None,
            "gender": char_map[n].get("gender"),
        } for n, chars_list in [(n, list(char_map.keys())) for n in char_map]]
        # assign line ids and character_id
        name_to_id = {c["name"]: c["id"] for c in characters}
        lines = []
        for i, l in enumerate(all_lines, 1):
            lines.append({
                "id": f"L{i:04d}",
                "text": l["text"],
                "character_id": name_to_id.get(l["speaker"], NARRATOR_ID),
                "type": l["type"],
                "instruct": l["instruct"],
                "status": "pending",
                "audio_url": None,
                "duration_sec": None,
                "error": None,
            })
        return characters, lines
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM split failed, falling back to rule-based: %s", exc)
        chars = analyze_characters(text)
        lines = split_lines(text, chars)
        return chars, lines


def analyze_characters(text: str) -> list[dict]:
    """Return [narrator, ...detected speakers].

    Heuristic: collect subjects before speech verbs, keep those that recur
    (real character names repeat; one-off adverbs don't).
    """
    chars = [{
        "id": NARRATOR_ID, "name": "旁白", "color": "#64748b",
        "voice_id": "preset:novel_m_uncle",
        "instruct": "用平稳舒缓、清晰的叙述语气朗读",
    }]
    candidates: dict[str, int] = {}
    for m in _SPEAKER_RE.finditer(text):
        name = m.group(1)
        if name in _STOP_NAMES:
            continue
        candidates[name] = candidates.get(name, 0) + 1
    # also handle "XX：" / "XX说" after a quote
    for m in re.finditer(r"[”\"]\s*([一-龥]{2,3})(?:说道|说|道|问|笑)", text):
        name = m.group(1)
        if name not in _STOP_NAMES:
            candidates[name] = candidates.get(name, 0) + 1
    # keep names that recur >=2 times in the whole text
    ordered = [name for name, cnt in candidates.items() if text.count(name) >= 2]
    seen = set()
    for name in ordered:
        if name and name not in seen:
            seen.add(name)
            chars.append(_new_char(name, PALETTE[len(chars) % len(PALETTE)]))
    return chars


def split_lines(text: str, characters: list[dict]) -> list[dict]:
    """Split text into editable lines, classified and character-assigned."""
    non_narrator = [c for c in characters if c["id"] != NARRATOR_ID]
    lines: list[dict] = []
    # split into sentences on strong punctuation, keep delimiters
    parts = re.split(r"(?<=[。！？!?…\n])", text)
    idx = 0
    for part in parts:
        s = part.strip()
        if not s:
            continue
        # merge a fragment that is only punctuation/quotes into previous line
        if re.fullmatch(r"[”\"’'\s。，、；：…！？!?]+", s) and lines:
            lines[-1]["text"] += s
            continue
        idx += 1
        line_id = f"L{idx:04d}"
        is_dialogue = ("“" in s) or ("”" in s) or ('"' in s)
        is_sfx = bool(_SFX_RE.search(s)) and not is_dialogue
        character_id = NARRATOR_ID
        if is_dialogue:
            # find a non-narrator character whose name appears in this line
            for c in non_narrator:
                if c["name"] in s:
                    character_id = c["id"]
                    break
            if character_id == NARRATOR_ID and non_narrator:
                character_id = non_narrator[0]["id"]
        ltype = "dialogue" if is_dialogue else ("sfx" if is_sfx else "narration")
        lines.append({
            "id": line_id,
            "text": s,
            "character_id": character_id,
            "type": ltype,
            "instruct": None,
            "status": "pending",
            "audio_url": None,
            "duration_sec": None,
            "error": None,
        })
    return lines


def resolve_voice(voice_id: str) -> dict:
    if voice_id.startswith("preset:"):
        vid = voice_id.split("preset:", 1)[1]
        preset = next((v for v in PRESET_VOICES if v["id"] == vid), None)
        if not preset:
            raise FileNotFoundError(f"preset voice not found: {vid}")
        return {"type": "preset", "speaker": preset["speaker"],
                "language": preset["language"], "instruct": preset.get("instruct")}
    v = db.get_voice(voice_id)
    if not v:
        raise FileNotFoundError(f"voice not found: {voice_id}")
    return v


def _project_dir(pid: str) -> str:
    d = settings.AUDIO_DIR / "novel" / pid
    os.makedirs(d, exist_ok=True)
    return str(d)


def dub_line(project: dict, line: dict) -> None:
    """Synthesize one line. Mutates line status/audio fields; caller persists."""
    char = next((c for c in project["characters"] if c["id"] == line["character_id"]), None)
    voice_id = char["voice_id"] if char else "preset:novel_m_uncle"
    voice = resolve_voice(voice_id)
    instruct = line.get("instruct") or (char.get("instruct") if char else None)
    if instruct and voice.get("type") == "preset":
        voice["instruct"] = instruct

    result = engine.synthesize(
        voice_map={"zh": voice, "ja": voice, "en": voice},
        text=line["text"],
        language="auto",
    )
    d = _project_dir(project["id"])
    fname = f"line_{line['id']}.wav"
    path = os.path.join(d, fname)
    sfx.write(path, result["wav"], result["sr"])
    line["audio_url"] = f"/audio/novel/{project['id']}/{fname}"
    line["duration_sec"] = round(len(result["wav"]) / result["sr"], 2)
    line["status"] = "done"
    line["error"] = None


def assemble(project: dict) -> str:
    """Concatenate all done lines in order; return final audio URL."""
    done = [l for l in project["lines"] if l["status"] == "done" and l.get("audio_url")]
    if not done:
        raise RuntimeError("no completed lines to assemble")
    pieces = []
    sr = None
    for line in done:
        fname = os.path.basename(line["audio_url"])
        path = os.path.join(_project_dir(project["id"]), fname)
        wav, sr = sfx.read(path)
        pieces.append(wav)
        # 0.3s silence gap between lines
        pieces.append(np.zeros(int(sr * 0.3), dtype=wav.dtype))
    merged = np.concatenate(pieces)
    out = os.path.join(_project_dir(project["id"]), "final.wav")
    sfx.write(out, merged, sr)
    return f"/audio/novel/{project['id']}/final.wav"
