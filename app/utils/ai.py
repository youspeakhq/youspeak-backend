"""
Bedrock AI client for structured outputs (instructor + AWS Bedrock).
Single provider; boto3/instructor imported lazily for fast startup.
"""
import asyncio
from typing import Any

from app.config import settings

# boto3 and instructor imported lazily in get_ai_client()

_ai_client: Any = None


class AsyncBedrockWrapper:
    """
    Wraps instructor's sync Bedrock client so it can be used with await.
    Exposes OpenAI-style .chat.completions.create(...) and forwards to client.create(...).
    """

    def __init__(self, client: Any) -> None:
        self._client = client

    @property
    def chat(self) -> "AsyncBedrockWrapper":
        return self

    @property
    def completions(self) -> "AsyncBedrockWrapper":
        return self

    async def create(self, **kwargs: Any) -> Any:
        # instructor from_provider client has .create(model=..., messages=..., response_model=...) at top level
        return await asyncio.to_thread(self._client.create, **kwargs)


def get_ai_client() -> AsyncBedrockWrapper:
    """
    Returns a cached, async-compatible Bedrock client (instructor + boto3).
    Uses settings.AWS_REGION and settings.BEDROCK_MODEL_ID; credentials from env/ECS task role.
    """
    global _ai_client
    if _ai_client is not None:
        return _ai_client

    import boto3
    import instructor
    from instructor import Mode

    sync_client = boto3.client(
        service_name="bedrock-runtime",
        region_name=settings.AWS_REGION,
    )
    model_id = settings.BEDROCK_MODEL_ID
    instructor_client = instructor.from_provider(
        f"bedrock/{model_id}",
        client=sync_client,
        mode=Mode.TOOLS,
    )
    _ai_client = AsyncBedrockWrapper(instructor_client)
    return _ai_client
