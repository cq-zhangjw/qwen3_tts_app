"""Voice management, cloning and design endpoints."""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from api.responses import ok
from core.config import settings
from core.database import db, now_iso
from core import worker
from core.tts_engine import PRESET_VOICES, engine

router = APIRouter(prefix="/api/voices", tags=["voices"])

_UPLOAD_DIR = settings.AUDIO_DIR / "uploads"
os.makedirs(_UPLOAD_DIR, exist_ok=True)
_PREVIEW_DIR = settings.AUDIO_DIR / "previews"
os.makedirs(_PREVIEW_DIR, exist_ok=True)

_PREVIEW_SAMPLES = {
    "zh": "你好，很高兴认识你，欢迎来到我的小世界。",
    "en": "Hello, nice to meet you. Welcome to my little world.",
    "ja": "こんにちは、はじめまして。よろしくお願いします。",
}


@router.get("")
def list_voices(type: str | None = None, keyword: str | None = None):
    rows = db.list_voices(vtype=type, keyword=keyword)
    return ok(rows)


@router.get("/{voice_id}")
def get_voice(voice_id: str):
    voice = db.get_voice(voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail="voice not found")
    return ok(voice)


def _resolve_voice_record(voice_id: str) -> dict:
    """Resolve either a preset voice id (preset:Speaker) or a stored custom voice."""
    if voice_id.startswith("preset:"):
        speaker = voice_id.split("preset:", 1)[1]
        preset = next((v for v in PRESET_VOICES if v["speaker"] == speaker), None)
        if not preset:
            raise HTTPException(status_code=404, detail="preset voice not found")
        return {"type": "preset", "speaker": speaker, "language": preset["language"]}
    voice = db.get_voice(voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail="voice not found")
    return voice


@router.post("/{voice_id}/preview")
def preview_voice(voice_id: str):
    """Synthesize (and cache) a short preview for any voice, including presets."""
    voice = _resolve_voice_record(voice_id)
    cache_key = voice_id.replace(":", "_")
    cache_file = _PREVIEW_DIR / f"{cache_key}.wav"
    if cache_file.exists():
        return ok({"audio_url": f"/audio/previews/{cache_key}.wav", "cached": True})

    lang = voice.get("language") or "zh"
    if voice.get("type") == "preset":
        lang = voice.get("language", "zh")
    sample = _PREVIEW_SAMPLES.get(lang, _PREVIEW_SAMPLES["zh"])
    result = engine.synthesize(voice=voice, text=sample, language=lang)
    engine.save_wav(result["wav"], result["sr"], f"previews/{cache_key}.wav")
    return ok({"audio_url": f"/audio/previews/{cache_key}.wav", "cached": False})


@router.delete("/{voice_id}")
def delete_voice(voice_id: str):
    voice = db.get_voice(voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail="voice not found")
    if voice.get("type") == "preset":
        raise HTTPException(status_code=400, detail="cannot delete preset voice")
    audio_url = voice.get("audio_url")
    if audio_url:
        p = settings.AUDIO_DIR / os.path.basename(audio_url)
        if p.exists():
            p.unlink()
    pp = voice.get("clone_prompt_path")
    if pp and os.path.exists(pp):
        try:
            os.remove(pp)
        except OSError:
            pass
    db.delete_voice(voice_id)
    return ok(True)


# ---- voice clone ----
@router.post("/clone")
async def create_clone(
    file: UploadFile = File(...),
    name: str = Form(...),
    ref_text: str = Form(...),
):
    ext = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    voice_id = f"v_clone_{uuid.uuid4().hex[:10]}"
    save_path = _UPLOAD_DIR / f"{voice_id}_ref{ext}"
    with open(save_path, "wb") as f:
        f.write(await file.read())

    placeholder = {
        "id": voice_id,
        "name": name,
        "type": "clone",
        "language": "auto",
        "description": "",
        "ref_audio": str(save_path),
        "ref_text": ref_text,
        "audio_url": None,
        "status": "processing",
        "error": None,
        "created_at": now_iso(),
    }
    db.insert_voice(placeholder)
    worker.enqueue({
        "kind": "clone",
        "voice_id": voice_id,
        "ref_audio": str(save_path),
        "ref_text": ref_text,
        "name": name,
    })
    return ok({"id": voice_id, "name": name, "status": "processing"})


# ---- voice design ----
class DesignBody(BaseModel):
    name: str
    instruct: str
    text: str
    language: str = "zh"


@router.post("/design")
def create_design(body: DesignBody):
    voice_id = f"v_design_{uuid.uuid4().hex[:10]}"
    placeholder = {
        "id": voice_id,
        "name": body.name,
        "type": "design",
        "language": body.language,
        "description": body.instruct,
        "instruct": body.instruct,
        "design_text": body.text,
        "audio_url": None,
        "status": "processing",
        "error": None,
        "created_at": now_iso(),
    }
    db.insert_voice(placeholder)
    worker.enqueue({
        "kind": "design",
        "voice_id": voice_id,
        "name": body.name,
        "instruct": body.instruct,
        "text": body.text,
        "language": body.language,
    })
    return ok({"id": voice_id, "name": body.name, "status": "processing"})
