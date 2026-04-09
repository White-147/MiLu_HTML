# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from copaw.app.routers.local_models import (
    StartServerRequest,
    start_llamacpp_server,
)
from copaw.providers.models import ModelSlotConfig


class FakeLocalModelManager:
    def __init__(self, port: int = 43123) -> None:
        self.port = port
        self.started_model_id: str | None = None

    async def setup_server(self, model_id: str) -> int:
        self.started_model_id = model_id
        return self.port


class FakeProviderManager:
    def __init__(self) -> None:
        self.active_model = ModelSlotConfig(
            provider_id="yunwu",
            model="claude-sonnet-4-6",
        )
        self.last_update: tuple[str, dict] | None = None

    def update_provider(self, provider_id: str, config: dict) -> None:
        self.last_update = (provider_id, config)


@pytest.mark.asyncio
async def test_start_llamacpp_server_does_not_override_active_model() -> None:
    local_manager = FakeLocalModelManager()
    provider_manager = FakeProviderManager()
    payload = StartServerRequest(model_id="AgentScope/CoPaw-Flash-2B-Q8_0")

    response = await start_llamacpp_server(
        payload=payload,
        model_manager=local_manager,
        provider_manager=provider_manager,
    )

    assert local_manager.started_model_id == payload.model_id
    assert response.port == 43123
    assert response.model_name == payload.model_id
    assert provider_manager.active_model == ModelSlotConfig(
        provider_id="yunwu",
        model="claude-sonnet-4-6",
    )
    assert provider_manager.last_update == (
        "copaw-local",
        {
            "base_url": "http://127.0.0.1:43123/v1",
            "extra_models": [
                {
                    "id": payload.model_id,
                    "name": payload.model_id,
                },
            ],
        },
    )
