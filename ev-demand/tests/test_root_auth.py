import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.access import Access
from app.main import create_app
from app.root_auth import load_root_hash
from app.store import Store, password_hash

PHRASE = 'fixture-owner-passphrase-for-tests'
VERIFIER = password_hash(PHRASE)


class RootPassphraseTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(':memory:', background=False, recovery_public_key=b'', root_password_hash=VERIFIER)
        self.context = TestClient(self.app)
        self.client = self.context.__enter__()
        self.assertEqual(self.client.post('/api/setup', json={'admin_password': 'fixture-admin-password'}).status_code, 200)

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def login(self, phrase=PHRASE):
        return self.client.post('/api/login', json={'username': 'root', 'password': phrase})

    def test_root_logs_in_offline_without_any_key_code_or_first_access_change(self):
        self.assertFalse(self.client.get('/api/recovery').json()['enabled'])
        response = self.login()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['role'], 'root')
        self.assertFalse(response.json()['must_change'])
        self.assertIn('Max-Age=900', response.headers['set-cookie'])
        self.assertEqual(self.client.get('/api/directory').status_code, 200)
        self.assertEqual(self.client.get('/api/state').status_code, 200)
        with patch('app.access.time.time', return_value=time.time() + 901):
            self.assertEqual(self.client.get('/api/me').status_code, 401)

    def test_exact_phrase_is_required_and_legacy_passwords_do_not_work(self):
        for wrong in ('wrong-owner-phrase', '31011986', ' ' + PHRASE, PHRASE + ' '):
            self.assertEqual(self.login(wrong).status_code, 401)
        self.assertEqual(self.login().status_code, 200)

    def test_phrase_is_rate_limited_and_does_not_reset_attempt_counter_on_success(self):
        for _ in range(8):
            self.assertEqual(self.login().status_code, 200)
        self.assertEqual(self.login().status_code, 429)

    def test_no_phrase_or_hash_in_api_audit_or_webpage(self):
        self.assertEqual(self.login().status_code, 200)
        text = json.dumps(self.app.state.store.pending())
        for path in ('/api/me', '/api/state', '/api/users', '/', '/ui/profile'):
            text += self.client.get(path).text
        self.assertNotIn(PHRASE, text)
        self.assertNotIn(VERIFIER, text)
        self.assertEqual(self.client.get('/static/root-credential.json').status_code, 404)
        self.assertEqual(self.client.get('/root-credential.json').status_code, 404)

    def test_site_cannot_replace_owner_passphrase_and_root_can_recover_admin(self):
        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(self.client.post('/api/change-password', json={'current_password': PHRASE, 'new_password': 'fixture-replacement-root'}).status_code, 422)
        root = self.app.state.access.by_name('root')
        self.assertEqual(self.client.post('/api/users/' + root['id'] + '/reset', json={}).status_code, 403)
        self.assertEqual(self.client.post('/api/recover-admin', json={'username': 'admin', 'password': 'fixture-recovered-admin'}).status_code, 200)
        self.assertEqual(self.client.post('/api/login', json={'username': 'admin', 'password': 'fixture-recovered-admin'}).status_code, 200)


class RootPolicyTests(unittest.TestCase):
    def test_policy_file_accepts_only_valid_pbkdf2_verifier(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'root.json'
            self.assertEqual(load_root_hash(path), '')
            path.write_text(json.dumps({'version': 1, 'password_hash': VERIFIER}))
            self.assertEqual(load_root_hash(path), VERIFIER)
            for value in ({'version': True, 'password_hash': VERIFIER}, {'version': 1, 'password_hash': PHRASE},
                          {'version': 1, 'password_hash': VERIFIER, 'password': PHRASE}):
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    load_root_hash(path)
            path.write_text('x' * 4097)
            with self.assertRaises(ValueError):
                load_root_hash(path)

    def test_migration_and_restart_preserve_other_accounts_and_revoke_only_changed_root(self):
        store = Store(':memory:')
        try:
            access = Access(store, root_password_hash=VERIFIER)
            with store.db:
                store.db.execute('INSERT INTO users(name,password,role,id,full_name) VALUES(?,?,?,?,?)', ('root', '', 'root', 'fixture-root', 'Root'))
                store.db.execute('INSERT INTO users(name,password,role,id,full_name) VALUES(?,?,?,?,?)', ('admin', 'fixture-admin-verifier', 'admin', 'fixture-admin', 'Admin'))
            migrated = Access(store, root_password_hash=VERIFIER)
            self.assertEqual(migrated.by_name('root')['password'], VERIFIER)
            self.assertEqual(migrated.by_name('admin')['password'], 'fixture-admin-verifier')
            epoch = migrated.by_name('root')['epoch']
            repeated = Access(store, root_password_hash=VERIFIER)
            self.assertEqual(repeated.by_name('root')['epoch'], epoch)
            rotated = Access(store, root_password_hash=password_hash('fixture-rotated-owner-passphrase'))
            self.assertGreater(rotated.by_name('root')['epoch'], epoch)
            self.assertEqual(rotated.by_name('admin')['password'], 'fixture-admin-verifier')
        finally:
            store.db.close()

    def test_missing_or_corrupt_packaged_policy_fails_closed_for_root_but_keeps_admin(self):
        with patch('app.main.load_root_hash', side_effect=ValueError('bad-policy')):
            app = create_app(':memory:', background=False, recovery_public_key=b'')
        with TestClient(app) as client:
            client.post('/api/setup', json={'admin_password': 'fixture-admin-password'})
            self.assertTrue(app.state.root_hash_error)
            self.assertFalse(app.state.root_password_enabled)
            self.assertEqual(client.post('/api/login', json={'username': 'root', 'password': PHRASE}).status_code, 401)
            self.assertEqual(client.post('/api/login', json={'username': 'admin', 'password': 'fixture-admin-password'}).status_code, 200)
