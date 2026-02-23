"""
Bedrock AI client for structured outputs (instructor + AWS Bedrock).
Uses BEDROCK_JSON mode so any Bedrock model (Nova, Gemma, etc.) works without native tool use.
boto3/instructor imported lazily for fast startup.
"""
import os
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

    import instructor
    from instructor import Mode

    # Let instructor create the boto3 client so we avoid "multiple values for argument 'client'" in from_bedrock.
    # Ensure region is set for the auto-created client (ECS/task role use default creds).
    region = settings.AWS_REGION
    if os.environ.get("AWS_DEFAULT_REGION") != region:
        os.environ["AWS_DEFAULT_REGION"] = region
    if os.environ.get("AWS_REGION") != region:
        os.environ["AWS_REGION"] = region

    model_id = settings.BEDROCK_MODEL_ID
    # BEDROCK_JSON: model-agnostic; no native tool/function calling required (works with Nova, Gemma, etc.)
    instructor_client = instructor.from_provider(
        f"bedrock/{model_id}",
        mode=Mode.BEDROCK_JSON,
    )
    _ai_client = AsyncBedrockWrapper(instructor_client)
    return _ai_client
