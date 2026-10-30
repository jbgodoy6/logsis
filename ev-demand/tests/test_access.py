import copy
import hashlib
import os
import time
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from app.access import Access
from app.directory import synchronize
from recovery_helpers import create_test_app as create_app, recover_root
from app.store import Store, password_hash, password_matches
from platform_service.server import create_platform
from platform_service.sheets import parse_rows, sheet_expiry


def global_record(identifier='TEC-001', name='tecnico.global', **changes):
    return {'id':identifier,'name':name,'full_name':'Técnico global','active':True,'deleted':False,
            'expires_at':None,'password':HASH,'activation_hash':None,'must_change':False,
            'credential_version':1,'meta_version':1} | changes


HASH = password_hash('fixture-global-password')


class PermissionsTests(unittest.TestCase):
    def setUp(self):
        self.app=create_app(':memory:',background=False)
        self.context=TestClient(self.app);self.c=self.context.__enter__()
        self.c.post('/api/setup',json={'root_password':'obsolete-root-password','admin_password':'fixture-admin'})
        self.login('root','31011986')

    def tearDown(self): self.context.__exit__(None,None,None)

    def login(self,name,password,code=''):
        if name == 'root':
            return recover_root(self.c)
        return self.c.post('/api/login',json={'username':name,'password':password,'activation_code':code})

    def create(self,name,role):
        self.login('root','31011986')
        r=self.c.post('/api/users',json={'name':name,'full_name':name,'role':role})
        self.assertEqual(r.status_code,200,r.text)
        return r.json()

    def activate(self,user):
        self.assertEqual(self.login(user['name'],'12345678').status_code,200)
        self.assertEqual(self.c.post('/api/change-password',json={'current_password':'12345678','new_password':'fixture-personal-password'}).status_code,200)
        self.assertEqual(self.login(user['name'],'fixture-personal-password').status_code,200)

    def test_root_requires_signature_and_cannot_be_changed_or_reset(self):
        self.assertEqual(self.login('root','31011986').status_code,200)
        self.assertEqual(self.c.post('/api/login',json={'username':'root','password':'31011986'}).status_code,401)
        self.assertFalse(self.c.get('/api/me').json()['must_change'])
        response=self.c.post('/api/change-password',json={'current_password':'31011986','new_password':'different-root-password'})
        self.assertEqual(response.status_code,422)
        root=self.app.state.access.by_name('root')
        self.assertEqual(self.c.post('/api/users/'+root['id']+'/reset',json={}).status_code,403)
        self.assertEqual(self.login('root','31011986').status_code,200)

    def test_existing_root_migration_revokes_sessions_and_preserves_admin(self):
        access=self.app.state.access
        old_token=self.c.cookies.get('ev_session')
        admin_before=access.by_name('admin')['password']
        with access.db:
            access.db.execute("UPDATE users SET password=?,must_change=1 WHERE name='root'",(HASH,))
        migrated=Access(self.app.state.store)
        root=migrated.by_name('root')
        self.assertEqual(root['password'],'')
        self.assertFalse(root['must_change'])
        self.assertIsNone(migrated.session(old_token))
        self.assertEqual(migrated.by_name('admin')['password'],admin_before)
        password_before=root['password'];epoch_before=root['epoch']
        repeated=Access(self.app.state.store).by_name('root')
        self.assertEqual(repeated['password'],password_before)
        self.assertEqual(repeated['epoch'],epoch_before)

    def test_first_access_needs_only_password_and_forces_change(self):
        u=self.create('operador.um','operator')
        self.assertNotIn('activation_code',u)
        self.assertEqual(self.login(u['name'],'12345678').status_code,200)
        self.assertTrue(self.c.get('/api/me').json()['must_change'])
        self.assertEqual(self.c.get('/api/state').status_code,403)
        self.assertEqual(self.c.post('/api/change-password',json={'current_password':'12345678','new_password':'12345678'}).status_code,422)
        self.assertEqual(self.c.post('/api/change-password',json={'current_password':'12345678','new_password':'fixture-personal-password'}).status_code,200)
        self.assertEqual(self.c.get('/api/me').status_code,401)
        self.assertEqual(self.login(u['name'],'fixture-personal-password').status_code,200)
        self.assertEqual(self.c.get('/api/state').status_code,200)

    def test_existing_activation_hash_no_longer_blocks_login_or_changes_personal_password(self):
        user=self.create('legacy.operator','operator')
        access=self.app.state.access
        with access.db:
            access.db.execute('UPDATE users SET activation_hash=? WHERE id=?',(HASH,user['id']))
        self.assertEqual(self.login(user['name'],'12345678').status_code,200)
        self.assertTrue(self.c.get('/api/me').json()['must_change'])
        self.assertEqual(self.c.post('/api/change-password',json={'current_password':'12345678','new_password':'fixture-personal-new'}).status_code,200)
        self.assertEqual(self.login(user['name'],'fixture-personal-new').status_code,200)

    def test_global_new_technician_logs_in_without_root_activation(self):
        access=self.app.state.access
        from app.access import INITIAL_PASSWORD
        access.apply_snapshot([global_record(password=password_hash(INITIAL_PASSWORD),activation_hash=HASH,must_change=True)])
        self.assertIsNone(access.by_name('tecnico.global')['activation_hash'])
        self.assertEqual(self.login('tecnico.global',INITIAL_PASSWORD).status_code,200)
        self.assertTrue(self.c.get('/api/me').json()['must_change'])

    def test_reset_returns_initial_password_flow_without_code_and_revokes_session(self):
        user=self.create('reset.operator','operator');self.activate(user)
        token=self.c.cookies.get('ev_session')
        self.login('root','31011986')
        response=self.c.post('/api/users/'+user['id']+'/reset',json={})
        self.assertEqual(response.status_code,200)
        self.assertNotIn('activation_code',response.json())
        self.assertIsNone(self.app.state.access.session(token))
        self.assertEqual(self.login(user['name'],'12345678').status_code,200)
        self.assertTrue(self.c.get('/api/me').json()['must_change'])

    def test_operator_cannot_manage_users_meter_or_peak_schedule(self):
        u=self.create('operador.dois','operator');self.activate(u)
        settings=self.app.state.store.settings()
        self.assertEqual(self.c.put('/api/settings',json=settings).status_code,403)
        self.assertEqual(self.c.post('/api/meter/test',json=settings['meter']).status_code,403)
        self.assertEqual(self.c.get('/api/users').status_code,403)
        self.assertEqual(self.c.get('/api/directory').status_code,403)
        self.assertEqual(self.c.post('/api/ports/unknown/action',json={'action':'emergency','reason':'test'}).status_code,403)

    def test_admin_changes_operational_limit_and_schedule_but_not_meter_or_ceiling(self):
        self.login('admin','fixture-admin')
        data=self.c.get('/api/state').json()['settings'];data['limit_kw']=800
        data['schedules']=[{'days':[0], 'start':'18:00','end':'21:00','enabled':True}]
        self.assertEqual(self.c.put('/api/settings',json=data).status_code,200)
        data['meter']['host']='192.0.2.1'
        self.assertEqual(self.c.put('/api/settings',json=data).status_code,403)
        data=self.app.state.store.settings();data['technical_limit_kw']=2000
        self.assertEqual(self.c.put('/api/settings',json=data).status_code,403)
        self.assertEqual(self.c.post('/api/users',json={'name':'new.tech','full_name':'Tech','role':'technician'}).status_code,403)
        self.assertEqual(self.c.post('/api/users',json={'name':'new.operator','full_name':'Operator','role':'operator'}).status_code,200)

    def test_technician_has_technical_access_but_cannot_create_technician_or_root(self):
        u=self.create('tecnico.local','technician');self.activate(u)
        settings=self.app.state.store.settings();settings['meter']['host']='192.0.2.1'
        self.assertEqual(self.c.put('/api/settings',json=settings).status_code,200)
        for role in ('technician','root'):
            self.assertEqual(self.c.post('/api/users',json={'name':'another.'+role,'full_name':'New','role':role}).status_code,403)
        self.assertEqual(self.c.post('/api/users',json={'name':'another.admin','full_name':'New','role':'admin'}).status_code,200)

    def test_block_and_delete_revoke_existing_sessions_and_preserve_identity(self):
        u=self.create('operador.tres','operator');self.activate(u)
        token=self.c.cookies.get('ev_session')
        self.login('root','31011986')
        result=self.c.put('/api/users/'+u['id'],json={'full_name':u['full_name'],'role':'operator','active':False,'deleted':True})
        self.assertEqual(result.status_code,200)
        self.c.cookies.set('ev_session',token,domain='testserver.local',path='/')
        self.assertEqual(self.c.get('/api/state').status_code,401)
        self.assertEqual(self.app.state.access.by_id(u['id'])['name'],u['name'])

    def test_offline_global_account_has_no_extra_expiry(self):
        access=self.app.state.access
        access.apply_snapshot([global_record()])
        access.status['last_success']=time.time()-90*86400
        self.assertEqual(self.login('tecnico.global','fixture-global-password').status_code,200)
        self.assertEqual(self.c.get('/api/state').status_code,200)
        access.apply_snapshot([global_record(expires_at=time.time()-1)])
        self.assertEqual(self.c.get('/api/state').status_code,401)
        self.assertEqual(self.login('tecnico.global','fixture-global-password').status_code,401)

    def test_malformed_snapshot_is_atomic_and_cannot_promote_local_root(self):
        access=self.app.state.access;access.apply_snapshot([global_record()])
        bad=global_record(identifier='TEC-002',name='outro.tecnico');bad.pop('password')
        with self.assertRaises(ValueError): access.apply_snapshot([global_record(active=False),bad])
        self.assertTrue(access.by_name('tecnico.global')['active'])
        with self.assertRaises(ValueError): access.apply_snapshot([global_record(name='root')])
        self.assertEqual(access.by_name('root')['role'],'root')

    def test_metadata_update_does_not_reset_password(self):
        access=self.app.state.access
        access.apply_snapshot([global_record()])
        access.apply_snapshot([global_record(full_name='Novo nome')])
        self.assertEqual(self.login('tecnico.global','fixture-global-password').status_code,200)
        access.apply_snapshot([])
        self.assertEqual(self.c.get('/api/state').status_code,401)

    def test_sync_period_is_root_only_and_separate_from_reading_uploads(self):
        data={'url':'https://directory.example','interval_s':600,'enabled':True}
        self.assertEqual(self.c.put('/api/directory',json=data).status_code,200)
        self.assertEqual(self.c.get('/api/directory').json()['config']['interval_s'],600)
        self.login('admin','fixture-admin')
        self.assertEqual(self.c.put('/api/directory',json=data|{'interval_s':30}).status_code,403)

    def test_public_users_and_audit_never_contain_hashes_or_activation_codes(self):
        u=self.create('operador.quatro','operator')
        text=self.c.get('/api/users').text
        self.assertNotIn('activation_code',text)
        self.assertNotIn('pbkdf2_sha256',text)
        import json
        self.assertNotIn('activation_code',json.dumps(self.app.state.store.pending()))

    def test_root_promotion_to_technician_is_queued_globally(self):
        u=self.create('operador.cinco','operator')
        result=self.c.put('/api/users/'+u['id'],json={'full_name':u['full_name'],'role':'technician','active':True})
        self.assertEqual(result.status_code,200)
        self.assertEqual(self.app.state.access.pending()[0]['kind'],'register')

    def test_device_key_can_be_saved_by_root_but_is_never_returned_or_audited(self):
        key='fixture-private-device-key-'+('x'*32)
        payload={'url':'https://script.google.com/macros/s/FIXTURE/exec','interval_s':300,'enabled':False,'device_token':key}
        self.assertEqual(self.c.put('/api/directory',json=payload).status_code,200)
        response=self.c.get('/api/directory')
        self.assertTrue(response.json()['token_present'])
        self.assertNotIn(key,response.text)
        import json
        self.assertNotIn(key,json.dumps(self.app.state.store.pending()))
        self.assertNotIn(key,self.c.get('/api/state').text)

    def test_existing_database_migration_disables_root_password_and_backs_up(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'old.sqlite3';old=Store(str(path))
            with old.db:old.db.execute('INSERT INTO users VALUES (?,?,?)',('root',HASH,'root'))
            Access(old)
            self.assertEqual(old.db.execute("SELECT password FROM users WHERE name='root'").fetchone()[0], '')
            self.assertTrue(list(Path(temp).glob('*.before-users-v03-*.sqlite3')))
            old.db.close()


class SheetTests(unittest.TestCase):
    def test_private_sheet_schema_global_and_date_validity(self):
        rows=parse_rows([['id','nome','login','situacao','valido_ate'],['TEC-001','Técnico','tecnico.um','ativo','']])
        self.assertIsNone(rows[0]['expires_at'])
        self.assertNotIn('client',rows[0])
        self.assertEqual(sheet_expiry('31/12/2026'),sheet_expiry('2026-12-31'))
        with self.assertRaises(ValueError): parse_rows([['id','nome','login','senha','valido_ate']])
        with self.assertRaises(ValueError): parse_rows([['id','nome','login','situacao','valido_ate'],['TEC-1','Root','root','ativo','']])


class FakeSheet:
    def __init__(self, rows=None): self.rows=copy.deepcopy(rows or [])
    def read(self): return copy.deepcopy(self.rows)
    def write(self, record):
        fields={k:record[k] for k in ('id','name','full_name','active','deleted','expires_at')}
        self.rows=[r for r in self.rows if r['id']!=record['id']]+[fields]


class SynchronizationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store=Store(':memory:');self.access=Access(self.store)
        self.access.configure({'url':'https://directory.example','interval_s':300,'enabled':True})

    async def asyncTearDown(self): self.store.db.close()

    async def test_failed_or_partial_sync_never_deletes_cached_accounts(self):
        self.access.apply_snapshot([global_record()])
        for body in ({'complete':False,'technicians':[]},{'complete':True,'technicians':[{}]}):
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=body))) as client:
                with patch.dict(os.environ,{'DMAX_DIRECTORY_TOKEN':'fixture-device-token'}):
                    self.assertFalse(await synchronize(self.access,client))
            self.assertTrue(self.access.by_name('tecnico.global')['active'])

    async def test_google_platform_to_edge_password_change_and_revocation(self):
        identity=self.store.entities('system')[0]['controller_id']
        sheet=FakeSheet([{'id':'TEC-001','name':'tecnico.global','full_name':'Técnico','active':True,'deleted':False,'expires_at':None}])
        platform=create_platform(':memory:',sheet=sheet,device_tokens={identity:hashlib.sha256(b'fixture-device-token').hexdigest()})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=platform)) as client:
            with patch.dict(os.environ,{'DMAX_DIRECTORY_TOKEN':'fixture-device-token'}):
                self.assertTrue(await synchronize(self.access,client))
                actor={'role':'root','name':'root','id':'fixture-root-id'}
                self.assertTrue(self.access.reset_password(actor,'TEC-001')['must_change'])
                self.assertTrue(await synchronize(self.access,client))
                row=self.access.by_id('TEC-001')
                self.access.change_password(self.access.public(row),'12345678','fixture-new-password')
                self.assertTrue(await synchronize(self.access,client))
                from app.store import password_matches
                self.assertTrue(password_matches('fixture-new-password',platform.state.accounts.by_id('TEC-001')['password']))
                self.assertFalse(self.access.by_id('TEC-001')['must_change'])
                sheet.rows[0]['active']=False
                self.assertTrue(await synchronize(self.access,client))
                self.assertFalse(self.access.by_id('TEC-001')['active'])
                self.assertFalse(self.access.pending())
        platform.state.store.db.close()

    async def test_root_offline_registration_publishes_metadata_without_password_in_sheet(self):
        identity=self.store.entities('system')[0]['controller_id'];sheet=FakeSheet()
        platform=create_platform(':memory:',sheet=sheet,device_tokens={identity:hashlib.sha256(b'fixture-device-token').hexdigest()})
        new=self.access.create({'role':'root','name':'root','id':'fixture-root-id'},'tecnico.offline','Técnico offline','technician')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=platform)) as client:
            with patch.dict(os.environ,{'DMAX_DIRECTORY_TOKEN':'fixture-device-token'}):
                self.assertTrue(await synchronize(self.access,client))
        self.assertEqual(sheet.rows[0]['name'],'tecnico.offline')
        self.assertNotIn('password',sheet.rows[0])
        self.assertEqual(self.access.by_id(new['id'])['source'],'directory')
        platform.state.store.db.close()

    async def test_pending_upload_failure_does_not_prevent_remote_block(self):
        self.access.apply_snapshot([global_record()])
        root={'role':'root','name':'root','id':'fixture-root-id'}
        self.access.reset_password(root,'TEC-001')
        def response(request):
            if request.method=='POST':return httpx.Response(503,json={'detail':'write unavailable'})
            return httpx.Response(200,json={'complete':True,'technicians':[global_record(active=False)]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
            with patch.dict(os.environ,{'DMAX_DIRECTORY_TOKEN':'fixture-device-token'}):
                self.assertTrue(await synchronize(self.access,client))
        self.assertFalse(self.access.by_id('TEC-001')['active'])
        self.assertTrue(self.access.pending())

    async def test_registration_retry_after_uncertain_google_write_is_idempotent(self):
        class UncertainSheet(FakeSheet):
            failed=False
            def write(self,record):
                super().write(record)
                if not self.failed:
                    self.failed=True
                    raise OSError('Response lost after Google committed')
        sheet=UncertainSheet();identity=self.store.entities('system')[0]['controller_id']
        platform=create_platform(':memory:',sheet=sheet,device_tokens={identity:hashlib.sha256(b'fixture-device-token').hexdigest()})
        new=self.access.create({'role':'root','name':'root','id':'fixture-root-id'},'tecnico.retry','Técnico retry','technician')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=platform)) as client:
            with patch.dict(os.environ,{'DMAX_DIRECTORY_TOKEN':'fixture-device-token'}):
                self.assertTrue(await synchronize(self.access,client))
                self.assertTrue(self.access.pending())
                self.assertTrue(await synchronize(self.access,client))
        self.assertEqual(len(sheet.rows),1)
        self.assertFalse(self.access.pending())
        self.assertEqual(self.access.by_id(new['id'])['source'],'directory')
        platform.state.store.db.close()

    async def test_google_apps_script_redirect_does_not_forward_device_secret(self):
        self.access.configure({'url':'https://script.google.com/macros/s/FIXTURE/exec','interval_s':300,'enabled':True})
        self.access.set_device_token('fixture-device-token')
        requests=[]
        def respond(request):
            requests.append(request)
            if request.method=='POST':
                import json
                body=json.loads(request.content)
                self.assertEqual(body['action'],'snapshot')
                self.assertEqual(body['key'],'fixture-device-token')
                self.assertNotIn('authorization',request.headers)
                return httpx.Response(302,headers={'Location':'https://script.googleusercontent.com/macros/echo?fixture=1'})
            self.assertEqual(request.url.host,'script.googleusercontent.com')
            self.assertNotIn('authorization',request.headers)
            self.assertFalse(request.content)
            return httpx.Response(200,json={'ok':True,'complete':True,'technicians':[global_record()]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            self.assertTrue(await synchronize(self.access,client))
        self.assertEqual(len(requests),2)
        self.assertTrue(self.access.by_name('tecnico.global')['active'])

    async def test_apps_script_untrusted_redirect_is_rejected_without_following(self):
        self.access.configure({'url':'https://script.google.com/macros/s/FIXTURE/exec','interval_s':300,'enabled':True})
        self.access.set_device_token('fixture-device-token');self.access.apply_snapshot([global_record()])
        requests=[]
        def respond(request):
            requests.append(request)
            return httpx.Response(302,headers={'Location':'https://untrusted.example/steal'})
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            self.assertFalse(await synchronize(self.access,client))
        self.assertEqual(len(requests),1)
        self.assertTrue(self.access.by_name('tecnico.global')['active'])


if __name__=='__main__': unittest.main()
