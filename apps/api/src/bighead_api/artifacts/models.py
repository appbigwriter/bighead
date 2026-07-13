from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator

from bighead_api.identity.models import ApiModel


class QuarantineStatus(StrEnum):
    INITIATED = "initiated"
    PENDING = "pending"
    CLEAN = "clean"
    REJECTED = "rejected"


class UploadInitiateRequest(ApiModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=3, max_length=160)
    size_bytes: int = Field(ge=1, le=52_428_800)
    checksum_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")

    @field_validator("filename")
    @classmethod
    def safe_filename(cls, value: str) -> str:
        if value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError("filename must not contain path separators")
        return value

    @field_validator("checksum_sha256")
    @classmethod
    def normalize_checksum(cls, value: str) -> str:
        return value.lower()


class UploadInitiateResponse(ApiModel):
    artifact_id: UUID
    path: str
    upload_url: str
    expires_at: datetime
    required_headers: dict[str, str]
    quarantine_status: QuarantineStatus = QuarantineStatus.INITIATED


class UploadConfirmRequest(ApiModel):
    checksum_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")

    @field_validator("checksum_sha256")
    @classmethod
    def normalize_checksum(cls, value: str) -> str:
        return value.lower()


class ArtifactStatusResponse(ApiModel):
    artifact_id: UUID
    quarantine_status: QuarantineStatus


class ArtifactDownloadResponse(ApiModel):
    artifact_id: UUID
    download_url: str
    expires_at: datetime
