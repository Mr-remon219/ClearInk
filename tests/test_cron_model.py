import time
import unittest

from clearink.tool.scheduler.model import CronJob


class TestCronJob(unittest.TestCase):
    def test_create_with_required_fields(self):
        job = CronJob(id="job1", cron="0 * * * *", prompt="run check")
        self.assertEqual(job.id, "job1")
        self.assertEqual(job.cron, "0 * * * *")
        self.assertEqual(job.prompt, "run check")

    def test_defaults(self):
        job = CronJob(id="j1", cron="* * * * *", prompt="test")
        self.assertTrue(job.recurring)
        self.assertTrue(job.durable)
        self.assertTrue(job.enabled)
        self.assertIsNone(job.last_fired)
        self.assertIsNone(job.last_fired_minute)
        self.assertIsNotNone(job.created_at)

    def test_recurring_false(self):
        job = CronJob(id="j1", cron="* * * * *", prompt="test", recurring=False)
        self.assertFalse(job.recurring)

    def test_durable_false(self):
        job = CronJob(id="j1", cron="* * * * *", prompt="test", durable=False)
        self.assertFalse(job.durable)

    def test_enabled_false(self):
        job = CronJob(id="j1", cron="* * * * *", prompt="test", enabled=False)
        self.assertFalse(job.enabled)

    def test_last_fired_set(self):
        now = time.time()
        job = CronJob(id="j1", cron="* * * * *", prompt="test", last_fired=now)
        self.assertEqual(job.last_fired, now)

    def test_last_fired_minute(self):
        job = CronJob(
            id="j1", cron="* * * * *", prompt="test",
            last_fired_minute="2026-06-01 14:00",
        )
        self.assertEqual(job.last_fired_minute, "2026-06-01 14:00")

    def test_created_at_custom(self):
        ts = 1000000.0
        job = CronJob(id="j1", cron="* * * * *", prompt="test", created_at=ts)
        self.assertEqual(job.created_at, ts)

    def test_to_dict_returns_all_fields(self):
        now = time.time()
        job = CronJob(
            id="j1",
            cron="*/5 * * * *",
            prompt="say hello",
            recurring=True,
            durable=True,
            enabled=True,
            last_fired=now,
            last_fired_minute="2026-06-01 14:00",
            created_at=now,
        )
        d = job.to_dict()
        self.assertEqual(d["id"], "j1")
        self.assertEqual(d["cron"], "*/5 * * * *")
        self.assertEqual(d["prompt"], "say hello")
        self.assertTrue(d["recurring"])
        self.assertTrue(d["durable"])
        self.assertTrue(d["enabled"])
        self.assertEqual(d["last_fired"], now)
        self.assertEqual(d["last_fired_minute"], "2026-06-01 14:00")
        self.assertEqual(d["created_at"], now)

    def test_to_dict_does_not_modify_original(self):
        job = CronJob(id="j1", cron="* * * * *", prompt="test")
        d = job.to_dict()
        d["id"] = "changed"
        self.assertEqual(job.id, "j1")

    def test_from_dict_reconstructs(self):
        now = time.time()
        d = {
            "id": "restored",
            "cron": "0 9 * * 1-5",
            "prompt": "weekday check",
            "recurring": False,
            "durable": True,
            "enabled": True,
            "last_fired": now,
            "last_fired_minute": None,
            "created_at": now,
        }
        job = CronJob.from_dict(d)
        self.assertIsInstance(job, CronJob)
        self.assertEqual(job.id, "restored")
        self.assertEqual(job.cron, "0 9 * * 1-5")
        self.assertEqual(job.prompt, "weekday check")
        self.assertFalse(job.recurring)
        self.assertTrue(job.durable)
        self.assertTrue(job.enabled)
        self.assertEqual(job.last_fired, now)
        self.assertIsNone(job.last_fired_minute)
        self.assertEqual(job.created_at, now)

    def test_from_dict_filters_unknown_fields(self):
        d = {
            "id": "j1",
            "cron": "* * * * *",
            "prompt": "test",
            "unknown_field": "should be ignored",
            "another_bad_key": 42,
        }
        job = CronJob.from_dict(d)
        self.assertFalse(hasattr(job, "unknown_field"))
        self.assertFalse(hasattr(job, "another_bad_key"))
        self.assertEqual(job.id, "j1")
        self.assertEqual(job.cron, "* * * * *")

    def test_from_dict_with_missing_fields_raises(self):
        with self.assertRaises(TypeError):
            CronJob.from_dict({"id": "j1"})  # missing 'cron' and 'prompt'

    def test_from_dict_partial_overrides_defaults(self):
        d = {"id": "j1", "cron": "30 * * * *", "prompt": "test", "enabled": False}
        job = CronJob.from_dict(d)
        self.assertFalse(job.enabled)
        self.assertTrue(job.recurring)  # default
        self.assertTrue(job.durable)     # default

    def test_from_dict_handles_none_last_fired(self):
        d = {"id": "j1", "cron": "* * * * *", "prompt": "test", "last_fired": None}
        job = CronJob.from_dict(d)
        self.assertIsNone(job.last_fired)

    def test_id_and_cron_are_strings(self):
        job = CronJob(id="42", cron="*/5 * * * *", prompt="ping")
        self.assertIsInstance(job.id, str)
        self.assertIsInstance(job.cron, str)

    def test_two_jobs_are_distinct(self):
        a = CronJob(id="a", cron="* * * * *", prompt="p1")
        b = CronJob(id="b", cron="* * * * *", prompt="p2")
        self.assertIsNot(a, b)
        self.assertNotEqual(a.id, b.id)

    def test_to_dict_includes_all_fields(self):
        job = CronJob(id="j1", cron="* * * * *", prompt="test")
        d = job.to_dict()
        expected_keys = {
            "id", "cron", "prompt", "recurring", "durable",
            "enabled", "last_fired", "last_fired_minute", "created_at",
        }
        self.assertEqual(set(d.keys()), expected_keys)

    def test_string_representation(self):
        job = CronJob(id="my-job", cron="0 */2 * * *", prompt="do something")
        s = repr(job)
        self.assertIn("my-job", s)
        self.assertIn("0 */2 * * *", s)

    def test_last_fired_minute_none_by_default(self):
        job = CronJob(id="j1", cron="* * * * *", prompt="test")
        self.assertIsNone(job.last_fired_minute)

    def test_created_at_default_is_time_dot_time(self):
        job = CronJob(id="j1", cron="* * * * *", prompt="test")
        self.assertIsInstance(job.created_at, float)

    def test_from_dict_default_created_at(self):
        d = {"id": "j1", "cron": "0 0 * * *", "prompt": "daily"}
        job = CronJob.from_dict(d)
        self.assertIsInstance(job.created_at, float)
