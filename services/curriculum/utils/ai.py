"""Bedrock AI client for structured outputs (boto3 Converse API, no instructor)."""

import asyncio
import json
import re
from typing import Any, List, Type, TypeVar, get_origin, get_args

from config import settings

T = TypeVar("T")
_bedrock: Any = None

# Default max tokens for curriculum generate (smaller = faster). Other flows can override.
DEFAULT_MAX_TOKENS = 2048
BEDROCK_TIMEOUT_SECONDS = 75


def _get_bedrock():
    global _bedrock
    if _bedrock is None:
        import boto3
        _bedrock = boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)
    return _bedrock


def _converse_sync(model_id: str, system: str, messages: List[dict], max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    """Sync Converse call. Returns assistant text content."""
    client = _get_bedrock()
    converse_messages = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, list):
            text = next((c.get("text", "") for c in content if isinstance(c, dict) and "text" in c), str(content))
        else:
            text = content
        if role in ("user", "assistant"):
            converse_messages.append({"role": role, "content": [{"text": text}]})
    system_block = [{"text": system}] if system else []
    response = client.converse(
        modelId=model_id,
        messages=converse_messages,
        system=system_block if system_block else None,
        inferenceConfig={"maxTokens": max_tokens, "temperature": 0.2},
    )
    output = response.get("output", {})
    message_list = output.get("message", {})
    content_list = message_list.get("content", [])
    for block in content_list:
        if "text" in block:
            return block["text"]
    return ""


def _extract_json(text: str) -> str:
    """Strip markdown code fences if present and return inner string."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


def _parse_and_validate(raw: Any, response_model: type) -> Any:
    """Parse raw JSON and validate into response_model (single model or List[Model])."""
    origin = get_origin(response_model)
    if origin is list:
        (item_type,) = get_args(response_model)
        if not isinstance(raw, list):
            raw = [raw] if raw is not None else []
        return [item_type.model_validate(x) for x in raw]
    return response_model.model_validate(raw)


async def structured_completion(
    model_id: str,
    messages: List[dict],
    response_model: Type[T],
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> T:
    """
    Call Bedrock Converse and return validated Pydantic model(s).
    messages: list of {"role": "system"|"user"|"assistant", "content": str or list of dicts}.
    response_model: TopicCreate, List[TopicCreate], EvaluateSubmissionResponse, etc.
    max_tokens: cap on generated tokens (lower = faster; default 2048 for curriculum generate).
    """
    from fastapi import HTTPException

    system_parts = []
    chat_messages = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, list):
            text = next((c.get("text", "") for c in content if isinstance(c, dict) and "text" in c), str(content))
        else:
            text = content
        if role == "system":
            system_parts.append(text)
        else:
            chat_messages.append({"role": role, "content": text})

    schema_hint = "Return valid JSON only: a JSON array for a list, a JSON object for a single object. No markdown, no explanation."
    system_parts.append(schema_hint)
    system = "\n\n".join(system_parts)

    loop = asyncio.get_event_loop()
    try:
        text = await asyncio.wait_for(
            loop.run_in_executor(None, _converse_sync, model_id, system, chat_messages, max_tokens),
            timeout=BEDROCK_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=503,
            detail="AI generation timed out; try a shorter prompt or retry.",
        )
    text = _extract_json(text)
    raw = json.loads(text)
    return _parse_and_validate(raw, response_model)


def get_ai_client() -> "BedrockStructuredClient":
    """Return a client that mimics instructor's chat.completions.create interface."""
    return BedrockStructuredClient()


class ChatCompletionsShim:
    """Exposes create() with the same signature as instructor (model, response_model, messages)."""

    @property
    def completions(self) -> "ChatCompletionsShim":
        return self

    async def create(self, *, model: str, response_model: type, messages: List[dict], max_tokens: int = DEFAULT_MAX_TOKENS, **kwargs: Any) -> Any:
        return await structured_completion(model, messages, response_model, max_tokens=max_tokens)


class BedrockStructuredClient:
    """Thin wrapper so curriculum_service can keep calling .chat.completions.create(...)."""

    def __init__(self) -> None:
        self._shim = ChatCompletionsShim()

    @property
    def chat(self) -> ChatCompletionsShim:
        return self._shim
