"""Curriculum routes: proxy to curriculum microservice (auth here, forward with X-School-Id)."""

import json
from typing import Any, List, Optional

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, Query, Form
from fastapi.responses import JSONResponse
from uuid import UUID

from app.api import deps
from app.models.user import User
from app.services import storage_service as storage
from app.config import settings
from app.schemas.content import (
    CurriculumCreate,
    CurriculumUpdate,
    CurriculumMergeProposeRequest,
    CurriculumMergeConfirmRequest,
    CurriculumGenerateRequest,
    TopicUpdate,
)
from app.schemas.responses import SuccessResponse, PaginatedResponse, ErrorResponse, ErrorDetail

router = APIRouter()


def _get_curriculum_client(request: Request) -> httpx.AsyncClient:
    client = getattr(request.app.state, "curriculum_http", None)
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Curriculum service is not configured (CURRICULUM_SERVICE_URL)",
        )
    return client


def _headers(school_id: UUID) -> dict:
    h = {"X-School-Id": str(school_id)}
    if settings.CURRICULUM_INTERNAL_SECRET:
        h["X-Internal-Secret"] = settings.CURRICULUM_INTERNAL_SECRET
    return h


def _proxy_error_response(r: httpx.Response) -> JSONResponse:
    """Return JSONResponse with upstream status and normalized ErrorResponse envelope for API contract."""
    try:
        raw = r.json()
        if isinstance(raw, dict) and "detail" in raw:
            detail = raw["detail"]
            message = detail if isinstance(detail, str) else "; ".join(str(x) for x in detail) if isinstance(detail, list) else str(detail)
        else:
            message = str(raw) if raw is not None else (r.text or r.reason_phrase or "Upstream error")
    except Exception:
        message = r.text or r.reason_phrase or "Upstream error"
    code = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        422: "VALIDATION_ERROR",
    }.get(r.status_code, "UPSTREAM_ERROR")
    body = ErrorResponse(error=ErrorDetail(code=code, message=message)).model_dump()
    return JSONResponse(status_code=r.status_code, content=body)


@router.get("", response_model=PaginatedResponse[Any])
async def list_curriculums(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None),
    language_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(deps.require_admin),
) -> Any:
    client = _get_curriculum_client(request)
    params = {"page": page, "page_size": page_size}
    if status is not None:
        params["status"] = status
    if language_id is not None:
        params["language_id"] = language_id
    if search is not None:
        params["search"] = search
    r = await client.get(
        "/curriculums",
        params=params,
        headers=_headers(current_user.school_id),
    )
    if r.status_code >= 400:
        return _proxy_error_response(r)
    return r.json()


