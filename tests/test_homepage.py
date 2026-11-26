import unittest
from typing import override
from unittest.mock import patch

from src.app import app
from tests.logging_utils import IsolatedLoggingTestCase


class HomepageTestCase(IsolatedLoggingTestCase):
    @override
    def setUp(self):
        super().setUp()
        self.config_patcher = patch.dict(  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
            app.config,
            {"TESTING": True},
        )
        self.config_patcher.start()  # pyright: ignore[reportAny]
        self.addCleanup(self.config_patcher.stop)  # pyright: ignore[reportAny]

        self.client = app.test_client()  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]

    @patch("src.routes.json_data_parser")
    def test_homepage_returns_200(self, mock_parser):  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]
        mock_parser.return_value = []

        response = self.client.get("/home")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"There are no articles yet!", response.data)  # pyright: ignore[reportAny]

    @patch("src.routes.json_data_parser")
    def test_homepage_displays_articles(self, mock_parser):  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]
        mock_parser.return_value = [
            {
                "title": "Test Article",
                "timestamp": "November 9 2026",
                "timestamp_raw": "2026-11-09T12:00",
                "article_id": "1",
            }
        ]

        response = self.client.get("/home")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test Article", response.data)  # pyright: ignore[reportAny]
        self.assertIn(b"November 9 2026", response.data)  # pyright: ignore[reportAny]
        self.assertIn(b"/article/1", response.data)  # pyright: ignore[reportAny]


if __name__ == "__main__":
    _ = unittest.main()
