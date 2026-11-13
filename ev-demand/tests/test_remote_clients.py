import json
import time
import unittest
from unittest.mock import AsyncMock,patch
import httpx
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store,password_hash
from app.access import Access
from app.remote_clients import fetch,DirectoryUnavailable

class CatalogTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.store=Store(':memory:');self.access=Access(self.store)
        self.access.configure(dict(url='https://script.google.com/macros/s/fixture/exec',enabled=True,interval_s=30));self.access.set_device_token('fixture-catalog-key')
        self.record=dict(controller_id='customer-1',site_name='Cliente Um',url='https://client-one.trycloudflare.com',updated_at=time.time(),connected=True)
    def tearDown(self):self.store.db.close()
    async def query(self,payload):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,json=payload))) as client:return await fetch(self.access,client)
    async def test_named_client_and_fresh_changed_url(self):
        data=await self.query(dict(ok=True,clients=[self.record]));self.assertEqual(data['clients'][0],self.record)
        self.record['url']='https://client-new.trycloudflare.com';self.assertEqual((await self.query(dict(ok=True,clients=[self.record])))['clients'][0]['url'],self.record['url'])
    async def test_disabled_missing_key_and_unsupported_platform(self):
        self.access.configure(dict(url='',enabled=False,interval_s=30))
        with self.assertRaises(DirectoryUnavailable):await fetch(self.access)
    async def test_unauthorized_catalog_is_not_an_empty_success(self):
        with self.assertRaisesRegex(DirectoryUnavailable,'Autorize'):await self.query(dict(ok=False,code=403))
    async def test_bad_or_reserved_urls_and_duplicate_id_rejected(self):
        for url in ('https://api.trycloudflare.com','javascript:alert(1)','https://evil.test','https://user@a.trycloudflare.com','https://ok.trycloudflare.com/path'):
            with self.assertRaises(DirectoryUnavailable):await self.query(dict(ok=True,clients=[dict(self.record,url=url)]))
        with self.assertRaises(DirectoryUnavailable):await self.query(dict(ok=True,clients=[self.record,self.record]))
    async def test_redirect_does_not_forward_device_key(self):
        requests=[]
        def handle(request):
            requests.append(request)
            if len(requests)==1:return httpx.Response(302,headers={'Location':'https://script.googleusercontent.com/result'})
            return httpx.Response(200,json=dict(ok=True,clients=[self.record]))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:await fetch(self.access,client)
        self.assertEqual(json.loads(requests[0].content)['action'],'remote_directory');self.assertEqual(requests[1].method,'GET');self.assertNotIn('fixture-catalog-key',str(requests[1].headers)+str(requests[1].content))
    async def test_external_redirect_refused(self):
        count=0
        def handle(request):
            nonlocal count
            count+=1;return httpx.Response(302,headers={'Location':'https://evil.test/result'})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            with self.assertRaises(DirectoryUnavailable):await fetch(self.access,client)
        self.assertEqual(count,1)

class CatalogPermissionTests(unittest.TestCase):
    def test_only_root_and_only_opening_catalog_queries_platform(self):
        app=create_app(':memory:',background=False,root_password_hash=password_hash('fixture-catalog-root'))
        data=dict(clients=[dict(controller_id='ID',site_name='<script>Cliente</script>',url='https://safe-client.trycloudflare.com',updated_at=time.time()-4000,connected=True)],fetched_at=time.time())
        with TestClient(app) as c,patch('app.remote_clients.fetch',new_callable=AsyncMock,return_value=data) as fetcher:
            self.assertEqual(c.get('/api/remote-clients').status_code,401)
            c.post('/api/setup',json={'admin_password':'fixture-catalog-admin'});c.post('/api/login',json={'username':'admin','password':'fixture-catalog-admin'})
            self.assertEqual(c.get('/api/remote-clients').status_code,403);self.assertNotIn('Buscar clientes remotos',c.get('/ui/overview').text)
            self.assertEqual(c.get('/ui/remoteclients').status_code,403);fetcher.assert_not_called()
            c.post('/api/login',json={'username':'root','password':'fixture-catalog-root'})
            c.get('/ui/overview');c.get('/api/remote');fetcher.assert_not_called()
            self.assertEqual(c.get('/ui/remoteclients').status_code,403)
            from test_v0140 import record, PASSWORD
            app.state.access.apply_snapshot([record()],scopes=('developer','commercial'))
            c.post('/api/login',json={'username':'developer-one','password':PASSWORD})
            page=c.get('/ui/remoteclients');self.assertEqual(page.status_code,200);self.assertEqual(fetcher.await_count,1)
            self.assertIn('&lt;script&gt;Cliente&lt;/script&gt;',page.text);self.assertIn('Sem comunicação recente',page.text)
            self.assertIn('rel="noopener noreferrer"',page.text);self.assertNotIn('data-live-page="remoteclients"',page.text)
            c.get('/ui/settings');self.assertEqual(fetcher.await_count,1)
            reply=c.get('/api/remote-clients');self.assertEqual(reply.headers['cache-control'],'no-store');self.assertEqual(fetcher.await_count,2)
        app.state.store.db.close()
