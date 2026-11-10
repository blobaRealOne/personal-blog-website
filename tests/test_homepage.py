import unittest
from typing import override
from unittest.mock import patch

from src.app import app


class HomepageTestCase(unittest.TestCase):
    @override
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]

    @patch("src.app.json_data_parser")
    def test_homepage_returns_200(self, mock_parser):  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]
        mock_parser.return_value = []

        response = self.client.get("/home")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"There are no articles yet!", response.data)  # pyright: ignore[reportAny]

    @patch("src.app.json_data_parser")
    def test_homepage_displays_articles(self, mock_parser):  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]
        mock_parser.return_value = [
            {
                "article_title": "Test Article",
                "article_timestamp": "November 9 2026",
                "article_name": "1",
            }
        ]

        response = self.client.get("/home")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test Article", response.data)  # pyright: ignore[reportAny]
        self.assertIn(b"November 9 2026", response.data)  # pyright: ignore[reportAny]
        self.assertIn(b"/article/1", response.data)  # pyright: ignore[reportAny]


if __name__ == "__main__":
    _ = unittest.main()
