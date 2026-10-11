"""System & preset voices endpoints."""
from __future__ import annotations

import logging
import os

import torch
from fastapi import APIRouter

from api.responses import ok
from core.config import settings
from core.tts_engine import PRESET_VOICES, engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["system"])


def _preview_url(vid: str) -> str | None:
    """Return cached preview URL if the file already exists."""
    p = settings.AUDIO_DIR / "previews" / f"preset_{vid}.wav"
    return f"/audio/previews/preset_{vid}.wav" if p.exists() else None


@router.get("/info")
def system_info():
    gpu_ok = torch.cuda.is_available()
    gpu_name = torch.cuda.get_device_name(0) if gpu_ok else None
    presets = [
        {
            "id": f"preset:{v['id']}",
            "speaker": v["speaker"],
            "gender": v["gender"],
            "language": v["language"],
            "instruct": v.get("instruct"),
            "label_zh": v["label_zh"],
            "label_en": v["label_en"],
            "label_ja": v["label_ja"],
            "audio_url": _preview_url(v["id"]),
        }
        for v in PRESET_VOICES
    ]
    return ok({
        "app_name": "Qwen3 TTS Studio",
        "version": "1.0.0",
        "gpu_available": gpu_ok,
        "gpu_name": gpu_name,
        "models_loaded": engine.models_loaded(),
        "preset_voices": presets,
        "supported_languages": ["zh", "ja", "en", "auto"],
    })


@router.post("/prewarm")
def prewarm():
    """Warm up all preset previews in the background (idempotent, skips cached)."""
    import threading

    def _warm():
        from core.tts_engine import PRESET_VOICES as PV
        for v in PV:
            cache = settings.AUDIO_DIR / "previews" / f"preset_{v['id']}.wav"
            if cache.exists():
                continue
            try:
                voice = {"type": "preset", "speaker": v["speaker"],
                         "language": "zh", "instruct": v.get("instruct")}
                sample = "你好，很高兴认识你，欢迎来到我的世界。"
                result = engine.synthesize({"zh": voice}, text=sample, language="zh")
                engine.save_wav(result["wav"], result["sr"], f"previews/preset_{v['id']}.wav")
                logger.info("warmup preview done: %s", v["id"])
            except Exception as exc:  # noqa: BLE001
                logger.warning("warmup preview failed %s: %s", v["id"], exc)

    threading.Thread(target=_warm, daemon=True).start()
    return ok("warmup started")
