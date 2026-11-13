import asyncio
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import password_hash
from test_v0140 import record, PASSWORD


class RequestedChangesTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(':memory:', background=False, root_password_hash=password_hash(PASSWORD))
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.client.post('/api/setup', json={'admin_password': PASSWORD})
        self.client.post('/api/login', json={'username': 'root', 'password': PASSWORD})

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def test_root_navigation_settings_and_soc_completion(self):
        self.assertEqual(self.client.post('/api/demo').status_code, 200)
        page = self.client.get('/ui/settings')
        self.assertEqual(page.status_code, 200)
        for tab in ('users', 'remoteclients', 'remote', 'directory', 'simulation'):
            self.assertNotIn('href="/ui/' + tab + '"', page.text)
            self.assertEqual(self.client.get('/ui/' + tab).status_code, 403)
        self.assertIn('Google Planilhas e Apps Script', page.text)
        self.assertIn('/static/position.js', page.text)
        self.assertIn("script-src 'self'", page.headers['content-security-policy'])
        engine = self.app.state.engine
        p = next(iter(engine.ports.values()))
        if p['connected']:
            engine.disconnect(p['key'])
        engine.connect_simulated(p['key'])
        self.assertEqual(p['soc'], 20)
        engine.start_session(p)
        session_id = p['session_id']
        p['soc'] = 99.99
        engine.simulate_energy(p, 100, 3600)
        self.assertEqual(p['soc'], 100)
        self.assertFalse(p['running'])
        self.assertEqual(p['power_kw'], 0)
        session = next(s for s in self.app.state.store.entities('session') if s['id'] == session_id)
        self.assertEqual(session['reason'], 'Bateria carregada a 100%')
        asyncio.run(engine.tick())
        self.assertFalse(p['running'])
        self.assertEqual(p['status'], 'Carga completa · 100%')
        self.assertIn('SOC da bateria', self.client.get('/ui/overview').text)
        self.assertIn('100,0%', self.client.get('/ui/chargers').text)
        engine.disconnect(p['key'])
        engine.connect_simulated(p['key'])
        self.assertFalse(p['charge_complete'])
        self.assertEqual(p['soc'], 20)

    def test_commercial_cannot_change_existing_production_session(self):
        self.client.post('/api/demo')
        engine = self.app.state.engine
        p = next(iter(engine.ports.values()))
        if not p['connected']:
            engine.connect_simulated(p['key'])
        engine.start_session(p)
        session_id = p['session_id']
        self.app.state.access.apply_snapshot([record('commercial', 'sales', 'sales-id')], scopes=('developer', 'commercial'))
        self.assertEqual(self.client.post('/api/login', json={'username': 'sales', 'password': PASSWORD}).status_code, 200)
        self.client.post('/api/ports/' + p['key'] + '/action', json={'action': 'pause'})
        self.client.post('/api/ports/' + p['key'] + '/action', json={'action': 'disconnect'})
        self.client.post('/api/demo')
        self.assertTrue(p['running'])
        self.assertFalse(p['manual_pause'])
        self.assertEqual(p['session_id'], session_id)

    def test_account_verifier_accepts_eight_rejects_seven(self):
        from tools import account_verifier
        with patch('getpass.getpass', side_effect=['1234567', '1234567']):
            with self.assertRaises(SystemExit): account_verifier.main()
        with patch('getpass.getpass', side_effect=['abcdefgh', 'abcdefgh']), patch('builtins.print') as output:
            account_verifier.main()
        self.assertTrue(output.call_args.args[0].startswith('pbkdf2_sha256$'))
