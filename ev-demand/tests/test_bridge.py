"""Company portal: no hardware routes; online identities and disposable simulation."""
import copy
from http.server import ThreadingHTTPServer
import re
import threading
import time
import unittest
from unittest.mock import patch
import httpx
from bridge.main import Bridge, Simulator, handler_for, verifier, matches, PlatformError, GooglePlatform

PASSWORD = 'fixture-bridge-password'
HASH = verifier(PASSWORD)

def person(role, identifier):
    return dict(id=identifier,name=identifier.lower(),full_name='Membro '+role,role=role,password=HASH,
                active=True,deleted=False,expires_at=None,must_change=False,credential_version=1,meta_version=1)

class Platform:
    def __init__(self):
        self.users=[person('developer','DEV001'),person('commercial','COM001'),person('technician','TEC001')]
        self.fail=False
        self.calls=[]
        self.clients=[dict(controller_id='client-one',site_name='Cliente <Um>',url='https://client-one.trycloudflare.com',connected=True,updated_at=time.time())]
    def request(self,config,action,**payload):
        self.calls.append(action)
        if self.fail:raise PlatformError('Offline')
        if action=='snapshot':
            return dict(ok=True,complete=True,accounts=copy.deepcopy([r for r in self.users if r['role']!='technician']),technicians=copy.deepcopy([r for r in self.users if r['role']=='technician']))
        if action=='remote_directory':return dict(ok=True,clients=copy.deepcopy(self.clients))
        if action=='manage_user':
            actor=next((r for r in self.users if r['name']==payload['actor_login']),None)
            if not actor or actor['role']!='developer' or not matches(payload['actor_password'],actor['password']):raise PlatformError('Denied')
            record=payload['record']
            old=next((r for r in self.users if r['id']==record['id']),None)
            if old: self.users.remove(old)
            self.users.append(dict(id=record['id'],name=record['name'],full_name=record['full_name'],role=record['role'],password=record['password'],active=record['status']=='ativo',deleted=record['status']=='excluido',expires_at=None,must_change=False))
            return dict(ok=True,acknowledged_id=record['id'])
        raise AssertionError(action)

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.platform=Platform()
        self.bridge=Bridge(':memory:',self.platform)
        self.bridge.configure('https://script.google.com/macros/s/fixture/exec','x'*64,'WIN-fixture')
    def tearDown(self):self.bridge.db.close()
    def login(self,name='dev001'):return self.bridge.login(name,PASSWORD)
    def test_roles_authorized_and_revoked_without_extending_offline_lease(self):
        tokens={r:self.login(n) for r,n in [('developer','dev001'),('commercial','com001'),('technician','tec001')]}
        for role,token in tokens.items():self.assertEqual(self.bridge.session(token)[0]['role'],role)
        self.platform.fail=True
        at=self.bridge.users()[1]
        self.assertFalse(self.bridge.sync());self.assertEqual(self.bridge.users()[1],at)
        with patch('bridge.main.time.time',return_value=at+301):
            self.assertIsNone(self.bridge.session(tokens['commercial'])[0])
            self.assertEqual(self.bridge.session(tokens['developer'])[0]['role'],'developer')
        self.platform.fail=False
        self.platform.users[0]['deleted']=True
        self.platform.users[0]['active']=False
        self.assertTrue(self.bridge.sync())
        self.assertIsNone(self.bridge.session(tokens['developer'])[0])
    def test_simulation_isolation_discard_on_logout_or_idle(self):
        first=self.login('com001');second=self.login('com001')
        a=self.bridge.sessions[first]['simulator'];b=self.bridge.sessions[second]['simulator']
        a.action('pause',0)
        self.assertTrue(a.ports[0]['paused']);self.assertFalse(b.ports[0]['paused'])
        self.bridge.sessions[first]['seen']-=901
        self.assertIsNone(self.bridge.session(first)[0]);self.assertNotIn(first,self.bridge.sessions)
        self.assertIsNotNone(self.bridge.session(second)[0])
    def test_simulator_soc_complete_and_new_connection(self):
        sim=Simulator();p=sim.ports[0];p['soc']=99.999
        sim.at-=3600
        sim.advance();self.assertEqual(p['soc'],100);self.assertEqual(p['kw'],0)
        sim.advance();self.assertEqual(p['soc'],100)
        sim.action('disconnect',0);sim.action('connect',0);self.assertAlmostEqual(p['soc'],20,places=4)
    def test_dev_creates_global_member_and_password_verifier(self):
        token=self.login()
        record=self.bridge.manage(token,dict(name='new.member',full_name='Novo',role='commercial',status='ativo',password='new-fixture-password',confirmation='new-fixture-password',actor_password=PASSWORD,expires=''))
        self.assertTrue(matches('new-fixture-password',record['password']))
        self.assertEqual(self.bridge.session(self.bridge.login('new.member','new-fixture-password'))[0]['role'],'commercial')
        commercial=self.login('com001')
        before=len(self.platform.calls)
        with self.assertRaisesRegex(ValueError,'Somente desenvolvedor'):self.bridge.manage(commercial,{})
        self.assertEqual(len(self.platform.calls),before)
    def test_invalid_catalog_and_snapshot_keep_last_valid_state(self):
        previous=self.bridge.users()
        self.platform.users.append(copy.deepcopy(self.platform.users[0]))
        self.assertFalse(self.bridge.sync());self.assertEqual(self.bridge.users(),previous)
        self.platform.clients[0]['url']='https://attacker.test'
        with self.assertRaises(PlatformError):self.bridge.catalog(True)
    def test_short_password_rejected(self):
        with self.assertRaises(ValueError):verifier('1234567')
        self.assertTrue(matches('12345678',verifier('12345678')))

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.platform=Platform();self.bridge=Bridge(':memory:',self.platform)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(self.bridge))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.client=httpx.Client(base_url='http://127.0.0.1:'+str(self.server.server_port),follow_redirects=False)
    def tearDown(self):
        self.client.close();self.server.shutdown();self.server.server_close();self.thread.join();self.bridge.db.close()
    def csrf(self,path,action):
        page=self.client.get(path)
        match=re.search(r'<form method="post" action="'+re.escape(action)+r'"><input type="hidden" name="csrf" value="([a-f0-9]+)"',page.text)
        self.assertIsNotNone(match,page.text)
        return match.group(1)
    def setup_login(self,login='dev001'):
        csrf=self.csrf('/','/settings')
        result=self.client.post('/settings',data=dict(csrf=csrf,url='https://script.google.com/macros/s/fixture/exec',key='x'*64))
        self.assertEqual(result.status_code,303)
        csrf=self.csrf('/','/login')
        result=self.client.post('/login',data=dict(csrf=csrf,name=login,password=PASSWORD))
        self.assertEqual(result.status_code,303)
    def test_bootstrap_login_catalog_buttons_and_no_hardware(self):
        self.setup_login()
        page=self.client.get('/')
        self.assertIn('Cliente &lt;Um&gt;',page.text)
        self.assertNotIn('https://client-one.trycloudflare.com',page.text)
        self.assertIn('/open?id=client-one',page.text)
        self.assertIn('Usuários',page.text)
        result=self.client.get('/open?id=client-one');self.assertEqual(result.status_code,302)
        self.assertEqual(result.headers['location'],'https://client-one.trycloudflare.com')
        for path in ['/api/state','/api/ports/real/action','/ocpp','/maintenance']:
            self.assertEqual(self.client.get(path).status_code,404)
        self.assertEqual(self.client.get('/users').status_code,200)
        self.assertNotIn(HASH,self.client.get('/users').text)
    def test_commercial_and_technician_can_access_clients_but_not_users(self):
        self.setup_login('com001')
        self.assertIn('Acessar cliente',self.client.get('/').text)
        self.assertEqual(self.client.get('/users').status_code,403)
        self.assertEqual(self.client.get('/settings').status_code,403)
        self.assertEqual(self.client.get('/simulation').status_code,200)
        old=len(self.platform.calls)
        result=self.client.post('/users',data={'csrf':'wrong'})
        self.assertEqual(result.status_code,400);self.assertEqual(len(self.platform.calls),old)
        csrf=self.csrf('/','/logout');self.client.post('/logout',data={'csrf':csrf})
        csrf=self.csrf('/','/login');self.client.post('/login',data=dict(csrf=csrf,name='tec001',password=PASSWORD))
        self.assertIn('Acessar cliente',self.client.get('/').text)
        self.assertEqual(self.client.get('/users').status_code,403)
    def test_csrf_origin_host_and_logout_discard_simulator(self):
        self.setup_login('com001')
        token=self.client.cookies.get('bridge_session')
        csrf=self.csrf('/simulation','/simulation')
        result=self.client.post('/simulation',data=dict(csrf=csrf,operation='disconnect',port=0),headers={'Origin':'https://attacker.test'})
        self.assertEqual(result.status_code,400)
        self.assertTrue(self.bridge.sessions[token]['simulator'].ports[0]['connected'])
        self.assertEqual(self.client.get('/',headers={'Host':'attacker.test'}).status_code,400)
        csrf=self.csrf('/','/logout');self.client.post('/logout',data={'csrf':csrf})
        self.assertNotIn(token,self.bridge.sessions)
        self.assertEqual(self.client.get('/api/simulation').status_code,401)

