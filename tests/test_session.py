import time
import threading
import unittest

from clearink.api.session import Session, SessionManager, get_session_manager


class TestSession(unittest.TestCase):
    def test_defaults(self):
        s = Session(session_id="abc", messages=[])
        self.assertEqual(s.mode, 1)
        self.assertFalse(s.step_mode)
        self.assertIsNotNone(s.created_at)
        self.assertIsNotNone(s.last_access)

    def test_created_at_and_last_access_are_set_at_init(self):
        before = time.time()
        s = Session(session_id="x1", messages=[])
        after = time.time()
        self.assertGreaterEqual(s.created_at, before)
        self.assertLessEqual(s.created_at, after)
        self.assertGreaterEqual(s.last_access, before)
        self.assertLessEqual(s.last_access, after)

    def test_created_at_and_last_access_can_differ_after_touch(self):
        s = Session(session_id="x1", messages=[])
        original_created = s.created_at
        original_access = s.last_access
        # Simulate a later time for last_access
        s.last_access = time.time() + 10
        self.assertEqual(s.created_at, original_created)
        self.assertGreater(s.last_access, original_access)

    def test_messages_empty_by_default(self):
        s = Session(session_id="s1", messages=[])
        self.assertEqual(s.messages, [])

    def test_mode_custom(self):
        s = Session(session_id="s1", messages=[], mode=2)
        self.assertEqual(s.mode, 2)

    def test_step_mode_true(self):
        s = Session(session_id="s1", messages=[], step_mode=True)
        self.assertTrue(s.step_mode)

    def test_fields_are_mutable(self):
        s = Session(session_id="s1", messages=[])
        s.mode = 2
        s.step_mode = True
        s.messages.append({"role": "user", "content": "hello"})
        self.assertEqual(s.mode, 2)
        self.assertTrue(s.step_mode)
        self.assertEqual(len(s.messages), 1)


