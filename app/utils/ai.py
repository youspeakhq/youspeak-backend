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
        return await anyio.to_thread.run_sync(
            lambda: self.client.chat.completions.create(**kwargs)
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
            region_name=settings.AWS_REGION
        )
        instructor_client = instructor.from_bedrock(sync_client)
        _ai_client = AsyncBedrockWrapper(instructor_client)
    elif provider == "openai":
        import instructor

        _ai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        _ai_client = instructor.from_openai(_ai_client)
    else:
        raise ValueError(f"Unsupported AI provider: {provider}")

    return _ai_client
