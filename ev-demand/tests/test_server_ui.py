import unittest
from html.parser import HTMLParser
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from recovery_helpers import create_test_app as create_app, recover_root


class Forms(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.forms, self.current, self.selected = [], None, None
        self.feed(text)

    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        if tag == 'form':
            self.current = {}
        if self.current is None:
            return
        name = attrs.get('name')
        if tag == 'input' and name:
            if attrs.get('type') == 'checkbox':
                if 'checked' in attrs:
                    if name == 'days':
                        self.current.setdefault(name, []).append(attrs.get('value', 'on'))
                    else:
                        self.current[name] = attrs.get('value', 'on')
            else:
                self.current[name] = attrs.get('value', '')
        if tag == 'select':
            self.selected = name
        if tag == 'option' and self.selected:
            if self.selected not in self.current or 'selected' in attrs:
                self.current[self.selected] = attrs.get('value', '')

    def handle_endtag(self, tag):
        if tag == 'select':
            self.selected = None
        if tag == 'form':
            self.forms.append(self.current)
            self.current = None

    def find(self, action):
        return next(form for form in self.forms if form.get('_action') == action)


class ServerUITests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(':memory:', background=False)
        self.context = TestClient(self.app)
        self.client = self.context.__enter__()

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def form(self, action, path='/'):
        return Forms(self.client.get(path).text).find(action)

    def submit(self, action, path='/', **changes):
        form = self.form(action, path)
        form.update(changes)
        return self.client.post('/ui/post', data=form)

    def setup_login(self, user='root'):
        response = self.submit('setup', admin_password='fixture-ui-admin')
        self.assertEqual(response.status_code, 200, response.text)
        response = recover_root(self.client) if user == 'root' else self.submit('login', username=user, password='fixture-ui-' + user)
        self.assertEqual(response.status_code, 200, response.text)

    def test_native_setup_login_has_no_scripts_and_strict_policy(self):
        page = self.client.get('/')
        self.assertEqual(page.status_code, 200)
        self.assertNotIn('name="root_password"', page.text)
        self.assertNotIn('31011986', page.text)
        self.assertNotIn('<script', page.text.lower())
        self.assertIn("script-src 'none'", page.headers['content-security-policy'])
        self.assertIn('httponly', page.headers['set-cookie'].lower())
        self.assertIn('samesite=strict', page.headers['set-cookie'].lower())
        self.assertEqual(page.headers['cache-control'], 'no-store')
        self.setup_login()
        self.assertIn('Visão geral', self.client.get('/').text)
        self.assertNotIn('fixture-ui-root', self.client.get('/').text)

    def test_csrf_missing_tampered_and_bound_to_session(self):
        form = self.form('setup')
        self.assertEqual(self.client.post('/ui/post', data={**form, '_csrf':'bad'}).status_code, 403)
        self.assertEqual(self.client.post('/ui/post', data={**form, '_action':'login'}).status_code, 403)
        self.assertEqual(self.client.get('/api/setup').json()['required'], True)
        self.setup_login()
        root_form = self.form('settings', '/ui/settings')
        self.client.post('/api/login', json={'username':'admin','password':'fixture-ui-admin'})
        root_form['limit_kw'] = '500'
        self.assertEqual(self.client.post('/ui/post', data=root_form).status_code, 403)
        self.assertEqual(self.app.state.store.settings()['limit_kw'], 1000)

    def test_remote_initial_setup_stays_forbidden_through_ui(self):
        remote = TestClient(self.app, client=('198.51.100.23', 1234))
        form = Forms(remote.get('/').text).find('setup')
        form.update(root_password='31011986', admin_password='fixture-admin')
        self.assertEqual(remote.post('/ui/post', data=form).status_code, 403)
        self.assertTrue(self.client.get('/api/setup').json()['required'])
        remote.close()

    def test_initial_setup_rejects_foreign_host_even_from_loopback(self):
        local = TestClient(self.app, client=('127.0.0.1', 1234), base_url='http://untrusted.invalid')
        form = Forms(local.get('/').text).find('setup')
        form.update(root_password='31011986', admin_password='fixture-admin')
        self.assertEqual(local.post('/ui/post', data=form).status_code, 403)
        self.assertTrue(self.client.get('/api/setup').json()['required'])
        local.close()

    def test_lan_browser_uses_same_accounts_without_installing_another_controller(self):
        self.setup_login()
        remote = TestClient(self.app, client=('192.0.2.25', 1234), base_url='http://dmax-garagem.local:9090')
        form = Forms(remote.get('/').text).find('login')
        self.assertNotIn('activation_code', form)
        response = recover_root(remote)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(remote.get('/api/me').json()['role'], 'root')
        remote.close()

    def test_admin_operational_limit_and_tampered_technical_fields(self):
        self.setup_login('admin')
        response = self.submit('settings', '/ui/settings', limit_kw='800')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.app.state.store.settings()['limit_kw'], 800)
        response = self.submit('settings', '/ui/settings', technical_limit_kw='9000')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.app.state.store.settings()['technical_limit_kw'], 1000)
        self.assertEqual(self.client.get('/ui/meter').status_code, 403)
        self.assertEqual(self.client.get('/ui/directory').status_code, 403)

    def test_account_first_password_change_without_code_and_operator_restrictions(self):
        self.setup_login()
        response = self.submit('user', '/ui/users', name='ui.operator', full_name='Operador UI', role='operator')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn('activation_result', response.text)
        self.assertNotIn('Código de ativação', response.text)
        self.submit('logout')
        response = self.submit('login', username='ui.operator', password='12345678')
        self.assertIn('Troque a senha inicial', response.text)
        self.assertEqual(self.client.get('/api/state').status_code, 403)
        response = self.submit('password', current_password='12345678',
                               new_password='fixture-ui-personal', confirmation='fixture-ui-personal')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/me').status_code, 401)
        self.submit('login', username='ui.operator', password='fixture-ui-personal')
        for page in ('users','settings','meter','directory'):
            self.assertEqual(self.client.get('/ui/' + page).status_code, 403)
        page = self.client.get('/')
        self.assertNotIn('href="/ui/users"', page.text)
        self.assertNotIn('<script', page.text.lower())

    def test_meter_draft_test_and_saved_manual_map(self):
        self.setup_login()
        before = self.app.state.store.settings()['meter']
        readings = [{'measurement':'power_total_kw','label':'Potência total','unit':'kW','address':5100,
                     'function':4,'at':1,'value':1200,'error':None}]
        with patch('app.main.read_meter', new=AsyncMock(return_value=readings)):
            response = self.submit('meter', '/ui/meter', host='192.0.2.12', reg_0_address='5100',
                                   reg_0_function='4', operation='test')
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn('1200', response.text)
        self.assertEqual(before, self.app.state.store.settings()['meter'])
        response = self.submit('meter', '/ui/meter', transport='rtu', serial_port='COM7',
                               baudrate='19200', parity='E', reg_0_address='5100', reg_0_function='4')
        self.assertEqual(response.status_code, 200, response.text)
        saved = self.app.state.store.settings()['meter']
        self.assertEqual(saved['serial_port'], 'COM7')
        self.assertEqual(saved['registers'][0]['address'], 5100)
        self.assertEqual(saved['registers'][0]['function'], 4)

    def test_html_values_remain_literal_and_are_not_reused_as_markup(self):
        self.setup_login()
        name = '<strong data-probe="untrusted">Nome externo</strong>'
        response = self.submit('vehicle', '/ui/vehicles', name=name, plate='', identifiers='UI-001')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('&lt;strong', response.text)
        self.assertNotIn('<strong data-probe=', response.text)
        self.assertEqual(self.app.state.store.entities('vehicle')[0]['name'], name)

    def test_form_limits_duplicates_and_content_type(self):
        form = self.form('setup')
        self.assertEqual(self.client.post('/ui/post', content='a' * 131073).status_code, 413)
        self.assertEqual(self.client.post('/ui/post', json=form).status_code, 415)
        from urllib.parse import urlencode
        encoded = urlencode(form) + '&_action=login'
        self.assertEqual(self.client.post('/ui/post', content=encoded,
                                         headers={'content-type':'application/x-www-form-urlencoded'}).status_code, 422)
        self.assertTrue(self.client.get('/api/setup').json()['required'])

    def test_directory_device_key_is_not_returned_after_save(self):
        self.setup_login()
        key = 'fixture-private-key-' + 'x' * 40
        response = self.submit('directory', '/ui/directory',
                               url='https://script.google.com/macros/s/FIXTURE/exec',
                               device_token=key, interval_s='600')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn(key, response.text)
        self.assertNotIn(key, self.client.get('/ui/directory').text)
        self.assertEqual(self.app.state.access.config()['interval_s'], 600)

    def test_real_client_address_is_used_for_login_limits(self):
        self.setup_login()
        first = TestClient(self.app, client=('198.51.100.11', 1234))
        second = TestClient(self.app, client=('198.51.100.12', 1234))
        try:
            for _ in range(8):
                form = Forms(first.get('/').text).find('login')
                form.update(username='root', password='wrong-password')
                self.assertEqual(first.post('/ui/post', data=form).status_code, 401)
            self.assertEqual(first.post('/ui/post', data=form).status_code, 429)
            form = Forms(second.get('/').text).find('login')
            self.assertEqual(recover_root(second).status_code, 200)
        finally:
            first.close(); second.close()
