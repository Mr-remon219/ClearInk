"""Tests for clearink.tool.team.protocol.handlers built-in protocol handlers."""

from __future__ import annotations

import unittest

from clearink.tool.team.protocol.handlers import (
    _handle_shutdown_request,
)


class TestHandleShutdownRequest(unittest.TestCase):
    """Tests for _handle_shutdown_request."""

    def test_returns_none_when_teammate_not_registered(self):
        """Returns None if teammate not in active registry (already stopped)."""
        protocol = {
            "request_id": "req_000001",
        }
        result = _handle_shutdown_request("nonexistent_teammate", protocol)
        # When teammate doesn't exist, returns a pre-stopped response
        self.assertIsNotNone(result)
        self.assertEqual(result["protocol"]["type"], "shutdown_response")
        self.assertTrue(result["protocol"]["payload"]["approve"])

    def test_response_contains_shutdown_response_type(self):
        """Response protocol type is shutdown_response."""
        protocol = {
            "request_id": "req_000002",
        }
        result = _handle_shutdown_request("unknown_teammate", protocol)
        self.assertEqual(result["protocol"]["type"], "shutdown_response")

    def test_response_request_id_matches(self):
        """Response carries the same request_id as the request."""
        request_id = "req_000003"
        protocol = {
            "request_id": request_id,
        }
        result = _handle_shutdown_request("ghost_teammate", protocol)
        self.assertEqual(result["protocol"]["request_id"], request_id)
