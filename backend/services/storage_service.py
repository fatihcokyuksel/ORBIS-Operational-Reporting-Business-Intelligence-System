import os
import shutil
import json
from pathlib import Path
from config.core_config import settings

class StorageService:
    @staticmethod
    def init_directories():
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
        os.makedirs(settings.METADATA_DIR, exist_ok=True)

    @staticmethod
    def get_upload_path(audit_run_id: str, filename: str) -> Path:
        dir_path = Path(settings.UPLOAD_DIR) / audit_run_id
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path / filename

    @staticmethod
    def get_output_dir(audit_run_id: str) -> Path:
        dir_path = Path(settings.OUTPUT_DIR) / audit_run_id
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path

    @staticmethod
    def get_metadata_path(audit_run_id: str) -> Path:
        dir_path = Path(settings.METADATA_DIR) / audit_run_id
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path / "result.json"

    @staticmethod
    def save_upload(file_obj, audit_run_id: str, original_filename: str) -> str:
        # Sanitize filename to be safe but keep original name
        import re
        base, ext = os.path.splitext(original_filename)
        # Keep alphanumeric, dashes, underscores, and dots. Replace others with underscore.
        clean_base = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', base)
        if not clean_base:
            clean_base = "input"
        safe_filename = f"{clean_base}{ext}"
        file_path = StorageService.get_upload_path(audit_run_id, safe_filename)
        counter = 1
        while file_path.exists():
            file_path = StorageService.get_upload_path(audit_run_id, f"{clean_base}_{counter}{ext}")
            counter += 1
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file_obj, buffer)
        return str(file_path)

    @staticmethod
    def save_metadata(audit_run_id: str, result: dict) -> str:
        file_path = StorageService.get_metadata_path(audit_run_id)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return str(file_path)
