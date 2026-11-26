from tests.logging_utils import IsolatedLoggingTestCase
import base64
import json
import tempfile
import unittest
from pathlib import Path
from typing import override
from unittest.mock import patch

from src.app import app


class TestForms(IsolatedLoggingTestCase):
    @override
    def setUp(self):
        super().setUp()
        self.temp_dir = tempfile.TemporaryDirectory()  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        self.addCleanup(self.temp_dir.cleanup)

        self.article_path = Path(self.temp_dir.name)  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]

        self.article_patcher = patch("src.app.ARTICLE_PATH", self.article_path)  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        _ = self.article_patcher.start()
        self.addCleanup(self.article_patcher.stop)

        self.user_patcher = patch("src.app.ADMIN_USER", "test_admin")  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        _ = self.user_patcher.start()
        self.addCleanup(self.user_patcher.stop)

        self.password_patcher = patch("src.app.ADMIN_PASSWORD", "test_password")  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        _ = self.password_patcher.start()
        self.addCleanup(self.password_patcher.stop)

        self.config_patcher = patch.dict(  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
            app.config,
            {
                "TESTING": True,
                "WTF_CSRF_ENABLED": False,
            },
        )
        self.config_patcher.start()  # pyright: ignore[reportAny]
        self.addCleanup(self.config_patcher.stop)  # pyright: ignore[reportAny]

        self.client = app.test_client()  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]

        self.auth_headers = {  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
            "Authorization": "Basic "
            + base64.b64encode(b"test_admin:test_password").decode("ascii")
        }

    def _create_test_article(self):
        article_file = self.article_path / "1.json"

        _ = article_file.write_text(
            json.dumps(
                {
                    "title": "Old title",
                    "content": "Old content",
                    "timestamp": "November 9 2026",
                    "timestamp_raw": "2026-11-09T12:00:00",
                    "comments": [],
                }
            ),
            encoding="utf-8",
        )

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
                    "timestamp": "November 9 2026",
                    "timestamp_raw": "2026-11-09T12:00:00",
                    "comments": [],
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
        self.assertEqual(article["timestamp"], "November 10 2026")
        self.assertEqual(article["timestamp_raw"], "2026-11-10T15:30:00")

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

    def test_get_edit_nonexistent_article(self):
        response = self.client.get(
            "/edit/999",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 404)

    def test_create_article_with_excessive_title_length(self):
        response = self.client.post(
            "/new",
            data={
                "title": "T" * 121,
                "content": "Article content",
                "publishing_date": "2026-11-09T12:00",
            },
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 400)

    def test_create_article_with_excessive_content_length(self):
        response = self.client.post(
            "/new",
            data={
                "title": "New article",
                "content": "C" * 50001,
                "publishing_date": "2026-11-09T12:00",
            },
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 400)

    def test_edit_article_with_excessive_title_length(self):
        self._create_test_article()

        response = self.client.post(
            "/edit/1",
            data={
                "title": "T" * 121,
                "content": "Updated content",
                "publishing_date": "2026-11-10T15:30",
            },
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 400)

    def test_edit_article_with_excessive_content_length(self):
        self._create_test_article()

        response = self.client.post(
            "/edit/1",
            data={
                "title": "Updated title",
                "content": "C" * 50001,
                "publishing_date": "2026-11-10T15:30",
            },
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    _ = unittest.main()
