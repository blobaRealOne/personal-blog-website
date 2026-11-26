import json
import logging
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from typing import override
from unittest.mock import patch

from src.app import app

logger = logging.getLogger("personal_blog")


class TestComments(unittest.TestCase):
    @override
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        self.article_path = Path(self.temp_dir.name)  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]

        self.patcher = patch("src.app.ARTICLE_PATH", self.article_path)  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        _ = self.patcher.start()

        self.original_handlers = logger.handlers.copy()  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        logger.handlers.clear()

        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False

        self.client = app.test_client()  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]

        self.article_file = self.article_path / "1.json"  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        self._create_article()

    @override
    def tearDown(self):
        logger.handlers.clear()
        logger.handlers.extend(self.original_handlers)

        self.patcher.stop()
        self.temp_dir.cleanup()

    def _create_article(self):
        article = {  # pyright: ignore[reportUnknownVariableType]
            "title": "Test article",
            "content": "Test content",
            "timestamp": "November 9 2026",
            "timestamp_raw": "2026-11-09T12:00:00",
            "comments": [],
        }

        _ = self.article_file.write_text(
            json.dumps(article),
            encoding="utf-8",
        )

    def _read_article(self):  # pyright: ignore[reportAny]
        return json.loads(  # pyright: ignore[reportAny]
            self.article_file.read_text(encoding="utf-8")
        )

    def test_comment_page_returns_200(self):
        response = self.client.get("/article/1/comment")

        self.assertEqual(response.status_code, 200)

    def test_comment_page_returns_404_for_nonexistent_article(self):
        response = self.client.get("/article/999/comment")

        self.assertEqual(response.status_code, 404)

    def test_add_comment(self):
        with self.assertLogs("personal_blog", level="INFO") as captured:
            response = self.client.post(
                "/article/1/comment",
                data={
                    "comment_username": "TestUser",
                    "comment_content": "Test comment",
                },
            )

        self.assertEqual(response.status_code, 302)

        article = self._read_article()  # pyright: ignore[reportAny]
        comments = article["comments"]  # pyright: ignore[reportAny]

        self.assertEqual(len(comments), 1)  # pyright: ignore[reportAny]

        comment = comments[0]  # pyright: ignore[reportAny]

        parsed_timestamp = datetime.fromisoformat(comment["timestamp_raw"])  # pyright: ignore[reportAny]

        self.assertEqual(comment["comment_id"], "1")
        self.assertEqual(comment["username"], "TestUser")
        self.assertEqual(comment["content"], "Test comment")
        self.assertEqual(
            comment["timestamp"],
            f"{parsed_timestamp:%B} {parsed_timestamp.day} {parsed_timestamp:%Y}",
        )
        self.assertIn(
            "Added comment: article_id=1, comment_id=1",
            [record.getMessage() for record in captured.records],
        )

    def test_add_comment_preserves_existing_comments(self):
        article = self._read_article()  # pyright: ignore[reportAny]

        article["comments"].append(  # pyright: ignore[reportAny]
            {
                "comment_id": "1",
                "username": "FirstUser",
                "content": "First comment",
                "timestamp": "November 9 2026",
                "timestamp_raw": "2026-11-09T13:00:00",
            }
        )

        _ = self.article_file.write_text(
            json.dumps(article),
            encoding="utf-8",
        )

        response = self.client.post(
            "/article/1/comment",
            data={
                "comment_username": "SecondUser",
                "comment_content": "Second comment",
            },
        )

        self.assertEqual(response.status_code, 302)

        updated_article = self._read_article()  # pyright: ignore[reportAny]
        comments = updated_article["comments"]  # pyright: ignore[reportAny]

        self.assertEqual(len(comments), 2)  # pyright: ignore[reportAny]
        self.assertEqual(comments[0]["comment_id"], "1")
        self.assertEqual(comments[1]["comment_id"], "2")
        self.assertEqual(comments[1]["username"], "SecondUser")

    def test_add_comment_with_empty_fields(self):
        response = self.client.post(
            "/article/1/comment",
            data={
                "comment_username": "",
                "comment_content": "Test comment",
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_add_comment_with_excessive_username_length(self):
        response = self.client.post(
            "/article/1/comment",
            data={
                "comment_username": "U" * 41,
                "comment_content": "Test comment",
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_add_comment_with_excessive_content_length(self):
        response = self.client.post(
            "/article/1/comment",
            data={
                "comment_username": "TestUser",
                "comment_content": "C" * 3001,
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_add_comment_to_nonexistent_article(self):
        response = self.client.post(
            "/article/999/comment",
            data={
                "comment_username": "TestUser",
                "comment_content": "Test comment",
            },
        )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    _ = unittest.main()
