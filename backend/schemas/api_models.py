from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict, Any

class ReportInfo(BaseModel):
    report_type: str
    display_name: str
    supported_input: List[str]
    supported_output: List[str]

class ReportListResponse(BaseModel):
    reports: List[ReportInfo]

class WarningItem(BaseModel):
    type: str
    severity: str
    message: str
    row: Optional[int] = None
    field: Optional[str] = None
    action: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class ReportGenerationResult(BaseModel):
    status: Literal["success", "warning", "failed"]
    report_type: str
    audit_run_id: str
    output_file_path: Optional[str] = None
    output_file_name: Optional[str] = None
    summary: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[WarningItem] = Field(default_factory=list)
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    filter: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
