import unittest
import asyncio
import threading
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app
from app.security import AttemptLimiter, same_origin, valid_host
from app.store import password_hash, password_matches


class SecurityTests(unittest.TestCase):
    def test_rate_limit_survives_success_and_has_bounded_memory(self):
        limiter = AttemptLimiter(limit=2, window=300, max_keys=2)
        with patch('app.security.time.monotonic', return_value=0):
            self.assertTrue(limiter.allow('one'))
            self.assertTrue(limiter.allow('one'))
            self.assertFalse(limiter.allow('one'))
            self.assertTrue(limiter.allow('two'))
            self.assertFalse(limiter.allow('three'))
            self.assertEqual(len(limiter.entries), 2)
        with patch('app.security.time.monotonic', return_value=301):
            self.assertTrue(limiter.allow('three'))

    def test_hash_validation_rejects_missing_malformed_or_expensive_parameters(self):
        encoded = password_hash('fixture-password')
        self.assertTrue(password_matches('fixture-password', encoded))
        for value in (None, '', 42, encoded.replace('600000', '999999999999'),
                      encoded.replace('pbkdf2_sha256', 'other')):
            self.assertFalse(password_matches('fixture-password', value))

    def test_host_and_origin_validation(self):
        for host in ('127.0.0.1:8080', '[::1]:8080', 'dmax.local', '192.168.1.20'):
            self.assertTrue(valid_host(host), host)
        for host in ('testserver/secret', 'user@testserver', r'\\server\share', 'testserver:99999', '[:::]'):
            self.assertFalse(valid_host(host), host)
        self.assertTrue(same_origin('http://testserver', 'testserver', 'http'))
        for origin in ('https://testserver', 'http://testserver/path', 'http://user@testserver',
                       'null', 'http://testserver?x=1', 'http://[invalid'):
            self.assertFalse(same_origin(origin, 'testserver', 'http'), origin)

    def test_api_rejects_bad_host_and_cross_scheme_origin(self):
        app = create_app(':memory:', background=False)
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/setup', headers={'Host':'testserver/path'}).status_code, 400)
            self.assertEqual(client.post('/api/setup', headers={'Origin':'https://testserver'}, json={}).status_code, 403)
            self.assertEqual(client.get('/').headers['X-Content-Type-Options'], 'nosniff')

    def test_successful_login_does_not_clear_attempt_limit(self):
        app = create_app(':memory:', background=False)
        with TestClient(app) as client:
            client.post('/api/setup', json={'root_password':'31011986', 'admin_password':'fixture-admin'})
            payload = {'username':'admin', 'password':'fixture-admin'}
            for _ in range(8):
                self.assertEqual(client.post('/api/login', json=payload).status_code, 200)
            self.assertEqual(client.post('/api/login', json=payload).status_code, 429)

    def test_ocpp_rejects_wrong_auth_scheme_and_missing_password_hash(self):
        import base64
        from starlette.websockets import WebSocketDisconnect
        app = create_app(':memory:', background=False)
        with TestClient(app) as client:
            store = app.state.store
            settings = store.settings(); settings['mode'] = 'physical'; store.save_settings(settings)
            store.put('charger', {'id':'station', 'transport':'ocpp'})
            value = base64.b64encode(b'station:fixture-password').decode()
            for header in ('Bearer ' + value, 'Basic ' + value):
                with self.assertRaises(WebSocketDisconnect):
                    with client.websocket_connect('/ocpp/station', headers={'Authorization':header}, subprotocols=['ocpp1.6']):
                        self.fail('Conexão sem credencial válida foi aceita')


class AuthenticationConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_password_verification_leaves_control_loop_free_and_rechecks_revocation(self):
        import httpx
        app = create_app(':memory:', background=False)
        started, release = threading.Event(), threading.Event()
        def slow_verify(*args):
            started.set()
            release.wait(3)
            return True
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://testserver') as client:
                # ASGITransport's default remote IP cannot perform first setup.
                store = app.state.store
                with store.db:
                    store.db.execute('INSERT INTO users(name,password,role,id,full_name) VALUES (?,?,?,?,?)',
                                     ('admin', 'fixture', 'admin', 'fixture-admin', 'Admin'))
                with patch('app.main.password_matches', slow_verify):
                    login = asyncio.create_task(client.post('/api/login', json={'username':'admin','password':'fixture'}))
                    for _ in range(100):
                        if started.is_set():
                            break
                        await asyncio.sleep(.01)
                    try:
                        self.assertTrue(started.is_set())
                        self.assertFalse(login.done())
                        result = await asyncio.wait_for(client.get('/api/setup'), timeout=.5)
                        self.assertEqual(result.status_code, 200)
                        with store.db:
                            store.db.execute("UPDATE users SET active=0 WHERE name='admin'")
                    finally:
                        release.set()
                    self.assertEqual((await login).status_code, 401)
        finally:
            release.set()
            app.state.store.db.close()
