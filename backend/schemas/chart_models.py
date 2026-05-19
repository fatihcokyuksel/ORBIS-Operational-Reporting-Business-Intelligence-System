from __future__ import annotations

from pydantic import BaseModel, Field


class ChartDefinition(BaseModel):
    artifact_id: str
    display_name: str
    output_format: str = "jpg"
    supported_input: list[str] = Field(default_factory=lambda: ["excel"])
    source_report_type: str
    required_fields: list[str] = Field(default_factory=list)
