"""
Modular document parsing: file (URL or path) → markdown.

Docling and transformer stay in the curriculum service only. Other services (e.g. main app
for assessment uploads) must call this service’s parse-document API; they do not run
parsing locally.

Used for: curriculum topic extraction; assessment “upload questions manually” (file);
assessment “upload marking scheme” (file).
"""

import os
import httpx


def parse_document_from_path(local_path: str) -> str:
    """
    Convert a local document file to markdown using docling.
    Caller is responsible for providing a valid local path (e.g. after downloading from URL).
    """
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(local_path)
    return result.document.export_to_markdown()


async def parse_document_to_markdown(file_url_or_path: str) -> str:
    """
    Convert a document to markdown. Accepts either:
    - HTTP/HTTPS URL (downloads to temp file, converts, then deletes temp file)
    - Local file path
    Returns markdown string.
    """
    if file_url_or_path.startswith("http://") or file_url_or_path.startswith("https://"):
        async with httpx.AsyncClient() as client:
            resp = await client.get(file_url_or_path)
            resp.raise_for_status()
            suffix = ".pdf"
            for ext in (".pdf", ".docx", ".doc", ".txt"):
                if ext in file_url_or_path.lower().split("?")[0]:
                    suffix = ext
                    break
            import tempfile

            fd, temp_path = tempfile.mkstemp(suffix=suffix)
            try:
                os.write(fd, resp.content)
                os.close(fd)
                return parse_document_from_path(temp_path)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
    return parse_document_from_path(file_url_or_path)
