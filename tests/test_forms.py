import base64
import json
import tempfile
import unittest
from pathlib import Path
from typing import override
from unittest.mock import patch

from src.app import app


class TestForms(unittest.TestCase):
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

    @override
    def tearDown(self):
        self.password_patcher.stop()
        self.user_patcher.stop()
        self.patcher.stop()
        self.temp_dir.cleanup()

    def test_create_article(self):
        response = self.client.post(
            "/new",
            data={
                "title": "New article",
                "content": "Article content",
                "publishing_date": "2026-11-09T12:00",
            },
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 302)

        article_file = self.article_path / "1.json"
        self.assertTrue(article_file.exists())

        article = json.loads(  # pyright: ignore[reportAny]
            article_file.read_text(encoding="utf-8")
        )

        self.assertEqual(article["title"], "New article")
        self.assertEqual(article["content"], "Article content")

    def test_create_article_with_empty_fields(self):
        response = self.client.post(
            "/new",
            data={
                "title": "",
                "content": "Article content",
                "publishing_date": "2026-11-09T12:00",
            },
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 400)

    def test_create_article_with_invalid_date(self):
        response = self.client.post(
            "/new",
            data={
                "title": "New article",
                "content": "Article content",
                "publishing_date": "not-a-date",
            },
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 400)

    def test_edit_article(self):
        article_file = self.article_path / "1.json"
        _ = article_file.write_text(
            json.dumps(
                {
                    "title": "Old title",
                    "content": "Old content",
                    "timestamp": "2026-11-09T12:00:00",
                }
            ),
            encoding="utf-8",
        )

        response = self.client.post(
            "/edit/1",
            data={
                "title": "Updated title",
                "content": "Updated content",
                "publishing_date": "2026-11-10T15:30",
            },
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 302)

        article = json.loads(  # pyright: ignore[reportAny]
            article_file.read_text(encoding="utf-8")
        )

        self.assertEqual(article["title"], "Updated title")
        self.assertEqual(article["content"], "Updated content")
        self.assertEqual(article["timestamp"], "2026-11-10T15:30:00")

    def test_edit_nonexistent_article(self):
        response = self.client.post(
            "/edit/999",
            data={
                "title": "Updated title",
                "content": "Updated content",
                "publishing_date": "2026-11-10T15:30",
            },
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    _ = unittest.main()
