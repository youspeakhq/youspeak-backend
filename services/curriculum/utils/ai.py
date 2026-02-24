"""Bedrock AI client for structured outputs (instructor + AWS Bedrock)."""

import os
import asyncio
from typing import Any

from config import settings

_ai_client: Any = None


class AsyncBedrockWrapper:
    def __init__(self, client: Any) -> None:
        self._client = client

    @property
    def chat(self) -> "AsyncBedrockWrapper":
        return self

    @property
    def completions(self) -> "AsyncBedrockWrapper":
        return self

    async def create(self, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self._client.create, **kwargs)


def get_ai_client() -> AsyncBedrockWrapper:
    global _ai_client
    if _ai_client is not None:
        return _ai_client

    import instructor
    from instructor import Mode

    region = settings.AWS_REGION
    if os.environ.get("AWS_DEFAULT_REGION") != region:
        os.environ["AWS_DEFAULT_REGION"] = region
    if os.environ.get("AWS_REGION") != region:
        os.environ["AWS_REGION"] = region

    model_id = settings.BEDROCK_MODEL_ID
    instructor_client = instructor.from_provider(
        f"bedrock/{model_id}",
        mode=Mode.BEDROCK_JSON,
    )
    _ai_client = AsyncBedrockWrapper(instructor_client)
    return _ai_client
