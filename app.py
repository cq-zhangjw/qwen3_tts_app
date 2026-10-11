"""Qwen3 TTS Studio — FastAPI entrypoint.

Run:  .venv/Scripts/uvicorn app:app --host 0.0.0.0 --port 9001 --reload
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api import system, voices, tts
from core.config import settings
from core import worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("tts_studio")

settings.ensure_dirs()

app = FastAPI(title=settings.APP_NAME, version=settings.VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- API routers ----
app.include_router(system.router)
app.include_router(voices.router)
app.include_router(tts.router)


@app.on_event("startup")
def _startup():
    worker.start_worker()
    logger.info("%s v%s started on port %s", settings.APP_NAME, settings.VERSION, settings.APP_PORT)
    # Background: pre-generate cached previews for all preset voices (skips cached).
    import threading
    from core.tts_engine import PRESET_VOICES, engine

    def _warm():
        for v in PRESET_VOICES:
            cache = settings.AUDIO_DIR / "previews" / f"preset_{v['id']}.wav"
            if cache.exists():
                continue
            try:
                voice = {"type": "preset", "speaker": v["speaker"],
                         "language": "zh", "instruct": v.get("instruct")}
                result = engine.synthesize({"zh": voice}, text="你好，很高兴认识你，欢迎来到我的世界。", language="zh")
                engine.save_wav(result["wav"], result["sr"], f"previews/preset_{v['id']}.wav")
            except Exception as exc:  # noqa: BLE001
                logger.warning("warmup preview failed %s: %s", v["id"], exc)

    threading.Thread(target=_warm, daemon=True).start()


# ---- static audio ----
app.mount("/audio", StaticFiles(directory=str(settings.AUDIO_DIR)), name="audio")

# ---- frontend SPA (built by `npm run build`) ----
_dist = settings.WEB_DIST
if _dist.exists() and (_dist / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=str(_dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        # Let /audio and /api already handled; serve index.html for the SPA.
        candidate = _dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_dist / "index.html"))
else:
    @app.get("/")
    def root():
        return {
            "app": settings.APP_NAME,
            "version": settings.VERSION,
            "message": "Frontend not built yet. Run `cd web && npm install && npm run build`. API docs at /docs.",
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.APP_HOST, port=settings.APP_PORT)
