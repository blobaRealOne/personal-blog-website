import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import override
from unittest.mock import patch

from src.app import json_data_parser


class TestJsonDataParser(unittest.TestCase):
    @override
    def setUp(self):
        self.temp_dir = TemporaryDirectory()  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        self.article_path = Path(self.temp_dir.name)  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]

        patcher = patch("src.app.ARTICLE_PATH", self.article_path)
        _ = patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def _create_article(self, article_id: int, title: str):
        article = {
            "title": title,
            "content": f"Content of {title}",
            "timestamp": "2025-01-15T12:30",
        }

        path = self.article_path / f"{article_id}.json"

        with path.open("w", encoding="utf-8") as file:
            json.dump(article, file, ensure_ascii=False)

    def test_parse_article_by_id(self):
        self._create_article(1, "First article")

        result = json_data_parser(1)

        self.assertEqual(result["title"], "First article")
        self.assertEqual(result["content"], "Content of First article")
        self.assertEqual(result["timestamp"], "January 15 2025")

    def test_parse_all_articles(self):
        self._create_article(2, "Second article")
        self._create_article(1, "First article")

        result = json_data_parser()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["article_name"], "1")
        self.assertEqual(result[1]["article_name"], "2")

    def test_parse_article_with_raw_date(self):
        self._create_article(1, "First article")

        result = json_data_parser(1, raw_date=True)

        self.assertEqual(result["timestamp"], "2025-01-15T12:30")

    def test_parse_nonexistent_article(self):
        with self.assertRaises(FileNotFoundError):
            _ = json_data_parser(999)

    def test_parse_empty_directory(self):
        result = json_data_parser()
        self.assertEqual(result, [])

    def test_parse_articles_in_numeric_order(self):
        self._create_article(10, "Tenth article")
        self._create_article(2, "Second article")
        self._create_article(1, "First article")

        result = json_data_parser()

        self.assertEqual(
            [article["article_name"] for article in result],
            ["1", "2", "10"],
        )


if __name__ == "__main__":
    _ = unittest.main()
