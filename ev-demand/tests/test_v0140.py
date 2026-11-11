import asyncio
import copy
import hashlib
import time
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import password_hash
from app import curve

PASSWORD='fixture-account-password'
HASH=password_hash(PASSWORD)
def record(role='developer',name='developer-one',identifier='dev-one'):
    return dict(id=identifier,name=name,full_name='Conta individual',role=role,password=HASH,active=True,deleted=False,expires_at=None,must_change=False,credential_version=1,meta_version=1)

class AccountsTests(unittest.TestCase):
    def setUp(self):
        self.app=create_app(':memory:',background=False,root_password_hash=HASH)
        self.client=TestClient(self.app);self.client.__enter__()
        self.client.post('/api/setup',json={'admin_password':PASSWORD})
    def tearDown(self):self.client.__exit__(None,None,None)
    def snapshot(self,*records):self.app.state.access.apply_snapshot(list(records),scopes=('developer','commercial'))
    def login(self,name):return self.client.post('/api/login',json={'username':name,'password':PASSWORD})
    def test_developer_management_lease_revocation_and_root_transition(self):
        access=self.app.state.access
        self.assertEqual(self.client.post('/api/login',json={'username':'root','password':PASSWORD},headers={'host':'fixture.trycloudflare.com'}).status_code,200)
        self.snapshot(record());self.assertEqual(self.login('developer-one').status_code,200)
        self.assertEqual(self.client.get('/api/directory').status_code,200)
        self.assertEqual(self.client.post('/api/users',json={'name':'operador','full_name':'Operador','role':'operator'}).status_code,200)
        self.assertEqual(self.client.post('/api/users',json={'name':'outroroot','full_name':'Raiz','role':'root'}).status_code,403)
        self.assertEqual(self.client.post('/api/login',json={'username':'root','password':PASSWORD},headers={'host':'fixture.trycloudflare.com'}).status_code,403)
        self.assertEqual(self.login('root').status_code,200)
        self.assertEqual(self.client.get('/api/me',headers={'host':'fixture.trycloudflare.com'}).status_code,403)
        self.assertEqual(self.client.get('/api/me').status_code,200)
        self.assertEqual(self.login('developer-one').status_code,200)
        with access.db:access.db.execute("UPDATE account_leases SET verified_at=? WHERE user_id='dev-one'",(time.time()-3601,))
        self.assertEqual(self.client.get('/api/me').status_code,401)
        self.snapshot(record());self.assertEqual(self.login('developer-one').status_code,200)
        self.snapshot(dict(record(),active=False))
        self.assertEqual(self.client.get('/api/me').status_code,401)
    def test_legacy_snapshot_does_not_revoke_or_renew_privileged_lease(self):
        self.snapshot(record());access=self.app.state.access
        before=access.db.execute("SELECT verified_at FROM account_leases WHERE user_id='dev-one'").fetchone()[0]
        access.apply_snapshot([])
        self.assertTrue(access.usable(access.by_name('developer-one')))
        self.assertEqual(before,access.db.execute("SELECT verified_at FROM account_leases WHERE user_id='dev-one'").fetchone()[0])
        self.snapshot();self.assertFalse(access.usable(access.by_name('developer-one')))
    def test_commercial_isolation_api_escape_logout_and_idle_expiry(self):
        self.snapshot(record('commercial','sales-one','sales-one'))
        production=self.app.state.store
        before={table:production.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ('entities','curve_points','events','outbox','logins')}
        with patch('app.main.read_meter',side_effect=AssertionError('hardware')),patch('serial.tools.list_ports.comports',side_effect=AssertionError('serial')):
            self.assertEqual(self.login('sales-one').status_code,200)
            token=self.client.cookies.get('dmax_demo');manager=self.app.state.demonstrations
            first=manager.sessions[token]['app'];state=self.client.get('/api/state').json()
            self.assertTrue(state['chargers']);self.assertEqual(state['settings']['mode'],'simulation')
            for method,path in [('get','/api/directory'),('get','/api/remote-clients'),('get','/api/remote'),('get','/api/meter/ports'),('post','/api/meter/test'),('post','/api/login'),('post','/api/setup'),('post','/api/maintenance/restore')]:
                self.assertEqual(getattr(self.client,method)(path).status_code,403,path)
            data=state['settings'];data['mode']='physical'
            self.assertEqual(self.client.put('/api/settings',json=data).status_code,403)
            data['mode']='simulation';data['cloud_url']='https://example.com'
            self.assertEqual(self.client.put('/api/settings',json=data).status_code,403)
            for role in ('root','developer','technician','commercial'):
                self.assertEqual(self.client.post('/api/users',json={'name':'fake-'+role,'full_name':'Falso','role':role}).status_code,403)
            self.assertEqual(self.client.post('/api/users',json={'name':'demo-operator','full_name':'Fictício','role':'operator'}).status_code,200)
            other=TestClient(self.app)
            if True:
                self.assertEqual(other.post('/api/login',json={'username':'sales-one','password':PASSWORD}).status_code,200)
                second_token=other.cookies.get('dmax_demo')
                self.assertNotEqual(token,second_token)
                self.assertNotIn('demo-operator',[u['name'] for u in other.get('/api/users').json()['users']])
                self.assertEqual(other.post('/api/logout').status_code,200)
                self.assertNotIn(second_token,manager.sessions)
            self.assertEqual(self.client.post('/api/logout').status_code,200)
            self.assertNotIn(token,manager.sessions)
            self.assertEqual(self.login('sales-one').status_code,200)
            token=self.client.cookies.get('dmax_demo');manager.sessions[token]['last']-=901;manager.expire()
            self.assertNotIn(token,manager.sessions)
            self.assertEqual(self.client.get('/api/state').status_code,401)
        for table,count in before.items():self.assertEqual(production.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],count,table)

