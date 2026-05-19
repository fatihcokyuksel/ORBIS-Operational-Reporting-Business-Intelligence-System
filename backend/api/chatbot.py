import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

import requests
from fastapi import Depends, APIRouter, HTTPException, Request, Response, status, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

from utils.auth import (
    clear_session_cookie,
    get_session_state,
    hash_password,
    require_user,
    set_session_cookie,
    verify_password,
)
from config.chatbot_config import FRONTEND_ORIGIN, RAG_API_URL
from utils.database import (
    database_location,
    db,
    init_db,
    new_id,
    now_iso,
    row_to_chat,
    row_to_message,
    row_to_user_public,
    row_to_report,
)


DEFAULT_AI_ERROR = "\u00dczg\u00fcn\u00fcm, bir yan\u0131t olu\u015fturulamad\u0131."
RAG_UNAVAILABLE = (
    "\u015eu anda yapay zeka servisine ula\u015f\u0131lam\u0131yor. "
    "L\u00fctfen Python RAG sunucusunun \u00e7al\u0131\u015ft\u0131\u011f\u0131ndan emin olun "
    "(`uvicorn rag_api:app --reload`) ve tekrar deneyin."
)
LEGACY_GREETING_PREFIXES = (
    "Merhaba! Ben ORBIS.",
    "Selam ben ORBIS",
    "Selam, ben ORBIS",
)

router = APIRouter()


class AuthRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    password: str | None = None


class ChatCreateRequest(BaseModel):
    title: str | None = None


class ChatPatchRequest(BaseModel):
    title: str | None = None
    isPinned: bool | None = None


class FileData(BaseModel):
    name: str
    type: str
    data: str


class MessageCreateRequest(BaseModel):
    role: str
    content: str
    file: FileData | None = None
    mode: str | None = None


def validate_password(password: str) -> list[str]:
    errors: list[str] = []
    if len(password) < 8:
        errors.append("en az 8 karakter")
    if not any(char.isupper() for char in password):
        errors.append("b\u00fcy\u00fck harf")
    if not any(char.islower() for char in password):
        errors.append("k\u00fc\u00e7\u00fck harf")
    if not any(char.isdigit() for char in password):
        errors.append("say\u0131")
    if not re.search(r"[!.,?@#$%^&*()_\-+=]", password):
        errors.append("\u00f6zel karakter (!, ., ?, @, #)")
    return errors


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "database": database_location()}


