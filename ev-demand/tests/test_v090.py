"""Subscription clock/replay, native OCPP and historical PDF regression tests."""
import asyncio
import hashlib
import hmac
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
import httpx
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.store import Store
from app.engine import Engine
from app.licensing import Subscription, DOMAIN, NOTICE_SECONDS
from app.ocpp_server import Station
from app.reports import report_data, build_pdf
from app.access import Access
from app.directory import synchronize
from recovery_helpers import create_test_app, recover_root
from test_server_ui import Forms

TOKEN='fixture-only-subscription-token'

def envelope(store, state='pending', revision=1, issued=None, server=None, **changes):
    issued=time.time() if issued is None else issued
    payload=dict(controller_id=store.entities('system')[0]['controller_id'],revision=revision,state=state,
                 issued_at=issued,deadline=issued+NOTICE_SECONDS if state=='pending' else None,
                 server_time=server or max(time.time(),issued),message='Regularize com seu fornecedor.')
    payload.update(changes)
    raw=json.dumps(payload,separators=(',',':'),ensure_ascii=False)
    signature=hmac.new(hashlib.sha256(TOKEN.encode()).hexdigest().encode(),DOMAIN+raw.encode(),hashlib.sha256).hexdigest()
    return dict(payload=raw,signature=signature)

class SubscriptionTests(unittest.TestCase):
    def setUp(self):self.store=Store(':memory:');self.sub=Subscription(self.store)
    def tearDown(self):self.store.db.close()

    def test_no_notice_keeps_demand_active(self):
        self.assertEqual(self.sub.status()['state'],'unconfigured');self.assertFalse(self.sub.status()['native'])

    def test_offline_deadline_survives_restart_and_regularization(self):
        start=time.time();notice=envelope(self.store,issued=start)
        self.sub.receive(notice,TOKEN)
        self.assertEqual(self.sub.status()['remaining_days'],10)
        self.sub=Subscription(self.store)
        with patch('app.licensing.time.time',return_value=start+NOTICE_SECONDS+1):
            self.assertTrue(self.sub.status()['native'])
        self.sub=Subscription(self.store)
        self.assertTrue(self.sub.status()['native'])
        regular=envelope(self.store,state='regular',revision=2,issued=start+NOTICE_SECONDS+2)
        self.sub.receive(regular,TOKEN)
        self.assertFalse(self.sub.status()['native'])
        with self.assertRaises(ValueError):self.sub.receive(notice,TOKEN)

    def test_authentication_scope_and_fixed_deadline(self):
        for changes in [dict(controller_id='other'),dict(deadline=time.time()+500),dict(revision=True)]:
            with self.assertRaises(ValueError):self.sub.receive(envelope(self.store,**changes),TOKEN)
        valid=envelope(self.store);valid['signature']='0'*64
        with self.assertRaises(ValueError):self.sub.receive(valid,TOKEN)
        valid=envelope(self.store);self.sub.receive(valid,TOKEN)
        with self.assertRaises(ValueError):self.sub.receive(envelope(self.store,revision=1,message='Conflicting'),TOKEN)

    def test_replay_cannot_extend_or_clear_an_expired_pending_notice(self):
        start=time.time();notice=envelope(self.store,issued=start)
        self.sub.receive(notice,TOKEN)
        with patch('app.licensing.time.time',return_value=start+NOTICE_SECONDS+1):self.sub.status()
        self.sub.receive(notice,TOKEN)
        self.assertTrue(self.sub.status()['native'])
        self.sub.receive(envelope(self.store,issued=start,revision=2,message='Mensagem alterada'),TOKEN)
        self.assertTrue(self.sub.status()['native'])

    def test_wall_clock_rollback_does_not_grant_more_days(self):
        self.sub.receive(envelope(self.store),TOKEN)
        self.sub.persist();self.sub=Subscription(self.store)
        with patch('app.licensing.time.time',return_value=self.sub.highwater-3600):
            state=self.sub.status()
        self.assertTrue(state['native']);self.assertTrue(state['clock_suspect'])

    def test_monotonic_clock_counts_while_wall_clock_is_frozen(self):
        self.sub.receive(envelope(self.store),TOKEN)
        before=self.sub.highwater;mono=self.sub.anchor
        with patch('app.licensing.time.monotonic',return_value=mono+NOTICE_SECONDS+2),patch('app.licensing.time.time',return_value=before):
            self.assertTrue(self.sub.status()['native'])

    def test_sqlite_file_preserves_notice_without_network(self):
        with tempfile.TemporaryDirectory() as folder:
            path=str(Path(folder)/'state.sqlite3');s=Store(path);sub=Subscription(s)
            sub.receive(envelope(s),TOKEN);deadline=sub.row['deadline'];s.db.close()
            s=Store(path);sub=Subscription(s)
            self.assertEqual(sub.status()['deadline'],deadline);s.db.close()

class NativeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store=Store(':memory:');settings=self.store.settings();settings['mode']='physical';self.store.save_settings(settings)
        self.store.put('charger',dict(id='REAL',transport='ocpp',name='Real',connectors=1,max_kw=320,connector_max_kw=320,
             min_kw=6,enabled=True,commissioned=True,circuit='principal',rate_unit='W',zero_supported=True))
        self.engine=Engine(self.store);self.port=self.engine.ports['REAL:1'];self.port.update(connected=True,ocpp_status='Preparing')
        self.cp=SimpleNamespace(release_native=AsyncMock(return_value=True),remote_start=AsyncMock(),limit=AsyncMock(return_value=True))
        self.engine.connections['REAL']=self.cp
        self.engine.subscription.receive(envelope(self.store,issued=time.time()-NOTICE_SECONDS-10),TOKEN)
    async def asyncTearDown(self):self.store.db.close()

    async def test_native_clears_profiles_and_starts_without_meter_or_demand_budget(self):
        self.port['limit_kw']=100
        await self.engine.tick()
        self.cp.release_native.assert_awaited_once_with(1)
        self.cp.remote_start.assert_awaited_once_with(self.port,native=True)
        self.cp.limit.assert_not_awaited();self.assertTrue(self.port['native_released'])
        await self.engine.tick();self.assertEqual(self.cp.release_native.await_count,1)
        self.assertFalse(await self.engine.set_limit(self.port,320));self.cp.limit.assert_not_awaited()

    async def test_rejected_clear_remains_pending_and_does_not_claim_native_release(self):
        self.cp.release_native.return_value=False
        await self.engine.tick();self.cp.remote_start.assert_not_awaited()
        self.assertIn('pendente',self.port['status']);self.assertFalse(self.port['native_released'])
        self.cp.release_native.side_effect=TimeoutError()
        self.port['native_attempt']=0
        await self.engine.tick();self.assertFalse(self.port['native_released'])

    async def test_renewal_reinitializes_managed_profiles(self):
        await self.engine.tick()
        self.engine.subscription.receive(envelope(self.store,state='regular',revision=2),TOKEN)
        self.port['last_command_at']=0
        await self.engine.tick()
        self.cp.limit.assert_awaited_with(1,0.0)
        self.assertFalse(self.port['native_mode']);self.assertFalse(self.port['native_released'])

    async def test_completed_transaction_does_not_restart_until_unplug(self):
        await self.engine.tick();self.engine.start_session(self.port,42)
        station=Station('REAL',SimpleNamespace(),self.engine)
        await station.stop_transaction(meter_stop=1000,timestamp='2026-11-09T15:00:00Z',transaction_id=42)
        self.cp.remote_start.reset_mock();self.port['start_pending_at']=0
        await self.engine.tick();self.cp.remote_start.assert_not_awaited()
        self.engine.disconnect(self.port['key']);self.assertFalse(self.port['manual_pause'])

    async def test_station_wire_commands_clear_only_owned_id_and_omit_profile(self):
        station=Station('REAL',SimpleNamespace(),self.engine)
        station.call=AsyncMock(return_value=SimpleNamespace(status='Accepted'))
        self.assertTrue(await station.release_native(1));request=station.call.call_args.args[0]
        self.assertEqual(request.id,1);self.assertIsNone(request.connector_id)
        await station.remote_start(self.port,native=True);request=station.call.call_args.args[0]
        self.assertIsNone(request.charging_profile)
        result=await station.start_transaction(connector_id=1,id_tag='plug-auto',meter_start=0,timestamp='2026-11-09T15:00:00Z')
        self.assertEqual(result.id_tag_info['status'],'Accepted')


class SignedDirectoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_signed_notice_received_by_existing_periodic_sync_and_retained_offline(self):
        store=Store(':memory:');access=Access(store);access.subscription=Subscription(store)
        access.set_device_token(TOKEN)
        access.configure(dict(enabled=True,url='https://script.google.com/macros/s/FIXTURE/exec',interval_s=300))
        notice=envelope(store)
        async def remote(request):
            return httpx.Response(200,json=dict(ok=True,complete=True,technicians=[],subscription=notice))
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(remote)) as client:
                self.assertTrue(await synchronize(access,client))
            self.assertEqual(access.subscription.status()['state'],'pending')
            async def offline(request):raise httpx.ConnectError('fixture offline')
            async with httpx.AsyncClient(transport=httpx.MockTransport(offline)) as client:
                self.assertFalse(await synchronize(access,client))
            self.assertEqual(access.subscription.status()['state'],'pending')
            notice['signature']='0'*64
            async with httpx.AsyncClient(transport=httpx.MockTransport(remote)) as client:
                self.assertFalse(await synchronize(access,client))
            self.assertEqual(access.subscription.status()['revision'],1)
        finally:store.db.close()

