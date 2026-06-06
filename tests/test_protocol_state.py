import unittest
import threading
import time
from clearink.tool.team.protocol.state import (
    ProtocolState, get_active_protocol_request,
    set_active_protocol_request, clear_protocol_request,
    _response_type_map,
)

class TestProtocolState(unittest.TestCase):
    def test_create_default(self):
        ps = ProtocolState(request_id="req_01", type="shutdown_request",
                          sender="lead", target="alice", status="pending",
                          payload={}, created_at=time.time())
        self.assertEqual(ps.request_id, "req_01")
        self.assertEqual(ps.status, "pending")
        self.assertIsNone(ps.responded_at)

    def test_fields_are_accessible(self):
        ts = time.time()
        ps = ProtocolState(request_id="r1", type="shutdown_request",
                          sender="s", target="t", status="pending",
                          payload={"k": "v"}, created_at=ts, responded_at=ts)
        self.assertEqual(ps.request_id, "r1")
        self.assertEqual(ps.payload, {"k": "v"})
        self.assertEqual(ps.responded_at, ts)


class TestThreadLocalProtocol(unittest.TestCase):
    def test_get_returns_none_initially(self):
        self.assertIsNone(get_active_protocol_request())

    def test_set_and_get(self):
        set_active_protocol_request("req_99", "shutdown_request")
        result = get_active_protocol_request()
        self.assertEqual(result["request_id"], "req_99")
        self.assertEqual(result["protocol_type"], "shutdown_request")

    def test_clear(self):
        set_active_protocol_request("req_99", "shutdown_request")
        clear_protocol_request()
        self.assertIsNone(get_active_protocol_request())

    def test_thread_isolation(self):
        set_active_protocol_request("main_req", "main_type")
        result_from_other = []
        def other_thread():
            result_from_other.append(get_active_protocol_request())

        t = threading.Thread(target=other_thread)
        t.start()
        t.join()
        self.assertIsNone(result_from_other[0])
        clear_protocol_request()


class TestResponseTypeMap(unittest.TestCase):
    def setUp(self):
        _response_type_map.clear()
        _response_type_map["shutdown_response"] = "shutdown_request"

    def test_shutdown_mapping(self):
        self.assertIn("shutdown_response", _response_type_map)
        self.assertEqual(
            _response_type_map["shutdown_response"], "shutdown_request"
        )

    def test_plan_review_removed(self):
        """plan_request/review_request protocols have been removed."""
        self.assertNotIn("plan_response", _response_type_map)
        self.assertNotIn("review_response", _response_type_map)
