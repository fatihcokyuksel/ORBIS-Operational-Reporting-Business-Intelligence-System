import sqlite3
import threading
import uuid
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Any

from config.chatbot_config import DATABASE_PATH

SQLITE_TIMEOUT_SECONDS = 30
SQLITE_BUSY_TIMEOUT_MS = SQLITE_TIMEOUT_SECONDS * 1000
DB_LOCK = threading.RLock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def new_id() -> str:
    return f"c{uuid.uuid4().hex[:24]}"


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    with DB_LOCK:
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(DATABASE_PATH, timeout=SQLITE_TIMEOUT_SECONDS)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def init_db() -> None:
    with db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS "User" (
                "id" TEXT NOT NULL PRIMARY KEY,
                "name" TEXT,
                "email" TEXT NOT NULL,
                "password" TEXT NOT NULL,
                "activeSessionId" TEXT,
                "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                "updatedAt" DATETIME NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS "User_email_key" ON "User"("email");

            CREATE TABLE IF NOT EXISTS "ChatSession" (
                "id" TEXT NOT NULL PRIMARY KEY,
                "title" TEXT NOT NULL,
                "userId" TEXT NOT NULL,
                "isPinned" BOOLEAN NOT NULL DEFAULT false,
                "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                "updatedAt" DATETIME NOT NULL,
                CONSTRAINT "ChatSession_userId_fkey"
                  FOREIGN KEY ("userId") REFERENCES "User" ("id")
                  ON DELETE CASCADE ON UPDATE CASCADE
            );

            CREATE TABLE IF NOT EXISTS "Message" (
                "id" TEXT NOT NULL PRIMARY KEY,
                "sessionId" TEXT NOT NULL,
                "role" TEXT NOT NULL,
                "content" TEXT NOT NULL,
                "fileName" TEXT,
                "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT "Message_sessionId_fkey"
                  FOREIGN KEY ("sessionId") REFERENCES "ChatSession" ("id")
                  ON DELETE CASCADE ON UPDATE CASCADE
            );

            CREATE TABLE IF NOT EXISTS "Report" (
                "id" TEXT NOT NULL PRIMARY KEY,
                "userId" TEXT,
                "sessionId" TEXT,
                "conversationId" TEXT,
                "artifactType" TEXT,
                "artifactId" TEXT,
                "reportType" TEXT NOT NULL,
                "displayName" TEXT NOT NULL,
                "status" TEXT NOT NULL,
                "filePath" TEXT,
                "fileName" TEXT,
                "downloadUrl" TEXT,
                "outputFormat" TEXT,
                "contentType" TEXT,
                "sourceFileName" TEXT,
                "warningCount" INTEGER NOT NULL DEFAULT 0,
                "warnings" TEXT,
                "filterSummary" TEXT,
                "errorMessage" TEXT,
                "auditRunId" TEXT,
                "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        try:
            connection.execute('ALTER TABLE "Message" ADD COLUMN "fileName" TEXT;')
        except sqlite3.OperationalError:
            pass
        try:
            connection.execute('ALTER TABLE "User" ADD COLUMN "activeSessionId" TEXT;')
        except sqlite3.OperationalError:
            pass
        try:
            connection.execute('ALTER TABLE "Report" ADD COLUMN "filterSummary" TEXT;')
        except sqlite3.OperationalError:
            pass
        try:
            connection.execute('ALTER TABLE "Report" ADD COLUMN "artifactType" TEXT;')
        except sqlite3.OperationalError:
            pass
        try:
            connection.execute('ALTER TABLE "Report" ADD COLUMN "artifactId" TEXT;')
        except sqlite3.OperationalError:
            pass
        try:
            connection.execute('ALTER TABLE "Report" ADD COLUMN "outputFormat" TEXT;')
        except sqlite3.OperationalError:
            pass
        try:
            connection.execute('ALTER TABLE "Report" ADD COLUMN "contentType" TEXT;')
        except sqlite3.OperationalError:
            pass


def row_to_user_public(row: sqlite3.Row) -> dict[str, str | None]:
    return {"id": row["id"], "name": row["name"], "email": row["email"]}


def row_to_chat(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "title": row["title"],
        "userId": row["userId"],
        "isPinned": bool(row["isPinned"]),
        "createdAt": row["createdAt"],
        "updatedAt": row["updatedAt"],
    }


def row_to_message(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "sessionId": row["sessionId"],
        "role": row["role"],
        "content": row["content"],
        "fileName": row["fileName"] if "fileName" in row.keys() else None,
        "createdAt": row["createdAt"],
    }


def row_to_report(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "userId": row["userId"],
        "sessionId": row["sessionId"],
        "conversationId": row["conversationId"],
        "artifactType": row["artifactType"] if "artifactType" in row.keys() and row["artifactType"] else "report",
        "artifactId": row["artifactId"] if "artifactId" in row.keys() and row["artifactId"] else row["reportType"],
        "reportType": row["reportType"],
        "displayName": row["displayName"],
        "status": row["status"],
        "filePath": row["filePath"],
        "fileName": row["fileName"],
        "downloadUrl": row["downloadUrl"],
        "outputFormat": row["outputFormat"] if "outputFormat" in row.keys() else None,
        "contentType": row["contentType"] if "contentType" in row.keys() else None,
        "sourceFileName": row["sourceFileName"],
        "warningCount": row["warningCount"],
        "warnings": json.loads(row["warnings"]) if row["warnings"] else [],
        "filterSummary": json.loads(row["filterSummary"]) if "filterSummary" in row.keys() and row["filterSummary"] else None,
        "errorMessage": row["errorMessage"],
        "auditRunId": row["auditRunId"],
        "createdAt": row["createdAt"],
    }


def database_location() -> str:
    return str(Path(DATABASE_PATH).resolve())
