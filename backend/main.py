import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables
load_dotenv()

# Disable huggingface telemetry warnings
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# Import startup services and DB initializers
from services.storage_service import StorageService
from utils.database import init_db
from api.rag import init_bge_model, clear_bge_model

# Import API Routers
from api.routes import reports as reports_router
from api.chatbot import router as chatbot_router
from api.rag import router as rag_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize report file storage directories
    StorageService.init_directories()
    # 2. Initialize sqlite database for the chatbot
    init_db()
    # 3. Load the RAG embedding model (BGE-M3)
    init_bge_model()
    yield
    # 4. Clean up BGE-M3 model on shutdown
    clear_bge_model()

app = FastAPI(
    title="ORBIS Unified Backend API",
    description="Unified FastAPI backend service for Chatbot, RAG knowledge base and Financial Report Generator.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global HTTP exception handler for consistent error messages
@app.exception_handler(HTTPException)
def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})

# Register routers
app.include_router(reports_router.router)
app.include_router(chatbot_router)
app.include_router(rag_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
