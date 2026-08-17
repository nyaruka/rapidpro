from unittest.mock import patch

from celery.app.task import Task

from temba.tests import TembaTest

from . import cron_task


class CronsTest(TembaTest):
    @patch("valkey.client.StrictValkey.lock")
    def test_cron_task(self, mock_valkey_lock):
        mock_valkey_lock.return_value.acquire.return_value = True
        task_calls = []

        @cron_task()
        def test_task1(foo, bar):
            task_calls.append("1-%d-%d" % (foo, bar))
            return {"foo": 1}

        @cron_task(name="task2", time_limit=100)
        def test_task2(foo, bar):
            task_calls.append("2-%d-%d" % (foo, bar))
            return 1234

        @cron_task(name="task3", time_limit=100, lock_timeout=55)
        def test_task3(foo, bar):
            task_calls.append("3-%d-%d" % (foo, bar))

        self.assertIsInstance(test_task1, Task)
        self.assertIsInstance(test_task2, Task)
        self.assertEqual(test_task2.name, "task2")
        self.assertEqual(test_task2.time_limit, 100)
        self.assertIsInstance(test_task3, Task)
        self.assertEqual(test_task3.name, "task3")
        self.assertEqual(test_task3.time_limit, 100)

        test_task1(11, 12)
        test_task2(21, bar=22)
        test_task3(foo=31, bar=32)

        mock_valkey_lock.assert_any_call("celery-task-lock:test_task1", timeout=900, blocking=False)
        mock_valkey_lock.assert_any_call("celery-task-lock:task2", timeout=100, blocking=False)
        mock_valkey_lock.assert_any_call("celery-task-lock:task3", timeout=55, blocking=False)

        self.assertEqual(task_calls, ["1-11-12", "2-21-22", "3-31-32"])

        # simulate task being already running so the lock can't be acquired
        mock_valkey_lock.reset_mock()
        mock_valkey_lock.return_value.acquire.return_value = False

        # try to run again
        test_task1(13, 14)

        # check that task is skipped
        mock_valkey_lock.assert_called_once_with("celery-task-lock:test_task1", timeout=900, blocking=False)
        self.assertEqual(task_calls, ["1-11-12", "2-21-22", "3-31-32"])