class FleetReportTests(unittest.TestCase):
    def setUp(self):
        self.app=create_test_app(':memory:',background=False);self.c=TestClient(self.app)
        self.c.post('/api/setup',json={'admin_password':'fixture-new-admin'});recover_root(self.c)
        self.c.post('/api/demo',json={});self.s=self.app.state.store;self.e=self.app.state.engine
    def tearDown(self):self.c.close();self.s.db.close()

    def test_vehicle_delete_confirmation_busy_rejection_and_history(self):
        p=next(p for p in self.e.ports.values() if p['vehicle_id']);vid=p['vehicle_id'];self.e.start_session(p);sid=p['session_id']
        self.assertEqual(self.c.delete('/api/vehicles/'+vid).status_code,409)
        self.e.disconnect(p['key'])
        form=next(f for f in Forms(self.c.get('/ui/vehicles').text).forms if f.get('_action')=='delete_vehicle' and f.get('id')==vid)
        self.assertEqual(self.c.post('/ui/post',data=form).status_code,422)
        form['confirm']='on';self.assertEqual(self.c.post('/ui/post',data=form).status_code,200)
        self.assertTrue(self.s.get('vehicle',vid)['archived']);self.assertIsNotNone(self.s.get('session',sid))
        self.assertNotIn(vid,[v['id'] for v in self.e.snapshot()['vehicles']])
        self.assertEqual(self.c.post('/api/ports/'+p['key']+'/action',json={'action':'connect','vehicle_id':vid}).status_code,422)
        self.e.identify(p,self.s.get('vehicle',vid)['identifiers'][0]);self.assertIsNone(p['vehicle_id'])
        name=self.s.get('vehicle',vid)['name'];self.assertIn(name,self.c.get('/ui/history').text)
        self.assertEqual(self.c.post('/api/vehicles',json={k:v for k,v in self.s.get('vehicle',vid).items() if k not in ('archived','archived_at')}).status_code,409)

    def seed(self,count=25):
        vehicles=self.s.entities('vehicle');vid=vehicles[0]['id'];cid=self.s.entities('charger')[0]['id']
        for n in range(count):
            self.s.put('session',dict(id='report-'+str(n),port=cid+':1',vehicle_id=vid,started_at=1794236400+n*3600,
                ended_at=1794238200+n*3600,energy_kwh=10.125,peak_kw=320,mode='ocpp',quality='measured'))
        return vid,cid

    def test_pdf_uses_full_filtered_history_and_totals_not_last100_cap(self):
        vid,cid=self.seed(105)
        data=report_data(self.s,vehicle_id=vid,charger_id=cid)
        self.assertEqual(len(data['sessions']),105);self.assertEqual(data['total_kwh'],105*10.125)
        filtered=report_data(self.s,start='2026-11-09T15:00:00Z',end='2026-11-09T16:00:00Z',vehicle_id=vid)
        self.assertEqual(len(filtered['sessions']),1)
        response=self.c.get('/api/reports/sessions.pdf',params={'vehicle_id':vid,'charger_id':cid})
        self.assertEqual(response.status_code,200);self.assertEqual(response.headers['content-type'],'application/pdf')
        self.assertIn(b'/Count 9 ',response.content);self.assertTrue(response.content.startswith(b'%PDF-1.4'))
        self.assertIn('Baixar relatório PDF',self.c.get('/ui/history').text)
        if shutil.which('pdftotext'):
            with tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'report.pdf';path.write_bytes(response.content)
                result=subprocess.run(['pdftotext',str(path),'-'],capture_output=True,text=True,check=True)
            self.assertIn('RELATÓRIO DE RECARGAS',result.stdout);self.assertIn('1.063,125',result.stdout);self.assertIn('Página 9/9',result.stdout)

    def test_filters_bad_dates_empty_pdf_and_access(self):
        for query in [dict(start='bad'),dict(start='2026-12-01',end='2026-11-01'),dict(vehicle_id='absent')]:
            self.assertEqual(self.c.get('/api/reports/sessions.pdf',params=query).status_code,422)
        self.assertEqual(self.c.get('/api/reports/sessions.pdf').status_code,200)
        self.c.post('/api/logout',json={})
        self.assertEqual(self.c.get('/api/reports/sessions.pdf').status_code,401)

    def test_banner_escaped_and_delivered_in_live_update(self):
        self.e.subscription.receive(envelope(self.s,message='<script>bad</script>'),TOKEN)
        page=self.c.get('/ui/overview').text
        self.assertIn('10 dia(s)',page);self.assertIn('&lt;script&gt;bad&lt;/script&gt;',page)
        data=self.c.get('/ui-data/monitor').json();self.assertIn('subscription_nodes',data)
        self.assertIn('Assinatura pendente',json.dumps(data['subscription_nodes'],ensure_ascii=False))

if __name__=='__main__':unittest.main()
