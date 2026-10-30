import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from app.main import create_app
from app.recovery import DOMAIN, TTL, Recovery, canonical, encode, payload_from
from app.store import Store
from recovery_helpers import PUBLIC, PRIVATE, create_test_app, recover_root, sign
from tools.recovery_admin import authorize, generate


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.app = create_test_app(':memory:', background=False)
        self.context = TestClient(self.app)
        self.client = self.context.__enter__()
        self.assertEqual(self.client.post('/api/setup', json={'admin_password': 'fixture-admin-pass'}).status_code, 200)

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def challenge(self, client=None):
        response = (client or self.client).post('/api/recovery/challenge', json={})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('httponly', response.headers['set-cookie'].lower())
        self.assertIn('samesite=strict', response.headers['set-cookie'].lower())
        return response.json()['challenge']

    def submit(self, token, client=None):
        return (client or self.client).post('/api/recovery/authorize', json={'authorization': token})

    def test_offline_signature_creates_short_root_session_without_changing_admin(self):
        before = self.app.state.access.by_name('admin')['password']
        challenge = self.challenge()
        self.assertEqual(self.client.get('/api/state').status_code, 401)
        response = self.submit(sign(challenge))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['role'], 'root')
        self.assertIn('Max-Age=900', response.headers['set-cookie'])
        self.assertEqual(self.client.get('/api/directory').status_code, 200)
        self.assertEqual(self.app.state.access.by_name('admin')['password'], before)
        with patch('app.access.time.time', return_value=time.time() + TTL + 1):
            self.assertEqual(self.client.get('/api/me').status_code, 401)

    def test_no_fixed_password_or_legacy_root_password_is_accepted(self):
        for password in ('31011986', '12345678', 'fixture-old-root-password'):
            response = self.client.post('/api/login', json={'username': 'root', 'password': password})
            self.assertEqual(response.status_code, 401)
        self.assertEqual(self.app.state.access.by_name('root')['password'], '')

    def test_authorization_is_single_use_even_if_browser_cookie_is_restored(self):
        token = sign(self.challenge())
        binding = self.client.cookies.get('dmax_recovery')
        self.assertEqual(self.submit(token).status_code, 200)
        self.client.cookies.set('dmax_recovery', binding)
        self.assertEqual(self.submit(token).status_code, 401)

    def test_another_browser_cannot_use_a_copied_authorization(self):
        token = sign(self.challenge())
        other = TestClient(self.app, client=('192.0.2.40', 1234))
        try:
            self.challenge(other)
            self.assertEqual(self.submit(token, other).status_code, 401)
            self.assertEqual(self.submit(token).status_code, 200)
        finally:
            other.close()

    def test_wrong_signer_does_not_consume_the_real_challenge(self):
        challenge = self.challenge()
        self.assertEqual(self.submit(sign(challenge, Ed25519PrivateKey.generate())).status_code, 401)
        self.assertEqual(self.submit(sign(challenge)).status_code, 200)

    def test_modified_payload_and_signature_are_rejected(self):
        challenge = self.challenge()
        token = sign(challenge)
        prefix, encoded, signature = token.split('.')
        payload = payload_from(encoded)
        payload['nonce'] = '0' * 32
        self.assertEqual(self.submit(prefix + '.' + encode(canonical(payload)) + '.' + signature).status_code, 401)
        self.assertEqual(self.submit(prefix + '.' + encoded + '.' + encode(bytes(64))).status_code, 401)
        self.assertEqual(self.submit(token).status_code, 200)

    def test_challenge_from_another_controller_is_rejected_even_with_same_owner_key(self):
        other_app = create_test_app(':memory:', background=False)
        with TestClient(other_app) as other:
            other.post('/api/setup', json={'admin_password': 'fixture-other-admin'})
            token = sign(self.challenge(other))
            self.challenge()
            self.assertEqual(self.submit(token).status_code, 401)

    def test_expired_authorization_and_future_clock_are_rejected(self):
        challenge = self.challenge()
        token = sign(challenge)
        with patch('app.recovery.time.time', return_value=time.time() + TTL + 1):
            self.assertEqual(self.submit(token).status_code, 401)
        encoded = token.split('.')[1]
        payload = payload_from(encoded)
        payload['issued'] += TTL
        payload['expires'] += TTL
        changed = canonical(payload)
        future = 'DMAX-R1.' + encode(changed) + '.' + encode(PRIVATE.sign(DOMAIN + changed))
        self.assertEqual(self.submit(future).status_code, 401)

    def test_disabled_or_invalid_public_key_has_no_password_fallback(self):
        for public in (b'', b'not-a-public-key'):
            app = create_app(':memory:', background=False, recovery_public_key=public)
            with TestClient(app) as client:
                client.post('/api/setup', json={'admin_password': 'fixture-other-admin'})
                self.assertFalse(client.get('/api/recovery').json()['enabled'])
                self.assertEqual(client.post('/api/recovery/challenge').status_code, 409)
                self.assertEqual(client.post('/api/login', json={'username': 'root', 'password': '31011986'}).status_code, 401)
                self.assertEqual(client.post('/api/login', json={'username': 'admin', 'password': 'fixture-other-admin'}).status_code, 200)

    def test_same_browser_reuses_pending_challenge_without_invalidating_it(self):
        first = self.challenge()
        self.assertEqual(self.challenge(), first)
        self.assertEqual(self.submit(sign(first)).status_code, 200)

    def test_attempts_and_pending_challenges_are_bounded(self):
        self.challenge()
        for _ in range(8):
            self.assertEqual(self.submit('invalid').status_code, 401)
        self.assertEqual(self.submit('invalid').status_code, 429)
        recovery = self.app.state.recovery
        for index in range(255):
            recovery.issue('fixture-binding-' + str(index))
        with self.assertRaises(ValueError):
            recovery.issue('another-fixture-binding')
        self.assertEqual(recovery.db.execute('SELECT COUNT(*) FROM recovery_challenges').fetchone()[0], 256)

    def test_tokens_and_private_keys_are_not_in_audit_or_public_status(self):
        challenge = self.challenge()
        token = sign(challenge)
        self.assertEqual(self.submit(token).status_code, 200)
        data = json.dumps(self.app.state.store.pending()) + self.client.get('/api/recovery').text
        self.assertNotIn(challenge, data)
        self.assertNotIn(token, data)
        self.assertNotIn('PRIVATE KEY', data)

    def test_bad_payload_schema_and_noncanonical_json_are_rejected(self):
        payload = payload_from(self.challenge().split('.')[1])
        for change in ({'issued': True}, {'controller': 'other'}, {'expires': payload['expires'] + 1}, {'extra': 1}):
            with self.assertRaises(ValueError):
                payload_from(encode(canonical(payload | change)))
        with self.assertRaises(ValueError):
            payload_from(encode(json.dumps(payload, indent=2).encode()))


