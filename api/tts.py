"""Text-to-speech async tasks / history endpoints."""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api.responses import ok
from core.config import settings
from core.database import db, now_iso
from core.tts_engine import PRESET_VOICES
from core import worker

router = APIRouter(prefix="/api/tts", tags=["tts"])


class TTSBody(BaseModel):
    text: str
    voice_map: dict[str, str]   # {"zh": voice_id, "ja": voice_id, "en": voice_id}


def _voice_display(voice_id: str) -> tuple[str, str]:
    if voice_id.startswith("preset:"):
        vid = voice_id.split("preset:", 1)[1]
        preset = next((v for v in PRESET_VOICES if v["id"] == vid), None)
        return (preset["label_zh"] if preset else vid), "preset"
    v = db.get_voice(voice_id)
    if not v:
        raise HTTPException(status_code=404, detail=f"voice not found: {voice_id}")
    return v.get("name", voice_id), v.get("type")


@router.post("")
def create_task(body: TTSBody):
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    vmap = body.voice_map or {}
    missing = [lang for lang in ("zh", "ja", "en") if not vmap.get(lang)]
    if missing:
        raise HTTPException(status_code=400, detail=f"missing voices: {','.join(missing)}")

    labels = []
    for lang in ("zh", "ja", "en"):
        name, _ = _voice_display(vmap[lang])
        labels.append(f"{lang}:{name}")

    task_id = f"t_{uuid.uuid4().hex[:10]}"
    task = {
        "id": task_id,
        "text": text,
        "voice_map": vmap,
        "voice_name": " / ".join(labels),
        "language": "auto",
        "status": "pending",
        "progress": 0,
        "error": None,
        "audio_url": None,
        "duration_sec": None,
        "elapsed_sec": None,
        "segments": [],
        "created_at": now_iso(),
        "started_at": None,
        "completed_at": None,
    }
    db.insert_task(task)
    worker.enqueue({"kind": "tts", "task_id": task_id})
    return ok({"id": task_id, "status": "pending", "progress": 0})


@router.get("/tasks")
def list_tasks(status: str | None = None, voice_id: str | None = None,
               page: int = 1, page_size: int = 20):
    return ok(db.list_tasks(status=status, voice_id=voice_id, page=page, page_size=page_size))


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return ok(task)


@router.get("/tasks/{task_id}/audio")
def task_audio(task_id: str):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    if task.get("status") != "completed" or not task.get("audio_url"):
        raise HTTPException(status_code=404, detail="audio not ready")
    fname = os.path.basename(task["audio_url"])
    path = settings.AUDIO_DIR / fname
    if not path.exists():
        raise HTTPException(status_code=404, detail="audio file missing")
    return FileResponse(str(path), media_type="audio/wav", filename=fname)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    audio_url = task.get("audio_url")
    if audio_url:
        p = settings.AUDIO_DIR / os.path.basename(audio_url)
        if p.exists():
            p.unlink()
    db.delete_task(task_id)
    return ok(True)
