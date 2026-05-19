import os

class Settings:
    STORAGE_DIR = os.getenv("STORAGE_DIR", "storage")
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "storage/uploads")
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "storage/outputs")
    METADATA_DIR = os.getenv("METADATA_DIR", "storage/metadata")
    MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "20"))
    ALLOWED_EXTENSIONS = [".xlsx"]
    DEFAULT_OUTPUT_FORMAT = "xlsx"

settings = Settings()
