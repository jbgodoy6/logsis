import json
import unittest
from unittest.mock import patch
import httpx
from app.access import Access
from app.store import Store
from app.directory import synchronize
from app import remote_registry as registry

class RegistryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store=Store(':memory:');self.access=Access(self.store)
        self.store.put('directory_config',dict(id='global',url='https://script.google.com/macros/s/fixture/exec',enabled=True,interval_s=30))
        self.state=dict(url='https://one.trycloudflare.com',connected=True,heartbeat_at=1794320000)
        self.mock=patch.object(registry,'public_status',return_value=self.state);self.mock.start()
    async def asyncTearDown(self):self.mock.stop();self.store.db.close()
    async def test_durable_retry_ack_and_reconnect_replaces_current_url(self):
        sent=registry.outgoing(self.access);self.assertEqual(registry.outgoing(self.access),sent)
        self.assertTrue(registry.publication(self.access)['pending'])
        registry.acknowledge(self.access,sent,None);self.assertTrue(registry.publication(self.access)['pending'])
        self.state.update(url='https://two.trycloudflare.com')
        newer=registry.outgoing(self.access);self.assertGreater(newer['revision'],sent['revision'])
        registry.acknowledge(self.access,sent,dict(revision=sent['revision'],accepted=True))
        self.assertTrue(registry.publication(self.access)['pending'])
        registry.acknowledge(self.access,newer,dict(revision=newer['revision'],accepted=True))
        self.assertFalse(registry.publication(self.access)['pending']);self.assertEqual(registry.publication(self.access)['published_url'],newer['url'])
    async def test_restore_conflict_advances_revision(self):
        sent=registry.outgoing(self.access);registry.acknowledge(self.access,sent,dict(revision=80,accepted=False))
        self.assertEqual(registry.outgoing(self.access)['revision'],81)
    async def test_legacy_provider_not_registered(self):
        self.state['url']='https://old.tunnl.gg';self.assertIsNone(registry.outgoing(self.access))
    async def test_google_transport_uses_authenticated_snapshot_without_extra_secret_cells(self):
        # Use the exact configuration entity used by Access.
        self.access.configure(dict(url='https://script.google.com/macros/s/fixture/exec',enabled=True,interval_s=30))
        requests=[]
        def handle(request):
            body=json.loads(request.content);requests.append(body)
            return httpx.Response(200,json=dict(ok=True,complete=True,technicians=[],remote_ack=dict(revision=body['remote']['revision'],accepted=True)))
        with patch.object(self.access,'device_token',return_value='fixture-device-secret'):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
                self.assertTrue(await synchronize(self.access,client))
        self.assertEqual(requests[0]['key'],'fixture-device-secret');self.assertNotIn('key',requests[0]['remote'])
        self.assertEqual(requests[0]['controller_id'],self.store.entities('system')[0]['controller_id'])
        self.assertFalse(registry.publication(self.access)['pending'])
