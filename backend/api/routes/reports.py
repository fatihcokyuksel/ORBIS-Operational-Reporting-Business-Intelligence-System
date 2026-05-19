import os
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from schemas.api_models import ReportListResponse, ReportInfo
from schemas.artifact_models import ArtifactGenerationRequest
from services.artifact_generation_service import generate_artifact, list_all_artifacts
from services.report.report_registry_service import ReportRegistryService
from services.storage_service import StorageService

router = APIRouter(prefix="/reports", tags=["reports"])
REGISTRY = ReportRegistryService()

@router.get("")
def list_reports():
    artifacts = list_all_artifacts()
    legacy_reports = [
        ReportInfo(
            report_type=item.artifact_id,
            display_name=item.display_name,
            supported_input=item.supported_input,
            supported_output=[item.output_format],
        )
        for item in artifacts
        if item.artifact_type == "report"
    ]
    return {
        "artifacts": [item.model_dump() for item in artifacts],
        "reports": [item.model_dump() for item in legacy_reports],
    }

@router.post("/generate")
def generate_report(
    report_type: str = Form(None),
    artifact_type: str = Form(None),
    artifact_id: str = Form(None),
    file: UploadFile = File(None),
    files: list[UploadFile] | None = File(None),
    user_prompt: str = Form(None),
    output_format: str = Form(None),
):
    resolved_artifact_type = artifact_type or ("report" if report_type else None)
    resolved_artifact_id = artifact_id or report_type
    if not resolved_artifact_type or not resolved_artifact_id:
        raise HTTPException(status_code=400, detail="artifact_type ve artifact_id zorunludur.")

    upload_files = [item for item in (files or []) if item and item.filename]
    if file is not None and file.filename:
        upload_files.insert(0, file)
    for upload in upload_files:
        if not upload.filename.lower().endswith(".xlsx"):
            raise HTTPException(status_code=400, detail="Sadece .xlsx dosyalari desteklenmektedir.")

    audit_run_id = uuid4().hex
    upload_paths: list[str] = []

    for upload in upload_files:
        try:
            upload.file.seek(0)
            upload_paths.append(StorageService.save_upload(upload.file, audit_run_id, upload.filename))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Dosya yukleme hatasi: {str(e)}")
    
    result = generate_artifact(
        artifact_type=resolved_artifact_type,
        artifact_id=resolved_artifact_id,
        audit_run_id=audit_run_id,
        output_format=output_format,
        file_paths=upload_paths,
        user_prompt=user_prompt,
    )

    StorageService.save_metadata(audit_run_id, result.model_dump())

    if result.status == "failed":
        if result.filter_summary and result.filter_summary.get("filtered_row_count") == 0:
            return JSONResponse(status_code=422, content=result.model_dump())
        return JSONResponse(status_code=400, content=result.model_dump())

    if not result.output_file_path or not os.path.exists(result.output_file_path):
        return JSONResponse(status_code=500, content={"message": "Artifact uretildi fakat dosya bulunamadi."})

    media_type = {
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "jpg": "image/jpeg",
        "pdf": "application/pdf",
    }.get(result.output_format, "application/octet-stream")

    headers = {
        "X-Artifact-Type": resolved_artifact_type,
        "X-Artifact-Id": resolved_artifact_id,
        "X-Report-Type": resolved_artifact_id if resolved_artifact_type == "report" else "",
        "X-Audit-Run-Id": audit_run_id,
        "X-Warning-Count": str(len(result.warnings)),
        "X-Artifact-Status": result.status,
        "X-Report-Status": result.status,
        "X-Filter-Applied": str(bool(result.filter_summary and result.filter_summary.get("applied"))).lower(),
        "X-Input-Row-Count": str((result.filter_summary or {}).get("input_row_count", 0)),
        "X-Filtered-Row-Count": str((result.filter_summary or {}).get("filtered_row_count", 0)),
    }

    return FileResponse(
        path=result.output_file_path,
        filename=f"{resolved_artifact_id}_{audit_run_id}.{result.output_format}",
        headers=headers,
        media_type=media_type,
    )

@router.post("/generate-json")
def generate_report_json(
    report_type: str = Form(None),
    artifact_type: str = Form(None),
    artifact_id: str = Form(None),
    file: UploadFile = File(None),
    files: list[UploadFile] | None = File(None),
    user_prompt: str = Form(None),
    output_format: str = Form(None),
):
    resolved_artifact_type = artifact_type or ("report" if report_type else None)
    resolved_artifact_id = artifact_id or report_type
    if not resolved_artifact_type or not resolved_artifact_id:
        raise HTTPException(status_code=400, detail="artifact_type ve artifact_id zorunludur.")
    upload_files = [item for item in (files or []) if item and item.filename]
    if file is not None and file.filename:
        upload_files.insert(0, file)
    for upload in upload_files:
        if not upload.filename.lower().endswith(".xlsx"):
            raise HTTPException(status_code=400, detail="Sadece .xlsx dosyalari desteklenmektedir.")

    audit_run_id = uuid4().hex
    upload_paths: list[str] = []

    for upload in upload_files:
        try:
            upload.file.seek(0)
            upload_paths.append(StorageService.save_upload(upload.file, audit_run_id, upload.filename))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Dosya yukleme hatasi: {str(e)}")
    
    result = generate_artifact(
        artifact_type=resolved_artifact_type,
        artifact_id=resolved_artifact_id,
        audit_run_id=audit_run_id,
        output_format=output_format,
        file_paths=upload_paths,
        user_prompt=user_prompt,
    )

    StorageService.save_metadata(audit_run_id, result.model_dump())

    response_data = result.model_dump()
    if result.status != "failed" and result.output_file_path:
        response_data["download_url"] = f"/reports/download/{audit_run_id}"

    if result.status == "failed":
        if result.filter_summary and result.filter_summary.get("filtered_row_count") == 0:
            return JSONResponse(status_code=422, content=response_data)
        return JSONResponse(status_code=400, content=response_data)

    return JSONResponse(content=response_data)

@router.get("/download/{job_id}")
def download_report(job_id: str):
    output_dir = StorageService.get_output_dir(job_id)
    candidate_files = [
        ("report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("chart.jpg", "image/jpeg"),
        ("analysis.pdf", "application/pdf"),
    ]
    selected = next((((output_dir / name), media_type) for name, media_type in candidate_files if (output_dir / name).exists()), None)
    if not selected:
        raise HTTPException(status_code=404, detail="Rapor dosyasi bulunamadi.")
    file_path, media_type = selected
    
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type=media_type,
    )
