import anyio
from typing import Any

from app.config import settings
from openai import AsyncOpenAI

# boto3 and instructor imported lazily in get_ai_client() to keep app startup fast

_ai_client = None


class AsyncBedrockWrapper:
    """Wrapper to make synchronous Bedrock/Instructor calls awaitable."""

    def __init__(self, client):
        self.client = client

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    async def create(self, **kwargs) -> Any:
        # instructor from_provider client exposes .create() at top level (not .chat.completions)
        return await anyio.to_thread.run_sync(
            lambda: self.client.create(**kwargs)
        )


def get_ai_client(provider: str = "bedrock"):
    """
    Modular AI Client Factory.
    Returns an async-compatible client.
    boto3 and instructor are imported here so app startup (e.g. /health) stays fast.
    """
    global _ai_client
    if _ai_client is not None:
        return _ai_client

    if provider == "bedrock":
        import boto3
        import instructor

        sync_client = boto3.client(
            service_name="bedrock-runtime",
            region_name=settings.AWS_REGION,
        )
        # instructor.from_bedrock was removed; use from_provider (see python.useinstructor.com/integrations/bedrock)
        model_id = settings.BEDROCK_MODEL_ID
        instructor_client = instructor.from_provider(
            f"bedrock/{model_id}",
            client=sync_client,
        )
        _ai_client = AsyncBedrockWrapper(instructor_client)
    elif provider == "openai":
        import instructor

        _ai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        _ai_client = instructor.from_openai(_ai_client)
    else:
        raise ValueError(f"Unsupported AI provider: {provider}")

    return _ai_client
