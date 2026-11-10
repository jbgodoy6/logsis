"""Measured curve persistence, gaps, reduction and authenticated exports."""
import csv
from datetime import datetime,timezone
from pathlib import Path
import tempfile
import time
import unittest
from fastapi.testclient import TestClient
from app import curve
from app.main import create_app
from app.store import Store,password_hash

class CurveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(str(Path(self.tmp.name)/'history.sqlite3'));self.settings=self.store.settings();self.settings['mode']='physical';self.now=time.time()
    def tearDown(self):self.store.db.close();self.tmp.cleanup()
    def point(self,t,total=100,ev=20,valid=True,mode='physical',limit=500):
        settings=dict(self.settings,mode=mode,limit_kw=limit)
        curve.record(self.store,t,dict(at=t,total_kw=total),ev,valid,settings)
    def data(self,seconds=900,**kw):return curve.query(self.store,self.settings,datetime.fromtimestamp(self.now-seconds,timezone.utc).isoformat(),datetime.fromtimestamp(self.now+1,timezone.utc).isoformat(),now=self.now,**kw)
    def test_record_interval_limit_changes_modes_and_restart(self):
        self.point(self.now-10);self.point(self.now-9,total=999);self.point(self.now-8,limit=600);self.point(self.now-7,mode='simulation')
        data=self.data();self.assertEqual(data['total_samples'],2);self.assertEqual(data['points'][0]['total_kw'],100)
        self.assertEqual(data['points'][-1]['limit_kw'],600)
        path=self.store.db.execute('PRAGMA database_list').fetchone()['file'];self.store.db.close();self.store=Store(path)
        self.assertEqual(self.data()['total_samples'],2);self.assertEqual(self.data(mode='simulation')['total_samples'],1)
    def test_missing_is_not_zero_and_gaps_break_lines(self):
        self.point(self.now-40,total=0,ev=0);self.point(self.now-35,valid=False);self.point(self.now-5)
        data=self.data();a,b,c=data['points'];self.assertEqual(a['total_kw'],0);self.assertIsNone(b['ev_kw']);self.assertIsNone(b['other_kw'])
        self.assertNotEqual(a['total_kw_segment'],c['total_kw_segment']);self.assertEqual(data['missing_samples'],1)
        self.assertIn('sem leitura',curve.render(data));self.assertIn('data-curve-value',curve.render(data))
    def test_reduction_preserves_peak_gap_and_full_csv_pdf(self):
        for n in range(2500):self.point(self.now-13000+n*5,total=987 if n==1234 else 100,valid=n!=1300)
        data=self.data(14000);self.assertTrue(data['reduced']);self.assertLessEqual(len(data['points']),1200)
        self.assertEqual(data['statistics']['total_kw']['max'],987);self.assertTrue(any(p['total_kw']==987 for p in data['points']))
        self.assertTrue(any(p['ev_kw'] is None for p in data['points']))
        out=Path(self.tmp.name)/'curve.csv';count=curve.export_csv(self.store,self.settings,out,datetime.fromtimestamp(self.now-14000,timezone.utc).isoformat())
        self.assertEqual(count,2500)
        with out.open(encoding='utf-8-sig') as stream:self.assertEqual(len(list(csv.reader(stream,delimiter=';'))),2501)
        self.assertTrue(curve.pdf(data,'0.12.0').startswith(b'%PDF-1.4'))
    def test_filter_timezone_and_invalid_ranges(self):
        cfg=dict(self.settings,timezone='America/Sao_Paulo')
        date=datetime.fromtimestamp(self.now,timezone.utc).strftime('%Y-%m-%d')
        a,_,_=curve.parameters(cfg,date+'T00:00',date+'T00:01',now=self.now+86400)
        self.assertEqual(datetime.fromtimestamp(a,timezone.utc).hour,3)
        for start,end,mode in [('bad','',''),('','bad',''),('','','evil'),('2020-01-01','','')]:
            with self.assertRaises(ValueError):curve.parameters(cfg,start,end,mode,now=self.now)
    def test_cleanup_curve_independent_of_unacknowledged_cloud_data(self):
        self.point(self.now-31*86400);self.point(self.now-10)
        self.store.record('fixture',{'unacknowledged':True})
        before=self.store.db.execute('SELECT count(*) FROM outbox').fetchone()[0]
        self.store.cleanup();self.assertEqual(self.data()['total_samples'],1)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM curve_points').fetchone()[0],1)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM outbox').fetchone()[0],before)

class CurveAPITests(unittest.TestCase):
    def test_auth_validation_top_position_and_exports_audited(self):
        app=create_app(':memory:',background=False,root_password_hash=password_hash('fixture-curve-root'))
        with TestClient(app) as c:
            for path in ('/api/curve','/api/curve/export.csv','/api/curve/report.pdf'):self.assertEqual(c.get(path).status_code,401)
            c.post('/api/setup',json={'admin_password':'fixture-curve-admin'});c.post('/api/login',json={'username':'root','password':'fixture-curve-root'});c.post('/api/demo',json={})
            page=c.get('/ui/overview').text
            self.assertLess(page.index('data-live-key="site-meter"'),page.index('data-live-key="chart"'));self.assertLess(page.index('data-live-key="chart"'),page.index('class="plant-section-title"'))
            self.assertEqual(c.get('/api/curve?start=bad').status_code,422)
            self.assertIn('últimos 15 minutos',c.get('/ui/overview?curve_start=bad').text)
            self.assertEqual(c.get('/api/curve/export.csv').status_code,200)
            self.assertTrue(c.get('/api/curve/report.pdf').content.startswith(b'%PDF-1.4'))
            self.assertEqual(app.state.store.db.execute("SELECT count(*) FROM events WHERE kind='curve_export'").fetchone()[0],2)
        app.state.store.db.close()

class CurveSimulationQualityTests(unittest.IsolatedAsyncioTestCase):
    async def test_simulator_sample_after_tick_start_is_valid(self):
        app=create_app(':memory:',background=False,root_password_hash=password_hash('fixture-simulation-root'))
        with TestClient(app) as c:
            c.post('/api/setup',json={'admin_password':'fixture-simulation-admin'});c.post('/api/login',json={'username':'root','password':'fixture-simulation-root'});c.post('/api/demo',json={})
            await app.state.engine.tick()
            points=curve.query(app.state.store,app.state.store.settings())['points']
            self.assertTrue(points);self.assertEqual(points[-1]['quality'],'valid');self.assertIsNotNone(points[-1]['ev_kw']);self.assertIsNotNone(points[-1]['other_kw'])
        app.state.store.db.close()
