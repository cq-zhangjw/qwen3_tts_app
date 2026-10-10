"""Qwen3 TTS engine wrapper: lazy model loading + split/synthesize/merge.

Three model variants (loaded on first use, kept in memory):
  - custom_voice : preset speaker synthesis
  - voice_design  : instruct-driven voice design
  - base          : voice cloning (prompt extraction + clone synthesis)

All public synthesis calls are BLOCKING (torch inference) and are expected to
be invoked from the background worker thread, never from an async route.
"""
from __future__ import annotations

import logging
import os
import pickle
import threading
import time
import uuid

import numpy as np
import soundfile as sf
import torch

from core.config import settings
from core.text_split import QWEN_LANG_MAP, build_segments

logger = logging.getLogger(__name__)

PRESET_VOICES = [
    {"speaker": "Vivian", "label_zh": "明亮年轻女声", "language": "zh"},
    {"speaker": "Serena", "label_zh": "温暖柔和女声", "language": "zh"},
    {"speaker": "Uncle_Fu", "label_zh": "沉稳男声", "language": "zh"},
    {"speaker": "Dylan", "label_zh": "北京口音男声", "language": "zh"},
    {"speaker": "Eric", "label_zh": "四川口音男声", "language": "zh"},
    {"speaker": "Ryan", "label_zh": "动态英语男声", "language": "en"},
    {"speaker": "Aiden", "label_zh": "美式英语男声", "language": "en"},
    {"speaker": "Ono_Anna", "label_zh": "日语女声", "language": "ja"},
]

_CLONE_PROMPT_DIR = settings.DB_DIR / "clone_prompts"


class TTSEngine:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._models: dict[str, object] = {}
        os.makedirs(_CLONE_PROMPT_DIR, exist_ok=True)

    # ---- model loading ----
    def _load(self, key: str, path: str):
        with self._lock:
            if key in self._models:
                return self._models[key]
            from qwen_tts import Qwen3TTSModel

            logger.info("Loading Qwen3 TTS model [%s] from %s ...", key, path)
            t0 = time.time()
            model = Qwen3TTSModel.from_pretrained(
                path,
                device_map=settings.DEVICE,
                dtype=torch.bfloat16,
            )
            logger.info("Model [%s] loaded in %.1fs", key, time.time() - t0)
            self._models[key] = model
            return model

    def custom_model(self):
        return self._load("custom_voice", settings.MODEL_CUSTOM_VOICE)

    def design_model(self):
        return self._load("voice_design", settings.MODEL_VOICE_DESIGN)

    def base_model(self):
        return self._load("base", settings.MODEL_BASE)

    def models_loaded(self) -> dict:
        return {k: (k in self._models) for k in ("custom_voice", "voice_design", "base")}

    # ---- low-level synthesis (single chunk) ----
    def _synth_chunk(self, voice: dict, text: str, lang: str, instruct: str | None):
        """Synthesize one chunk according to the resolved voice record."""
        qwen_lang = QWEN_LANG_MAP.get(lang, "Auto")
        vtype = voice.get("type")
        if vtype == "preset":
            model = self.custom_model()
            kwargs = {"text": text, "language": qwen_lang, "speaker": voice["speaker"]}
            if instruct:
                kwargs["instruct"] = instruct
            wavs, sr = model.generate_custom_voice(**kwargs)
        elif vtype == "design":
            model = self.design_model()
            wavs, sr = model.generate_voice_design(
                text=text, language=qwen_lang, instruct=voice.get("instruct", "")
            )
        elif vtype == "clone":
            model = self.base_model()
            prompt = self._load_clone_prompt(voice["id"])
            wavs, sr = model.generate_voice_clone(
                text=text, language=qwen_lang, voice_clone_prompt=prompt
            )
        else:
            raise ValueError(f"unknown voice type: {vtype}")
        return np.asarray(wavs[0]).squeeze(), sr

    # ---- high-level: split -> synth -> merge ----
    def synthesize(self, voice: dict, text: str, language: str,
                   instruct: str | None = None, progress_cb=None) -> dict:
        """Full synthesis pipeline. Returns {wav, sr, segments, elapsed_sec}.

        progress_cb(step_index, total, segment_info) optional callback.
        """
        plan = build_segments(text, language, settings.MAX_CHARS_PER_SEGMENT)
        if not plan:
            raise ValueError("empty text after splitting")

        pieces: list[np.ndarray] = []
        sr = None
        t0 = time.time()
        for i, seg in enumerate(plan):
            wav, sr = self._synth_chunk(voice, seg["text"], seg["lang"], instruct)
            pieces.append(wav)
            seg["status"] = "done"
            if progress_cb:
                progress_cb(i + 1, len(plan), seg)

        merged = np.concatenate(pieces) if len(pieces) > 1 else pieces[0]
        elapsed = time.time() - t0
        return {
            "wav": merged,
            "sr": sr,
            "segments": plan,
            "elapsed_sec": round(elapsed, 2),
        }

    def save_wav(self, wav: np.ndarray, sr: int, filename: str) -> str:
        os.makedirs(settings.AUDIO_DIR, exist_ok=True)
        path = settings.AUDIO_DIR / filename
        sf.write(str(path), wav, sr)
        return f"/audio/{filename}"

    # ---- voice clone ----
    def clone_extract(self, name: str, ref_audio_path: str, ref_text: str) -> dict:
        """Extract a clone prompt and persist it. Returns the voice record (without id)."""
        model = self.base_model()
        prompt = model.create_voice_clone_prompt(
            ref_audio=ref_audio_path, ref_text=ref_text, x_vector_only_mode=False
        )
        voice_id = f"v_clone_{uuid.uuid4().hex[:10]}"
        prompt_path = _CLONE_PROMPT_DIR / f"{voice_id}.pkl"
        with open(prompt_path, "wb") as f:
            pickle.dump(prompt, f)
        return {
            "id": voice_id,
            "name": name,
            "type": "clone",
            "language": "auto",
            "ref_audio": os.path.relpath(ref_audio_path, settings.BASE_DIR) if os.path.isabs(ref_audio_path) else ref_audio_path,
            "ref_text": ref_text,
            "clone_prompt_path": str(prompt_path),
            "status": "ready",
        }

    def _load_clone_prompt(self, voice_id: str):
        # The voice record stores clone_prompt_path; resolve from db to be safe.
        from core.database import db
        voice = db.get_voice(voice_id)
        path = voice.get("clone_prompt_path") if voice else None
        if not path or not os.path.exists(path):
            # fallback by id
            path = _CLONE_PROMPT_DIR / f"{voice_id}.pkl"
        with open(path, "rb") as f:
            return pickle.load(f)

    # ---- voice design ----
    def design_create(self, name: str, instruct: str, text: str, language: str) -> dict:
        """Generate a designed voice preview. Returns voice record + preview audio."""
        model = self.design_model()
        qwen_lang = QWEN_LANG_MAP.get(language, "Auto")
        wavs, sr = model.generate_voice_design(text=text, language=qwen_lang, instruct=instruct)
        voice_id = f"v_design_{uuid.uuid4().hex[:10]}"
        filename = f"{voice_id}_preview.wav"
        audio_url = self.save_wav(np.asarray(wavs[0]).squeeze(), sr, filename)
        return {
            "id": voice_id,
            "name": name,
            "type": "design",
            "language": language,
            "instruct": instruct,
            "design_text": text,
            "audio_url": audio_url,
            "status": "ready",
        }


engine = TTSEngine()
