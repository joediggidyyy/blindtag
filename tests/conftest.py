"""
tests/conftest.py
=================
Shared pytest fixtures for the BlindTag test suite.

Provides a session-scoped QApplication instance for widget tests.
No new runtime dependency required — PySide6 is already a project dependency.
"""
import pytest


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication for PySide6 widget tests."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
