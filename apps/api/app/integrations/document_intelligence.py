"""Azure Document Intelligence client (prebuilt-layout for resume PDFs)."""

from __future__ import annotations

import asyncio
import logging
import os
from functools import lru_cache
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

_di_client: Optional["DocumentIntelligenceService"] = None


class DocumentIntelligenceService:
    """Extract layout-aware text from PDFs using Azure DI prebuilt-layout."""

    def __init__(
        self,
        *,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        model_id: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        self.endpoint = (endpoint or settings.azure_document_intelligence_endpoint).rstrip("/")
        self.api_key = api_key or settings.azure_document_intelligence_api_key
        self.model_id = model_id or settings.azure_document_intelligence_model
        if enabled is None:
            self.enabled = settings.azure_document_intelligence_enabled
        else:
            self.enabled = enabled
        self._client = None

    def is_configured(self) -> bool:
        if not self.enabled:
            return False
        return bool(self.endpoint and (self.api_key or self._managed_identity_available()))

    @staticmethod
    def _managed_identity_available() -> bool:
        try:
            import azure.identity  # noqa: F401

            return True
        except ImportError:
            return False

    def _get_client(self):
        if self._client is not None:
            return self._client

        from azure.ai.documentintelligence import DocumentIntelligenceClient

        if self.api_key:
            from azure.core.credentials import AzureKeyCredential

            self._client = DocumentIntelligenceClient(
                endpoint=self.endpoint,
                credential=AzureKeyCredential(self.api_key),
            )
            return self._client

        from azure.identity import DefaultAzureCredential

        self._client = DocumentIntelligenceClient(
            endpoint=self.endpoint,
            credential=DefaultAzureCredential(),
        )
        return self._client

    def _extract_text_sync(self, file_bytes: bytes) -> str:
        import io

        client = self._get_client()
        poller = client.begin_analyze_document(
            self.model_id,
            body=io.BytesIO(file_bytes),
            content_type="application/octet-stream",
        )
        result = poller.result()

        parts: list[str] = []

        if getattr(result, "content", None):
            main = str(result.content).strip()
            if main:
                parts.append(main)

        # Tables often hold skills/competency matrices — append if not fully in content
        table_lines: list[str] = []
        for table in getattr(result, "tables", []) or []:
            row_cells: list[str] = []
            for cell in getattr(table, "cells", []) or []:
                content = getattr(cell, "content", None)
                if content:
                    row_cells.append(str(content).strip())
            if row_cells:
                table_lines.append(" | ".join(row_cells))
        if table_lines:
            table_block = "\n".join(table_lines).strip()
            if table_block and table_block not in "\n".join(parts):
                parts.append("\n--- Tables ---\n" + table_block)

        # Paragraph fallback when content is sparse (some OCR layouts)
        if not parts or len("".join(parts)) < 80:
            para_lines: list[str] = []
            for paragraph in getattr(result, "paragraphs", []) or []:
                content = getattr(paragraph, "content", None)
                if content:
                    para_lines.append(str(content).strip())
            if para_lines:
                parts = ["\n".join(para_lines)]

        if not parts:
            for page in getattr(result, "pages", []) or []:
                for line in getattr(page, "lines", []) or []:
                    content = getattr(line, "content", None)
                    if content:
                        parts.append(str(content))

        text = "\n".join(part for part in parts if part).strip()
        logger.info(
            "Document Intelligence extracted %s characters (model=%s)",
            len(text),
            self.model_id,
        )
        return text

    def extract_text_from_pdf_sync(self, file_bytes: bytes) -> str:
        if not self.is_configured():
            raise RuntimeError("Document Intelligence is not configured")
        return self._extract_text_sync(file_bytes)

    async def extract_text_from_pdf(self, file_bytes: bytes) -> str:
        return await asyncio.to_thread(self.extract_text_from_pdf_sync, file_bytes)


def document_intelligence_enabled() -> bool:
    raw = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENABLED", "")
    if raw.strip().lower() in ("0", "false", "no", "off"):
        return False
    return settings.azure_document_intelligence_enabled


def get_document_intelligence_client() -> DocumentIntelligenceService:
    global _di_client
    if _di_client is None:
        _di_client = DocumentIntelligenceService()
    return _di_client