@router.post("", response_model=SuccessResponse[Any])
async def upload_curriculum(
    request: Request,
    title: str = Form(...),
    language_id: int = Form(...),
    description: Optional[str] = Form(None),
    class_ids_json: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(deps.require_admin),
) -> Any:
    class_ids = []
    if class_ids_json:
        try:
            class_ids = [str(UUID(cid)) for cid in json.loads(class_ids_json)]
        except (ValueError, json.JSONDecodeError):
            raise HTTPException(status_code=400, detail="Invalid class_ids format")

    content = await file.read()
    key_prefix = f"curriculums/{current_user.school_id}"
    try:
        file_url = await storage.upload(
            key_prefix,
            file.filename or "document.pdf",
            content,
            content_type=file.content_type,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    client = _get_curriculum_client(request)
    body = {
        "title": title,
        "language_id": language_id,
        "description": description,
        "class_ids": class_ids,
        "file_url": file_url,
    }
    r = await client.post(
        "/curriculums",
        json=body,
        headers={**_headers(current_user.school_id), "Content-Type": "application/json"},
    )
    if r.status_code >= 400:
        return _proxy_error_response(r)
    return r.json()


@router.post("/generate", response_model=SuccessResponse[List[Any]])
async def generate_curriculum(
    request: Request,
    generate_in: CurriculumGenerateRequest,
    current_user: User = Depends(deps.require_admin),
) -> Any:
    client = _get_curriculum_client(request)
    r = await client.post(
        "/curriculums/generate",
        json=generate_in.model_dump(),
        headers={**_headers(current_user.school_id), "Content-Type": "application/json"},
    )
    if r.status_code >= 400:
        return _proxy_error_response(r)
    return r.json()


@router.post("/{curriculum_id}/extract", response_model=SuccessResponse[List[Any]])
async def extract_topics(
    request: Request,
    curriculum_id: UUID,
    current_user: User = Depends(deps.require_admin),
) -> Any:
    client = _get_curriculum_client(request)
    r = await client.post(
        f"/curriculums/{curriculum_id}/extract",
        headers=_headers(current_user.school_id),
    )
    if r.status_code >= 400:
        return _proxy_error_response(r)
    return r.json()


@router.patch("/topics/{topic_id}", response_model=SuccessResponse[Any])
async def update_topic(
    request: Request,
    topic_id: UUID,
    topic_in: TopicUpdate,
    current_user: User = Depends(deps.require_admin),
) -> Any:
    client = _get_curriculum_client(request)
    r = await client.patch(
        f"/curriculums/topics/{topic_id}",
        json=topic_in.model_dump(exclude_unset=True),
        headers={**_headers(current_user.school_id), "Content-Type": "application/json"},
    )
    if r.status_code >= 400:
        return _proxy_error_response(r)
    return r.json()


@router.get("/{curriculum_id}", response_model=SuccessResponse[Any])
async def get_curriculum(
    request: Request,
    curriculum_id: UUID,
    current_user: User = Depends(deps.require_admin),
) -> Any:
    client = _get_curriculum_client(request)
    r = await client.get(
        f"/curriculums/{curriculum_id}",
        headers=_headers(current_user.school_id),
    )
    if r.status_code >= 400:
        return _proxy_error_response(r)
    return r.json()


@router.patch("/{curriculum_id}", response_model=SuccessResponse[Any])
async def update_curriculum(
    request: Request,
    curriculum_id: UUID,
    curriculum_in: CurriculumUpdate,
    current_user: User = Depends(deps.require_admin),
) -> Any:
    client = _get_curriculum_client(request)
    r = await client.patch(
        f"/curriculums/{curriculum_id}",
        json=curriculum_in.model_dump(exclude_unset=True),
        headers={**_headers(current_user.school_id), "Content-Type": "application/json"},
    )
    if r.status_code >= 400:
        return _proxy_error_response(r)
    return r.json()


@router.post("/{curriculum_id}/merge/propose", response_model=SuccessResponse[Any])
async def propose_merge(
    request: Request,
    curriculum_id: UUID,
    merge_in: CurriculumMergeProposeRequest,
    current_user: User = Depends(deps.require_admin),
) -> Any:
    client = _get_curriculum_client(request)
    r = await client.post(
        f"/curriculums/{curriculum_id}/merge/propose",
        json=merge_in.model_dump(),
        headers={**_headers(current_user.school_id), "Content-Type": "application/json"},
    )
    if r.status_code >= 400:
        return _proxy_error_response(r)
    return r.json()


@router.post("/{curriculum_id}/merge/confirm", response_model=SuccessResponse[Any])
async def confirm_merge(
    request: Request,
    curriculum_id: UUID,
    merge_in: CurriculumMergeConfirmRequest,
    current_user: User = Depends(deps.require_admin),
) -> Any:
    client = _get_curriculum_client(request)
    r = await client.post(
        f"/curriculums/{curriculum_id}/merge/confirm",
        json=merge_in.model_dump(),
        headers={**_headers(current_user.school_id), "Content-Type": "application/json"},
    )
    if r.status_code >= 400:
        return _proxy_error_response(r)
    return r.json()


@router.delete("/{curriculum_id}", response_model=SuccessResponse)
async def delete_curriculum(
    request: Request,
    curriculum_id: UUID,
    current_user: User = Depends(deps.require_admin),
) -> Any:
    client = _get_curriculum_client(request)
    r = await client.delete(
        f"/curriculums/{curriculum_id}",
        headers=_headers(current_user.school_id),
    )
    if r.status_code >= 400:
        return _proxy_error_response(r)
    return r.json()
