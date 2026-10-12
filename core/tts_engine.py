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
    # ---- zh female ----
    {"id": "p_zh_f_bright", "speaker": "Vivian", "gender": "female", "language": "zh",
     "instruct": "用活泼明亮、充满朝气的少女语气朗读",
     "label_zh": "明亮少女 (Vivian)", "label_en": "Bright Girl (Vivian)", "label_ja": "明るい少女 (Vivian)"},
    {"id": "p_zh_f_gentle", "speaker": "Serena", "gender": "female", "language": "zh",
     "instruct": "用温柔舒缓、娓娓道来的语气朗读",
     "label_zh": "温柔姐姐 (Serena)", "label_en": "Gentle Sister (Serena)", "label_ja": "優しいお姉さん (Serena)"},
    {"id": "p_zh_f_mature", "speaker": "Serena", "gender": "female", "language": "zh",
     "instruct": "用知性冷静、成熟优雅的御姐语气朗读",
     "label_zh": "知性御姐 (Serena)", "label_en": "Mature Lady (Serena)", "label_ja": "知的な女性 (Serena)"},
    {"id": "p_zh_f_cool", "speaker": "Vivian", "gender": "female", "language": "zh",
     "instruct": "用清冷疏离、空灵飘渺的语气朗读",
     "label_zh": "清冷仙子 (Vivian)", "label_en": "Cool Fairy (Vivian)", "label_ja": "クールな妖精 (Vivian)"},
    # ---- zh male ----
    {"id": "p_zh_m_uncle", "speaker": "Uncle_Fu", "gender": "male", "language": "zh",
     "instruct": "用沉稳厚重、值得信赖的大叔语气朗读",
     "label_zh": "沉稳大叔 (Uncle_Fu)", "label_en": "Steady Uncle (Uncle_Fu)", "label_ja": "落ち着いた叔父 (Uncle_Fu)"},
    {"id": "p_zh_m_warm", "speaker": "Uncle_Fu", "gender": "male", "language": "zh",
     "instruct": "用温和亲切、干净清朗的青年男子语气朗读",
     "label_zh": "温暖青年 (Uncle_Fu)", "label_en": "Warm Youth (Uncle_Fu)", "label_ja": "温かい青年 (Uncle_Fu)"},
    {"id": "p_zh_m_cold", "speaker": "Uncle_Fu", "gender": "male", "language": "zh",
     "instruct": "用冷峻克制、严肃威严的男主语气朗读",
     "label_zh": "冷峻男主 (Uncle_Fu)", "label_en": "Cold Hero (Uncle_Fu)", "label_ja": "クールな主人公 (Uncle_Fu)"},
    {"id": "p_zh_m_beijing", "speaker": "Dylan", "gender": "male", "language": "zh",
     "instruct": "用北京口音、抑扬顿挫的说书人语气朗读",
     "label_zh": "北京说书人 (Dylan)", "label_en": "Beijing Storyteller (Dylan)", "label_ja": "北京語の語り部 (Dylan)"},
    {"id": "p_zh_m_sichuan", "speaker": "Eric", "gender": "male", "language": "zh",
     "instruct": "用四川口音、朴实幽默的语气朗读",
     "label_zh": "四川小哥 (Eric)", "label_en": "Sichuan Guy (Eric)", "label_ja": "四川の若者 (Eric)"},
    # ---- ja ----
    {"id": "p_ja_f_anna", "speaker": "Ono_Anna", "gender": "female", "language": "ja",
     "instruct": "明るく自然な女性の声で朗読する",
     "label_zh": "小野安娜 (Ono_Anna)", "label_en": "Ono Anna (Ono_Anna)", "label_ja": "小野アンナ (Ono_Anna)"},
    # ---- en ----
    {"id": "p_en_m_dynamic", "speaker": "Ryan", "gender": "male", "language": "en",
     "instruct": "Read with a dynamic, energetic male voice",
     "label_zh": "动态男声 (Ryan)", "label_en": "Dynamic Male (Ryan)", "label_ja": "ダイナミック男声 (Ryan)"},
    {"id": "p_en_m_american", "speaker": "Aiden", "gender": "male", "language": "en",
     "instruct": "Read with an American-accented male voice",
     "label_zh": "美式男声 (Aiden)", "label_en": "American Male (Aiden)", "label_ja": "アメリカ男声 (Aiden)"},
    {"id": "p_en_f_bright", "speaker": "Vivian", "gender": "female", "language": "en",
     "instruct": "Read with a bright, cheerful young female voice",
     "label_zh": "明亮女声 (Vivian)", "label_en": "Bright Female (Vivian)", "label_ja": "明るい女声 (Vivian)"},
    {"id": "p_en_f_gentle", "speaker": "Serena", "gender": "female", "language": "en",
     "instruct": "Read with a warm, gentle female voice",
     "label_zh": "温柔女声 (Serena)", "label_en": "Gentle Female (Serena)", "label_ja": "優しい女声 (Serena)"},
]

