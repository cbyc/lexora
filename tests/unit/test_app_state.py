"""Tests for AppState NamedTuple."""

from src.app_state import AppState


class TestAppState:
    def test_app_state_is_named_tuple(self):
        """AppState should be a NamedTuple subclass."""
        assert issubclass(AppState, tuple)

    def test_app_state_has_pipeline_field(self):
        """AppState should have a 'pipeline' field."""
        assert "pipeline" in AppState._fields

    def test_app_state_has_feed_service_field(self):
        """AppState should have a 'feed_service' field."""
        assert "feed_service" in AppState._fields