class RecoveryPersistenceTests(unittest.TestCase):
    def test_replacing_or_removing_public_key_revokes_existing_root_sessions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'controller.sqlite3')
            app = create_test_app(path, background=False)
            with TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 1234)) as client:
                client.post('/api/setup', json={'admin_password': 'fixture-admin-rotate'})
                self.assertEqual(recover_root(client).status_code, 200)
                root_session = client.cookies.get('ev_session')
                client.post('/api/login', json={'username': 'admin', 'password': 'fixture-admin-rotate'})
                admin_session = client.cookies.get('ev_session')
            app = create_app(path, background=False, recovery_public_key=b'invalid-key')
            with TestClient(app) as client:
                client.cookies.set('ev_session', root_session)
                self.assertEqual(client.get('/api/me').status_code, 401)
                client.cookies.set('ev_session', admin_session)
                self.assertEqual(client.get('/api/me').status_code, 200)

    def test_restart_retains_challenge_and_consumption_and_key_rotation_invalidates_old_codes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'controller.sqlite3')
            app = create_test_app(path, background=False)
            # Use localhost for initial setup of a real file database.
            with TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 1234)) as client:
                self.assertEqual(client.post('/api/setup', json={'admin_password': 'fixture-admin-restart'}).status_code, 200)
                challenge = client.post('/api/recovery/challenge').json()['challenge']
                binding = client.cookies.get('dmax_recovery')
            app = create_test_app(path, background=False)
            with TestClient(app) as client:
                client.cookies.set('dmax_recovery', binding)
                token = sign(challenge)
                self.assertEqual(client.post('/api/recovery/authorize', json={'authorization': token}).status_code, 200)
            app = create_test_app(path, background=False)
            with TestClient(app) as client:
                client.cookies.set('dmax_recovery', binding)
                self.assertEqual(client.post('/api/recovery/authorize', json={'authorization': token}).status_code, 401)
                fresh = client.post('/api/recovery/challenge').json()['challenge']
            rotated = Ed25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
            app = create_app(path, background=False, recovery_public_key=rotated)
            with TestClient(app) as client:
                client.cookies.set('dmax_recovery', binding)
                self.assertEqual(client.post('/api/recovery/authorize', json={'authorization': sign(fresh)}).status_code, 401)


class OwnerToolTests(unittest.TestCase):
    def test_key_generation_is_encrypted_exclusive_and_can_authorize_offline(self):
        with tempfile.TemporaryDirectory() as folder:
            private = Path(folder) / 'owner.pem'
            public = Path(folder) / 'recovery-public.pem'
            password = 'fixture-owner-password'
            identifier = generate(private, public, password)
            self.assertIn(b'ENCRYPTED PRIVATE KEY', private.read_bytes())
            self.assertNotIn(b'PRIVATE KEY', public.read_bytes())
            original = private.read_bytes()
            with self.assertRaises(ValueError):
                generate(private, public, password)
            self.assertEqual(private.read_bytes(), original)
            store = Store(':memory:')
            try:
                recovery = Recovery(store, public.read_bytes())
                self.assertEqual(recovery.public()['fingerprint'], identifier)
                challenge = recovery.issue('fixture-browser-binding')['challenge']
                token = authorize(challenge, private, password)
                recovery.consume(token, 'fixture-browser-binding')
                with self.assertRaises(ValueError):
                    authorize(challenge, private, 'incorrect-password')
            finally:
                store.db.close()

    def test_unprotected_private_key_is_not_accepted_by_the_owner_tool(self):
        with tempfile.TemporaryDirectory() as folder:
            private = Path(folder) / 'owner.pem'
            private.write_bytes(PRIVATE.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            store = Store(':memory:')
            try:
                challenge = Recovery(store, PUBLIC).issue('fixture-browser')['challenge']
                with self.assertRaises(TypeError):
                    authorize(challenge, private, 'fixture-password')
            finally:
                store.db.close()
