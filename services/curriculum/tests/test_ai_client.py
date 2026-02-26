"""Unit tests for Bedrock structured completion (boto3 Converse, no instructor).

Required behavior: Converse response text is parsed as JSON and validated into
the requested Pydantic model(s). Tests mock the Converse call and assert outcomes.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

# PYTHONPATH=services/curriculum when running from repo root
from utils.ai import (
    structured_completion,
    get_ai_client,
    _extract_json,
    _parse_and_validate,
)
from schemas.content import TopicCreate, EvaluateSubmissionResponse


# --- _extract_json behavior ---


def test_extract_json_returns_plain_text_unchanged():
    """Plain JSON string without fences is returned as-is."""
    raw = '[{"title": "A", "duration_hours": 1.0}]'
    assert _extract_json(raw) == raw


def test_extract_json_strips_markdown_fence():
    """Text inside ```json ... ``` is extracted."""
    wrapped = '```json\n[{"title": "B"}]\n```'
    assert _extract_json(wrapped) == '[{"title": "B"}]'


def test_extract_json_strips_fence_without_json_label():
    """Text inside ``` ... ``` (no json label) is extracted."""
    wrapped = '```\n{"score": 80}\n```'
    assert _extract_json(wrapped) == '{"score": 80}'


# --- _parse_and_validate behavior ---


def test_parse_and_validate_list_of_models():
    """List response_model parses array into list of Pydantic models."""
    raw = [
        {"title": "Topic 1", "content": "C1", "duration_hours": 1.0, "learning_objectives": [], "order_index": 0},
        {"title": "Topic 2", "duration_hours": 2.0, "learning_objectives": ["L1"], "order_index": 1},
    ]
    result = _parse_and_validate(raw, list[TopicCreate])
    assert len(result) == 2
    assert result[0].title == "Topic 1"
    assert result[0].duration_hours == 1.0
    assert result[1].title == "Topic 2"
    assert result[1].learning_objectives == ["L1"]


def test_parse_and_validate_single_model():
    """Single response_model parses object into one Pydantic model."""
    raw = {"score": 85.0, "feedback": "Good work."}
    result = _parse_and_validate(raw, EvaluateSubmissionResponse)
    assert result.score == 85.0
    assert result.feedback == "Good work."


# --- structured_completion (mocked Converse) ---


@pytest.mark.asyncio
async def test_structured_completion_returns_list_of_topic_create():
    """When Converse returns JSON array, structured_completion returns List[TopicCreate]."""
    fake_response = '[{"title": "Generated Topic", "content": "Summary", "duration_hours": 1.5, "learning_objectives": ["Obj1"], "order_index": 0}]'
    with patch("utils.ai._converse_sync", return_value=fake_response):
        result = await structured_completion(
            "amazon.nova-lite-v1:0",
            [
                {"role": "system", "content": "You are a curriculum designer."},
                {"role": "user", "content": "Generate one topic."},
            ],
            list[TopicCreate],
        )
    assert len(result) == 1
    assert result[0].title == "Generated Topic"
    assert result[0].duration_hours == 1.5
    assert result[0].learning_objectives == ["Obj1"]


@pytest.mark.asyncio
async def test_structured_completion_returns_single_evaluate_response():
    """When Converse returns JSON object, structured_completion returns single Pydantic model."""
    fake_response = '{"score": 72.5, "feedback": "Needs improvement."}'
    with patch("utils.ai._converse_sync", return_value=fake_response):
        result = await structured_completion(
            "amazon.nova-lite-v1:0",
            [{"role": "user", "content": "Score this submission."}],
            EvaluateSubmissionResponse,
        )
    assert result.score == 72.5
    assert result.feedback == "Needs improvement."


@pytest.mark.asyncio
async def test_structured_completion_accepts_markdown_wrapped_json():
    """When Converse returns ```json ... ```, we extract and parse correctly."""
    fake_response = '```json\n[{"title": "Wrapped", "duration_hours": 1.0, "learning_objectives": [], "order_index": 0}]\n```'
    with patch("utils.ai._converse_sync", return_value=fake_response):
        result = await structured_completion(
            "amazon.nova-lite-v1:0",
            [{"role": "user", "content": "Generate."}],
            list[TopicCreate],
        )
    assert len(result) == 1
    assert result[0].title == "Wrapped"


# --- get_ai_client().chat.completions.create interface ---


@pytest.mark.asyncio
async def test_get_ai_client_chat_completions_create_returns_validated_models():
    """Required: curriculum_service calls get_ai_client().chat.completions.create(...); must return same shape."""
    fake_response = '[{"title": "API Topic", "duration_hours": 2.0, "learning_objectives": [], "order_index": 0}]'
    with patch("utils.ai._converse_sync", return_value=fake_response):
        client = get_ai_client()
        result = await client.chat.completions.create(
            model="amazon.nova-lite-v1:0",
            response_model=list[TopicCreate],
            messages=[
                {"role": "system", "content": "You are an expert."},
                {"role": "user", "content": "Generate curriculum."},
            ],
        )
    assert len(result) == 1
    assert result[0].title == "API Topic"
    assert result[0].duration_hours == 2.0
