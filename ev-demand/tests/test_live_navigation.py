"""Live data must never reload the navigation shell or expose an unauthenticated view."""
import unittest
from fastapi.testclient import TestClient
from app.main import create_app


class LiveNavigationTests(unittest.TestCase):
    def setUp(self):
        self.app=create_app(':memory:',background=False,root_password_hash='')
        self.client=TestClient(self.app)
        self.client.post('/api/setup',json={'admin_password':'test-admin-for-navigation'})
        self.client.post('/api/login',json={'username':'admin','password':'test-admin-for-navigation'})

    def tearDown(self):
        self.client.close();self.app.state.store.db.close()

    def test_only_readonly_content_refreshes(self):
        for page in ['overview','monitor']:
            shell=self.client.get('/ui/'+page)
            self.assertEqual(shell.status_code,200)
            self.assertNotIn('http-equiv="refresh"',shell.text)
            self.assertIn('src="/ui-live/'+page+'"',shell.text)
            self.assertIn('referrerpolicy="same-origin"',shell.text)
            self.assertEqual(shell.headers['x-frame-options'],'DENY')
            child=self.client.get('/ui-live/'+page)
            self.assertEqual(child.status_code,200)
            self.assertIn('http-equiv="refresh"',child.text)
            self.assertNotIn('<aside',child.text)
            self.assertNotIn('<form',child.text)
            self.assertNotIn('<script',child.text)
            self.assertEqual(child.headers['x-frame-options'],'SAMEORIGIN')
            self.assertIn("frame-ancestors 'self'",child.headers['content-security-policy'])
            self.assertIn("script-src 'none'",child.headers['content-security-policy'])

    def test_configuration_and_credentials_cannot_be_embedded_or_auto_refreshed(self):
        for page in ['settings','chargers','profile']:
            response=self.client.get('/ui/'+page)
            self.assertNotIn('http-equiv="refresh"',response.text)
            self.assertNotIn('class="live-data"',response.text)
            self.assertEqual(response.headers['x-frame-options'],'DENY')
        self.assertEqual(self.client.get('/ui-live/settings').status_code,404)
        self.assertEqual(self.client.get('/static/live.css').status_code,200)
        self.assertEqual(self.client.get('/api/state').headers['x-frame-options'],'DENY')

    def test_live_view_checks_session_on_every_refresh(self):
        self.client.post('/api/logout')
        for page in ['overview','monitor']:
            response=self.client.get('/ui-live/'+page)
            self.assertEqual(response.status_code,401)
            self.assertNotIn('http-equiv="refresh"',response.text)
            self.assertIn('Entrar novamente',response.text)
            self.assertNotIn('class="plant"',response.text)
            self.assertEqual(response.headers['cache-control'],'no-store')

    def test_palette_saved_and_validated_without_resetting_other_settings(self):
        before=self.app.state.store.settings()
        palette=dict(before['display_colors'],charging='#a855f7')
        self.assertEqual(self.client.put('/api/appearance',json=palette).status_code,200)
        saved=self.app.state.store.settings()
        self.assertEqual(saved['display_colors']['charging'],'#a855f7')
        self.assertEqual(saved['meter'],before['meter'])
        self.assertEqual(saved['limit_kw'],before['limit_kw'])
        css=self.client.get('/ui-colors.css')
        self.assertEqual(css.status_code,200)
        self.assertIn('--plant-charging:#a855f7;',css.text)
        self.assertEqual(css.headers['cache-control'],'no-store')
        bad=dict(palette,alarm='red; background:url(https://example.test)')
        self.assertEqual(self.client.put('/api/appearance',json=bad).status_code,422)
        self.assertEqual(self.app.state.store.settings()['display_colors'],palette)
        legacy=dict(saved);legacy.pop('display_colors')
        self.assertEqual(self.client.put('/api/settings',json=legacy).status_code,200)
        self.assertEqual(self.app.state.store.settings()['display_colors'],palette)

    def test_palette_cannot_be_changed_without_administrative_role(self):
        self.client.post('/api/users',json={'name':'operator-ui','full_name':'Operador','role':'operator'})
        self.client.post('/api/logout')
        self.assertEqual(self.client.put('/api/appearance',json={}).status_code,401)
        self.assertEqual(self.client.get('/ui-colors.css').status_code,401)
        self.client.post('/api/login',json={'username':'operator-ui','password':'12345678'})
        self.client.post('/api/change-password',json={'current_password':'12345678','new_password':'test-new-operator-password'})
        self.client.post('/api/login',json={'username':'operator-ui','password':'test-new-operator-password'})
        self.assertEqual(self.client.put('/api/appearance',json={}).status_code,403)
