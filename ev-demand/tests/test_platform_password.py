import asyncio
import json
import unittest
from unittest.mock import AsyncMock,patch
import httpx
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import password_hash
from app.platform_password import change

INITIAL='12345678'
INITIAL_HASH=password_hash(INITIAL)


class InitialPasswordTests(unittest.TestCase):
    def setUp(self):
        self.app=create_app(':memory:',background=False,root_password_hash=password_hash('fixture-root-pass'))
        self.client=TestClient(self.app);self.client.__enter__()
        self.client.post('/api/setup',json={'admin_password':'fixture-admin-pass'})
        self.access=self.app.state.access
        self.record=dict(id='FIRST',name='first.sales',full_name='Primeiro acesso',role='commercial',active=True,deleted=False,expires_at=None,password=INITIAL_HASH,must_change=True,activation_hash=None,credential_version=1,meta_version=1)
        self.access.apply_snapshot([self.record],scopes=('developer','commercial'))

    def tearDown(self):self.client.__exit__(None,None,None)

    def test_initial_commercial_does_not_enter_demo_or_hardware(self):
        reply=self.client.post('/api/login',json={'username':'first.sales','password':INITIAL})
        self.assertEqual(reply.status_code,200,reply.text);self.assertTrue(reply.json()['must_change'])
        self.assertTrue(self.client.cookies.get('ev_session'));self.assertFalse(self.client.cookies.get('dmax_demo'))
        self.assertEqual(self.client.get('/api/state').status_code,403)
        self.assertTrue(self.client.get('/api/me').json()['must_change'])
        with patch('app.platform_password.change',new_callable=AsyncMock) as confirmed,patch('app.main.synchronize',new_callable=AsyncMock,return_value=True):
            changed=self.client.post('/api/change-password',json={'current_password':INITIAL,'new_password':'MinhaNovaSenha123'})
            self.assertEqual(changed.status_code,200);self.assertTrue(changed.json()['login_required']);confirmed.assert_awaited_once()


class PlatformChangeTests(unittest.IsolatedAsyncioTestCase):
    async def test_confirmed_change_invalidates_old_cache_lease_and_never_replays_password_on_redirect(self):
        from app.store import Store
        from app.access import Access
        store=Store(':memory:');access=Access(store)
        record=dict(id='GLOBAL',name='global.dev',full_name='Teste',role='developer',active=True,deleted=False,expires_at=None,password=INITIAL_HASH,must_change=True,activation_hash=None,credential_version=1,meta_version=1)
        access.apply_snapshot([record],scopes=('developer','commercial'));actor=access.public(access.by_id('GLOBAL'))
        access.configure({'enabled':True,'url':'https://script.google.com/macros/s/fixture/exec','interval_s':300})
        requests=[];action=''
        def handler(request):
            nonlocal action
            requests.append(request)
            if request.method=='POST':action=json.loads(request.content)['action'];return httpx.Response(302,headers={'Location':'https://script.googleusercontent.com/macros/echo'})
            if action=='desktop_login':return httpx.Response(200,json={'ok':True,'token':'a'*64,'user':{'id':'GLOBAL','must_change':True}})
            if action=='desktop_change_password':return httpx.Response(200,json={'ok':True,'token':'b'*64,'user':{'id':'GLOBAL','must_change':False}})
            return httpx.Response(200,json={'ok':True})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler),follow_redirects=False) as client:
            await change(access,actor,INITIAL,'MinhaNovaSenha123',client)
        self.assertFalse(access.usable(access.by_id('GLOBAL')))
        for request in requests:
            if request.method=='GET':self.assertFalse(request.content);self.assertNotIn(INITIAL,str(request.headers))
        self.assertNotIn('MinhaNovaSenha123',json.dumps(access.by_id('GLOBAL')))
        store.db.close()
