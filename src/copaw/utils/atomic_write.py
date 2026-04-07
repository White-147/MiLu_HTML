# -*- coding: utf-8 -*-
"""Helpers for resilient file writes on Windows/dev environments."""

from __future__ import annotations

from pathlib import Path


def write_text_fallback(path: Path, content: str) -> None:
    """Write text directly to destination when atomic rename is unavailable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
