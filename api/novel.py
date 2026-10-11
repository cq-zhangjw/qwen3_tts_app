"""Novel dubbing endpoints."""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api.responses import ok
from core.config import settings
from core.database import db, now_iso
from core import novel as novel_svc
from core import worker

router = APIRouter(prefix="/api/novel", tags=["novel"])


def _load(pid: str) -> dict:
    p = db.get_novel_project(pid)
    if not p:
        raise HTTPException(status_code=404, detail="project not found")
    return p


def _recount(p: dict) -> dict:
    p["total_count"] = len(p["lines"])
    p["done_count"] = sum(1 for l in p["lines"] if l["status"] == "done")
    return p


@router.post("/projects")
async def create_project(file: UploadFile = File(...)):
    raw = (await file.read()).decode("utf-8", errors="ignore").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="empty file")
    pid = f"np_{uuid.uuid4().hex[:10]}"
    characters, lines = novel_svc.analyze_and_split_llm(raw)
    project = {
        "id": pid,
        "filename": file.filename or "novel.txt",
        "raw_text": raw,
        "characters": characters,
        "lines": lines,
        "status": "idle",
        "done_count": len(lines),
        "total_count": len(lines),
        "final_audio_url": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    db.insert_novel_project(project)
    return ok(project)


@router.get("/projects")
def list_projects():
    return ok(db.list_novel_projects())


@router.get("/projects/{pid}")
def get_project(pid: str):
    return ok(_load(pid))


class CharactersBody(BaseModel):
    characters: list[dict]


class AddCharacterBody(BaseModel):
    name: str
    voice_id: str | None = None
    instruct: str | None = None


@router.post("/projects/{pid}/characters")
def add_character(pid: str, body: AddCharacterBody):
    p = _load(pid)
    import uuid as _uuid
    colors = ["#64748b", "#6366f1", "#ec4899", "#10b981", "#f59e0b", "#8b5cf6"]
    new_c = {
        "id": f"c_{_uuid.uuid4().hex[:8]}",
        "name": body.name,
        "color": colors[len(p["characters"]) % len(colors)],
        "voice_id": body.voice_id or "preset:novel_m_uncle",
        "instruct": body.instruct,
    }
    p["characters"].append(new_c)
    db.update_novel_project(pid, {"characters": p["characters"], "updated_at": now_iso()})
    return ok(new_c)


@router.patch("/projects/{pid}/characters")
def update_characters(pid: str, body: CharactersBody):
    p = _load(pid)
    p["characters"] = body.characters
    p["updated_at"] = now_iso()
    db.update_novel_project(pid, {"characters": body.characters, "updated_at": p["updated_at"]})
    return ok(p)


@router.post("/projects/{pid}/split")
def resplit(pid: str):
    p = _load(pid)
    p["characters"], p["lines"] = novel_svc.analyze_and_split_llm(p["raw_text"])
    p["final_audio_url"] = None
    _recount(p)
    db.update_novel_project(pid, {"characters": p["characters"], "lines": p["lines"],
                                   "final_audio_url": None, "updated_at": now_iso()})
    return ok(p)


class LineBody(BaseModel):
    text: str | None = None
    character_id: str | None = None
    type: str | None = None
    instruct: str | None = None


@router.post("/projects/{pid}/lines")
def add_line(pid: str, body: LineBody):
    p = _load(pid)
    new = {
        "id": f"L{uuid.uuid4().hex[:6]}",
        "text": body.text or "",
        "character_id": body.character_id or novel_svc.NARRATOR_ID,
        "type": body.type or "narration",
        "instruct": body.instruct,
        "status": "pending", "audio_url": None, "duration_sec": None, "error": None,
    }
    p["lines"].append(new)
    _recount(p)
    db.update_novel_project(pid, {"lines": p["lines"], "updated_at": now_iso()})
    return ok(new)


@router.patch("/projects/{pid}/lines/{lid}")
def edit_line(pid: str, lid: str, body: LineBody):
    p = _load(pid)
    line = next((l for l in p["lines"] if l["id"] == lid), None)
    if not line:
        raise HTTPException(status_code=404, detail="line not found")
    for k in ("text", "character_id", "type", "instruct"):
        v = getattr(body, k)
        if v is not None:
            line[k] = v
    db.update_novel_project(pid, {"lines": p["lines"], "updated_at": now_iso()})
    return ok(line)


@router.delete("/projects/{pid}/lines/{lid}")
def remove_line(pid: str, lid: str):
    p = _load(pid)
    p["lines"] = [l for l in p["lines"] if l["id"] != lid]
    _recount(p)
    db.update_novel_project(pid, {"lines": p["lines"], "updated_at": now_iso()})
    return ok(True)


@router.post("/projects/{pid}/dub")
def start_dub(pid: str):
    p = _load(pid)
    pending = [l for l in p["lines"] if l["status"] in ("pending", "failed")]
    if not pending:
        return ok({"status": "done", "total": len(p["lines"]), "done": p["done_count"]})
    p["status"] = "dubbing"
    db.update_novel_project(pid, {"status": "dubbing", "updated_at": now_iso()})
    worker.enqueue({"kind": "novel_line", "project_id": pid})
    return ok({"status": "dubbing", "total": len(p["lines"]), "done": p["done_count"]})


@router.post("/projects/{pid}/lines/{lid}/redub")
def redub_line(pid: str, lid: str):
    p = _load(pid)
    line = next((l for l in p["lines"] if l["id"] == lid), None)
    if not line:
        raise HTTPException(status_code=404, detail="line not found")
    line["status"] = "pending"
    db.update_novel_project(pid, {"lines": p["lines"]})
    worker.enqueue({"kind": "novel_line", "project_id": pid, "line_id": lid})
    return ok({"status": "queued"})


@router.post("/projects/{pid}/assemble")
def assemble(pid: str):
    p = _load(pid)
    done = [l for l in p["lines"] if l["status"] == "done"]
    if not done:
        raise HTTPException(status_code=400, detail="no completed lines")
    p["status"] = "assembling"
    db.update_novel_project(pid, {"status": "assembling"})
    worker.enqueue({"kind": "novel_assemble", "project_id": pid})
    return ok({"status": "assembling"})


@router.get("/projects/{pid}/lines/{lid}/audio")
def line_audio(pid: str, lid: str):
    p = _load(pid)
    line = next((l for l in p["lines"] if l["id"] == lid), None)
    if not line or not line.get("audio_url"):
        raise HTTPException(status_code=404, detail="audio not ready")
    path = settings.AUDIO_DIR / "novel" / pid / f"line_{lid}.wav"
    if not path.exists():
        raise HTTPException(status_code=404, detail="file missing")
    return FileResponse(str(path), media_type="audio/wav")


@router.get("/projects/{pid}/final")
def final_audio(pid: str):
    p = _load(pid)
    path = settings.AUDIO_DIR / "novel" / pid / "final.wav"
    if not path.exists():
        raise HTTPException(status_code=404, detail="final audio not ready")
    return FileResponse(str(path), media_type="audio/wav", filename=f"{p['filename']}.wav")


@router.delete("/projects/{pid}")
def delete_project(pid: str):
    import shutil
    d = settings.AUDIO_DIR / "novel" / pid
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    db.delete_novel_project(pid)
    return ok(True)
