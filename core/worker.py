"""Background worker: serializes all GPU jobs on a single thread.

Job kinds:
  - {"kind": "tts", "task_id": ...}
  - {"kind": "clone", "voice_id": ..., "ref_audio": path, "ref_text": ..., "name": ...}
  - {"kind": "design", "voice_id": ..., "name": ..., "instruct": ..., "text": ..., "language": ...}
"""
from __future__ import annotations

import logging
import queue
import threading
import time

from core.config import settings
from core.database import db, now_iso
from core.tts_engine import PRESET_VOICES, engine

logger = logging.getLogger(__name__)

_job_queue: "queue.Queue[dict]" = queue.Queue()
_worker_started = False
_worker_lock = threading.Lock()


def enqueue(job: dict) -> None:
    _job_queue.put(job)


def start_worker() -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        _worker_started = True
    threading.Thread(target=_run, daemon=True, name="tts-worker").start()
    logger.info("TTS background worker started")


def _run() -> None:
    while True:
        try:
            job = _job_queue.get(timeout=1.0)
        except queue.Empty:
            continue
        try:
            _dispatch(job)
        except Exception as exc:  # noqa: BLE001
            logger.exception("job failed: %s", exc)
            _handle_job_error(job, str(exc))
        finally:
            _job_queue.task_done()


def _dispatch(job: dict) -> None:
    kind = job["kind"]
    if kind == "tts":
        _run_tts(job["task_id"])
    elif kind == "clone":
        _run_clone(job)
    elif kind == "design":
        _run_design(job)
    else:
        logger.warning("unknown job kind: %s", kind)


def _resolve_voice(task: dict) -> dict:
    voice_id = task["voice_id"]
    if voice_id.startswith("preset:"):
        speaker = voice_id.split("preset:", 1)[1]
        return {"type": "preset", "speaker": speaker, "language": "zh"}
    voice = db.get_voice(voice_id)
    if not voice:
        raise FileNotFoundError(f"voice not found: {voice_id}")
    if voice.get("status") != "ready":
        raise RuntimeError(f"voice not ready: {voice.get('status')}")
    return voice


def _run_tts(task_id: str) -> None:
    task = db.get_task(task_id)
    if not task:
        logger.warning("task %s vanished", task_id)
        return

    db.update_task(task_id, {"status": "running", "started_at": now_iso(), "progress": 1})
    voice = _resolve_voice(task)

    def progress_cb(done: int, total: int, seg: dict):
        pct = int(done / total * 95)  # leave 5% for saving
        db.update_task(task_id, {"progress": pct, "status": "running"})

    result = engine.synthesize(
        voice=voice,
        text=task["text"],
        language=task.get("language", "auto"),
        instruct=task.get("instruct"),
        progress_cb=progress_cb,
    )
    filename = f"{task_id}.wav"
    audio_url = engine.save_wav(result["wav"], result["sr"], filename)
    duration = round(len(result["wav"]) / result["sr"], 2)

    db.update_task(task_id, {
        "status": "completed",
        "progress": 100,
        "audio_url": audio_url,
        "duration_sec": duration,
        "elapsed_sec": result["elapsed_sec"],
        "segments": result["segments"],
        "completed_at": now_iso(),
    })


def _run_clone(job: dict) -> None:
    voice_id = job["voice_id"]
    created = engine.clone_extract(job["name"], job["ref_audio"], job["ref_text"])
    # created has a fresh voice_id; but we reserved voice_id at request time.
    # Replace the reserved placeholder with the real one (same id scheme).
    created["id"] = voice_id
    # rewrite prompt file to reserved id
    import os, pickle
    old_prompt = created.pop("clone_prompt_path")
    new_prompt = str(settings.DB_DIR / "clone_prompts" / f"{voice_id}.pkl")
    if os.path.abspath(old_prompt) != os.path.abspath(new_prompt) and os.path.exists(old_prompt):
        os.replace(old_prompt, new_prompt)
    created["clone_prompt_path"] = new_prompt
    created["created_at"] = now_iso()
    # The placeholder row already exists; overwrite fields via update.
    db.update_voice(voice_id, {k: v for k, v in created.items() if k != "id"})


def _run_design(job: dict) -> None:
    voice_id = job["voice_id"]
    created = engine.design_create(job["name"], job["instruct"], job["text"], job["language"])
    created["id"] = voice_id
    created["created_at"] = now_iso()
    # design_create saved preview to <fresh_id>_preview.wav; rename to reserved id.
    import os
    old_url = created["audio_url"]
    old_path = settings.AUDIO_DIR / os.path.basename(old_url)
    new_name = f"{voice_id}_preview.wav"
    new_path = settings.AUDIO_DIR / new_name
    if old_path.exists() and old_path != new_path:
        os.replace(old_path, new_path)
    created["audio_url"] = f"/audio/{new_name}"
    db.update_voice(voice_id, {k: v for k, v in created.items() if k != "id"})


def _handle_job_error(job: dict, message: str) -> None:
    kind = job["kind"]
    if kind == "tts":
        db.update_task(job["task_id"], {"status": "failed", "error": message, "completed_at": now_iso()})
    elif kind in ("clone", "design"):
        db.update_voice(job["voice_id"], {"status": "failed", "error": message})
