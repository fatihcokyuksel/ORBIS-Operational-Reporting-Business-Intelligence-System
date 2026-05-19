import tempfile
import unittest
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from api import chatbot
from services.report.report_registry_service import ReportRegistryService
from utils import database as database_utils


class ChatbotReportRegressionTests(unittest.TestCase):
    def test_report_registry_loads_definitions_from_backend_root(self):
        service = ReportRegistryService()
        definition = service.get_report_definition("income_expense_report")
        self.assertEqual(definition["report_id"], "income_expense_report")

    def test_empty_filter_message_only_used_for_real_applied_filters(self):
        self.assertFalse(
            chatbot.should_report_empty_filter_result(
                {
                    "applied": False,
                    "summaryLines": [],
                    "filteredRowCount": 0,
                }
            )
        )
        self.assertTrue(
            chatbot.should_report_empty_filter_result(
                {
                    "applied": True,
                    "summaryLines": [],
                    "filteredRowCount": 0,
                }
            )
        )

    def test_download_report_endpoint_resolves_legacy_storage_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            backend_root = temp_root / "backend"
            backend_root.mkdir(parents=True, exist_ok=True)

            report_id = "report-1"
            user_id = "user-1"
            actual_file = backend_root / "storage" / "reports" / user_id / f"{report_id}.xlsx"
            actual_file.parent.mkdir(parents=True, exist_ok=True)
            actual_file.write_bytes(b"fake-xlsx")

            original_db_path = database_utils.DATABASE_PATH
            original_backend_root = chatbot.BACKEND_ROOT
            original_repo_root = chatbot.REPO_ROOT
            try:
                database_utils.DATABASE_PATH = temp_root / "test.db"
                chatbot.BACKEND_ROOT = backend_root
                chatbot.REPO_ROOT = temp_root
                database_utils.init_db()

                with database_utils.db() as connection:
                    connection.execute(
                        """
                        INSERT INTO "Report" (
                            "id", "userId", "reportType", "displayName", "status",
                            "filePath", "downloadUrl", "outputFormat", "createdAt"
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            report_id,
                            user_id,
                            "income_expense_report",
                            "Gelir Gider Raporu",
                            "success",
                            str(temp_root / "chatbot-api" / "storage" / "reports" / user_id / f"{report_id}.xlsx"),
                            f"/api/reports/download/{report_id}",
                            "xlsx",
                            database_utils.now_iso(),
                        ),
                    )

                response = chatbot.download_report_endpoint(report_id, {"userId": user_id})
                self.assertEqual(Path(response.path), actual_file)

                with database_utils.db() as connection:
                    updated_path = connection.execute(
                        'SELECT "filePath" FROM "Report" WHERE "id" = ?',
                        (report_id,),
                    ).fetchone()["filePath"]
                self.assertEqual(updated_path, str(actual_file))
            finally:
                database_utils.DATABASE_PATH = original_db_path
                chatbot.BACKEND_ROOT = original_backend_root
                chatbot.REPO_ROOT = original_repo_root


if __name__ == "__main__":
    unittest.main()
