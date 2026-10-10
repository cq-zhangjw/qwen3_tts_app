"""System & preset voices endpoints."""
from __future__ import annotations

import logging

import torch
from fastapi import APIRouter

from api.responses import ok
from core.tts_engine import PRESET_VOICES, engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/info")
def system_info():
    gpu_ok = torch.cuda.is_available()
    gpu_name = torch.cuda.get_device_name(0) if gpu_ok else None
    presets = [
        {"id": f"preset:{v['speaker']}", "speaker": v["speaker"],
         "label": v["label_zh"], "language": v["language"]}
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


@router.post("/preload")
def preload():
    # Touch the custom model in a background thread to warm it up.
    import threading
    threading.Thread(target=engine.custom_model, daemon=True).start()
    return ok("loading started")
