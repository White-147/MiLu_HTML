# -*- coding: utf-8 -*-
"""Parser for text-based local-model tool-call tags."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

TOOL_CALL_RE = re.compile(
    r"<tool_call>(.*?)</tool_call>",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(slots=True)
class ParsedToolCall:
    """A tool call extracted from a text tag."""

    name: str
    arguments: dict[str, Any]
    raw_arguments: str


@dataclass(slots=True)
class ParsedToolCallText:
    """Result of scanning text for tool-call tags."""

    text_before: str
    tool_calls: list[ParsedToolCall] = field(default_factory=list)


def text_contains_tool_call_tag(text: str) -> bool:
    """Return whether text appears to contain a tool-call tag."""

    return bool(text and "<tool_call>" in text.lower())


def _coerce_tool_call(payload: Any, raw: str) -> ParsedToolCall | None:
    if not isinstance(payload, dict):
        return None

    name = payload.get("name") or payload.get("tool_name")
    if not isinstance(name, str) or not name.strip():
        return None

    arguments = (
        payload.get("arguments")
        if "arguments" in payload
        else payload.get("input", {})
    )
    if isinstance(arguments, str):
        raw_arguments = arguments
        try:
            parsed_arguments = json.loads(arguments)
        except json.JSONDecodeError:
            parsed_arguments = {"value": arguments}
    elif isinstance(arguments, dict):
        parsed_arguments = arguments
        raw_arguments = json.dumps(arguments, ensure_ascii=False)
    else:
        parsed_arguments = {"value": arguments}
        raw_arguments = json.dumps(arguments, ensure_ascii=False)

    return ParsedToolCall(
        name=name.strip(),
        arguments=parsed_arguments,
        raw_arguments=raw_arguments or raw,
    )


def parse_tool_calls_from_text(text: str) -> ParsedToolCallText:
    """Parse JSON payloads wrapped in ``<tool_call>`` tags."""

    if not text:
        return ParsedToolCallText(text_before="")

    first_match = TOOL_CALL_RE.search(text)
    text_before = text[: first_match.start()] if first_match else text
    tool_calls: list[ParsedToolCall] = []

    for match in TOOL_CALL_RE.finditer(text):
        raw = match.group(1).strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if isinstance(payload, list):
            for item in payload:
                parsed = _coerce_tool_call(item, raw)
                if parsed is not None:
                    tool_calls.append(parsed)
            continue

        parsed = _coerce_tool_call(payload, raw)
        if parsed is not None:
            tool_calls.append(parsed)

    return ParsedToolCallText(text_before=text_before, tool_calls=tool_calls)
