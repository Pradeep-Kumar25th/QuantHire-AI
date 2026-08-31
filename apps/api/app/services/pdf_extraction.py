"""Resume text extraction — Azure DI primary, local libraries as fallback.

Supports PDF, DOCX, DOC, TXT, and common image formats (scanned resumes).
"""

from __future__ import annotations

import asyncio
import io
import logging
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

MIN_TEXT_LENGTH = 100

# Formats accepted by the universal resume upload path
SUPPORTED_RESUME_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".txt",
        ".docx",
        ".doc",
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".tif",
        ".tiff",
        ".bmp",
    }
)

IMAGE_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
)


def extract_pdf_text_local(content: bytes) -> Tuple[str, str]:
    """Extract PDF text using local libraries (PyMuPDF → pdfplumber → pdfminer → PyPDF2)."""
    extraction_errors: list[str] = []
    resume_text = ""

    try:
        import fitz

        pdf_doc = fitz.open(stream=content, filetype="pdf")
        text_parts = [page.get_text("text") for page in pdf_doc]
        pdf_doc.close()
        resume_text = "\n".join(text_parts).strip()
        if len(resume_text) >= MIN_TEXT_LENGTH:
            return resume_text, "pymupdf"
    except Exception as exc:
        extraction_errors.append(f"PyMuPDF: {exc}")

    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text_parts = [page.extract_text() or "" for page in pdf.pages]
        resume_text = "\n".join(text_parts).strip()
        if len(resume_text) >= MIN_TEXT_LENGTH:
            return resume_text, "pdfplumber"
    except Exception as exc:
        extraction_errors.append(f"pdfplumber: {exc}")

    try:
        from pdfminer.high_level import extract_text as pdfminer_extract

        resume_text = (pdfminer_extract(io.BytesIO(content)) or "").strip()
        if len(resume_text) >= MIN_TEXT_LENGTH:
            return resume_text, "pdfminer"
    except Exception as exc:
        extraction_errors.append(f"pdfminer: {exc}")

    try:
        import PyPDF2

        pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
        text_parts = [page.extract_text() or "" for page in pdf_reader.pages]
        resume_text = "\n".join(text_parts).strip()
        if len(resume_text) >= MIN_TEXT_LENGTH:
            return resume_text, "pypdf2"
    except Exception as exc:
        extraction_errors.append(f"PyPDF2: {exc}")

    details = "; ".join(extraction_errors) or "insufficient text from all local extractors"
    raise RuntimeError(f"Local PDF extraction failed: {details}")


def _extract_docx_local(content: bytes) -> str:
    """Extract text from DOCX including paragraphs and tables."""
    try:
        import docx
    except ImportError as exc:
        raise RuntimeError("python-docx not installed") from exc

    document = docx.Document(io.BytesIO(content))
    parts: list[str] = []
    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            parts.append(paragraph.text.strip())
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    text = "\n".join(parts).strip()
    if len(text) < 20:
        raise RuntimeError("DOCX extraction returned insufficient text")
    return text


def _di_extract_sync(content: bytes) -> str:
    from app.integrations.document_intelligence import (
        document_intelligence_enabled,
        get_document_intelligence_client,
    )

    if not document_intelligence_enabled():
        raise RuntimeError("Document Intelligence is disabled")
    di = get_document_intelligence_client()
    if not di.is_configured():
        raise RuntimeError("Document Intelligence is not configured")
    return di.extract_text_from_pdf_sync(content)


def extract_pdf_text(content: bytes, *, prefer_document_intelligence: bool = True) -> Tuple[str, str]:
    """Extract PDF text synchronously. Prefer ``extract_pdf_text_async`` from FastAPI."""
    if prefer_document_intelligence:
        try:
            text = _di_extract_sync(content)
            if text and len(text.strip()) >= MIN_TEXT_LENGTH:
                logger.info(
                    "PDF extracted via Azure Document Intelligence (%s chars)",
                    len(text),
                )
                return text.strip(), "azure_document_intelligence"
        except Exception as exc:
            logger.warning("Document Intelligence extraction failed, using local fallback: %s", exc)

    text, method = extract_pdf_text_local(content)
    logger.info("PDF extracted via %s (%s chars)", method, len(text))
    return text, method


async def extract_pdf_text_async(
    content: bytes, *, prefer_document_intelligence: bool = True
) -> Tuple[str, str]:
    """Async PDF extraction — DI runs in a worker thread so the event loop stays free."""
    if prefer_document_intelligence:
        try:
            text = await asyncio.to_thread(_di_extract_sync, content)
            if text and len(text.strip()) >= MIN_TEXT_LENGTH:
                logger.info(
                    "PDF extracted via Azure Document Intelligence (%s chars)",
                    len(text),
                )
                return text.strip(), "azure_document_intelligence"
        except Exception as exc:
            logger.warning("Document Intelligence extraction failed, using local fallback: %s", exc)

    text, method = await asyncio.to_thread(extract_pdf_text_local, content)
    logger.info("PDF extracted via %s (%s chars)", method, len(text))
    return text, method


async def extract_resume_text(content: bytes, filename: str) -> Tuple[str, str]:
    """Universal resume text extraction for Azure and local paths.

    Returns ``(text, method_name)``.
    """
    from app.config import settings

    prefer_di = settings.is_azure_nonprod
    ext = Path(filename or "").suffix.lower()
    if ext not in SUPPORTED_RESUME_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {ext or '(none)'}. "
            f"Supported: {', '.join(sorted(SUPPORTED_RESUME_EXTENSIONS))}"
        )

    if ext == ".txt":
        text = content.decode("utf-8", errors="ignore").strip()
        if len(text) < 20:
            raise ValueError("Text resume is empty or too short")
        return text, "txt_decode"

    # Scanned images and legacy .doc need OCR / DI — no useful local fallback
    if ext in IMAGE_EXTENSIONS or ext == ".doc":
        try:
            text = await asyncio.to_thread(_di_extract_sync, content)
        except Exception as exc:
            raise RuntimeError(
                f"Azure Document Intelligence is required for {ext} resumes "
                f"(scanned/image or legacy Word). Error: {exc}"
            ) from exc
        if not text or len(text.strip()) < MIN_TEXT_LENGTH:
            raise RuntimeError(
                f"Document Intelligence returned insufficient text for {ext} resume"
            )
        return text.strip(), "azure_document_intelligence"

    if ext == ".docx":
        if not prefer_di:
            try:
                text = await asyncio.to_thread(_extract_docx_local, content)
                if len(text) >= MIN_TEXT_LENGTH:
                    return text, "python-docx"
            except Exception as exc:
                logger.warning("Local DOCX extraction failed, trying Document Intelligence: %s", exc)
        try:
            text = await asyncio.to_thread(_di_extract_sync, content)
            if text and len(text.strip()) >= MIN_TEXT_LENGTH:
                return text.strip(), "azure_document_intelligence"
        except Exception as exc:
            if prefer_di:
                raise RuntimeError(
                    f"Azure Document Intelligence is required for DOCX on Non-Prod. Error: {exc}"
                ) from exc
            logger.warning("Document Intelligence DOCX fallback failed: %s", exc)
        if not prefer_di:
            text = await asyncio.to_thread(_extract_docx_local, content)
            return text, "python-docx"
        raise RuntimeError("DOCX extraction returned insufficient text")

    # PDF
    return await extract_pdf_text_async(content, prefer_document_intelligence=True)
