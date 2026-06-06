import unittest
import time
from unittest.mock import MagicMock
from clearink.tool.team.protocol import state as proto_state
from clearink.tool.team.protocol.protocol import (
    consume_lead_inbox, generate_request_id, register_protocol, match_response,
)

class TestGenerateRequestId(unittest.TestCase):
    def test_ids_are_monotonically_increasing(self):
        id1 = generate_request_id()
        id2 = generate_request_id()
        id3 = generate_request_id()
        # IDs should have the req_XXXXXX format
        self.assertRegex(id1, r"req_\d{6}")
        # IDs should be increasing
        n1 = int(id1.split("_")[1])
        n2 = int(id2.split("_")[1])
        n3 = int(id3.split("_")[1])
        self.assertLess(n1, n2)
        self.assertLess(n2, n3)


class TestMatchResponse(unittest.TestCase):
    def setUp(self):
        proto_state.pending_requests.clear()
        proto_state._response_type_map.clear()
        register_protocol("shutdown_request", "shutdown_response")
        ts = time.time()
        proto_state.pending_requests["req_01"] = MagicMock(
            request_id="req_01", type="shutdown_request",
            sender="lead", target="alice", status="pending",
            payload={}, created_at=ts,
        )
        proto_state.pending_requests["req_01"].responded_at = None

    def test_match_approve(self):
        result = match_response("shutdown_response", "req_01", True)
        self.assertIsNotNone(result)
        self.assertEqual(result.status, "approved")
        self.assertIsNotNone(result.responded_at)

    def test_match_reject(self):
        result = match_response("shutdown_response", "req_01", False)
        self.assertIsNotNone(result)
        self.assertEqual(result.status, "rejected")

    def test_unknown_response_type(self):
        result = match_response("unknown_response", "req_01", True)
        self.assertIsNone(result)

    def test_unknown_request_id(self):
        result = match_response("shutdown_response", "nonexistent", True)
        self.assertIsNone(result)

    def test_type_mismatch(self):
        register_protocol("plan_request", "plan_response")
        result = match_response("plan_response", "req_01", True)
        self.assertIsNone(result)


def test_consume_lead_inbox_ignores_stale_process_messages(monkeypatch):
    import clearink.tool.team.protocol.protocol as protocol_mod

    class FakeBus:
        def read_and_clear(self, name):
            assert name == "lead"
            return [
                {"from": "old", "content": "stale", "timestamp": 10.0},
                {"from": "new", "content": "fresh", "timestamp": 30.0},
            ]

    monkeypatch.setattr(protocol_mod, "_PROCESS_STARTED_AT", 20.0)
    monkeypatch.setattr(protocol_mod, "_get_bus", lambda: FakeBus())

    assert consume_lead_inbox(route_protocol=False) == [{
        "role": "user",
        "content": "[Teammate new]: fresh",
    }]
