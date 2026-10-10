"""Application configuration, loaded from .env with sensible defaults."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load project-root .env (idempotent)
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    # ---- HTTP server ----
    APP_HOST: str = os.getenv("TTS_APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("TTS_APP_PORT", "9001"))

    # ---- Storage ----
    DATA_ROOT: Path = Path(os.getenv("DATA_ROOT", str(BASE_DIR / "data")))
    DB_DIR: Path = DATA_ROOT / "db"
    AUDIO_DIR: Path = DATA_ROOT / "audio"

    # ---- Frontend ----
    WEB_DIST: Path = Path(os.getenv("WEB_DIST", str(BASE_DIR / "web" / "dist")))

    # ---- Qwen3 TTS models ----
    MODEL_CUSTOM_VOICE: str = os.getenv(
        "MODEL_CUSTOM_VOICE", r"E:\models\tts\qwen3-tts-12hz-1.7b-custom_voice"
    )
    MODEL_VOICE_DESIGN: str = os.getenv(
        "MODEL_VOICE_DESIGN", r"E:\models\tts\qwen3-tts-12hz-1.7b-voice_design"
    )
    MODEL_BASE: str = os.getenv(
        "MODEL_BASE", r"E:\models\tts\qwen3-tts-12hz-1.7b-base"
    )
    DEVICE: str = os.getenv("TTS_DEVICE", "cuda:0")

    # ---- Synthesis tuning ----
    MAX_CHARS_PER_SEGMENT: int = int(os.getenv("TTS_MAX_CHARS", "120"))

    # ---- App metadata ----
    APP_NAME: str = "Qwen3 TTS Studio"
    VERSION: str = "1.0.0"

    def ensure_dirs(self) -> None:
        for d in (self.DATA_ROOT, self.DB_DIR, self.AUDIO_DIR):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
