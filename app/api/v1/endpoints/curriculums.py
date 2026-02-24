"""Curriculum routes: proxy to curriculum microservice (auth here, forward with X-School-Id)."""

import json
import os
import time
from typing import Any, List, Optional

import httpx
# #region agent log
def _debug_log_path():
    try:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        return os.path.join(root, ".cursor", "debug-ab308d.log")
    except Exception:
        return "/tmp/debug-ab308d.log"
def _dlog(location: str, message: str, data: dict, hypothesis_id: str):
    try:
        path = _debug_log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = {"sessionId": "ab308d", "timestamp": int(time.time() * 1000), "location": location, "message": message, "data": data, "hypothesisId": hypothesis_id}
        with open(path, "a") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception:
        pass
# #endregion
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
    # #region agent log
    _dlog("curriculums.py:_proxy_error_response:entry", "proxy_error_response entered", {"status_code": getattr(r, "status_code", None), "r_type": type(r).__name__}, "H3")
    # #endregion
    try:
        raw = r.json()
        if isinstance(raw, dict) and "detail" in raw:
            detail = raw["detail"]
            message = detail if isinstance(detail, str) else "; ".join(str(x) for x in detail) if isinstance(detail, list) else str(detail)
        else:
            message = str(raw) if raw is not None else (r.text or r.reason_phrase or "Upstream error")
    except Exception as e1:
        message = r.text or r.reason_phrase or "Upstream error"
        # #region agent log
        _dlog("curriculums.py:_proxy_error_response:r.json_exc", "r.json() raised", {"exc_type": type(e1).__name__, "exc_msg": str(e1)}, "H5")
        # #endregion
    code = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        422: "VALIDATION_ERROR",
    }.get(r.status_code, "UPSTREAM_ERROR")
    # #region agent log
    _dlog("curriculums.py:_proxy_error_response:before_body", "building body", {"code": code, "message_len": len(message) if message else 0}, "H2")
    # #endregion
    try:
        body = ErrorResponse(error=ErrorDetail(code=code, message=message)).model_dump()
        out = JSONResponse(status_code=r.status_code, content=body)
        # #region agent log
        _dlog("curriculums.py:_proxy_error_response:return", "returning JSONResponse", {"status_code": r.status_code}, "H2")
        # #endregion
        return out
    except Exception as e2:
        # #region agent log
        _dlog("curriculums.py:_proxy_error_response:body_exc", "ErrorResponse/model_dump or JSONResponse raised", {"exc_type": type(e2).__name__, "exc_msg": str(e2)}, "H2")
        # #endregion
        raise


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
    # #region agent log
    _dlog("curriculums.py:propose_merge:entry", "propose_merge entered", {"curriculum_id": str(curriculum_id)}, "H1")
    # #endregion
    try:
        body_dict = merge_in.model_dump()
        # #region agent log
        _dlog("curriculums.py:propose_merge:after_model_dump", "merge_in.model_dump() ok", {}, "H4")
        # #endregion
    except Exception as e:
        # #region agent log
        _dlog("curriculums.py:propose_merge:model_dump_exc", "merge_in.model_dump() raised", {"exc_type": type(e).__name__, "exc_msg": str(e)}, "H4")
        # #endregion
        raise
    client = _get_curriculum_client(request)
    r = await client.post(
        f"/curriculums/{curriculum_id}/merge/propose",
        json=body_dict,
        headers={**_headers(current_user.school_id), "Content-Type": "application/json"},
    )
    # #region agent log
    _dlog("curriculums.py:propose_merge:after_post", "client.post returned", {"r_type": type(r).__name__, "status_code": getattr(r, "status_code", None)}, "H3")
    # #endregion
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
