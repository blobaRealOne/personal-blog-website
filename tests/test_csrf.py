import base64
import unittest
from typing import override
from unittest.mock import patch

from src.app import app


class TestCSRF(unittest.TestCase):
    @override
    def setUp(self):
        self.config_patcher = patch.dict(  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
            app.config,
            {
                "TESTING": True,
                "WTF_CSRF_ENABLED": True,
            },
        )
        self.config_patcher.start()  # pyright: ignore[reportAny]
        self.addCleanup(self.config_patcher.stop)  # pyright: ignore[reportAny]

        self.client = app.test_client()  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]

        credentials = base64.b64encode(b"test_admin:test_password").decode("ascii")

        self.auth_headers = {  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
            "Authorization": f"Basic {credentials}",
        }

        self.user_patcher = patch(  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
            "src.app.ADMIN_USER",
            "test_admin",
        )
        _ = self.user_patcher.start()
        self.addCleanup(self.user_patcher.stop)

        self.password_patcher = patch(  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
            "src.app.ADMIN_PASSWORD",
            "test_password",
        )
        _ = self.password_patcher.start()
        self.addCleanup(self.password_patcher.stop)

    def test_comment_post_without_csrf_token(self):
        response = self.client.post(
            "/article/1/comment",
            data={
                "comment_username": "TestUser",
                "comment_content": "Test comment",
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_admin_post_without_csrf_token(self):
        response = self.client.post(
            "/new",
            headers=self.auth_headers,
            data={
                "title": "New article",
                "content": "Article content",
                "publishing_date": "2026-11-09T12:00",
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_delete_post_without_csrf_token(self):
        response = self.client.post(
            "/delete/1",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    _ = unittest.main()
