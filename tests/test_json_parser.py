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
        self.addCleanup(self.temp_dir.cleanup)

        self.article_path = Path(self.temp_dir.name)  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]

        self.patcher = patch("src.app.ARTICLE_PATH", self.article_path)  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        _ = self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def _create_article(self, article_id: int, title: str):
        article = {  # pyright: ignore[reportUnknownVariableType]
            "title": title,
            "content": f"Content of {title}",
            "timestamp": "January 15 2025",
            "timestamp_raw": "2025-01-15T12:30",
            "comments": [],
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
        self.assertEqual(result["timestamp_raw"], "2025-01-15T12:30")

    def test_parse_all_articles(self):
        self._create_article(2, "Second article")
        self._create_article(1, "First article")

        result = json_data_parser()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["article_id"], "1")
        self.assertEqual(result[1]["article_id"], "2")

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
            [article["article_id"] for article in result],
            ["1", "2", "10"],
        )

    def test_parse_article_with_invalid_json(self):
        path = self.article_path / "1.json"

        _ = path.write_text(
            '{"title": "Broken article"',
            encoding="utf-8",
        )

        with self.assertRaises(RuntimeError):
            _ = json_data_parser(1)

    def test_parse_article_with_duplicate_json_keys(self):
        path = self.article_path / "1.json"
        _ = path.write_text(
            """
            {
                "title": "First title",
                "title": "Second title",
                "content": "Content",
                "timestamp": "January 15 2025",
                "timestamp_raw": "2025-01-15T12:30",
                "comments": []
            }
            """,
            encoding="utf-8",
        )

        with self.assertRaises(FileNotFoundError):
            _ = json_data_parser(1)

    def test_parse_article_with_missing_field(self):
        self._create_article(1, "Test article")

        path = self.article_path / "1.json"
        article = json.loads(path.read_text(encoding="utf-8"))  # pyright: ignore[reportAny]
        del article["content"]

        _ = path.write_text(
            json.dumps(article),
            encoding="utf-8",
        )

        with self.assertRaises(FileNotFoundError):
            _ = json_data_parser(1)

    def test_parse_article_with_unexpected_field(self):
        self._create_article(1, "Test article")

        path = self.article_path / "1.json"
        article = json.loads(path.read_text(encoding="utf-8"))  # pyright: ignore[reportAny]
        article["unexpected"] = "Unexpected value"

        _ = path.write_text(
            json.dumps(article),
            encoding="utf-8",
        )

        with self.assertRaises(FileNotFoundError):
            _ = json_data_parser(1)

    def test_parse_article_with_invalid_field_type(self):
        self._create_article(1, "Test article")

        path = self.article_path / "1.json"
        article = json.loads(path.read_text(encoding="utf-8"))  # pyright: ignore[reportAny]
        article["title"] = 123

        _ = path.write_text(
            json.dumps(article),
            encoding="utf-8",
        )

        with self.assertRaises(FileNotFoundError):
            _ = json_data_parser(1)

    def test_parse_article_with_invalid_timestamp(self):
        self._create_article(1, "Test article")

        path = self.article_path / "1.json"
        article = json.loads(path.read_text(encoding="utf-8"))  # pyright: ignore[reportAny]
        article["timestamp_raw"] = "not-a-timestamp"

        _ = path.write_text(
            json.dumps(article),
            encoding="utf-8",
        )

        with self.assertRaises(FileNotFoundError):
            _ = json_data_parser(1)

    def test_parse_article_with_invalid_comments_type(self):
        self._create_article(1, "Test article")

        path = self.article_path / "1.json"
        article = json.loads(path.read_text(encoding="utf-8"))  # pyright: ignore[reportAny]
        article["comments"] = "not-a-list"

        _ = path.write_text(
            json.dumps(article),
            encoding="utf-8",
        )

        with self.assertRaises(FileNotFoundError):
            _ = json_data_parser(1)

    def test_parse_article_with_duplicate_comment_ids(self):
        self._create_article(1, "Test article")

        path = self.article_path / "1.json"
        article = json.loads(path.read_text(encoding="utf-8"))  # pyright: ignore[reportAny]

        comment = {
            "comment_id": "1",
            "username": "TestUser",
            "content": "Test comment",
            "timestamp": "January 15 2025",
            "timestamp_raw": "2025-01-15T12:30",
        }

        article["comments"] = [comment, comment.copy()]

        _ = path.write_text(
            json.dumps(article),
            encoding="utf-8",
        )

        with self.assertRaises(FileNotFoundError):
            _ = json_data_parser(1)

    def test_parse_all_articles_skips_invalid_json(self):
        self._create_article(1, "Valid article")

        invalid_path = self.article_path / "2.json"
        _ = invalid_path.write_text(
            '{"title": "Broken"',
            encoding="utf-8",
        )

        self._create_article(3, "Another valid article")

        result = json_data_parser()

        self.assertEqual(
            [article["article_id"] for article in result],
            ["1", "3"],
        )


if __name__ == "__main__":
    _ = unittest.main()
