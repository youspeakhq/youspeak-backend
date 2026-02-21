import boto3
import instructor
from openai import AsyncOpenAI
from app.config import settings
from typing import Any
import anyio

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
    """
    global _ai_client
    if _ai_client is not None:
        return _ai_client

    if provider == "bedrock":
        sync_client = boto3.client(
            service_name="bedrock-runtime",
            region_name=settings.AWS_REGION
        )
        instructor_client = instructor.from_bedrock(sync_client)
        _ai_client = AsyncBedrockWrapper(instructor_client)
    elif provider == "openai":
        _ai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        # Note: instructor.from_openai(AsyncOpenAI) already returns an async client
        _ai_client = instructor.from_openai(_ai_client)
    else:
        raise ValueError(f"Unsupported AI provider: {provider}")
    
    return _ai_client