class TestSessionManager(unittest.TestCase):
    def setUp(self):
        self.mgr = SessionManager()

    def test_create_auto_id(self):
        sess = self.mgr.create()
        self.assertIsInstance(sess, Session)
        self.assertIsNotNone(sess.session_id)
        self.assertGreater(len(sess.session_id), 0)
        self.assertEqual(sess.messages, [])

    def test_create_with_custom_id(self):
        sess = self.mgr.create("my-custom-id")
        self.assertEqual(sess.session_id, "my-custom-id")

    def test_create_returns_valid_session(self):
        sess = self.mgr.create()
        self.assertIsNotNone(sess.session_id)
        self.assertEqual(sess.mode, 1)

    def test_get_existing(self):
        created = self.mgr.create("sid1")
        fetched = self.mgr.get("sid1")
        self.assertIs(fetched, created)

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.mgr.get("nonexistent"))

    def test_get_or_create_first_call_creates(self):
        sess = self.mgr.get_or_create("abc")
        self.assertEqual(sess.session_id, "abc")
        self.assertIsNotNone(self.mgr.get("abc"))

    def test_get_or_create_second_call_returns_same(self):
        first = self.mgr.get_or_create("abc")
        second = self.mgr.get_or_create("abc")
        self.assertIs(first, second)

    def test_delete_removes_session(self):
        self.mgr.create("to-delete")
        self.mgr.delete("to-delete")
        self.assertIsNone(self.mgr.get("to-delete"))

    def test_delete_nonexistent_is_noop(self):
        # Should not raise
        self.mgr.delete("does-not-exist")

    def test_touch_updates_last_access(self):
        sess = self.mgr.create("t1")
        original = sess.last_access
        time.sleep(0.01)
        self.mgr.touch("t1")
        self.assertGreater(sess.last_access, original)

    def test_touch_nonexistent_is_noop(self):
        self.mgr.touch("no-such-session")  # should not raise

    def test_cleanup_removes_old_sessions(self):
        old = self.mgr.create("old")
        old.last_access = time.time() - 1000
        recent = self.mgr.create("recent")
        recent.last_access = time.time() - 10

        removed = self.mgr.cleanup(max_age=100)
        self.assertEqual(removed, 1)
        self.assertIsNone(self.mgr.get("old"))
        self.assertIsNotNone(self.mgr.get("recent"))

    def test_cleanup_keeps_recent_sessions(self):
        self.mgr.create("a")
        self.mgr.create("b")
        removed = self.mgr.cleanup(max_age=3600)
        self.assertEqual(removed, 0)
        self.assertIsNotNone(self.mgr.get("a"))
        self.assertIsNotNone(self.mgr.get("b"))

    def test_cleanup_removes_all_stale(self):
        for i in range(5):
            s = self.mgr.create(f"old-{i}")
            s.last_access = time.time() - 10000
        self.mgr.create("current")
        removed = self.mgr.cleanup(max_age=60)
        self.assertEqual(removed, 5)

    def test_create_generates_unique_ids(self):
        ids = {self.mgr.create().session_id for _ in range(100)}
        self.assertEqual(len(ids), 100)

    def test_thread_safety(self):
        errors = []

        def writer(prefix: str):
            try:
                for i in range(50):
                    sid = f"{prefix}-{i}"
                    self.mgr.create(sid)
                    s = self.mgr.get(sid)
                    assert s is not None, f"expected {sid}"
                    self.mgr.touch(sid)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=("A",)),
            threading.Thread(target=writer, args=("B",)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(errors, [])

    def test_thread_safety_concurrent_create_and_get(self):
        barrier = threading.Barrier(4, timeout=5)
        results: list[Exception | None] = [None] * 4

        def accessor(idx: int, sid: str):
            try:
                barrier.wait()
                for _ in range(100):
                    s = self.mgr.get_or_create(sid)
                    assert s is not None
                    self.mgr.touch(sid)
            except Exception as e:
                results[idx] = e

        threads = [
            threading.Thread(target=accessor, args=(0, "shared")),
            threading.Thread(target=accessor, args=(1, "shared")),
            threading.Thread(target=accessor, args=(2, "shared-a")),
            threading.Thread(target=accessor, args=(3, "shared-b")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=6)

        for r in results:
            if r is not None:
                raise r

    def test_get_or_create_is_atomic_for_shared_id(self):
        barrier = threading.Barrier(8, timeout=5)
        errors: list[Exception] = []
        sessions: list[Session] = []
        sessions_lock = threading.Lock()

        def accessor():
            try:
                barrier.wait()
                session = self.mgr.get_or_create("shared")
                with sessions_lock:
                    sessions.append(session)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=accessor) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=6)

        for error in errors:
            raise error

        self.assertEqual(len(sessions), 8)
        self.assertEqual({id(session) for session in sessions}, {id(sessions[0])})

    def test_cleanup_returns_count(self):
        s = self.mgr.create("gone")
        s.last_access = time.time() - 5000
        self.mgr.create("keep")
        count = self.mgr.cleanup(max_age=100)
        self.assertEqual(count, 1)

    def test_cleanup_with_zero_max_age_removes_all(self):
        self.mgr.create("a")
        self.mgr.create("b")
        self.mgr.create("c")
        removed = self.mgr.cleanup(max_age=0)
        self.assertEqual(removed, 3)

    def test_multiple_sessions_independent(self):
        a = self.mgr.create("a")
        b = self.mgr.create("b")
        a.mode = 2
        b.step_mode = True
        a.messages.append({"role": "user", "content": "hello"})
        self.assertEqual(self.mgr.get("a").mode, 2)
        self.assertTrue(self.mgr.get("b").step_mode)
        self.assertEqual(len(self.mgr.get("b").messages), 0)

    def test_cleanup_does_not_affect_sessions_outside_range(self):
        for i in range(10):
            self.mgr.create(f"s{i}")
        removed = self.mgr.cleanup(max_age=999999)
        self.assertEqual(removed, 0)
        for i in range(10):
            self.assertIsNotNone(self.mgr.get(f"s{i}"))


class TestGetSessionManagerSingleton(unittest.TestCase):
    def test_returns_same_instance(self):
        m1 = get_session_manager()
        m2 = get_session_manager()
        self.assertIs(m1, m2)

    def test_singleton_is_session_manager(self):
        self.assertIsInstance(get_session_manager(), SessionManager)

    def test_singleton_works_with_crud(self):
        mgr = get_session_manager()
        mgr.create("singleton-test")
        self.assertIsNotNone(mgr.get("singleton-test"))
        mgr.delete("singleton-test")
        self.assertIsNone(mgr.get("singleton-test"))
