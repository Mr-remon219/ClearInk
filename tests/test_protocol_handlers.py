"""Tests for clearink.tool.team.protocol.handlers built-in protocol handlers."""

from __future__ import annotations

import unittest

from clearink.tool.team.protocol.handlers import (
    _handle_plan_request,
    _handle_review_request,
)


class TestHandlePlanRequest(unittest.TestCase):
    """Tests for _handle_plan_request."""

    def test_returns_dict_with_role_user(self):
        protocol = {
            "request_id": "req_000001",
            "payload": {"plan": "Implement feature X in three steps."},
        }
        result = _handle_plan_request("teammate_a", protocol)
        self.assertEqual(result["role"], "user")

    def test_content_contains_plan_text(self):
        plan_text = "Step 1: Design. Step 2: Implement. Step 3: Test."
        protocol = {
            "request_id": "req_000002",
            "payload": {"plan": plan_text},
        }
        result = _handle_plan_request("teammate_b", protocol)
        self.assertIn(plan_text, result["content"])

    def test_content_contains_request_id(self):
        request_id = "req_000003"
        protocol = {
            "request_id": request_id,
            "payload": {"plan": "Some plan."},
        }
        result = _handle_plan_request("teammate_c", protocol)
        self.assertIn(request_id, result["content"])


class TestHandleReviewRequest(unittest.TestCase):
    """Tests for _handle_review_request."""

    def test_returns_dict_with_role_user(self):
        protocol = {
            "request_id": "req_000010",
            "payload": {"content": "Code review content."},
        }
        result = _handle_review_request("teammate_x", protocol)
        self.assertEqual(result["role"], "user")

    def test_content_contains_review_content(self):
        review_text = "Please review this pull request for correctness."
        protocol = {
            "request_id": "req_000011",
            "payload": {"content": review_text},
        }
        result = _handle_review_request("teammate_y", protocol)
        self.assertIn(review_text, result["content"])

    def test_content_contains_request_id(self):
        request_id = "req_000012"
        protocol = {
            "request_id": request_id,
            "payload": {"content": "Review this."},
        }
        result = _handle_review_request("teammate_z", protocol)
        self.assertIn(request_id, result["content"])