class AdaptiveTests(unittest.TestCase):
    def test_adaptive_rises_drops_independent_fields_noise_and_exports(self):
        from app.store import Store
        store=Store(':memory:');settings=store.settings();t=time.time()-20
        def sample(dt,total,ev):curve.record(store,t+dt,dict(at=t+dt,total_kw=total),ev,True,settings)
        sample(0,100,0);sample(1,115,0) # exactly 15% does not trigger
        self.assertEqual(store.db.execute('SELECT COUNT(*) FROM curve_points').fetchone()[0],1)
        sample(2,116,20);sample(2.5,100,40);sample(3,50,40)
        rows=store.db.execute('SELECT * FROM curve_points ORDER BY ts').fetchall()
        self.assertEqual([r['total_kw'] for r in rows],[100,116,100,50])
        self.assertEqual(getattr(store,'_curve_revision'),3)
        settings['mode']='physical';sample(4,0,0);sample(4.1,.9,0)
        self.assertEqual(store.db.execute("SELECT COUNT(*) FROM curve_points WHERE mode='physical'").fetchone()[0],1)
        settings['curve_min_delta_kw']=.1;sample(4.2,.9,0)
        self.assertEqual(store.db.execute("SELECT COUNT(*) FROM curve_points WHERE mode='physical'").fetchone()[0],2)
        store.db.close()

class MigrationAndPackagingTests(unittest.TestCase):
    def test_existing_installation_backup_and_defaults_preserve_root_history(self):
        import json,sqlite3,tempfile
        from pathlib import Path
        from app.store import Store
        from app.access import Access
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'controller.sqlite3';store=Store(str(path));access=Access(store,HASH)
            with store.db:
                store.db.execute("INSERT INTO users(name,password,role,id,full_name) VALUES ('root',?,'root','root-id','Raiz')",(HASH,))
                store.db.execute('DROP TABLE account_leases')
                settings=store.settings();settings.pop('curve_min_delta_kw');store.db.execute('UPDATE settings SET payload=?',(json.dumps(settings),))
            store.record('preserved-history',{'fixture':True});store.db.close()
            app=create_app(str(path),background=False,root_password_hash=HASH)
            self.assertEqual(app.state.access.by_name('root')['password'],HASH)
            self.assertEqual(app.state.store.settings()['curve_min_delta_kw'],1.0)
            self.assertTrue(app.state.store.db.execute("SELECT 1 FROM events WHERE kind='preserved-history'").fetchone())
            backups=list(Path(directory).glob('*.before-access-v0140-*.sqlite3'));self.assertEqual(len(backups),1)
            self.assertEqual(backups[0].stat().st_mode&0o777,0o600)
            with sqlite3.connect(backups[0]) as saved:self.assertEqual(saved.execute("SELECT password FROM users WHERE name='root'").fetchone()[0],HASH)
            app.state.store.db.close()

    def test_packager_rejects_a_different_signing_identity(self):
        import tempfile
        from pathlib import Path
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from tools.package_raspberry import load_signing_key
        # Ephemeral test key only; production trust and private key are untouched.
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.pem';key=Ed25519PrivateKey.generate()
            path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
            with self.assertRaises(ValueError):load_signing_key(Path(__file__).resolve().parents[1],path)

class CurveCacheTests(unittest.TestCase):
    def test_peak_invalidates_curve_cache_within_same_five_second_bucket(self):
        app=create_app(':memory:',background=False,root_password_hash=HASH)
        with TestClient(app) as client:
            client.post('/api/setup',json={'admin_password':PASSWORD})
            client.post('/api/login',json={'username':'root','password':PASSWORD})
            at=time.time();settings=app.state.store.settings()
            with patch('app.main.time.time',return_value=at+1):
                self.assertEqual(client.get('/api/curve').json()['total_samples'],0)
                curve.record(app.state.store,at,dict(at=at,total_kw=100),0,True,settings)
                curve.record(app.state.store,at+.5,dict(at=at+.5,total_kw=777),0,True,settings)
                data=client.get('/api/curve').json()
                self.assertEqual(data['total_samples'],2)
                self.assertEqual(data['statistics']['total_kw']['max'],777)
