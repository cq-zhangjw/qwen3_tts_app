"""MooFile-backed data access for voices and tasks collections."""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Any

from utils.moofile_util import MooFileUtil
from core.config import settings

_COLLECTION_LOCK = threading.RLock()

# Collection names
VOICES = "voices"
TASKS = "tasks"


class _DB:
    def __init__(self) -> None:
        self.util = MooFileUtil(str(settings.DB_DIR))
        self._init_collections()

    def _init_collections(self) -> None:
        settings.ensure_dirs()
        for name in (VOICES, TASKS):
            if not self.util.database_exists(name):
                self.util.create_database(name)

    # ---- voices ----
    def list_voices(self, vtype: str | None = None, keyword: str | None = None) -> list[dict]:
        query: dict[str, Any] = {}
        if vtype:
            query["type"] = vtype
        rows = self.util.query_data(VOICES, query, indexes=["id"])
        if keyword:
            kw = keyword.lower()
            rows = [r for r in rows if kw in r.get("name", "").lower()]
        return sorted(rows, key=lambda r: r.get("created_at", ""), reverse=True)

    def get_voice(self, voice_id: str) -> dict | None:
        rows = self.util.query_data(VOICES, {"id": voice_id}, indexes=["id"])
        return rows[0] if rows else None

    def insert_voice(self, voice: dict) -> None:
        with _COLLECTION_LOCK:
            self.util.insert_data(VOICES, [voice], indexes=["id"])

    def update_voice(self, voice_id: str, update: dict) -> None:
        with _COLLECTION_LOCK:
            self.util.update_data(VOICES, {"id": voice_id}, update, indexes=["id"])

    def delete_voice(self, voice_id: str) -> None:
        with _COLLECTION_LOCK:
            self.util.delete_data(VOICES, {"id": voice_id}, indexes=["id"])

    # ---- tasks ----
    def list_tasks(self, status: str | None = None, voice_id: str | None = None,
                   page: int = 1, page_size: int = 20) -> dict:
        query: dict[str, Any] = {}
        if status:
            query["status"] = status
        if voice_id:
            query["voice_id"] = voice_id
        rows = self.util.query_data(TASKS, query, indexes=["id"])
        rows = sorted(rows, key=lambda r: r.get("created_at", ""), reverse=True)
        total = len(rows)
        start = (page - 1) * page_size
        end = start + page_size
        return {"total": total, "page": page, "page_size": page_size, "items": rows[start:end]}

    def get_task(self, task_id: str) -> dict | None:
        rows = self.util.query_data(TASKS, {"id": task_id}, indexes=["id"])
        return rows[0] if rows else None

    def insert_task(self, task: dict) -> None:
        with _COLLECTION_LOCK:
            self.util.insert_data(TASKS, [task], indexes=["id"])

    def update_task(self, task_id: str, update: dict) -> None:
        with _COLLECTION_LOCK:
            self.util.update_data(TASKS, {"id": task_id}, update, indexes=["id"])

    def delete_task(self, task_id: str) -> None:
        with _COLLECTION_LOCK:
            self.util.delete_data(TASKS, {"id": task_id}, indexes=["id"])


db = _DB()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
