"""Voice management, cloning and design endpoints."""
from __future__ import annotations

import os
import uuid
from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from api.responses import ok
from core.config import settings
from core.database import db, now_iso
from core import worker

router = APIRouter(prefix="/api/voices", tags=["voices"])

_UPLOAD_DIR = settings.AUDIO_DIR / "uploads"
os.makedirs(_UPLOAD_DIR, exist_ok=True)


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


@router.delete("/{voice_id}")
def delete_voice(voice_id: str):
    voice = db.get_voice(voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail="voice not found")
    if voice.get("type") == "preset":
        raise HTTPException(status_code=400, detail="cannot delete preset voice")
    # remove preview audio if present
    audio_url = voice.get("audio_url")
    if audio_url:
        fname = os.path.basename(audio_url)
        p = settings.AUDIO_DIR / fname
        if p.exists():
            p.unlink()
    # remove clone prompt pickle
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
