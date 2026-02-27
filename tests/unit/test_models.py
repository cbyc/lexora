"""Tests for Pydantic models in src/models.py."""

import pytest
from pydantic import ValidationError

from models import NOT_FOUND, AskResponse


class TestAskResponse:
    def test_valid_answer_with_sources_passes(self):
        """A non-empty answer with at least one source is valid."""
        r = AskResponse(text="Python's GIL is a mutex.", sources=["notes/python.txt"])
        assert r.text == "Python's GIL is a mutex."
        assert r.sources == ["notes/python.txt"]

    def test_not_found_with_empty_sources_passes(self):
        """The NOT_FOUND sentinel with empty sources is valid."""
        r = AskResponse(text=NOT_FOUND, sources=[])
        assert r.text == NOT_FOUND
        assert r.sources == []

    def test_answer_with_empty_sources_raises(self):
        """An answer that is not NOT_FOUND must have at least one source."""
        with pytest.raises(ValidationError):
            AskResponse(text="Some real answer.", sources=[])

    def test_multiple_sources_are_accepted(self):
        """Multiple sources should be stored as-is."""
        r = AskResponse(
            text="Both tools differ.",
            sources=["https://a.com", "https://b.com"],
        )
        assert len(r.sources) == 2