if __name__=='__main__':unittest.main()

class SourcePackageTests(unittest.TestCase):
    def test_minimal_package_manifest_and_tamper_detection(self):
        import tempfile
        from pathlib import Path
        import zipfile
        from tools.package_bridge import package
        from bridge.main import verify_package
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            first=folder/'one.zip';second=folder/'two.zip'
            count,sha=package(root,first)
            self.assertEqual(count,5)
            self.assertEqual(package(root,second)[1],sha)
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(set(archive.namelist()),{'D-Max-Acesso-Windows/'+name for name in ['DMaxAcesso.py','style.css','portal.js','LEIA-ME.md','SHA256SUMS.txt']})
                for item in archive.infolist():
                    archive.read(item).decode('utf-8')
                    self.assertFalse(item.flag_bits & 1)
                archive.extractall(folder)
            shipped=folder/'D-Max-Acesso-Windows'
            with patch('bridge.main.ROOT',shipped):
                verify_package()
                (shipped/'portal.js').write_text('changed')
                with self.assertRaisesRegex(ValueError,'Arquivo ausente ou alterado'):
                    verify_package()
    def test_manifest_rejects_path_traversal(self):
        import tempfile
        from pathlib import Path
        from bridge.main import verify_package
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'SHA256SUMS.txt').write_text('0'*64+'  ../../outside\n')
            with patch('bridge.main.ROOT',root),self.assertRaisesRegex(ValueError,'Manifesto inválido'):
                verify_package()
