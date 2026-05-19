from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from schemas.api_models import WarningItem


class ArtifactGenerationRequest(BaseModel):
    artifact_type: Literal["report", "chart", "analysis"]
    artifact_id: str
    user_prompt: str | None = None
    output_format: str | None = None


class UploadedFileInfo(BaseModel):
    file_name: str
    file_path: str


class FileNormalizationSummary(BaseModel):
    file_name: str
    status: Literal["success", "warning", "failed"]
    raw_row_count: int = 0
    normalized_row_count: int = 0
    mapped_fields: list[str] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)


class MultiFileNormalizeResult(BaseModel):
    status: Literal["success", "warning", "failed"]
    normalized_records: list[dict[str, Any]] = Field(default_factory=list)
    file_summaries: list[FileNormalizationSummary] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    input_row_count: int = 0
    normalized_row_count: int = 0
    filter_summary: dict[str, Any] | None = None
    source_report_type: str | None = None


class ArtifactInfo(BaseModel):
    artifact_type: Literal["report", "chart", "analysis"]
    artifact_id: str
    display_name: str
    output_format: str
    supported_input: list[str] = Field(default_factory=list)


class ArtifactGenerationResult(BaseModel):
    status: Literal["success", "warning", "failed"]
    artifact_type: str
    artifact_id: str
    audit_run_id: str
    output_file_path: str | None = None
    output_file_name: str | None = None
    output_format: str
    summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[WarningItem] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    filter_summary: dict[str, Any] | None = None
    message: str | None = None
