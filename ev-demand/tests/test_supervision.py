import asyncio
import os
from pathlib import Path
import socket
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import create_app
from app.supervision import Notifier, controller_healthy, supervise


class SupervisionTests(unittest.TestCase):
    def test_notifications_are_disabled_outside_systemd_or_for_a_different_pid(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(Notifier.from_environment())
        for fields in ({'WATCHDOG_PID': str(os.getpid() + 1)}, {'WATCHDOG_USEC': 'bad'}, {'WATCHDOG_PID': 'bad'}):
            with patch.dict(os.environ, {'NOTIFY_SOCKET': '/tmp/fixture-notify', **fields}, clear=True):
                self.assertIsNone(Notifier.from_environment())
        with patch.dict(os.environ, {'NOTIFY_SOCKET': '@fixture', 'WATCHDOG_USEC': '120000000'}, clear=True):
            notifier = Notifier.from_environment()
            self.assertEqual(notifier.address, '\0fixture')
            self.assertEqual(notifier.timeout, 120)

    def test_health_requires_progress_and_running_tasks_without_control_faults(self):
        engine = SimpleNamespace(fault='', control_progress_at=100)
        running = SimpleNamespace(done=lambda: False)
        ended = SimpleNamespace(done=lambda: True)
        self.assertTrue(controller_healthy(engine, [running], 120, now=180))
        self.assertFalse(controller_healthy(engine, [running], 120, now=191))
        self.assertFalse(controller_healthy(engine, [ended], 120, now=101))
        engine.fault = 'control failure'
        self.assertFalse(controller_healthy(engine, [running], 120, now=101))

    def test_dead_notification_socket_does_not_block_or_crash_control(self):
        self.assertFalse(Notifier('/tmp/dmax-no-such-notify-socket', 120).send('WATCHDOG=1'))

    @unittest.skipUnless(hasattr(socket, 'AF_UNIX'), 'Requires Unix notification socket')
    def test_real_application_sends_ready_watchdog_and_stopping_to_service_manager(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'notify')
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as listener:
                listener.bind(path)
                listener.settimeout(3)
                env = {'NOTIFY_SOCKET': path, 'WATCHDOG_USEC': '120000000', 'WATCHDOG_PID': str(os.getpid())}
                with patch.dict(os.environ, env):
                    app = create_app(':memory:', root_password_hash='', recovery_public_key=b'')
                    with TestClient(app):
                        first = listener.recv(4096).decode()
                        second = listener.recv(4096).decode()
                        self.assertIn('READY=1', first)
                        self.assertEqual(second, 'WATCHDOG=1')
                    self.assertEqual(listener.recv(4096).decode(), 'STOPPING=1')


class SupervisorLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_heartbeat_when_control_stalls_even_though_event_loop_still_runs(self):
        for stalled in (False, True):
            sent = []
            notifier = SimpleNamespace(timeout=120, send=sent.append)
            engine = SimpleNamespace(fault='', control_progress_at=time.monotonic() - (100 if stalled else 0))
            running = SimpleNamespace(done=lambda: False)
            with patch('app.supervision.asyncio.sleep', new=AsyncMock(side_effect=asyncio.CancelledError)):
                with self.assertRaises(asyncio.CancelledError):
                    await supervise(engine, [running], notifier)
            self.assertTrue(sent[0].startswith('READY=1'))
            self.assertEqual('WATCHDOG=1' in sent, not stalled)
