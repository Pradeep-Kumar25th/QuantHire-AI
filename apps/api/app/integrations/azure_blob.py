"""Azure Blob Storage client for resume uploads and processed artifacts."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

_blob_client: Optional["AzureBlobStorage"] = None


class AzureBlobStorage:
    """Upload and download blobs in Azure Storage (Non-Prod: dlsailnpdqc01)."""

    def __init__(
        self,
        *,
        connection_string: Optional[str] = None,
        account_name: Optional[str] = None,
        uploads_container: Optional[str] = None,
        processed_container: Optional[str] = None,
        blob_endpoint: Optional[str] = None,
    ) -> None:
        self.connection_string = connection_string or settings.azure_storage_connection_string
        self.account_name = account_name or settings.azure_storage_account_name
        self.uploads_container = uploads_container or settings.azure_storage_container
        self.processed_container = (
            processed_container or settings.azure_storage_container_processed
        )
        self.blob_endpoint = (blob_endpoint or settings.azure_storage_blob_endpoint).rstrip("/")
        self._service_client = None

    def is_configured(self) -> bool:
        return bool(self.connection_string or self.account_name)

    def _get_service_client(self):
        if self._service_client is not None:
            return self._service_client

        from azure.storage.blob import BlobServiceClient

        if self.connection_string:
            self._service_client = BlobServiceClient.from_connection_string(
                self.connection_string
            )
            return self._service_client

        if self.account_name:
            try:
                from azure.identity import DefaultAzureCredential

                account_url = self.blob_endpoint or (
                    f"https://{self.account_name}.blob.core.windows.net"
                )
                self._service_client = BlobServiceClient(
                    account_url=account_url,
                    credential=DefaultAzureCredential(),
                )
                return self._service_client
            except ImportError as exc:
                raise RuntimeError(
                    "azure-identity is required for managed-identity Blob access"
                ) from exc

        raise RuntimeError(
            "Azure Blob Storage is not configured. Set AZURE_STORAGE_CONNECTION_STRING "
            "or AZURE_STORAGE_ACCOUNT_NAME."
        )

    def _upload_bytes_sync(
        self,
        container: str,
        blob_name: str,
        data: bytes,
        content_type: Optional[str] = None,
    ) -> str:
        client = self._get_service_client()
        blob_client = client.get_blob_client(container=container, blob=blob_name)
        kwargs = {"overwrite": True}
        if content_type:
            from azure.storage.blob import ContentSettings

            kwargs["content_settings"] = ContentSettings(content_type=content_type)
        blob_client.upload_blob(data, **kwargs)
        return f"{container}/{blob_name}"

    def _download_bytes_sync(self, blob_ref: str) -> bytes:
        container, blob_name = self._parse_blob_ref(blob_ref)
        client = self._get_service_client()
        blob_client = client.get_blob_client(container=container, blob=blob_name)
        return blob_client.download_blob().readall()

    def _copy_to_processed_sync(self, source_ref: str, dest_blob_name: str) -> str:
        source_container, source_blob = self._parse_blob_ref(source_ref)
        client = self._get_service_client()
        source_url = client.get_blob_client(
            container=source_container, blob=source_blob
        ).url
        dest_client = client.get_blob_client(
            container=self.processed_container, blob=dest_blob_name
        )
        dest_client.start_copy_from_url(source_url)
        return f"{self.processed_container}/{dest_blob_name}"

    @staticmethod
    def _parse_blob_ref(blob_ref: str) -> tuple[str, str]:
        ref = blob_ref.strip().lstrip("/")
        if "/" not in ref:
            raise ValueError(f"Invalid blob reference: {blob_ref!r}")
        container, blob_name = ref.split("/", 1)
        return container, blob_name

    async def upload_resume(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: Optional[str] = None,
        *,
        resume_id: Optional[str] = None,
    ) -> str:
        """Upload raw resume bytes; returns ``container/blob`` reference."""
        safe_name = Path(filename).name or "resume.pdf"
        prefix = resume_id or str(uuid.uuid4())
        blob_name = f"resumes/{prefix}/{safe_name}"
        return await asyncio.to_thread(
            self._upload_bytes_sync,
            self.uploads_container,
            blob_name,
            file_bytes,
            content_type or "application/octet-stream",
        )

    async def download_blob(self, blob_ref: str) -> bytes:
        return await asyncio.to_thread(self._download_bytes_sync, blob_ref)

    async def move_to_processed(self, source_ref: str, *, dest_name: Optional[str] = None) -> str:
        _, source_blob = self._parse_blob_ref(source_ref)
        dest_blob_name = dest_name or f"processed/{source_blob}"
        return await asyncio.to_thread(self._copy_to_processed_sync, source_ref, dest_blob_name)


def get_blob_storage() -> AzureBlobStorage:
    global _blob_client
    if _blob_client is None:
        _blob_client = AzureBlobStorage()
    return _blob_client


def blob_storage_enabled() -> bool:
    if settings.storage_backend != "azure_blob":
        return False
    return get_blob_storage().is_configured()
