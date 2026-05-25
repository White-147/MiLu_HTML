# -*- coding: utf-8 -*-
"""Local model runtime manager.

The public MiLu build keeps the local-model settings surface but does not
bundle a llama.cpp runtime or GGUF model catalog. This manager provides a
stable no-runtime implementation so the web app can boot and report the local
runtime as unavailable instead of failing at import time.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class DownloadSource(str, Enum):
    """Supported model download source identifiers."""

    AUTO = "auto"
    MODELSCOPE = "modelscope"
    HUGGINGFACE = "huggingface"


class LocalModelInfo(BaseModel):
    """Local model metadata returned to the console."""

    id: str
    name: str
    size_bytes: int = Field(default=0)
    downloaded: bool = Field(default=False)
    description: Optional[str] = None
    source: Optional[str] = None
    local_path: Optional[str] = None


def _idle_progress() -> dict[str, object]:
    return {
        "status": "idle",
        "model_name": None,
        "downloaded_bytes": 0,
        "total_bytes": None,
        "speed_bytes_per_sec": 0.0,
        "source": None,
        "error": None,
        "local_path": None,
    }


class LocalModelManager:
    """No-runtime local model manager used by the public desktop build."""

    DEFAULT_LLAMA_CPP_RELEASE_TAG = "b4761"
    DEFAULT_LLAMA_CPP_BASE_URLS = ()

    _instance: "LocalModelManager | None" = None

    def __init__(self, models_root: Path | None = None) -> None:
        self.models_root = models_root

    @classmethod
    def get_instance(cls) -> "LocalModelManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def check_llamacpp_installability(self) -> tuple[bool, str]:
        return (
            False,
            "Local model runtime is not bundled in this public build.",
        )

    def check_llamacpp_installation(self) -> tuple[bool, str]:
        return False, "llama.cpp runtime is not installed."

    def get_llamacpp_server_status(self) -> dict[str, object]:
        return {
            "running": False,
            "port": None,
            "model_name": None,
            "pid": None,
        }

    def is_llamacpp_server_transitioning(self) -> bool:
        return False

    async def check_llamacpp_server_ready(
        self,
        timeout: float = 120.0,
    ) -> bool:
        return False

    async def has_update(self) -> bool:
        return False

    async def start_llamacpp_download(self) -> bool:
        raise RuntimeError(
            "Local model runtime download is not available in this build.",
        )

    def get_llamacpp_download_progress(self) -> dict[str, object]:
        return _idle_progress()

    def cancel_llamacpp_download(self) -> None:
        return None

    async def setup_server(self, model_id: str) -> int:
        raise RuntimeError(
            f"Local model server is unavailable; cannot start {model_id}.",
        )

    async def shutdown_server(self) -> None:
        return None

    def get_recommended_models(self) -> list[LocalModelInfo]:
        return []

    def is_model_downloaded(self, model_name: str) -> bool:
        return False

    def list_downloaded_models(self) -> list[LocalModelInfo]:
        return []

    def start_model_download(
        self,
        model_name: str,
        source: DownloadSource | None = None,
    ) -> None:
        raise RuntimeError(
            f"Local model download is not available in this build: "
            f"{model_name}",
        )

    def get_model_download_progress(self) -> dict[str, object]:
        return _idle_progress()

    def cancel_model_download(self) -> None:
        return None

    def remove_downloaded_model(self, model_name: str) -> None:
        return None
