import json
import time
import unittest
from fastapi.testclient import TestClient
from app.main import create_app


class APITests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(':memory:', background=False)
        self.context = TestClient(self.app)
        self.c = self.context.__enter__()
        self.c.post('/api/setup', json={'root_password': 'fixture-root-123', 'admin_password': 'fixture-admin-123'})
        self.c.post('/api/login', json={'username': 'root', 'password': 'fixture-root-123'})

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def test_setup_only_once_and_password_not_exposed(self):
        self.assertEqual(self.c.post('/api/setup', json={'root_password': 'another-root', 'admin_password': 'another-admin'}).status_code, 409)
        text = self.c.get('/api/state').text
        self.assertNotIn('password_hash', text)
        self.assertNotIn('fixture-', text)

    def test_unauthorized_state_and_cross_origin_write(self):
        self.c.cookies.clear()
        self.assertEqual(self.c.get('/api/state').status_code, 401)
        r = self.c.post('/api/login', headers={'Origin': 'https://attacker.invalid'}, json={'username': 'admin', 'password': 'fixture-admin-123'})
        self.assertEqual(r.status_code, 403)

    def test_demo_configurable_large_power_and_persistence(self):
        self.assertEqual(self.c.post('/api/demo', json={}).status_code, 200)
        data = self.c.get('/api/state').json()
        self.assertEqual(len(data['chargers']), 3)
        self.assertEqual(max(c['max_kw'] for c in data['chargers']), 320)
        settings = data['settings'];settings['limit_kw'] = 5000;settings['technical_limit_kw'] = 5000;settings['circuits'][0]['limit_kw'] = 5000
        self.assertEqual(self.c.put('/api/settings', json=settings).status_code, 200)
        self.assertEqual(self.c.get('/api/state').json()['settings']['limit_kw'], 5000)

    def test_duplicate_vehicle_identifier_rejected(self):
        data = {'name': 'Carro A', 'identifiers': ['AUTO-123']}
        self.assertEqual(self.c.post('/api/vehicles', json=data).status_code, 200)
        self.assertEqual(self.c.post('/api/vehicles', json=data | {'name': 'Carro B'}).status_code, 409)

    def test_root_can_recover_admin_and_revoke_sessions(self):
        self.c.post('/api/login', json={'username': 'admin', 'password': 'fixture-admin-123'})
        self.assertEqual(self.c.post('/api/recover-admin', json={'username': 'admin', 'password': 'changed-password'}).status_code, 403)
        self.c.post('/api/login', json={'username': 'root', 'password': 'fixture-root-123'})
        self.assertEqual(self.c.post('/api/recover-admin', json={'username': 'admin', 'password': 'changed-password'}).status_code, 200)
        self.assertEqual(self.c.post('/api/login', json={'username': 'admin', 'password': 'fixture-admin-123'}).status_code, 401)
        self.assertEqual(self.c.post('/api/login', json={'username': 'admin', 'password': 'changed-password'}).status_code, 200)

    def test_unsent_records_survive_retention(self):
        store = self.app.state.store
        identifier = store.record('minute', {'energy_kwh': 1}, 'test')
        with store.db:
            store.db.execute('UPDATE samples SET ts=? WHERE id=?', (time.time() - 100 * 86400, identifier))
        store.cleanup()
        self.assertTrue(store.db.execute('SELECT 1 FROM samples WHERE id=?', (identifier,)).fetchone())
        store.acknowledge([identifier])
        store.cleanup()
        self.assertFalse(store.db.execute('SELECT 1 FROM samples WHERE id=?', (identifier,)).fetchone())

    def test_settings_validation_and_no_plaintext_charger_password(self):
        settings = self.c.get('/api/state').json()['settings']
        settings['margin_kw'] = settings['limit_kw'] + 1
        self.assertEqual(self.c.put('/api/settings', json=settings).status_code, 422)
        data = {'id': 'station', 'name': 'Physical', 'transport': 'ocpp', 'max_kw': 320,
                'connector_max_kw': 320, 'password': 'fixture-ocpp-123'}
        self.assertEqual(self.c.post('/api/chargers', json=data).status_code, 200)
        text = self.c.get('/api/state').text
        self.assertNotIn('fixture-ocpp-123', text)
        self.assertNotIn('password_hash', text)

    def test_ocpp_boot_and_telemetry_with_basic_auth(self):
        password = 'fixture-station-123'
        data = {'id': 'station', 'name': 'Physical', 'transport': 'ocpp', 'max_kw': 320,
                'connector_max_kw': 320, 'password': password}
        self.c.post('/api/chargers', json=data)
        store = self.app.state.store
        settings = store.settings();settings['mode'] = 'physical';store.save_settings(settings)
        import base64
        auth = base64.b64encode(('station:' + password).encode()).decode()
        with self.c.websocket_connect('/ocpp/station', subprotocols=['ocpp1.6'], headers={'Authorization': 'Basic ' + auth}) as ws:
            ws.send_json([2, 'boot', 'BootNotification', {'chargePointVendor': 'Test', 'chargePointModel': '320-kW'}])
            boot = ws.receive_json()
            self.assertEqual(boot[0:2], [3, 'boot'])
            self.assertEqual(boot[2]['status'], 'Accepted')
            ws.send_json([2, 'status', 'StatusNotification', {'connectorId': 1, 'errorCode': 'NoError', 'status': 'Preparing'}])
            self.assertEqual(ws.receive_json()[0:2], [3, 'status'])
            ws.send_json([2, 'auth', 'Authorize', {'idTag': 'AUTO-TEST'}])
            self.assertEqual(ws.receive_json()[2]['idTagInfo']['status'], 'Blocked')
            self.assertEqual(self.app.state.engine.ports['station:1']['identifier'], 'AUTO-TEST')
            from datetime import datetime, timezone
            ws.send_json([2, 'meter', 'MeterValues', {'connectorId': 1, 'meterValue': [
                {'timestamp': datetime.now(timezone.utc).isoformat(), 'sampledValue': [
                    {'value': '30000', 'measurand': 'Power.Active.Import', 'unit': 'W'}]}]}])
            self.assertEqual(ws.receive_json()[0:2], [3, 'meter'])
            self.assertEqual(self.app.state.engine.ports['station:1']['power_kw'], 30)

    def test_rtu_settings_and_manual_map_are_persisted(self):
        settings = self.c.get('/api/state').json()['settings']
        settings['mode'] = 'physical'
        settings['meter'].update(transport='rtu', serial_port='COM8', baudrate=19200, parity='E', stopbits=1)
        settings['meter']['registers'][0].update(address=5100, function=4, type='int32', scale=.001)
        self.assertEqual(self.c.put('/api/settings', json=settings).status_code, 200)
        saved = self.c.get('/api/state').json()['settings']['meter']
        self.assertEqual(saved['transport'], 'rtu')
        self.assertEqual(saved['serial_port'], 'COM8')
        self.assertEqual(saved['registers'][0]['address'], 5100)
        self.assertEqual(saved['registers'][0]['function'], 4)

    def test_physical_requires_total_power_register(self):
        settings = self.c.get('/api/state').json()['settings']
        settings['mode'] = 'physical';settings['meter']['host'] = '192.0.2.1'
        for reg in settings['meter']['registers']: reg['enabled'] = False
        self.assertEqual(self.c.put('/api/settings', json=settings).status_code, 422)

    def test_meter_test_uses_unsaved_draft_and_preserves_settings(self):
        from unittest.mock import AsyncMock, patch
        before = self.c.get('/api/state').json()['settings']['meter']
        draft = dict(before, host='192.0.2.44')
        readings = [{'measurement': 'power_total_kw', 'label': 'Potência ativa total', 'unit': 'kW',
                     'address': 0, 'function': 3, 'at': time.time(), 'value': 1200, 'error': None}]
        with patch('app.main.read_meter', new=AsyncMock(return_value=readings)) as read:
            response = self.c.post('/api/meter/test', json=draft)
            self.assertTrue(response.json()['ok'])
            self.assertEqual(response.json()['readings'][0]['value'], 1200)
            self.assertEqual(read.call_args.args[0]['host'], '192.0.2.44')
        self.assertEqual(self.c.get('/api/state').json()['settings']['meter'], before)

    def test_energycube_brand_and_logo_are_local_assets(self):
        html = self.c.get('/').text
        self.assertIn('D-Max', html)
        self.assertIn('EnergyCube', html)
        self.assertNotIn('LOGSIS', html)
        response = self.c.get('/static/energycube-logo.png')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['content-type'], 'image/png')


if __name__ == '__main__':
    unittest.main()
