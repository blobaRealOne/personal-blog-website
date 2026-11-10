import base64
import json
import tempfile
import unittest
from pathlib import Path
from typing import override
from unittest.mock import patch

from src.app import app


class TestDelete(unittest.TestCase):
    @override
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        self.article_path = Path(self.temp_dir.name)  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]

        self.patcher = patch("src.app.ARTICLE_PATH", self.article_path)  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        _ = self.patcher.start()

        self.user_patcher = patch("src.app.ADMIN_USER", "test_admin")  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        self.password_patcher = patch("src.app.ADMIN_PASSWORD", "test_password")  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        _ = self.user_patcher.start()
        _ = self.password_patcher.start()

        app.config["TESTING"] = True
        self.client = app.test_client()  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]

        self.auth_headers = {  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
            "Authorization": "Basic "
            + base64.b64encode(b"test_admin:test_password").decode("ascii")
        }

        self.article_file = self.article_path / "1.json"  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        _ = self.article_file.write_text(
            json.dumps(
                {
                    "title": "Test article",
                    "content": "Test content",
                    "timestamp": "2026-11-09T12:00:00",
                }
            ),
            encoding="utf-8",
        )

    @override
    def tearDown(self):
        self.password_patcher.stop()
        self.user_patcher.stop()
        self.patcher.stop()
        self.temp_dir.cleanup()

    def test_delete_existing_article(self):
        response = self.client.post(
            "/delete/1",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.article_file.exists())

    def test_delete_without_authentication(self):
        response = self.client.post("/delete/1")

        self.assertEqual(response.status_code, 401)
        self.assertTrue(self.article_file.exists())

    def test_delete_nonexistent_article(self):
        response = self.client.post(
            "/delete/999",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 302)


if __name__ == "__main__":
    _ = unittest.main()
