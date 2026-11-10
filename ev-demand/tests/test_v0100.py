"""0.10: offline deadlines, role boundaries, history and authenticated maintenance."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch, AsyncMock
from types import SimpleNamespace
import zipfile
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from app.main import create_app
from app.engine import Engine
from app.access import Access, SESSION_IDLE
from app.store import Store, password_hash
from app.licensing import Subscription
from app.maintenance import verify_update, validate_backup, DOMAIN
from app.reports import report_data, build_pdf
from test_v090 import envelope, TOKEN

class OfflineTests(unittest.TestCase):
    def setUp(self):self.s=Store(':memory:');self.sub=Subscription(self.s);self.start=self.sub.highwater
    def tearDown(self):self.s.db.close()
    def at(self, days):
        with patch('app.licensing.time.time', return_value=self.start+days*86400):return self.sub.status()
    def test_exact_15_30_40_days_and_restart_without_notice(self):
        self.assertEqual(self.at(14.99)['offline_state'],'connected')
        self.assertEqual(self.at(15)['offline_state'],'warning');self.assertFalse(self.at(29.99)['native'])
        self.assertEqual(self.at(30)['remaining_days'],10);self.assertFalse(self.at(39.99)['native'])
        self.assertTrue(self.at(40)['native'])
        self.sub=Subscription(self.s);self.assertTrue(self.sub.status()['native'])
    def test_signed_reconnect_does_not_clear_financial_pending_or_replay_extend(self):
        self.sub.receive(envelope(self.s,issued=self.start),TOKEN)
        with patch('app.licensing.time.time',return_value=self.start+5*86400):
            self.sub.receive(envelope(self.s,issued=self.start,server=self.start+5*86400),TOKEN)
        self.assertEqual(self.sub.status()['remaining_days'],5)
        contact=self.sub.row['last_valid_contact']
        self.sub.receive(envelope(self.s,issued=self.start,server=self.start+1),TOKEN)
        self.assertEqual(self.sub.row['last_valid_contact'],contact)
        self.assertTrue(self.at(11)['financial_expired'])
    def test_regular_reconnect_clears_only_connectivity_native(self):
        self.sub.receive(envelope(self.s,state='regular',issued=self.start),TOKEN)
        self.assertTrue(self.at(41)['native'])
        with patch('app.licensing.time.time',return_value=self.start+41*86400):
            self.sub.receive(envelope(self.s,state='regular',issued=self.start,server=self.start+41*86400),TOKEN)
        self.assertFalse(self.sub.status()['native'])
    def test_invalid_contact_never_renews(self):
        invalid=envelope(self.s);invalid['signature']='0'*64
        with self.assertRaises(ValueError):self.sub.receive(invalid,TOKEN)
        self.assertIsNone(self.sub.status()['last_valid_contact'])

class APITests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.environment=patch.dict(os.environ,{'DMAX_MAINTENANCE_DIR':self.temporary.name+'/maintenance'})
        self.environment.start()
        self.app=create_app(':memory:',background=False,root_password_hash=password_hash('fixture-root-0100'))
        self.c=TestClient(self.app);self.c.post('/api/setup',json={'admin_password':'fixture-admin-0100'})
        self.login('root','fixture-root-0100');self.assertEqual(self.c.post('/api/demo',json={}).status_code,200)
    def tearDown(self):
        self.c.close();self.app.state.store.db.close();self.environment.stop();self.temporary.cleanup()
    def login(self,name,password):
        r=self.c.post('/api/login',json={'username':name,'password':password});self.assertEqual(r.status_code,200,r.text);return r
    def test_admin_cannot_operate_simulator_through_any_endpoint(self):
        self.login('admin','fixture-admin-0100');key=next(iter(self.app.state.engine.ports))
        for path,payload in [('/api/demo',{}),('/api/simulation',{'other_kw':300}),('/api/ports/'+key+'/action',{'action':'disconnect'}),('/api/ports/'+key+'/action',{'action':'pause'})]:
            self.assertEqual(self.c.post(path,json=payload).status_code,403,path)
        page=self.c.get('/ui/overview').text
        self.assertNotIn('name="other_kw"',page);self.assertNotIn('href="/ui/simulation"',page)
        self.assertEqual(self.c.post('/api/maintenance/restore',content=b'bad').status_code,403)
        self.assertEqual(self.c.get('/api/maintenance/backup').status_code,403)
    def test_overview_contains_one_plant_all_ports_and_simulation_form_outside_live_region(self):
        page=self.c.get('/ui/overview').text
        self.assertEqual(page.count('data-live-key="site-meter"'),1)
        self.assertEqual(page.count('class="plant-charger'),3)
        self.assertNotIn('href="/ui/monitor"',page)
        self.assertGreater(page.index('name="other_kw"'),page.index('</noscript>'))
        self.assertEqual(self.c.get('/ui-data/overview').status_code,200)
    def test_flash_is_consumed_on_first_get_and_does_not_return_on_refresh(self):
        self.c.cookies.set('dmax_saved','1',domain='testserver.local',path='/')
        self.assertIn('Alteração aplicada.',self.c.get('/ui/overview').text)
        self.assertNotIn('Alteração aplicada.',self.c.get('/ui/overview?notice=saved').text)
    def test_general_pdf_multiselection_and_separate_origins(self):
        s=self.app.state.store;start=time.time()-100
        for ident,mode,vehicle,energy in [('a','ocpp','frota-01',20),('b','simulator','frota-01',9),('c','ocpp',None,4)]:
            s.put('session',dict(id=ident,port='DC-01:1',vehicle_id=vehicle,mode=mode,started_at=start,ended_at=start+10,energy_kwh=energy,peak_kw=10))
        data=report_data(s,start='2099-01-01',report_type='vehicles',vehicles='frota-01,unassigned')
        self.assertEqual(len(data['vehicle_summary']),3)
        self.assertEqual(sum(r['total_kwh'] for r in data['vehicle_summary']),33)
        self.assertEqual(sum(r['period_kwh'] for r in data['vehicle_summary']),0)
        r=self.c.get('/api/reports/sessions.pdf',params=[('report_type','vehicles'),('vehicle_selection','frota-01'),('vehicle_selection','unassigned')])
        self.assertEqual(r.status_code,200);self.assertIn(b'GERAL POR',r.content)
    def test_backup_download_validates_and_does_not_change_live_database(self):
        root=self.app.state.access.by_name('root')['password']
        r=self.c.get('/api/maintenance/backup');self.assertEqual(r.status_code,200)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'backup.sqlite3';p.write_bytes(r.content)
            validate_backup(p,self.app.state.store.entities('system')[0]['controller_id'])
            with self.assertRaises(ValueError):validate_backup(p,'other-controller')
            with sqlite3.connect(p) as db:self.assertEqual(db.execute('select count(*) from logins').fetchone()[0],0)
        self.assertEqual(root,self.app.state.access.by_name('root')['password'])
        self.assertEqual(self.c.get('/api/state').status_code,200)
    def test_maintenance_rejects_upload_without_csrf_and_without_worker(self):
        self.assertEqual(self.c.post('/api/maintenance/update',content=b'bad').status_code,403)
        csrf=self.c.get('/api/maintenance').json()['csrf']
        self.assertEqual(self.c.post('/api/maintenance/update',content=b'bad',headers={'X-DMax-Maintenance':csrf}).status_code,409)
    def test_validated_restore_upload_is_queued_atomically_and_duplicate_refused(self):
        backup=self.c.get('/api/maintenance/backup').content
        csrf=self.c.get('/api/maintenance').json()['csrf'];original=Path.is_file
        with patch.object(Path,'is_file',lambda p:True if str(p)=='/etc/systemd/system/d-max-maintenance.path' else original(p)):
            r=self.c.post('/api/maintenance/restore',content=backup,headers={'X-DMax-Maintenance':csrf})
            self.assertEqual(r.status_code,200,r.text)
            queue=Path(self.temporary.name)/'maintenance';request=json.loads((queue/'request.json').read_text())
            self.assertEqual(request['action'],'restore');self.assertEqual((queue/(request['id']+'.upload')).read_bytes(),backup)
            self.assertFalse((queue/'pending.json').exists())
            self.assertEqual(self.c.post('/api/maintenance/restore',content=backup,headers={'X-DMax-Maintenance':csrf}).status_code,409)
    def test_sessions_renew_and_explicit_revocation_wins(self):
        s=self.app.state.store;token=self.c.cookies.get('ev_session');digest=hashlib.sha256(token.encode()).hexdigest()
        now=time.time()
        with s.db:s.db.execute('UPDATE logins SET expires=? WHERE token=?',(now+30,digest))
        self.assertEqual(self.c.get('/api/state').status_code,200)
        expires=s.db.execute('SELECT expires FROM logins WHERE token=?',(digest,)).fetchone()[0]
        self.assertGreater(expires,now+SESSION_IDLE['root']-5)
        with s.db:self.app.state.access.revoke('root')
        self.assertEqual(self.c.get('/api/state').status_code,401)
    def test_origin_queues_remain_separate_after_switch(self):
        s=self.app.state.store;sim=s.record('connected',{'port':'sim:1'})
        cfg=s.settings();cfg['mode']='physical';s.save_settings(cfg)
        real=s.record('connected',{'port':'real:1'})
        self.assertIn(real,[r['id'] for r in s.pending()]);self.assertNotIn(sim,[r['id'] for r in s.pending()])
        self.assertIn(sim,[r['id'] for r in s.pending('simulation')])
    def test_audit_is_restricted_and_contains_actor_without_secrets(self):
        self.c.post('/api/simulation',json={'other_kw':200})
        r=self.c.get('/api/audit');self.assertEqual(r.status_code,200)
        self.assertNotIn('pbkdf2',r.text);self.assertNotIn('fixture-root',r.text)

class PackageSecurityTests(unittest.TestCase):
    def test_worker_restore_preserves_current_root_subscription_and_identity(self):
        from deploy import maintenance_worker as worker
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);target=folder/'current.sqlite3';incoming=folder/'backup.sqlite3';backups=folder/'backups';backups.mkdir()
            app=create_app(str(target),background=False,root_password_hash=password_hash('fixture-existing-root'))
            c=TestClient(app,base_url='http://127.0.0.1',client=('127.0.0.1',50000))
            self.assertEqual(c.post('/api/setup',json={'admin_password':'fixture-old-admin'}).status_code,200)
            with sqlite3.connect(incoming) as db:app.state.store.db.backup(db)
            root=app.state.access.by_name('root')['password'];identity=app.state.store.entities('system')[0]['controller_id']
            app.state.engine.subscription.receive(envelope(app.state.store),TOKEN)
            deadline=app.state.engine.subscription.row['deadline']
            app.state.store.db.close();c.close()
            with patch.object(worker,'DB',target),patch.object(worker,'run'),patch.object(worker.time,'sleep'):
                worker.restore(incoming,backups)
            restored=Store(str(target))
            self.assertEqual(restored.db.execute("select password from users where name='root'").fetchone()[0],root)
            self.assertEqual(restored.entities('system')[0]['controller_id'],identity)
            self.assertEqual(restored.get('subscription','current')['deadline'],deadline)
            self.assertTrue((backups/'controller.sqlite3').is_file());restored.db.close()

class CommandDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_meter_error_preserves_reading_age_but_blocks_demand_admission(self):
        s=Store(':memory:');settings=s.settings();settings['mode']='physical';s.save_settings(settings)
        e=Engine(s);e.meter.update(at=time.time(),total_kw=100,error='Falha de leitura')
        await e.tick()
        self.assertFalse(e.summary['meter_fresh']);self.assertEqual(e.summary['budget_kw'],0)
        self.assertGreater(e.meter['at'],0);s.db.close()

    async def test_requested_accepted_and_measured_power_remain_distinct(self):
        s=Store(':memory:')
        s.put('charger',dict(id='REAL',name='Real',transport='ocpp',connectors=1,max_kw=320,enabled=True))
        e=Engine(s);port=e.ports['REAL:1'];cp=SimpleNamespace(limit=AsyncMock(return_value=False));e.connections['REAL']=cp
        self.assertFalse(await e.set_limit(port,100))
        self.assertEqual(port['requested_limit_kw'],100);self.assertEqual(port['command_status'],'Rejeitado');self.assertEqual(port['limit_kw'],0)
        port['last_command_at']=0;cp.limit.return_value=True
        self.assertTrue(await e.set_limit(port,100))
        self.assertIn('Aceito',port['command_status']);self.assertEqual(port['power_kw'],0)
        self.assertEqual(port['sample_at'],0)
        e.telemetry(port,power_kw=0);self.assertGreater(port['sample_at'],0)
        s.db.close()

class PackageSignatureTests(unittest.TestCase):
    def test_signature_tamper_and_path_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);key=Ed25519PrivateKey.generate();public=folder/'key.pem'
            public.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
            files={name:b'fixture' for name in ('run.py','requirements.lock','instalar-raspberry.sh','app/main.py','deploy/manage.py')}
            manifest=''.join(hashlib.sha256(v).hexdigest()+'  '+k+'\n' for k,v in files.items()).encode()
            def make(extra=None,tamper=False):
                path=folder/'package.zip'
                with zipfile.ZipFile(path,'w') as z:
                    for name,data in files.items():z.writestr('D-Max-Raspberry/'+name,data+(b'x' if tamper else b''))
                    z.writestr('D-Max-Raspberry/SHA256SUMS.txt',manifest)
                    z.writestr('D-Max-Raspberry/SHA256SUMS.sig',key.sign(DOMAIN+manifest))
                    if extra:z.writestr(extra,b'bad')
                return path
            self.assertEqual(verify_update(make(),public),5)
            for kwargs in [dict(tamper=True),dict(extra='../escape'),dict(extra='D-Max-Raspberry/extra.py')]:
                with self.assertRaises(Exception):verify_update(make(**kwargs),public)

if __name__=='__main__':unittest.main()
