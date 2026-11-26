import json
import tempfile
import unittest
from pathlib import Path
from typing import override
from unittest.mock import patch

from src.app import app
from tests.logging_utils import IsolatedLoggingTestCase


class TestArticlePage(IsolatedLoggingTestCase):
    @override
    def setUp(self):
        super().setUp()
        self.temp_dir = tempfile.TemporaryDirectory()  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        self.addCleanup(self.temp_dir.cleanup)

        self.article_path = Path(self.temp_dir.name)  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]

        self.article_patcher = patch(  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
            "src.app.ARTICLE_PATH",
            self.article_path,
        )
        _ = self.article_patcher.start()
        self.addCleanup(self.article_patcher.stop)

        self.config_patcher = patch.dict(  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
            app.config,
            {"TESTING": True},
        )
        self.config_patcher.start()  # pyright: ignore[reportAny]
        self.addCleanup(self.config_patcher.stop)  # pyright: ignore[reportAny]

        self.client = app.test_client()  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]

    def _create_article(self):
        article = {  # pyright: ignore[reportUnknownVariableType]
            "title": "Test article",
            "content": "Test content",
            "timestamp": "November 9 2026",
            "timestamp_raw": "2026-11-09T12:00:00",
            "comments": [],
        }

        path = self.article_path / "1.json"
        _ = path.write_text(
            json.dumps(article),
            encoding="utf-8",
        )

    def test_article_page_returns_200(self):
        self._create_article()

        response = self.client.get("/article/1")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"Test article",
            response.data,  # pyright: ignore[reportAny]
        )
        self.assertIn(
            b"Test content",
            response.data,  # pyright: ignore[reportAny]
        )

    def test_article_page_returns_404_for_nonexistent_article(self):
        response = self.client.get("/article/999")

        self.assertEqual(response.status_code, 404)

    def test_article_page_returns_500_for_invalid_json(self):
        path = self.article_path / "1.json"

        _ = path.write_text(
            '{"title": "Broken article"',
            encoding="utf-8",
        )

        response = self.client.get("/article/1")

        self.assertEqual(response.status_code, 500)


if __name__ == "__main__":
    _ = unittest.main()
