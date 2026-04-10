# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from .models import CronJobSpec

logger = logging.getLogger(__name__)


class CronExecutor:
    def __init__(
        self,
        *,
        runner: Any,
        channel_manager: Any,
        task_tracker: Any = None,
        chat_manager: Any = None,
    ):
        self._runner = runner
        self._channel_manager = channel_manager
        self._task_tracker = task_tracker
        self._chat_manager = chat_manager

    def _build_request(self, job: CronJobSpec) -> Dict[str, Any]:
        """Build the agent request dict from job spec."""
        if job.task_type == "text" and job.text:
            req: Dict[str, Any] = {
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": job.text.strip()},
                        ],
                    },
                ],
            }
        else:
            assert job.request is not None
            req = job.request.model_dump(mode="json")

        target_user_id = job.dispatch.target.user_id
        target_session_id = job.dispatch.target.session_id
        req["user_id"] = target_user_id or "cron"
        req["session_id"] = target_session_id or f"cron:{job.id}"
        return req

    async def execute(self, job: CronJobSpec) -> None:
        """Execute one job once.

        For console channel jobs with TaskTracker available, routes
        through ConsoleChannel.stream_one + TaskTracker so the frontend
        can reconnect and see real-time streaming in the chat UI.

        For other channels or when TaskTracker is unavailable, falls
        back to the original stream_query + channel_manager path.
        """
        target_user_id = job.dispatch.target.user_id
        target_session_id = job.dispatch.target.session_id
        dispatch_meta: Dict[str, Any] = dict(job.dispatch.meta or {})
        logger.info(
            "cron execute: job_id=%s channel=%s task_type=%s "
            "target_user_id=%s target_session_id=%s",
            job.id,
            job.dispatch.channel,
            job.task_type,
            target_user_id[:40] if target_user_id else "",
            target_session_id[:40] if target_session_id else "",
        )

        req = self._build_request(job)

        use_console_streaming = (
            job.dispatch.channel == "console"
            and self._task_tracker is not None
            and self._chat_manager is not None
        )

        if use_console_streaming:
            await self._execute_via_console(job, req)
        else:
            await self._execute_classic(job, req, dispatch_meta)

    async def _execute_via_console(
        self,
        job: CronJobSpec,
        req: Dict[str, Any],
    ) -> None:
        """Execute through TaskTracker + ConsoleChannel for real-time
        streaming in the chat UI. The frontend can reconnect to see
        live progress.

        Builds a proper AgentRequest with typed content objects so
        that ConsoleChannel.stream_one's debounce logic correctly
        detects text content (it uses getattr, not dict access).
        """
        from ..channels.base import TextContent, ContentType

        target_user_id = req.get("user_id", "cron")
        session_id = req.get("session_id", f"cron:{job.id}")

        console_channel = await self._channel_manager.get_channel("console")
        if console_channel is None:
            logger.warning(
                "cron execute: console channel not found, "
                "falling back to classic path job_id=%s",
                job.id,
            )
            dispatch_meta: Dict[str, Any] = dict(job.dispatch.meta or {})
            await self._execute_classic(job, req, dispatch_meta)
            return

        user_text = self._extract_user_text(job)
        chat_name = user_text[:10] if user_text else job.name
        chat = await self._chat_manager.get_or_create_chat(
            session_id,
            target_user_id,
            "console",
            name=chat_name,
        )

        content_parts = [
            TextContent(type=ContentType.TEXT, text=user_text or " "),
        ]
        channel_meta = {
            "session_id": session_id,
            "user_id": target_user_id,
        }
        agent_request = console_channel.build_agent_request_from_user_content(
            channel_id="console",
            sender_id=target_user_id,
            session_id=session_id,
            content_parts=content_parts,
            channel_meta=channel_meta,
        )
        agent_request.channel_meta = channel_meta

        tracker = self._task_tracker

        async def _run_via_tracker() -> None:
            queue, _is_new = await tracker.attach_or_start(
                chat.id,
                agent_request,
                console_channel.stream_one,
            )
            async for _ in tracker.stream_from_queue(queue, chat.id):
                pass

        try:
            await asyncio.wait_for(
                _run_via_tracker(),
                timeout=job.runtime.timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "cron execute (console): job_id=%s timed out after %ss",
                job.id,
                job.runtime.timeout_seconds,
            )
            raise
        except asyncio.CancelledError:
            logger.info(
                "cron execute (console): job_id=%s cancelled", job.id,
            )
            raise

    @staticmethod
    def _extract_user_text(job: CronJobSpec) -> str:
        """Extract plain user text from a cron job spec."""
        if job.task_type == "text" and job.text:
            return job.text.strip()
        if job.request and job.request.input:
            inp = job.request.input
            items = inp if isinstance(inp, list) else [inp]
            for item in items:
                if isinstance(item, dict):
                    content = item.get("content", [])
                elif hasattr(item, "content"):
                    content = list(item.content or [])
                else:
                    continue
                for c in (content if isinstance(content, list) else [content]):
                    if isinstance(c, dict) and c.get("type") == "text":
                        return c.get("text", "")
                    if hasattr(c, "type") and c.type == "text":
                        return getattr(c, "text", "")
        return ""

    async def _execute_classic(
        self,
        job: CronJobSpec,
        req: Dict[str, Any],
        dispatch_meta: Dict[str, Any],
    ) -> None:
        """Original execution path: stream_query + channel_manager."""
        target_user_id = job.dispatch.target.user_id
        target_session_id = job.dispatch.target.session_id

        async def _run() -> None:
            async for event in self._runner.stream_query(req):
                await self._channel_manager.send_event(
                    channel=job.dispatch.channel,
                    user_id=target_user_id,
                    session_id=target_session_id,
                    event=event,
                    meta=dispatch_meta,
                )

        try:
            await asyncio.wait_for(
                _run(),
                timeout=job.runtime.timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "cron execute: job_id=%s timed out after %ss",
                job.id,
                job.runtime.timeout_seconds,
            )
            raise
        except asyncio.CancelledError:
            logger.info("cron execute: job_id=%s cancelled", job.id)
            raise
