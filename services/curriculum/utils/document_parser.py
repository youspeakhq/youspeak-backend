"""
Modular document parsing: file (URL or path) → markdown/text.

Uses lightweight libs only (pymupdf4llm for PDF, docx2txt for DOCX). No torch/docling.
Other services (e.g. main app for assessment uploads) call this service's parse-document API.

Used for: curriculum topic extraction; assessment "upload questions manually" (file);
assessment "upload marking scheme" (file).
"""

import os
import tempfile
import httpx


def _suffix_from_url_or_path(file_url_or_path: str) -> str:
    """Infer file suffix from URL path or local path (query string stripped)."""
    path_part = file_url_or_path.split("?")[0].lower()
    for ext in (".pdf", ".docx", ".doc", ".txt"):
        if ext in path_part:
            return ext
    return ".pdf"


def parse_document_from_path(local_path: str) -> str:
    """
    Convert a local document file to markdown (or plain text for DOCX/TXT).
    Caller must provide a valid local path (e.g. after downloading from URL).
    """
    path_lower = local_path.lower()
    if path_lower.endswith(".pdf"):
        import pymupdf4llm
        return pymupdf4llm.to_markdown(local_path)
    if path_lower.endswith(".docx") or path_lower.endswith(".doc"):
        import docx2txt
        return docx2txt.process(local_path) or ""
    if path_lower.endswith(".txt"):
        with open(local_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    raise ValueError(f"Unsupported file type; path must end with .pdf, .docx, .doc, or .txt: {local_path}")


async def parse_document_to_markdown(file_url_or_path: str) -> str:
    """
    Convert a document to markdown (or plain text). Accepts either:
    - HTTP/HTTPS URL (downloads to temp file, converts, then deletes temp file)
    - Local file path
    Returns markdown or text string.
    """
    if file_url_or_path.startswith("http://") or file_url_or_path.startswith("https://"):
        async with httpx.AsyncClient() as client:
            resp = await client.get(file_url_or_path)
            resp.raise_for_status()
            suffix = _suffix_from_url_or_path(file_url_or_path)
            fd, temp_path = tempfile.mkstemp(suffix=suffix)
            try:
                os.write(fd, resp.content)
                os.close(fd)
                return parse_document_from_path(temp_path)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
    return parse_document_from_path(file_url_or_path)
