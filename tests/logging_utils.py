import logging
import unittest
from typing import override


class IsolatedLoggingTestCase(unittest.TestCase):

    @override
    def setUp(self):
        super().setUp()

        self.logger = logging.getLogger("personal_blog") # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        self.original_handlers = self.logger.handlers.copy() # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        self.original_propagate = self.logger.propagate # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]

        self.logger.handlers.clear()
        self.logger.propagate = False
        self.logger.addHandler(logging.NullHandler())

        self.addCleanup(self.restore_handlers)

    def restore_handlers(self):
        self.logger.handlers.clear()
        self.logger.handlers.extend(self.original_handlers)
        self.logger.propagate = self.original_propagate
