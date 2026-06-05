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

    def test_to_dict(self):
        ts = time.time()
        ps = ProtocolState(request_id="r1", type="t1", sender="s", target="t",
                          status="pending", payload={"k": "v"}, created_at=ts)
        d = ps.to_dict()
        self.assertEqual(d["request_id"], "r1")
        self.assertEqual(d["type"], "t1")
        self.assertEqual(d["payload"], {"k": "v"})

    def test_to_dict_with_responded(self):
        ts = time.time()
        ps = ProtocolState(request_id="r2", type="t2", sender="s", target="t",
                          status="approved", payload={}, created_at=ts, responded_at=ts)
        d = ps.to_dict()
        self.assertEqual(d["responded_at"], ts)

    def test_from_dict(self):
        ts = time.time()
        d = {"request_id": "r3", "type": "t3", "sender": "s", "target": "t",
             "status": "pending", "payload": {}, "created_at": ts}
        ps = ProtocolState.from_dict(d)
        self.assertEqual(ps.request_id, "r3")

    def test_from_dict_ignores_unknown(self):
        d = {"request_id": "r4", "type": "t4", "sender": "s", "target": "t",
             "status": "pending", "payload": {}, "created_at": time.time(),
             "extra_field": "should_be_ignored"}
        ps = ProtocolState.from_dict(d)
        self.assertFalse(hasattr(ps, "extra_field"))


class TestThreadLocalProtocol(unittest.TestCase):
    def test_get_returns_none_initially(self):
        self.assertIsNone(get_active_protocol_request())

    def test_set_and_get(self):
        set_active_protocol_request("req_99", "plan_request")
        result = get_active_protocol_request()
        self.assertEqual(result["request_id"], "req_99")
        self.assertEqual(result["protocol_type"], "plan_request")

    def test_clear(self):
        set_active_protocol_request("req_99", "plan_request")
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
        # Restore default mappings in case other tests cleared them
        _response_type_map.clear()
        _response_type_map["shutdown_response"] = "shutdown_request"
        _response_type_map["plan_response"] = "plan_request"
        _response_type_map["review_response"] = "review_request"

    def test_mappings(self):
        self.assertIn("shutdown_response", _response_type_map)
        self.assertIn("plan_response", _response_type_map)
        self.assertIn("review_response", _response_type_map)
        self.assertEqual(_response_type_map["shutdown_response"], "shutdown_request")
        self.assertEqual(_response_type_map["plan_response"], "plan_request")
        self.assertEqual(_response_type_map["review_response"], "review_request")
