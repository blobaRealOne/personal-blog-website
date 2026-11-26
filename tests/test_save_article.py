import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import override
from unittest.mock import patch

from src.app import save_article
from tests.logging_utils import IsolatedLoggingTestCase


class TestArticleCreator(IsolatedLoggingTestCase):
    @override
    def setUp(self):
        super().setUp()
        self.temp_dir = TemporaryDirectory()  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        self.addCleanup(self.temp_dir.cleanup)

        self.article_path = Path(self.temp_dir.name)  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]

        self.patcher = patch("src.app.ARTICLE_PATH", self.article_path)  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        _ = self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def _read_article(self, article_id: int) -> dict:  # pyright: ignore[reportUnknownParameterType, reportMissingTypeArgument]
        path = self.article_path / f"{article_id}.json"

        with path.open("r", encoding="utf-8") as file:
            return json.load(file)  # pyright: ignore[reportAny]

    def test_create_first_article(self):
        save_article(
            title="First article",
            content="Hello world!",
            timestamp_raw="2025-01-15T12:30",
        )

        result = self._read_article(1)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]

        self.assertEqual(result["title"], "First article")
        self.assertEqual(result["content"], "Hello world!")
        self.assertEqual(result["timestamp_raw"], "2025-01-15T12:30")
        self.assertEqual(result["timestamp"], "January 15 2025")

    def test_create_next_article(self):
        save_article("First", "Content 1", "2025-01-15T12:30")
        save_article("Second", "Content 2", "2025-01-16T12:30")

        self.assertTrue((self.article_path / "1.json").exists())
        self.assertTrue((self.article_path / "2.json").exists())

    def test_edit_existing_article(self):
        save_article("Old title", "Old content", "2025-01-15T12:30")

        save_article(
            title="New title",
            content="New content",
            timestamp_raw="2025-02-15T12:30",
            edit_by_id=1,
        )

        result = self._read_article(1)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]

        self.assertEqual(result["title"], "New title")
        self.assertEqual(result["content"], "New content")
        self.assertEqual(result["timestamp"], "February 15 2025")
        self.assertEqual(result["timestamp_raw"], "2025-02-15T12:30")

    def test_unicode_content(self):
        save_article(
            title="Привет, мир!",
            content="Тестирование UTF-8: Привет!",
            timestamp_raw="2025-01-15T12:30",
        )

        result = self._read_article(1)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]

        self.assertEqual(result["title"], "Привет, мир!")
        self.assertEqual(result["content"], "Тестирование UTF-8: Привет!")


if __name__ == "__main__":
    _ = unittest.main()
