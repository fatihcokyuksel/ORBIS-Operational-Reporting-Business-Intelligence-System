from __future__ import annotations

from pydantic import BaseModel, Field


class AnalysisDefinition(BaseModel):
    artifact_id: str
    display_name: str
    output_format: str = "pdf"
    supported_input: list[str] = Field(default_factory=lambda: ["excel"])
    source_report_type: str
    required_fields: list[str] = Field(default_factory=list)
