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
    elif kind == "novel_line":
        _run_novel_line(job)
    elif kind == "novel_assemble":
        _run_novel_assemble(job)
    else:
        logger.warning("unknown job kind: %s", kind)


def _resolve_voice_by_id(voice_id: str) -> dict:
    if voice_id.startswith("preset:"):
        vid = voice_id.split("preset:", 1)[1]
        preset = next((v for v in PRESET_VOICES if v["id"] == vid), None)
        if not preset:
            raise FileNotFoundError(f"preset voice not found: {vid}")
        return {
            "type": "preset",
            "speaker": preset["speaker"],
            "language": preset["language"],
            "instruct": preset.get("instruct"),
        }
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

    # voice_map: {"zh": voice_id, "ja": voice_id, "en": voice_id}
    vmap_ids = task.get("voice_map") or {}
    voice_map = {lang: _resolve_voice_by_id(vid) for lang, vid in vmap_ids.items() if vid}

    def progress_cb(done: int, total: int, seg: dict):
        pct = int(done / total * 95)  # leave 5% for saving
        db.update_task(task_id, {"progress": pct, "status": "running"})

    result = engine.synthesize(
        voice_map=voice_map,
        text=task["text"],
        language="auto",
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
    ref_audio = job["ref_audio"]
    # Convert WebM/other formats to WAV if needed
    if not ref_audio.lower().endswith(".wav"):
        import subprocess
        wav_path = ref_audio.rsplit(".", 1)[0] + ".wav"
        subprocess.run(["ffmpeg", "-y", "-i", ref_audio, "-ar", "24000", "-ac", "1", wav_path],
                       capture_output=True, check=True)
        ref_audio = wav_path
    created = engine.clone_extract(job["name"], ref_audio, job["ref_text"])
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
    created["status"] = "ready"
    db.update_voice(voice_id, {k: v for k, v in created.items() if k != "id"})


def _run_design(job: dict) -> None:
    voice_id = job["voice_id"]
    created = engine.design_create(job["name"], job["instruct"], job["text"], job["language"])
    fresh_id = created["id"]
    created["id"] = voice_id
    created["created_at"] = now_iso()
    # design_create saved <fresh_id>_{zh,ja,en}.wav; rename to reserved voice_id.
    import os
    for lang in ("zh", "ja", "en"):
        old_name = f"{fresh_id}_{lang}.wav"
        new_name = f"{voice_id}_{lang}.wav"
        old_path = settings.AUDIO_DIR / old_name
        new_path = settings.AUDIO_DIR / new_name
        if old_path.exists() and old_path != new_path:
            os.replace(old_path, new_path)
        created[f"audio_url_{lang}"] = f"/audio/{new_name}"
    created["audio_url"] = created["audio_url_zh"]
    created["status"] = "ready"
    db.update_voice(voice_id, {k: v for k, v in created.items() if k != "id"})


def _run_novel_line(job: dict) -> None:
    from core import novel as novel_svc
    pid = job["project_id"]
    p = db.get_novel_project(pid)
    if not p:
        return
    # pick target line: explicit line_id (redub) else first pending/failed
    line = None
    if job.get("line_id"):
        line = next((l for l in p["lines"] if l["id"] == job["line_id"]), None)
    else:
        line = next((l for l in p["lines"] if l["status"] in ("pending", "failed")), None)
    if not line:
        # no more lines → mark project ready
        db.update_novel_project(pid, {"status": "ready", "updated_at": now_iso()})
        return
    line["status"] = "running"
    db.update_novel_project(pid, {"lines": p["lines"]})
    try:
        novel_svc.dub_line(p, line)
    except Exception as exc:  # noqa: BLE001
        line["status"] = "failed"
        line["error"] = str(exc)
        logger.warning("novel line %s failed: %s", line["id"], exc)
    db.update_novel_project(pid, {
        "lines": p["lines"],
        "done_count": sum(1 for l in p["lines"] if l["status"] == "done"),
        "total_count": len(p["lines"]),
        "updated_at": now_iso(),
    })
    # chain next pending line
    nxt = next((l for l in p["lines"] if l["status"] in ("pending", "failed")), None)
    if nxt:
        enqueue({"kind": "novel_line", "project_id": pid})
    else:
        done = now_iso()
        done_count = sum(1 for l in p["lines"] if l["status"] == "done")
        total_count = len(p["lines"])
        t0 = None
        for l in p["lines"]:
            if l.get("started_at"):
                t0 = l["started_at"]
                break
        elapsed = None
        if t0:
            from datetime import datetime
            try:
                t0_dt = datetime.fromisoformat(t0)
                done_dt = datetime.fromisoformat(done)
                elapsed = round((done_dt - t0_dt).total_seconds(), 1)
            except Exception:
                pass
        # auto-assemble after all lines done
        db.update_novel_project(pid, {
            "status": "assembling", "done_count": done_count, "total_count": total_count,
            "updated_at": now_iso(), "ended_at": done, "elapsed_sec": elapsed,
        })
        enqueue({"kind": "novel_assemble", "project_id": pid})


def _run_novel_assemble(job: dict) -> None:
    from core import novel as novel_svc
    pid = job["project_id"]
    p = db.get_novel_project(pid)
    if not p:
        return
    try:
        url = novel_svc.assemble(p)
        db.update_novel_project(pid, {"status": "done", "final_audio_url": url,
                                       "updated_at": now_iso(), "ended_at": now_iso()})
    except Exception as exc:  # noqa: BLE001
        db.update_novel_project(pid, {"status": "failed", "updated_at": now_iso()})
        logger.warning("assemble failed: %s", exc)


def _handle_job_error(job: dict, message: str) -> None:
    kind = job["kind"]
    if kind == "tts":
        db.update_task(job["task_id"], {"status": "failed", "error": message, "completed_at": now_iso()})
    elif kind in ("clone", "design"):
        db.update_voice(job["voice_id"], {"status": "failed", "error": message})
