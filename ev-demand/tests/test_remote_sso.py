import asyncio
import copy
import hashlib
import unittest
import httpx
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import password_hash

PASSWORD='fixture-sso-password'
HASH=password_hash(PASSWORD)


class RemoteSSOTests(unittest.TestCase):
    def setUp(self):
        self.app=create_app(':memory:',background=False,root_password_hash=HASH)
        self.client=TestClient(self.app,base_url='https://testserver');self.client.__enter__()
        self.client.post('/api/setup',json={'admin_password':PASSWORD})
        self.access=self.app.state.access
        self.access.configure({'url':'https://script.google.com/macros/s/fixture/exec','enabled':True,'interval_s':300})
        self.access.set_device_token('fixture-device-key')
        self.actor=dict(id='SSO-DEV',name='sso.dev',full_name='SSO Teste',role='developer',active=True,deleted=False,expires_at=None,password=HASH,must_change=False,activation_hash=None,credential_version=1,meta_version=1)
        self.refuse=False;self.requests=[]
        def transport(request):
            self.requests.append(request)
            if request.method=='POST':return httpx.Response(302,headers={'Location':'https://script.googleusercontent.com/macros/echo?fixture=sso'})
            if self.refuse:return httpx.Response(200,json={'ok':False,'code':401})
            public={k:self.actor[k] for k in ('id','name','full_name','role','active','deleted','expires_at')}
            return httpx.Response(200,json={'ok':True,'user':public,'snapshot':{'complete':True,'technicians':[],'accounts':[self.actor]}})
        self.transport=httpx.AsyncClient(transport=httpx.MockTransport(transport),follow_redirects=False)
        self.app.state.sso_client=self.transport

    def tearDown(self):
        self.client.__exit__(None,None,None);asyncio.run(self.transport.aclose())

    def test_developer_session_and_safe_redirect(self):
        response=self.client.post('/api/remote/sso',json={'ticket':'a'*64})
        self.assertEqual(response.status_code,200,response.text)
        self.assertTrue(self.client.cookies.get('ev_session'))
        self.assertEqual(self.client.get('/api/me').json()['name'],'sso.dev')
        self.assertEqual(self.requests[1].method,'GET');self.assertFalse(self.requests[1].content)
        self.assertNotIn('fixture-device-key',str(self.requests[1].headers))
        self.assertNotIn(PASSWORD,self.requests[0].content.decode())
        self.assertTrue(self.client.get('/remote/sso').headers['cache-control']=='no-store')
        self.assertIn('/static/remote-sso.js',self.client.get('/remote/sso').text)

    def test_commercial_demo_does_not_change_real_controller(self):
        self.actor.update(id='SSO-SALES',name='sso.sales',role='commercial')
        before_settings=copy.deepcopy(self.app.state.store.settings())
        before_chargers=copy.deepcopy(self.app.state.store.entities('chargers'))
        response=self.client.post('/api/remote/sso',json={'ticket':'b'*64})
        self.assertEqual(response.status_code,200,response.text)
        self.assertTrue(self.client.cookies.get('dmax_demo'));self.assertFalse(self.client.cookies.get('ev_session'))
        self.assertEqual(self.app.state.store.settings(),before_settings)
        self.assertEqual(self.app.state.store.entities('chargers'),before_chargers)
        self.assertEqual(self.client.get('/api/meter').status_code,403)

    def test_refused_and_malformed_pass_never_create_session(self):
        self.assertEqual(self.client.post('/api/remote/sso',json={'ticket':'bad'}).status_code,401)
        self.assertEqual(len(self.requests),0)
        self.refuse=True
        self.assertEqual(self.client.post('/api/remote/sso',json={'ticket':'a'*64}).status_code,401)
        self.assertFalse(self.client.cookies.get('ev_session'))
        self.assertEqual(self.access.db.execute('SELECT COUNT(*) FROM logins').fetchone()[0],0)

    def test_local_root_cannot_be_assumed(self):
        self.actor.update(id='root',name='root',role='root')
        self.assertEqual(self.client.post('/api/remote/sso',json={'ticket':'a'*64}).status_code,401)
        self.assertFalse(self.client.cookies.get('ev_session'))

    def test_existing_demo_can_switch_only_after_a_valid_pass(self):
        self.actor.update(id='SSO-SALES',name='sso.sales',role='commercial')
        self.assertEqual(self.client.post('/api/remote/sso',json={'ticket':'a'*64}).status_code,200)
        previous=self.client.cookies.get('dmax_demo');self.assertTrue(previous)
        self.refuse=True
        self.assertEqual(self.client.post('/api/remote/sso',json={'ticket':'b'*64}).status_code,401)
        self.assertEqual(self.client.cookies.get('dmax_demo'),previous)
        self.refuse=False;self.actor.update(id='SSO-DEV2',name='sso.dev2',role='developer')
        self.assertEqual(self.client.post('/api/remote/sso',json={'ticket':'c'*64}).status_code,200)
        self.assertFalse(self.client.cookies.get('dmax_demo'))
        self.assertEqual(self.client.get('/api/me').json()['name'],'sso.dev2')
