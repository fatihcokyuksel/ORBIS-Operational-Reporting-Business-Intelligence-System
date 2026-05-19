import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
CHATBOT_ROOT = REPO_ROOT / "chatbot-api"

if str(CHATBOT_ROOT) not in sys.path:
    sys.path.insert(0, str(CHATBOT_ROOT))

from app import database as chatbot_db  # noqa: E402
from app import main as chatbot_main  # noqa: E402


class FakeReportGenResponse:
    def __init__(self, *, status_code: int, headers: dict | None = None, content: bytes = b"", json_body: dict | None = None):
        self.status_code = status_code
        self.headers = headers or {}
        self.content = content
        self._json_body = json_body or {}

    def json(self):
        return self._json_body


class ReportFilterApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        chatbot_db.DATABASE_PATH = Path(self.temp_dir.name) / "test.db"
        chatbot_db.init_db()
        self.client = TestClient(chatbot_main.app)
        chatbot_main.app.dependency_overrides[chatbot_main.require_user] = lambda: {"userId": "test-user"}

        with chatbot_db.db() as connection:
            connection.execute(
                """
                INSERT INTO "User" ("id", "name", "email", "password", "activeSessionId", "createdAt", "updatedAt")
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("test-user", "Test User", "test@example.com", "hashed", "session-1", chatbot_db.now_iso(), chatbot_db.now_iso()),
            )
            connection.execute(
                """
                INSERT INTO "ChatSession" ("id", "title", "userId", "isPinned", "createdAt", "updatedAt")
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("chat-1", "Rapor Sohbeti", "test-user", False, chatbot_db.now_iso(), chatbot_db.now_iso()),
            )

        self.metadata_dirs: list[Path] = []
        self.report_storage_dir = CHATBOT_ROOT / "storage" / "reports" / "test-user"

    def tearDown(self):
        chatbot_main.app.dependency_overrides.clear()
        self.client.close()
        for metadata_dir in self.metadata_dirs:
            if metadata_dir.exists():
                shutil.rmtree(metadata_dir)
        if self.report_storage_dir.exists():
            shutil.rmtree(self.report_storage_dir)
        self.temp_dir.cleanup()

    def write_metadata(self, audit_run_id: str, payload: dict):
        metadata_dir = REPO_ROOT / "report_table_generator" / "storage" / "metadata" / audit_run_id
        metadata_dir.mkdir(parents=True, exist_ok=True)
        (metadata_dir / "result.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        self.metadata_dirs.append(metadata_dir)

    def test_generate_report_forwards_user_prompt_and_persists_filter_summary(self):
        self.write_metadata(
            "audit-success",
            {
                "warnings": [],
                "filter": {
                    "applied": True,
                    "user_prompt": "son 3 ay ve 50 bin üzeri işlemler",
                    "summary_lines": ["Son 3 ay", "total_sales >= 50000"],
                    "input_row_count": 10,
                    "filtered_row_count": 4,
                },
            },
        )

        captured_data = {}

        def fake_post(url, files, data, timeout):
            captured_data.update(data)
            return FakeReportGenResponse(
                status_code=200,
                headers={
                    "X-Audit-Run-Id": "audit-success",
                    "X-Warning-Count": "0",
                    "X-Report-Status": "success",
                    "X-Filter-Applied": "true",
                    "X-Input-Row-Count": "10",
                    "X-Filtered-Row-Count": "4",
                },
                content=b"fake-xlsx",
            )

        with patch.object(chatbot_main.requests, "post", side_effect=fake_post):
            response = self.client.post(
                "/api/reports/generate",
                data={
                    "reportType": "sales_performance_report",
                    "conversationId": "chat-1",
                    "userPrompt": "son 3 ay ve 50 bin üzeri işlemler",
                },
                files={
                    "file": (
                        "veriler.xlsx",
                        b"fake-input",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured_data["user_prompt"], "son 3 ay ve 50 bin üzeri işlemler")

        assistant_payload = json.loads(response.json()["content"])
        self.assertEqual(assistant_payload["type"], "report_result")
        self.assertEqual(assistant_payload["filterSummary"]["filteredRowCount"], 4)
        self.assertEqual(assistant_payload["filterSummary"]["summaryLines"], ["Son 3 ay", "total_sales >= 50000"])

        with chatbot_db.db() as connection:
            report_row = connection.execute('SELECT * FROM "Report" WHERE "id" = ?', (assistant_payload["reportId"],)).fetchone()
        stored_report = chatbot_db.row_to_report(report_row)
        self.assertEqual(stored_report["filterSummary"]["inputRowCount"], 10)
        self.assertEqual(stored_report["filterSummary"]["filteredRowCount"], 4)

        list_response = self.client.get("/api/reports")
        self.assertEqual(list_response.status_code, 200)
        reports = list_response.json()["reports"]
        self.assertEqual(reports[0]["filterSummary"]["filteredRowCount"], 4)

    def test_generate_report_surfaces_empty_filter_result_as_failed_report(self):
        def fake_post(url, files, data, timeout):
            return FakeReportGenResponse(
                status_code=422,
                json_body={
                    "status": "failed",
                    "message": "Uygulanan filtrelerden sonra rapor uretecek veri kalmadi.",
                    "filter": {
                        "applied": True,
                        "user_prompt": "sadece İstanbul bölgesi",
                        "summary_lines": ["region: İstanbul"],
                        "input_row_count": 25,
                        "filtered_row_count": 0,
                    },
                },
            )

        with patch.object(chatbot_main.requests, "post", side_effect=fake_post):
            response = self.client.post(
                "/api/reports/generate",
                data={
                    "reportType": "sales_performance_report",
                    "conversationId": "chat-1",
                    "userPrompt": "sadece İstanbul bölgesi",
                },
                files={
                    "file": (
                        "veriler.xlsx",
                        b"fake-input",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )

        self.assertEqual(response.status_code, 200)
        assistant_payload = json.loads(response.json()["content"])
        self.assertEqual(assistant_payload["type"], "report_error")
        self.assertEqual(assistant_payload["errorMessage"], "Seçtiğin filtrelerden sonra rapor üretilecek veri kalmadı.")
        self.assertEqual(assistant_payload["filterSummary"]["filteredRowCount"], 0)

        with chatbot_db.db() as connection:
            report_row = connection.execute('SELECT * FROM "Report" ORDER BY "createdAt" DESC LIMIT 1').fetchone()
        stored_report = chatbot_db.row_to_report(report_row)
        self.assertEqual(stored_report["status"], "failed")
        self.assertEqual(stored_report["filterSummary"]["userPrompt"], "sadece İstanbul bölgesi")
        self.assertEqual(stored_report["filterSummary"]["filteredRowCount"], 0)


if __name__ == "__main__":
    unittest.main()
