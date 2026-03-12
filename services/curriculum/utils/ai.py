"""Bedrock AI client for structured outputs (boto3 Converse API, no instructor)."""

import asyncio
import json
import logging
import random
import re
import time
from typing import Any, Dict, List, Tuple, Type, TypeVar, get_origin, get_args
from uuid import uuid4

from config import settings

# Configure structured logging
logger = logging.getLogger(__name__)

T = TypeVar("T")
_bedrock: Any = None

# Default max tokens for curriculum generate (smaller = faster). Other flows can override.
DEFAULT_MAX_TOKENS = 2048
BEDROCK_TIMEOUT_SECONDS = 75
MAX_RETRIES = 3

# Circuit breaker settings
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5  # Open circuit after 5 consecutive failures
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 60  # Try recovery after 60 seconds


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open (fail-fast mode)."""
    pass


class CircuitBreaker:
    """
    Circuit breaker pattern for Bedrock API calls.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, fail fast without calling Bedrock
    - HALF_OPEN: Testing recovery, allow one request through
    """

    def __init__(self, failure_threshold: int, recovery_timeout: int):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        current_time = time.time()

        # Check if circuit is open
        if self.state == "OPEN":
            # Check if recovery timeout has passed
            if current_time - self.last_failure_time >= self.recovery_timeout:
                logger.info("Circuit breaker entering HALF_OPEN state (testing recovery)")
                self.state = "HALF_OPEN"
            else:
                # Still open, fail fast
                logger.warning(
                    "Circuit breaker is OPEN, failing fast",
                    extra={
                        "failure_count": self.failure_count,
                        "time_until_retry": self.recovery_timeout - (current_time - self.last_failure_time),
                    }
                )
                raise CircuitBreakerOpen(
                    f"Circuit breaker is OPEN due to {self.failure_count} consecutive failures. "
                    f"Retry in {int(self.recovery_timeout - (current_time - self.last_failure_time))} seconds."
                )

        # Try to execute the function
        try:
            result = func(*args, **kwargs)

            # Success - reset failure count
            if self.state == "HALF_OPEN":
                logger.info("Circuit breaker recovery successful, returning to CLOSED state")
            self.failure_count = 0
            self.state = "CLOSED"
            return result

        except Exception:
            # Failure - increment count
            self.failure_count += 1
            self.last_failure_time = current_time

            if self.failure_count >= self.failure_threshold:
                logger.error(
                    "Circuit breaker threshold exceeded, opening circuit",
                    extra={
                        "failure_count": self.failure_count,
                        "threshold": self.failure_threshold,
                        "recovery_timeout": self.recovery_timeout,
                    }
                )
                self.state = "OPEN"
            else:
                logger.warning(
                    "Circuit breaker recorded failure",
                    extra={
                        "failure_count": self.failure_count,
                        "threshold": self.failure_threshold,
                    }
                )

            # Re-raise the original exception
            raise


# Global circuit breaker instance
_circuit_breaker = CircuitBreaker(
    failure_threshold=CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    recovery_timeout=CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
)


def _get_bedrock():
    """Get Bedrock client with connection pooling configuration."""
    global _bedrock
    if _bedrock is None:
        import boto3
        from botocore.config import Config

        config = Config(
            region_name=settings.AWS_REGION,
            max_pool_connections=50,  # Connection pooling
            retries={'max_attempts': 0},  # Handle retries ourselves
            connect_timeout=5,
            read_timeout=70,
        )
        _bedrock = boto3.client("bedrock-runtime", config=config)
        logger.info(
            "Bedrock client initialized",
            extra={"region": settings.AWS_REGION, "model": settings.BEDROCK_MODEL_ID}
        )
    return _bedrock


def _converse_sync(
    model_id: str,
    system: str,
    messages: List[dict],
    max_tokens: int = DEFAULT_MAX_TOKENS,
    correlation_id: str = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Sync Converse call. Returns (text_content, metadata).

    Returns:
        Tuple of (assistant text, response metadata dict with request_id, usage, etc.)
    """
    client = _get_bedrock()
    converse_messages = []

    # Build messages
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

    # Log request
    prompt_preview = messages[0]["content"][:300] if messages else "empty"
    logger.info(
        "Bedrock request starting",
        extra={
            "correlation_id": correlation_id,
            "model_id": model_id,
            "max_tokens": max_tokens,
            "message_count": len(converse_messages),
            "prompt_preview": prompt_preview,
        }
    )

    # Make API call
    response = client.converse(
        modelId=model_id,
        messages=converse_messages,
        system=system_block if system_block else None,
        inferenceConfig={"maxTokens": max_tokens, "temperature": 0.2},
    )

    # Extract metadata
    metadata = {
        "request_id": response.get("ResponseMetadata", {}).get("RequestId", "unknown"),
        "http_status": response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0),
        "stop_reason": response.get("stopReason", "unknown"),
        "usage": response.get("usage", {}),
        "latency_ms": response.get("metrics", {}).get("latencyMs", 0),
    }

    # Extract text
    output = response.get("output", {})
    message_list = output.get("message", {})
    content_list = message_list.get("content", [])

    text = ""
    for block in content_list:
        if "text" in block:
            text = block["text"]
            break

    # Log response
    logger.info(
        "Bedrock response received",
        extra={
            "correlation_id": correlation_id,
            "request_id": metadata["request_id"],
            "response_length": len(text),
            "usage": metadata["usage"],
            "latency_ms": metadata["latency_ms"],
            "stop_reason": metadata["stop_reason"],
        }
    )

    # Log warning if empty
    if not text or not text.strip():
        logger.error(
            "Bedrock returned empty content",
            extra={
                "correlation_id": correlation_id,
                "request_id": metadata["request_id"],
                "metadata": metadata,
                "prompt_preview": prompt_preview,
                "raw_output": output,
            }
        )

    return text, metadata


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
    Call Bedrock Converse with retry logic and return validated Pydantic model(s).

    messages: list of {"role": "system"|"user"|"assistant", "content": str or list of dicts}.
    response_model: TopicCreate, List[TopicCreate], EvaluateSubmissionResponse, etc.
    max_tokens: cap on generated tokens (lower = faster; default 2048 for curriculum generate).

    Implements:
    - Exponential backoff with jitter (Netflix pattern)
    - Structured logging with correlation IDs
    - Rich error diagnostics with AWS request IDs
    """
    from fastapi import HTTPException

    correlation_id = str(uuid4())

    # Separate system and chat messages
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
    metadata = {}

    # Retry loop with exponential backoff + jitter
    for attempt in range(MAX_RETRIES):
        try:
            # Check circuit breaker before making call
            try:
                text, metadata = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        _circuit_breaker.call,
                        _converse_sync,
                        model_id,
                        system,
                        chat_messages,
                        max_tokens,
                        correlation_id
                    ),
                    timeout=BEDROCK_TIMEOUT_SECONDS,
                )
            except CircuitBreakerOpen as e:
                # Circuit breaker is open, fail fast
                logger.error(
                    "Request blocked by circuit breaker",
                    extra={"correlation_id": correlation_id}
                )
                raise HTTPException(
                    status_code=503,
                    detail=f"AI service temporarily unavailable (circuit breaker open). {str(e)} Correlation ID: {correlation_id}",
                )

            # Success - break out of retry loop
            break

        except asyncio.TimeoutError:
            if attempt < MAX_RETRIES - 1:
                # Exponential backoff: 1s, 2s, 4s with ±50% jitter
                base_delay = 2 ** attempt
                jitter = random.uniform(0.5, 1.5)
                delay = base_delay * jitter

                logger.warning(
                    "Bedrock request timed out, retrying",
                    extra={
                        "correlation_id": correlation_id,
                        "attempt": attempt + 1,
                        "max_retries": MAX_RETRIES,
                        "delay_seconds": delay,
                    }
                )
                await asyncio.sleep(delay)
            else:
                # Final attempt failed
                logger.error(
                    "Bedrock request timed out after all retries",
                    extra={
                        "correlation_id": correlation_id,
                        "attempts": MAX_RETRIES,
                    }
                )
                raise HTTPException(
                    status_code=503,
                    detail=f"AI generation timed out after {MAX_RETRIES} attempts. Correlation ID: {correlation_id}",
                )
        except Exception as e:
            # Check if it's a retryable error (connection issues, transient errors)
            error_name = type(e).__name__
            is_retryable = any(
                err in error_name
                for err in [
                    "ConnectionClosed",
                    "ConnectionReset",
                    "ConnectionError",
                    "BrokenPipe",
                    "EndpointConnectionError",
                    "ReadTimeout",
                    "ConnectTimeout",
                ]
            )

            if is_retryable and attempt < MAX_RETRIES - 1:
                # Retry transient connection errors with exponential backoff
                base_delay = 2 ** attempt
                jitter = random.uniform(0.5, 1.5)
                delay = base_delay * jitter

                logger.warning(
                    "Bedrock request failed with retryable error, retrying",
                    extra={
                        "correlation_id": correlation_id,
                        "error_type": error_name,
                        "error": str(e),
                        "attempt": attempt + 1,
                        "max_retries": MAX_RETRIES,
                        "delay_seconds": delay,
                    }
                )
                await asyncio.sleep(delay)
            else:
                # Non-retryable error or final retry attempt failed
                logger.error(
                    "Bedrock request failed",
                    extra={
                        "correlation_id": correlation_id,
                        "error_type": error_name,
                        "error": str(e),
                        "is_retryable": is_retryable,
                        "attempts": attempt + 1,
                    }
                )
                raise HTTPException(
                    status_code=503,
                    detail=f"AI service error: {error_name}. Correlation ID: {correlation_id}",
                )

    # Extract JSON from response
    text = _extract_json(text)

    # Check for empty response
    if not text or not text.strip():
        logger.error(
            "Bedrock returned empty response after JSON extraction",
            extra={
                "correlation_id": correlation_id,
                "request_id": metadata.get("request_id", "unknown"),
                "raw_text_length": len(text),
            }
        )
        raise HTTPException(
            status_code=503,
            detail=(
                f"AI returned empty response. "
                f"Request ID: {metadata.get('request_id', 'unknown')}. "
                f"Correlation ID: {correlation_id}"
            ),
        )

    # Parse JSON
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(
            "Bedrock returned invalid JSON",
            extra={
                "correlation_id": correlation_id,
                "request_id": metadata.get("request_id", "unknown"),
                "error_position": e.pos,
                "text_preview": text[:500],
            }
        )
        raise HTTPException(
            status_code=503,
            detail=(
                f"AI returned invalid JSON at character {e.pos}. "
                f"Preview: {text[:200]}... "
                f"Request ID: {metadata.get('request_id', 'unknown')}. "
                f"Correlation ID: {correlation_id}"
            ),
        )

    # Validate and return
    try:
        return _parse_and_validate(raw, response_model)
    except Exception as e:
        logger.error(
            "Pydantic validation failed on AI response",
            extra={
                "correlation_id": correlation_id,
                "request_id": metadata.get("request_id", "unknown"),
                "validation_error": str(e),
                "raw_data_preview": str(raw)[:500],
            }
        )
        raise HTTPException(
            status_code=503,
            detail=(
                f"AI response validation failed: {str(e)}. "
                f"Request ID: {metadata.get('request_id', 'unknown')}. "
                f"Correlation ID: {correlation_id}"
            ),
        )


def get_ai_client() -> "BedrockStructuredClient":
    """Return a client that mimics instructor's chat.completions.create interface."""
    return BedrockStructuredClient()


class ChatCompletionsShim:
    """Exposes create() with the same signature as instructor (model, response_model, messages)."""

    @property
    def completions(self) -> "ChatCompletionsShim":
        return self

    async def create(self, *, model: str, response_model: type, messages: List[dict], max_tokens: int = DEFAULT_MAX_TOKENS, **_kwargs: Any) -> Any:
        return await structured_completion(model, messages, response_model, max_tokens=max_tokens)


class BedrockStructuredClient:
    """Thin wrapper so curriculum_service can keep calling .chat.completions.create(...)."""

    def __init__(self) -> None:
        self._shim = ChatCompletionsShim()

    @property
    def chat(self) -> ChatCompletionsShim:
        return self._shim