@router.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register(payload: AuthRequest, response: Response) -> dict[str, Any]:
    if not payload.email or not payload.password:
        raise HTTPException(status_code=400, detail={"message": "E-posta ve \u015fifre zorunludur"})
    password_errors = validate_password(payload.password)
    if password_errors:
        raise HTTPException(
            status_code=400,
            detail={"message": f"\u015eifre \u015fu kriterleri i\u00e7ermelidir: {', '.join(password_errors)}"},
        )

    timestamp = now_iso()
    session_id = new_id()
    with db() as connection:
        existing = connection.execute(
            'SELECT * FROM "User" WHERE "email" = ?',
            (payload.email,),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail={"message": "Bu e-posta ile kay\u0131tl\u0131 kullan\u0131c\u0131 var"})

        user_id = new_id()
        connection.execute(
            """
            INSERT INTO "User" ("id", "name", "email", "password", "activeSessionId", "createdAt", "updatedAt")
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, payload.name, payload.email, hash_password(payload.password), session_id, timestamp, timestamp),
        )
        user = connection.execute('SELECT * FROM "User" WHERE "id" = ?', (user_id,)).fetchone()

    set_session_cookie(response, user["id"], user["email"], session_id)
    return {"user": row_to_user_public(user)}


@router.post("/api/auth/login")
def login(payload: AuthRequest, response: Response) -> dict[str, Any]:
    if not payload.email or not payload.password:
        raise HTTPException(status_code=400, detail={"message": "E-posta ve \u015fifre zorunludur"})

    session_id = new_id()
    with db() as connection:
        user = connection.execute(
            'SELECT * FROM "User" WHERE "email" = ?',
            (payload.email,),
        ).fetchone()

        if not user or not verify_password(payload.password, user["password"]):
            raise HTTPException(status_code=401, detail={"message": "E-posta veya \u015fifre hatal\u0131"})

        connection.execute(
            'UPDATE "User" SET "activeSessionId" = ?, "updatedAt" = ? WHERE "id" = ?',
            (session_id, now_iso(), user["id"]),
        )
        user = connection.execute('SELECT * FROM "User" WHERE "id" = ?', (user["id"],)).fetchone()

    set_session_cookie(response, user["id"], user["email"], session_id)
    return {"user": row_to_user_public(user)}


@router.post("/api/auth/logout")
def logout(
    response: Response,
    state: dict[str, Any] = Depends(get_session_state),
) -> dict[str, str]:
    payload = state.get("payload")
    if payload and payload.get("userId") and payload.get("sessionId"):
        with db() as connection:
            connection.execute(
                'UPDATE "User" SET "activeSessionId" = NULL, "updatedAt" = ? WHERE "id" = ? AND "activeSessionId" = ?',
                (now_iso(), payload["userId"], payload["sessionId"]),
            )
    clear_session_cookie(response)
    return {"message": "\u00c7\u0131k\u0131\u015f yap\u0131ld\u0131"}


@router.get("/api/auth/session")
def session(state: dict[str, Any] = Depends(get_session_state)) -> dict[str, Any]:
    payload = state.get("payload")
    if not payload:
        return {"user": None, "reason": state.get("reason")}
    with db() as connection:
        user = connection.execute(
            'SELECT * FROM "User" WHERE "id" = ?',
            (payload.get("userId"),),
        ).fetchone()
    if not user:
        return {"user": None, "reason": "missing"}
    return {"user": row_to_user_public(user)}


@router.get("/api/chats")
def list_chats(user: dict[str, Any] = Depends(require_user)) -> list[dict[str, Any]]:
    with db() as connection:
        rows = connection.execute(
            'SELECT * FROM "ChatSession" WHERE "userId" = ? ORDER BY "updatedAt" DESC',
            (user["userId"],),
        ).fetchall()
    chats = [row_to_chat(row) for row in rows]
    return sorted(chats, key=lambda chat: not bool(chat["isPinned"]))


@router.post("/api/chats")
def create_chat(payload: ChatCreateRequest, user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    timestamp = now_iso()
    chat_id = new_id()
    with db() as connection:
        connection.execute(
            """
            INSERT INTO "ChatSession" ("id", "title", "userId", "isPinned", "createdAt", "updatedAt")
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (chat_id, payload.title or "Yeni sohbet", user["userId"], False, timestamp, timestamp),
        )
        chat = connection.execute('SELECT * FROM "ChatSession" WHERE "id" = ?', (chat_id,)).fetchone()
    return row_to_chat(chat)


def get_owned_chat(chat_id: str, user_id: str):
    with db() as connection:
        return connection.execute(
            'SELECT * FROM "ChatSession" WHERE "id" = ? AND "userId" = ?',
            (chat_id, user_id),
        ).fetchone()


@router.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str, user: dict[str, Any] = Depends(require_user)) -> dict[str, bool]:
    if not get_owned_chat(chat_id, user["userId"]):
        raise HTTPException(status_code=404, detail={"message": "Bulunamad\u0131"})

    with db() as connection:
        connection.execute('DELETE FROM "ChatSession" WHERE "id" = ?', (chat_id,))
    return {"success": True}


