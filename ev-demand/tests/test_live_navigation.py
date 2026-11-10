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

    def test_live_values_use_json_and_never_reload_a_document(self):
        for page in ['overview','monitor']:
            shell=self.client.get('/ui/'+page)
            self.assertEqual(shell.status_code,200)
            self.assertNotIn('http-equiv="refresh"',shell.text)
            self.assertNotIn('<iframe',shell.text)
            self.assertIn('data-live-page="overview"',shell.text)
            self.assertIn('/static/live.js?v=',shell.text)
            self.assertIn("script-src 'self'",shell.headers['content-security-policy'])
            self.assertEqual(shell.headers['x-frame-options'],'DENY')
            data=self.client.get('/ui-data/'+page)
            self.assertEqual(data.status_code,200)
            self.assertEqual(data.json()['schema_version'],1)
            self.assertIsInstance(data.json()['nodes'],list)
            self.assertEqual(data.headers['cache-control'],'no-store')
            self.assertEqual(data.headers['x-frame-options'],'DENY')
            self.assertIn('data-dmax-version',shell.text)

    def test_configuration_and_credentials_do_not_run_scripts_or_auto_refresh(self):
        for page in ['settings','chargers','profile']:
            response=self.client.get('/ui/'+page)
            self.assertNotIn('http-equiv="refresh"',response.text)
            self.assertNotIn('<script',response.text)
            self.assertIn("script-src 'none'",response.headers['content-security-policy'])
            self.assertEqual(response.headers['x-frame-options'],'DENY')
        self.assertEqual(self.client.get('/ui-data/settings').status_code,404)

    def test_live_view_checks_session_on_every_poll(self):
        self.client.post('/api/logout')
        for page in ['overview','monitor']:
            response=self.client.get('/ui-data/'+page)
            self.assertEqual(response.status_code,401)
            self.assertNotIn('nodes',response.json())
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

    def test_static_styles_use_versioned_urls_on_shell_and_live_document(self):
        from app.server_ui import VERSION
        for path in ['/ui/monitor','/ui/overview','/ui/settings']:
            response=self.client.get(path)
            for name in ['style.css','energycube.css','server.css','plant.css']:
                self.assertIn('/static/'+name+'?v='+VERSION,response.text)
            self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertIn('/static/live.css?v='+VERSION,self.client.get('/ui/overview').text)

    def test_dom_contract_escapes_labels_and_rejects_executable_markup(self):
        from app.live_dom import view_tree
        tree=view_tree('<p>&lt;script&gt;untrusted&lt;/script&gt;</p>')
        self.assertEqual(tree[0]['children'],['<script>untrusted</script>'])
        with self.assertRaises(ValueError):view_tree('<script>alert(1)</script>')
        tree=view_tree('<a href="/ui/simulation" onclick="bad()">Abrir</a>')
        self.assertNotIn('onclick',tree[0]['attrs'])
        self.assertEqual(self.client.get('/static/live.js').status_code,200)
