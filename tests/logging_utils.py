"""Logging utilities for isolated unit tests.

Provides a base test case that temporarily replaces application
logger handlers and restores the original logging configuration
after each test.
"""
import logging
import unittest
from typing import override


class IsolatedLoggingTestCase(unittest.TestCase):
    """Base test case that isolates application logging.

    Temporarily replaces the handlers of the ``personal_blog`` logger
    with a ``NullHandler`` and disables log propagation.

    The original handlers and propagation setting are saved during
    setup and restored during test cleanup.

    Subclasses can use the standard ``unittest`` logging assertions,
    such as ``assertLogs``, without writing test-generated messages
    to the application's configured log files.
    """
    @override
    def setUp(self):
        """Save and isolate the application logger configuration.

        Registers logger restoration as a cleanup action to ensure that
        the original configuration is recovered after the test.
        """
        super().setUp()

        self.logger = logging.getLogger("personal_blog")  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        self.original_handlers = self.logger.handlers.copy()  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]
        self.original_propagate = self.logger.propagate  # pyright: ignore[reportUnannotatedClassAttribute, reportUninitializedInstanceVariable]

        self.logger.handlers.clear()
        self.logger.propagate = False
        self.logger.addHandler(logging.NullHandler())

        self.addCleanup(self.restore_handlers)

    def restore_handlers(self):
        """Restore the original application logger configuration.

        Removes the temporary handler, reinstates the original handlers,
        and restores the logger's previous propagation setting.
        """
        self.logger.handlers.clear()
        self.logger.handlers.extend(self.original_handlers)
        self.logger.propagate = self.original_propagate