@router.patch("/api/chats/{chat_id}")
def patch_chat(
    chat_id: str,
    payload: ChatPatchRequest,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    if not get_owned_chat(chat_id, user["userId"]):
        raise HTTPException(status_code=404, detail={"message": "Bulunamad\u0131"})

    updates: list[str] = []
    values: list[Any] = []
    if payload.isPinned is not None:
        updates.append('"isPinned" = ?')
        values.append(payload.isPinned)
    if payload.title is not None:
        updates.append('"title" = ?')
        values.append(payload.title)
    updates.append('"updatedAt" = ?')
    values.append(now_iso())
    values.append(chat_id)

    with db() as connection:
        connection.execute(
            f'UPDATE "ChatSession" SET {", ".join(updates)} WHERE "id" = ?',
            tuple(values),
        )
        chat = connection.execute('SELECT * FROM "ChatSession" WHERE "id" = ?', (chat_id,)).fetchone()
    return row_to_chat(chat)


@router.get("/api/chats/{chat_id}/messages")
def list_messages(chat_id: str, user: dict[str, Any] = Depends(require_user)) -> list[dict[str, Any]]:
    if not get_owned_chat(chat_id, user["userId"]):
        raise HTTPException(status_code=404, detail={"message": "Bulunamad\u0131"})

    with db() as connection:
        messages = connection.execute(
            'SELECT * FROM "Message" WHERE "sessionId" = ? ORDER BY "createdAt" ASC',
            (chat_id,),
        ).fetchall()
    return [row_to_message(row) for row in messages if not is_legacy_greeting(row)]


def is_legacy_greeting(row: Any) -> bool:
    return row["role"] == "assistant" and str(row["content"]).startswith(LEGACY_GREETING_PREFIXES)


def ask_rag(question: str, file: dict | None = None) -> str:
    payload = {"question": question}
    if file:
        payload["file"] = file
    request = urllib.request.Request(
        f"{RAG_API_URL.rstrip('/')}/ask",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        rag_data = json.loads(response.read().decode("utf-8"))

    content = rag_data.get("answer") or DEFAULT_AI_ERROR
    sources = rag_data.get("sources")
    retrieval_mode = rag_data.get("retrieval_mode")
    if isinstance(sources, list) and sources:
        source_lines: list[str] = []
        seen_sources: set[str] = set()
        for source in sources:
            if isinstance(source, dict):
                formatted_source = format_source(source)
                if formatted_source and formatted_source not in seen_sources:
                    seen_sources.add(formatted_source)
                    source_lines.append(f"{len(source_lines) + 1}. {formatted_source}")
            elif isinstance(source, str):
                formatted_source = source.strip()
                if formatted_source and formatted_source not in seen_sources:
                    seen_sources.add(formatted_source)
                    source_lines.append(f"{len(source_lines) + 1}. {formatted_source}")
        if source_lines:
            return json.dumps(
                {
                    "type": "rag_answer",
                    "answer": content,
                    "sources": source_lines,
                    "retrievalMode": retrieval_mode,
                },
                ensure_ascii=False,
            )
    return content


def format_source(source: dict[str, Any]) -> str | None:
    raw_source = str(
        source.get("kanun_adi")
        or source.get("official_name")
        or source.get("source_file")
        or source.get("source")
        or source.get("file")
        or source.get("dosya")
        or ""
    ).strip()
    raw_page = source.get("page") or source.get("page_start") or source.get("sayfa")
    if not raw_source and raw_page is None:
        return None

    stem = os.path.splitext(os.path.basename(raw_source))[0]
    kanun_no = str(source.get("kanun_no") or source.get("law_no") or "").strip()
    if kanun_no and source.get("kanun_adi"):
        law_name = f"{kanun_no} sayili {source['kanun_adi']}"
    else:
        law_name = law_display_name(stem)
    page_part = f" sayfa {raw_page}" if raw_page not in (None, "") else ""
    return f"{law_name}{page_part}"


def law_display_name(stem: str) -> str:
    normalized = stem.strip().replace("_", " ")
    known_laws = {
        "193": "193 say\u0131l\u0131 Gelir Vergisi Kanunu",
        "213": "213 say\u0131l\u0131 Vergi Usul Kanunu",
        "5237": "5237 say\u0131l\u0131 Turk Ceza Kanunu",
        "6102": "6102 say\u0131l\u0131 Turk Ticaret Kanunu",
    }
    return known_laws.get(normalized, f"{normalized} say\u0131l\u0131 Kanun" if normalized.isdigit() else normalized)


@router.post("/api/chats/{chat_id}/messages")
def create_message(
    chat_id: str,
    payload: MessageCreateRequest,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    if not get_owned_chat(chat_id, user["userId"]):
        raise HTTPException(status_code=404, detail={"message": "Bulunamad\u0131"})

    with db() as connection:
        user_message_id = new_id()
        connection.execute(
            """
            INSERT INTO "Message" ("id", "sessionId", "role", "content", "fileName", "createdAt")
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_message_id, chat_id, payload.role, payload.content, payload.file.name if payload.file else None, now_iso()),
        )
        connection.execute(
            'UPDATE "ChatSession" SET "updatedAt" = ? WHERE "id" = ?',
            (now_iso(), chat_id),
        )
        message = connection.execute('SELECT * FROM "Message" WHERE "id" = ?', (user_message_id,)).fetchone()

    if payload.role != "user":
        return row_to_message(message)

    try:
        if payload.mode and "report" in payload.mode:
            ai_content = "Rapor olu\u015fturma i\u015flemi ba\u015flat\u0131ld\u0131. Gelecekteki rapor mimarisi burada \u00e7al\u0131\u015facak."
        else:
            file_dict = payload.file.model_dump() if payload.file else None
            ai_content = ask_rag(payload.content, file_dict)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        ai_content = RAG_UNAVAILABLE

    with db() as connection:
        assistant_message_id = new_id()
        connection.execute(
            """
            INSERT INTO "Message" ("id", "sessionId", "role", "content", "fileName", "createdAt")
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (assistant_message_id, chat_id, "assistant", ai_content, None, now_iso()),
        )
        connection.execute(
            'UPDATE "ChatSession" SET "updatedAt" = ? WHERE "id" = ?',
            (now_iso(), chat_id),
        )
        assistant_message = connection.execute(
            'SELECT * FROM "Message" WHERE "id" = ?',
            (assistant_message_id,),
        ).fetchone()

    return row_to_message(assistant_message)


# ----------------------------------------------------
# REPORT CONFIG & ENDPOINTS
# ----------------------------------------------------
from pathlib import Path

REPORT_GEN_API_URL = os.getenv("REPORT_GEN_API_URL", "http://localhost:8002")

REPORT_DISPLAY_NAMES = {
    "income_expense_report": "Gelir Gider Raporu",
    "cash_flow_report": "Nakit Akış Raporu",
    "debt_receivable_report": "Borç-Alacak Raporu",
    "vat_summary_report": "KDV Özet Raporu",
    "personnel_expense_report": "Personel Gider Analiz Raporu",
    "sales_performance_report": "Satış Performans Raporu",
    "profitability_report": "Nakit Bazlı Karlılık Raporu",
    "current_account_report": "Cari Hesap Takip Raporu",
    "payroll_cost_report": "Maaş ve Personel Maliyet Raporu",
    "inventory_cost_report": "Stok Maliyet Raporu",
    "tax_calculation_report": "Vergi Hesaplama Raporu"
}

CHART_DISPLAY_NAMES = {
    "income_expense_pie_chart": "Gelir-Gider Pasta Grafiği",
    "monthly_expense_trend_chart": "Aylık Harcama Trend Grafiği",
    "cashflow_bar_chart": "Nakit Akış Bar Grafiği",
    "top_expenses_chart": "En Büyük Giderler Grafiği",
    "daily_balance_change_chart": "Günlük Bakiye Değişim Grafiği",
    "debt_receivable_distribution_chart": "Borç-Alacak Dağılım Grafiği",
    "sales_performance_chart": "Satış Performans Grafiği",
    "tax_distribution_chart": "Vergi Dağılım Grafiği",
}

ANALYSIS_DISPLAY_NAMES = {
    "financial_risk_analysis": "Finansal Risk Analizi",
    "cash_runway_analysis": "Nakit Tükenme Riski Analizi",
    "anomaly_spending_analysis": "Anormal Harcama Analizi",
    "expense_optimization_analysis": "Gider Optimizasyon Analizi",
    "profitability_analysis": "Kârlılık Analizi",
    "receivable_debt_risk_analysis": "Borç-Alacak Risk Analizi",
    "sales_risk_analysis": "Satış Risk ve Performans Analizi",
    "tax_risk_analysis": "Vergi Risk Analizi",
}

ARTIFACT_DISPLAY_NAMES = {
    **{("report", key): value for key, value in REPORT_DISPLAY_NAMES.items()},
    **{("chart", key): value for key, value in CHART_DISPLAY_NAMES.items()},
    **{("analysis", key): value for key, value in ANALYSIS_DISPLAY_NAMES.items()},
}

ARTIFACT_OUTPUT_FORMATS = {
    "report": "xlsx",
    "chart": "jpg",
    "analysis": "pdf",
}

ARTIFACT_MEDIA_TYPES = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "jpg": "image/jpeg",
    "pdf": "application/pdf",
}

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent


def format_filter_summary_for_client(filter_payload: dict | None, user_prompt: str | None = None) -> dict[str, Any] | None:
    if not isinstance(filter_payload, dict):
        return None
    return {
        "applied": bool(filter_payload.get("applied")),
        "userPrompt": filter_payload.get("user_prompt") or user_prompt,
        "summaryLines": list(filter_payload.get("summary_lines") or []),
        "inputRowCount": int(filter_payload.get("input_row_count") or 0),
        "filteredRowCount": int(filter_payload.get("filtered_row_count") or 0),
    }


def fallback_filter_summary_from_headers(headers, user_prompt: str | None = None) -> dict[str, Any] | None:
    applied = headers.get("X-Filter-Applied")
    input_row_count = headers.get("X-Input-Row-Count")
    filtered_row_count = headers.get("X-Filtered-Row-Count")
    if applied is None and input_row_count is None and filtered_row_count is None:
        return None
    return {
        "applied": str(applied).lower() == "true",
        "userPrompt": user_prompt,
        "summaryLines": [],
        "inputRowCount": int(input_row_count or 0),
        "filteredRowCount": int(filtered_row_count or 0),
    }


def should_report_empty_filter_result(filter_summary: dict[str, Any] | None) -> bool:
    if not isinstance(filter_summary, dict):
        return False
    filtered_row_count = filter_summary.get("filteredRowCount")
    if filtered_row_count is None or int(filtered_row_count) != 0:
        return False
    if bool(filter_summary.get("applied")):
        return True
    return any(
        isinstance(line, str) and line.strip()
        for line in (filter_summary.get("summaryLines") or [])
    )


def collect_failure_details(err_json: dict[str, Any]) -> tuple[list[str], list[str]]:
    error_details: list[str] = []
    warning_details: list[str] = []

    for item in err_json.get("errors", []):
        value = item.get("message") if isinstance(item, dict) else str(item)
        if isinstance(value, str) and value.strip():
            error_details.append(value.strip())

    for item in err_json.get("warnings", []):
        value = item.get("message") if isinstance(item, dict) else str(item)
        if isinstance(value, str) and value.strip():
            warning_details.append(value.strip())

    return error_details, warning_details


def infer_output_format(record: dict[str, Any]) -> str:
    output_format = str(record.get("outputFormat") or "").strip().lower()
    if output_format in ARTIFACT_MEDIA_TYPES:
        return output_format

    artifact_type = str(record.get("artifactType") or "report").strip().lower()
    fallback = ARTIFACT_OUTPUT_FORMATS.get(artifact_type)
    if fallback:
        return fallback

    file_name = str(record.get("fileName") or "").strip().lower()
    if "." in file_name:
        ext = file_name.rsplit(".", 1)[-1]
        if ext in ARTIFACT_MEDIA_TYPES:
            return ext

    return "xlsx"


def resolve_report_file_path(record: dict[str, Any]) -> Path | None:
    candidates: list[Path] = []
    raw_path = record.get("filePath")

    if raw_path:
        raw_path_str = str(raw_path)
        candidates.append(Path(raw_path_str))

        normalized_path = raw_path_str.replace("/", "\\")
        marker = "storage\\reports\\"
        if marker in normalized_path:
            relative_suffix = Path(normalized_path.split(marker, 1)[1])
            candidates.append(BACKEND_ROOT / "storage" / "reports" / relative_suffix)
            candidates.append(REPO_ROOT / "storage" / "reports" / relative_suffix)

    user_id = record.get("userId")
    report_id = record.get("id")
    output_format = infer_output_format(record)
    if user_id and report_id:
        candidates.append(BACKEND_ROOT / "storage" / "reports" / str(user_id) / f"{report_id}.{output_format}")
        candidates.append(REPO_ROOT / "storage" / "reports" / str(user_id) / f"{report_id}.{output_format}")

    audit_run_id = str(record.get("auditRunId") or "").strip()
    if audit_run_id:
        artifact_files = [
            f"report.{output_format}",
            f"chart.{output_format}",
            f"analysis.{output_format}",
            "report.xlsx",
            "chart.jpg",
            "analysis.pdf",
        ]
        for base_dir in (BACKEND_ROOT / "storage" / "outputs", REPO_ROOT / "storage" / "outputs"):
            for file_name in artifact_files:
                candidates.append(base_dir / audit_run_id / file_name)

    seen: set[str] = set()
    for candidate in candidates:
        candidate_key = str(candidate)
        if candidate_key in seen:
            continue
        seen.add(candidate_key)
        if candidate.exists():
            return candidate

    return None


@router.post("/api/reports/generate")
def generate_report_endpoint(
    reportType: str = Form(None),
    artifactType: str = Form(None),
    artifactId: str = Form(None),
    file: UploadFile = File(None),
    files: list[UploadFile] | None = File(None),
    conversationId: str = Form(None),
    userPrompt: str = Form(None),
    user: dict[str, Any] = Depends(require_user),
):
    user_id = user["userId"]
    resolved_artifact_type = artifactType or ("report" if reportType else None)
    resolved_artifact_id = artifactId or reportType
    if not resolved_artifact_type or not resolved_artifact_id:
        raise HTTPException(status_code=400, detail={"message": "Artifact tipi ve kimli?i zorunludur."})

    display_name = ARTIFACT_DISPLAY_NAMES.get((resolved_artifact_type, resolved_artifact_id))
    if not display_name:
        raise HTTPException(status_code=400, detail={"message": "Bu artifact tipi desteklenmiyor."})

    upload_files = [item for item in (files or []) if item and item.filename]
    if file is not None and file.filename:
        upload_files.insert(0, file)
    for upload in upload_files:
        if not upload.filename.lower().endswith(".xlsx"):
            raise HTTPException(status_code=400, detail={"message": "Lutfen .xlsx formatinda dosya yukle."})
    if resolved_artifact_type in {"report", "analysis"} and not upload_files:
        raise HTTPException(status_code=400, detail={"message": "Bu i?lem i?in Excel dosyas? zorunludur."})
    if resolved_artifact_type == "chart" and not upload_files and not (userPrompt and userPrompt.strip()):
        raise HTTPException(status_code=400, detail={"message": "Grafik ?retmek i?in Excel dosyas? veya do?al dil promptu gerekli."})

    source_file_names = [upload.filename for upload in upload_files]
    source_file_name = ", ".join(source_file_names) if source_file_names else None

    if conversationId:
        with db() as connection:
            user_message_id = new_id()
            connection.execute(
                """
                INSERT INTO "Message" ("id", "sessionId", "role", "content", "fileName", "createdAt")
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_message_id, conversationId, "user", userPrompt or "Artifact ?retim talebi", source_file_name, now_iso()),
            )
            connection.execute('UPDATE "ChatSession" SET "updatedAt" = ? WHERE "id" = ?', (now_iso(), conversationId))

    url = f"{REPORT_GEN_API_URL.rstrip('/')}/reports/generate"
    output_format = ARTIFACT_OUTPUT_FORMATS[resolved_artifact_type]

    try:
        outbound_files = []
        for upload in upload_files:
            upload.file.seek(0)
            outbound_files.append(("files", (upload.filename, upload.file.read(), upload.content_type)))
        data = {
            "artifact_type": resolved_artifact_type,
            "artifact_id": resolved_artifact_id,
            "output_format": output_format,
        }
        if resolved_artifact_type == "report":
            data["report_type"] = resolved_artifact_id
        if userPrompt:
            data["user_prompt"] = userPrompt
        api_res = requests.post(url, files=outbound_files or None, data=data, timeout=240)
    except Exception as e:
        print(f"report_gen_api call failed: {str(e)}")
        raise HTTPException(status_code=503, detail={"message": "Artifact servisine ula??lamad?. L?tfen servislerin ?al??t???ndan emin olun."})

    report_id = new_id()

    if api_res.status_code == 200:
        audit_run_id = api_res.headers.get("X-Audit-Run-Id", "")
        warning_count = int(api_res.headers.get("X-Warning-Count", "0"))
        artifact_status = api_res.headers.get("X-Artifact-Status") or api_res.headers.get("X-Report-Status", "success")
        response_artifact_type = api_res.headers.get("X-Artifact-Type", resolved_artifact_type)
        response_artifact_id = api_res.headers.get("X-Artifact-Id", resolved_artifact_id)
        response_output_format = ARTIFACT_OUTPUT_FORMATS.get(response_artifact_type, output_format)
        content_type = api_res.headers.get("content-type", ARTIFACT_MEDIA_TYPES[response_output_format])

        storage_dir = Path(__file__).resolve().parent.parent / "storage" / "reports" / user_id
        storage_dir.mkdir(parents=True, exist_ok=True)
        local_file_path = storage_dir / f"{report_id}.{response_output_format}"
        with open(local_file_path, "wb") as f:
            f.write(api_res.content)

        warnings_list = []
        filter_summary = None
        try:
            metadata_file = Path(__file__).resolve().parent.parent / "storage" / "metadata" / audit_run_id / "result.json"
            if metadata_file.exists():
                with open(metadata_file, "r", encoding="utf-8") as mf:
                    metadata_data = json.load(mf)
                for w in metadata_data.get("warnings", []):
                    warnings_list.append(w.get("message", "") if isinstance(w, dict) else str(w))
                filter_summary = format_filter_summary_for_client(
                    metadata_data.get("filter_summary") or metadata_data.get("filter") or (metadata_data.get("metadata") or {}).get("filter"),
                    user_prompt=userPrompt,
                )
        except Exception as ex:
            print(f"Failed to read warning metadata file: {str(ex)}")

        if filter_summary is None:
            filter_summary = fallback_filter_summary_from_headers(api_res.headers, user_prompt=userPrompt)
        if not warnings_list and warning_count > 0:
            warnings_list = [f"Artifact ?retildi ancak {warning_count} adet uyar? tespit edildi."]

        report_record = {
            "id": report_id,
            "userId": user_id,
            "sessionId": conversationId,
            "conversationId": conversationId,
            "artifactType": response_artifact_type,
            "artifactId": response_artifact_id,
            "reportType": response_artifact_id,
            "displayName": display_name,
            "status": artifact_status,
            "filePath": str(local_file_path),
            "fileName": f"{display_name}.{response_output_format}",
            "downloadUrl": f"/api/reports/download/{report_id}",
            "outputFormat": response_output_format,
            "contentType": content_type,
            "sourceFileName": source_file_name,
            "warningCount": warning_count,
            "warnings": json.dumps(warnings_list),
            "filterSummary": json.dumps(filter_summary, ensure_ascii=False) if filter_summary else None,
            "errorMessage": None,
            "auditRunId": audit_run_id,
            "createdAt": now_iso(),
        }

        with db() as connection:
            connection.execute(
                """
                INSERT INTO "Report" (
                    "id", "userId", "sessionId", "conversationId", "artifactType", "artifactId", "reportType", "displayName",
                    "status", "filePath", "fileName", "downloadUrl", "outputFormat", "contentType", "sourceFileName",
                    "warningCount", "warnings", "filterSummary", "errorMessage", "auditRunId", "createdAt"
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_record["id"], report_record["userId"], report_record["sessionId"], report_record["conversationId"],
                    report_record["artifactType"], report_record["artifactId"], report_record["reportType"], report_record["displayName"],
                    report_record["status"], report_record["filePath"], report_record["fileName"], report_record["downloadUrl"],
                    report_record["outputFormat"], report_record["contentType"], report_record["sourceFileName"], report_record["warningCount"],
                    report_record["warnings"], report_record["filterSummary"], report_record["errorMessage"], report_record["auditRunId"], report_record["createdAt"],
                ),
            )

        assistant_content = json.dumps({
            "type": "report_result",
            "status": artifact_status,
            "artifactType": response_artifact_type,
            "artifactId": response_artifact_id,
            "reportType": response_artifact_id,
            "displayName": display_name,
            "reportId": report_id,
            "downloadUrl": f"/api/reports/download/{report_id}",
            "outputFormat": response_output_format,
            "warningCount": warning_count,
            "warnings": warnings_list,
            "filterSummary": filter_summary,
            "createdAt": report_record["createdAt"],
        }, ensure_ascii=False)

        if conversationId:
            with db() as connection:
                assistant_message_id = new_id()
                connection.execute(
                    """
                    INSERT INTO "Message" ("id", "sessionId", "role", "content", "fileName", "createdAt")
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (assistant_message_id, conversationId, "assistant", assistant_content, None, now_iso()),
                )
                connection.execute('UPDATE "ChatSession" SET "updatedAt" = ? WHERE "id" = ?', (now_iso(), conversationId))
                assistant_msg_row = connection.execute('SELECT * FROM "Message" WHERE "id" = ?', (assistant_message_id,)).fetchone()
                return row_to_message(assistant_msg_row)
        return {"id": report_id, "role": "assistant", "content": assistant_content}

    error_message = "Beklenmeyen bir hata olu?tu. L?tfen tekrar dene."
    details_list = []
    warning_details: list[str] = []
    audit_run_id = ""
    filter_summary = None
    try:
        err_json = api_res.json()
        if isinstance(err_json, dict):
            error_message = err_json.get("message") or error_message
            audit_run_id = err_json.get("audit_run_id") or ""
            filter_summary = format_filter_summary_for_client(err_json.get("filter_summary") or err_json.get("filter"), user_prompt=userPrompt)
            details_list, warning_details = collect_failure_details(err_json)
    except Exception:
        pass

    if should_report_empty_filter_result(filter_summary):
        error_message = "Seçtiğin filtrelerden sonra üretilecek veri kalmadı."

    report_record = {
        "id": report_id,
        "userId": user_id,
        "sessionId": conversationId,
        "conversationId": conversationId,
        "artifactType": resolved_artifact_type,
        "artifactId": resolved_artifact_id,
        "reportType": resolved_artifact_id,
        "displayName": display_name,
        "status": "failed",
        "filePath": None,
        "fileName": None,
        "downloadUrl": None,
        "outputFormat": ARTIFACT_OUTPUT_FORMATS[resolved_artifact_type],
        "contentType": ARTIFACT_MEDIA_TYPES[ARTIFACT_OUTPUT_FORMATS[resolved_artifact_type]],
        "sourceFileName": source_file_name,
        "warningCount": len(warning_details),
        "warnings": json.dumps(warning_details),
        "filterSummary": json.dumps(filter_summary, ensure_ascii=False) if filter_summary else None,
        "errorMessage": error_message,
        "auditRunId": audit_run_id,
        "createdAt": now_iso(),
    }

    with db() as connection:
        connection.execute(
            """
            INSERT INTO "Report" (
                "id", "userId", "sessionId", "conversationId", "artifactType", "artifactId", "reportType", "displayName",
                "status", "filePath", "fileName", "downloadUrl", "outputFormat", "contentType", "sourceFileName",
                "warningCount", "warnings", "filterSummary", "errorMessage", "auditRunId", "createdAt"
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_record["id"], report_record["userId"], report_record["sessionId"], report_record["conversationId"],
                report_record["artifactType"], report_record["artifactId"], report_record["reportType"], report_record["displayName"],
                report_record["status"], report_record["filePath"], report_record["fileName"], report_record["downloadUrl"],
                report_record["outputFormat"], report_record["contentType"], report_record["sourceFileName"], report_record["warningCount"],
                report_record["warnings"], report_record["filterSummary"], report_record["errorMessage"], report_record["auditRunId"], report_record["createdAt"],
            ),
        )

    assistant_content = json.dumps({
        "type": "report_error",
        "status": "failed",
        "artifactType": resolved_artifact_type,
        "artifactId": resolved_artifact_id,
        "reportType": resolved_artifact_id,
        "displayName": display_name,
        "outputFormat": ARTIFACT_OUTPUT_FORMATS[resolved_artifact_type],
        "errorMessage": error_message,
        "details": details_list,
        "warnings": warning_details,
        "filterSummary": filter_summary,
        "createdAt": report_record["createdAt"],
    }, ensure_ascii=False)

    if conversationId:
        with db() as connection:
            assistant_message_id = new_id()
            connection.execute(
                """
                INSERT INTO "Message" ("id", "sessionId", "role", "content", "fileName", "createdAt")
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (assistant_message_id, conversationId, "assistant", assistant_content, None, now_iso()),
            )
            connection.execute('UPDATE "ChatSession" SET "updatedAt" = ? WHERE "id" = ?', (now_iso(), conversationId))
            assistant_msg_row = connection.execute('SELECT * FROM "Message" WHERE "id" = ?', (assistant_message_id,)).fetchone()
            return row_to_message(assistant_msg_row)
    return {"id": report_id, "role": "assistant", "content": assistant_content}


@router.get("/api/reports")
def list_reports_endpoint(
    user: dict[str, Any] = Depends(require_user)
):
    user_id = user["userId"]
    with db() as connection:
        rows = connection.execute(
            'SELECT * FROM "Report" WHERE "userId" = ? ORDER BY "createdAt" DESC',
            (user_id,)
        ).fetchall()
        
    reports_list = []
    for row in rows:
        record = dict(row)
        try:
            record["warnings"] = json.loads(record["warnings"]) if record.get("warnings") else []
        except Exception:
            record["warnings"] = []
        try:
            record["filterSummary"] = json.loads(record["filterSummary"]) if record.get("filterSummary") else None
        except Exception:
            record["filterSummary"] = None
            
        reports_list.append({
            "id": record["id"],
            "artifactType": record.get("artifactType") or "report",
            "artifactId": record.get("artifactId") or record["reportType"],
            "reportType": record["reportType"],
            "displayName": record["displayName"],
            "status": record["status"],
            "createdAt": record["createdAt"],
            "fileName": record["fileName"],
            "downloadUrl": record["downloadUrl"],
            "outputFormat": record.get("outputFormat"),
            "sourceFileName": record["sourceFileName"],
            "warningCount": record["warningCount"],
            "warnings": record["warnings"],
            "errorMessage": record["errorMessage"],
            "filterSummary": record["filterSummary"]
        })
        
    return {"reports": reports_list}


@router.get("/api/reports/download/{report_id}")
def download_report_endpoint(
    report_id: str,
    user: dict[str, Any] = Depends(require_user)
):
    user_id = user["userId"]
    
    with db() as connection:
        row = connection.execute(
            'SELECT * FROM "Report" WHERE "id" = ?',
            (report_id,)
        ).fetchone()
        
    if not row:
        raise HTTPException(status_code=404, detail="Rapor bulunamadı.")
        
    record = dict(row)
    if record["userId"] != user_id:
        raise HTTPException(status_code=403, detail="Bu raporu indirmeye yetkiniz yok.")
        
    file_path = resolve_report_file_path(record)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Rapor dosyası sistemde bulunamadı.")

    if record.get("filePath") != str(file_path):
        resolved_output_format = infer_output_format(record)
        with db() as connection:
            connection.execute(
                'UPDATE "Report" SET "filePath" = ?, "outputFormat" = ?, "contentType" = ? WHERE "id" = ?',
                (
                    str(file_path),
                    resolved_output_format,
                    record.get("contentType") or ARTIFACT_MEDIA_TYPES.get(resolved_output_format, "application/octet-stream"),
                    report_id,
                ),
            )
        
    return FileResponse(
        path=str(file_path),
        filename=record["fileName"] or f"{record['reportType']}_{report_id}.{record.get('outputFormat') or 'xlsx'}",
        media_type=record.get("contentType") or ARTIFACT_MEDIA_TYPES.get(record.get("outputFormat") or "xlsx", "application/octet-stream")
    )