_CLONE_PROMPT_DIR = settings.DB_DIR / "clone_prompts"


class TTSEngine:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._infer_lock = threading.RLock()  # serializes all GPU inference
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
                text=text, language=qwen_lang, voice_clone_prompt=prompt,
                non_streaming_mode=True,
            )
        else:
            raise ValueError(f"unknown voice type: {vtype}")
        return np.asarray(wavs[0]).squeeze(), sr

    # ---- high-level: split -> synth -> merge ----
    def synthesize(self, voice_map: dict, text: str, language: str = "auto",
                   instruct: str | None = None, progress_cb=None) -> dict:
        """Full synthesis pipeline. Returns {wav, sr, segments, elapsed_sec}.

        voice_map: {"zh": voice_record, "ja": voice_record, "en": voice_record}.
        Each segment is synthesized with the voice mapped to its detected language
        (falls back to the zh voice when a slot is missing).
        progress_cb(step_index, total, segment_info) optional callback.
        """
        with self._infer_lock:
            plan = build_segments(text, language, settings.MAX_CHARS_PER_SEGMENT)
            if not plan:
                raise ValueError("empty text after splitting")

            default_voice = voice_map.get("zh") or next(iter(voice_map.values()))
            pieces: list[np.ndarray] = []
            sr = None
            t0 = time.time()
            for i, seg in enumerate(plan):
                voice = voice_map.get(seg["lang"], default_voice)
                seg_kwargs = voice.get("instruct") if not instruct else instruct
                wav, sr = self._synth_chunk(voice, seg["text"], seg["lang"], seg_kwargs)
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
    def clone_extract(self, name: str, ref_audio_path: str, ref_text: str, language: str = "zh") -> dict:
        """Extract a clone prompt and persist it. Returns the voice record (without id)."""
        with self._infer_lock:
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
            "language": language,
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
        """Generate a designed voice preview in zh/ja/en so the same voice
        character can be used across languages in mixed synthesis."""
        voice_id = f"v_design_{uuid.uuid4().hex[:10]}"
        samples = {
            "zh": text or "你好，欢迎来到我的世界。",
            "ja": "こんにちは、よろしくお願いします。",
            "en": "Hello, welcome to my world. Nice to meet you.",
        }
        audio_urls: dict[str, str] = {}
        with self._infer_lock:
            model = self.design_model()
            for lang, sample in samples.items():
                qwen_lang = QWEN_LANG_MAP.get(lang, "Auto")
                wavs, sr = model.generate_voice_design(text=sample, language=qwen_lang, instruct=instruct)
                fname = f"{voice_id}_{lang}.wav"
                audio_urls[lang] = self.save_wav(np.asarray(wavs[0]).squeeze(), sr, fname)
        return {
            "id": voice_id,
            "name": name,
            "type": "design",
            "language": language,
            "instruct": instruct,
            "design_text": text,
            "audio_url": audio_urls.get("zh"),
            "audio_url_zh": audio_urls.get("zh"),
            "audio_url_ja": audio_urls.get("ja"),
            "audio_url_en": audio_urls.get("en"),
            "status": "ready",
        }


engine = TTSEngine()
