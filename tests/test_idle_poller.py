"""Tests for clearink.tool.team.idle.poller."""

from __future__ import annotations

import unittest

from clearink.tool.team.idle.poller import PollResult, inject_identity_message


class TestPollResultEnum(unittest.TestCase):
    """Tests for PollResult enum values."""

    def test_shutdown_value(self):
        self.assertEqual(PollResult.SHUTDOWN, "shutdown")

    def test_work_value(self):
        self.assertEqual(PollResult.WORK, "work")


class TestInjectIdentityMessage(unittest.TestCase):
    """Tests for inject_identity_message."""

    def test_returns_unchanged_when_messages_empty(self):
        result = inject_identity_message([], "alice", "helper")
        self.assertEqual(result, [])

    def test_returns_unchanged_when_name_already_in_first_message(self):
        messages = [
            {"role": "user", "content": "alice please help with this task"}
        ]
        result = inject_identity_message(messages, "alice", "helper")
        self.assertEqual(result, messages)

    def test_prepends_identity_message_when_name_not_present(self):
        messages = [{"role": "user", "content": "do something"}]
        result = inject_identity_message(messages, "alice", "helper")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["role"], "user")
        self.assertIn("alice", result[0]["content"])
        self.assertIn("helper", result[0]["content"])
        self.assertEqual(result[1], messages[0])

    def test_handles_nested_list_content(self):
        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": "hello world"}],
            }
        ]
        result = inject_identity_message(messages, "bob", "researcher")
        self.assertEqual(len(result), 2)
        self.assertIn("bob", result[0]["content"])
        self.assertIn("researcher", result[0]["content"])
        self.assertEqual(result[1], messages[0])
