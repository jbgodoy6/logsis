"""Unified central roster: role changes, atomic snapshots and local recovery."""
import hashlib
import time
import unittest
import httpx
from app.store import Store,password_hash
from app.access import Access
from app.directory import synchronize

HASH=password_hash('fixture-unified-password')
def person(role='technician',identifier='global-one',name='global.one'):
    return dict(id=identifier,name=name,full_name='Usuário global',role=role,password=HASH,active=True,deleted=False,expires_at=None,must_change=False,credential_version=1,meta_version=1)

class UnifiedAccountsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store=Store(':memory:');self.access=Access(self.store)
        self.access.configure({'enabled':True,'url':'https://directory.example','interval_s':300})
        self.access.set_device_token('fixture-key-'+'x'*32)
        self.access.apply_snapshot([person()])
    async def asyncTearDown(self):self.store.db.close()
    async def sync(self,technicians,accounts):
        data={'complete':True,'technicians':technicians,'accounts':accounts}
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=data))) as client:
            return await synchronize(self.access,client)
    def session(self,token):
        row=self.access.by_id('global-one')
        with self.store.db:
            self.store.db.execute('INSERT INTO logins VALUES (?,?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),row['name'],time.time()+3600,row['epoch'],0))
        return self.access.session(token)
    async def test_promote_and_demote_same_identity_revokes_previous_sessions(self):
        self.assertEqual(self.session('before-promotion')['role'],'technician')
        self.assertTrue(await self.sync([],[person('developer')]))
        self.assertIsNone(self.access.session('before-promotion'))
        self.assertEqual(self.session('before-demotion')['role'],'developer')
        self.assertTrue(await self.sync([person()],[]))
        self.assertIsNone(self.access.session('before-demotion'))
        self.assertEqual(self.access.by_id('global-one')['role'],'technician')
        self.assertEqual(self.access.by_id('global-one')['name'],'global.one')
    async def test_central_role_change_discards_old_offline_technical_upload(self):
        actor={'role':'root','id':'fixture-root','name':'root'}
        self.access.reset_password(actor,'global-one');self.assertTrue(self.access.pending())
        # Isolate the downloaded authoritative snapshot after a failed pending upload.
        async def handler(request):
            if request.method=='POST':return httpx.Response(403,json={'detail':'Denied'})
            return httpx.Response(200,json={'complete':True,'technicians':[],'accounts':[person('commercial')]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            self.assertTrue(await synchronize(self.access,client))
        self.assertEqual(self.access.by_id('global-one')['role'],'commercial')
        self.assertEqual(self.access.by_id('global-one')['password'],HASH)
        self.assertFalse(self.access.pending())
    async def test_cross_role_duplicate_snapshot_does_not_partially_change_accounts(self):
        before=self.access.by_id('global-one')
        self.assertFalse(await self.sync([person()],[person('developer')]))
        self.assertEqual(self.access.by_id('global-one'),before)
        self.assertIsNone(self.store.db.execute("SELECT 1 FROM account_leases WHERE user_id='global-one'").fetchone())
    async def test_platform_cannot_take_over_local_operator_identity(self):
        row=self.access.create({'role':'root','id':'root','name':'root'},'local.user','Local','operator')
        self.assertFalse(await self.sync([person()],[person('developer',row['id'],'local.user')]))
        self.assertEqual(self.access.by_id(row['id'])['role'],'operator')
    async def test_commercial_revoked_session_discards_demo_on_next_expiration_check(self):
        self.assertTrue(await self.sync([],[person('commercial')]))
        from app.commercial import Demonstrations
        manager=Demonstrations(self.access)
        token=await manager.create(self.access.by_id('global-one'))
        self.assertTrue(await self.sync([person()],[]))
        manager.expire();self.assertNotIn(token,manager.sessions)
        manager.close()
