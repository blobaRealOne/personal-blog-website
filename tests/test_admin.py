import base64
import unittest
from typing import override
from unittest.mock import patch

from src.app import app


class AdminTestCase(unittest.TestCase):
    @override
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]

        self.credentials = patch.multiple(  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
            "src.app", ADMIN_USER="test_admin", ADMIN_PASSWORD="test_password"
        )
        self.credentials.start()
        self.addCleanup(self.credentials.stop)

    def get_auth_headers(self):
        credentials = base64.b64encode(b"test_admin:test_password").decode("ascii")

        return {"Authorization": f"Basic {credentials}"}

    def test_admin_requires_authentication(self):
        response = self.client.get("/admin")

        self.assertEqual(response.status_code, 401)
        self.assertIn(
            "WWW-Authenticate",
            response.headers,
        )

    @patch("src.app.json_data_parser")
    def test_admin_returns_200_with_valid_credentials(
        self,
        mock_parser,  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]
    ):
        mock_parser.return_value = []

        response = self.client.get(
            "/admin",
            headers=self.get_auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "There are no articles yet!",
            response.get_data(as_text=True),
        )

    @patch("src.app.json_data_parser")
    def test_admin_displays_articles(self, mock_parser):  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]
        mock_parser.return_value = [
            {
                "article_title": "Admin Test Article",
                "article_timestamp": "November 9 2026",
                "article_name": "1",
            }
        ]

        response = self.client.get(
            "/admin",
            headers=self.get_auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Admin Test Article",
            response.get_data(as_text=True),
        )


if __name__ == "__main__":
    _ = unittest.main()
