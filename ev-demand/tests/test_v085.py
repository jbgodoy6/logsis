import asyncio
import copy
import json
import os
import time
import unittest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
import httpx
from fastapi.testclient import TestClient
from app.meter import DEFAULT_METER, Meter, normalize_meter
from app.telemetry import plant_snapshot
from app.store import Store, password_matches
from app.access import Access
from app.directory import synchronize, directory_loop
from recovery_helpers import create_test_app as create_app
from tools.plant_demo import fixture
from platform_service.server import create_platform
from test_access import FakeSheet
from recovery_helpers import recover_root
from test_server_ui import Forms
import hashlib


class NewConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.app=create_app(':memory:',background=False)
        self.c=TestClient(self.app)
        self.c.post('/api/setup',json={'admin_password':'test-v085-admin'})
        recover_root(self.c)

    def tearDown(self):self.c.close();self.app.state.store.db.close()

    def test_serial_port_and_test_draft_do_not_lose_slash(self):
        m=copy.deepcopy(DEFAULT_METER);m.update(transport='rtu',serial_port=' dev/ttyUSB0 ')
        self.assertEqual(Meter.model_validate(m).serial_port,'/dev/ttyUSB0')
        self.assertEqual(normalize_meter(m)['serial_port'],'/dev/ttyUSB0')
        for name in ['COM7','/dev/serial/by-id/usb-FT232R']:
            m['serial_port']=name;self.assertEqual(Meter.model_validate(m).serial_port,name)
        port=SimpleNamespace(device='/dev/ttyUSB0',description='FT232R USB UART')
        with patch('serial.tools.list_ports.comports',return_value=[port]):
            page=self.c.get('/ui/meter')
            self.assertIn('select name="serial_port"',page.text)
            self.assertIn('/dev/ttyUSB0',page.text)
            form=Forms(page.text).find('meter');form.update(transport='rtu',serial_port='/dev/ttyUSB0',operation='test')
            with patch('app.main.read_meter',new=AsyncMock(return_value=[])) as read:
                response=self.c.post('/ui/post',data=form)
            self.assertEqual(read.call_args.args[0]['serial_port'],'/dev/ttyUSB0')
            self.assertEqual(Forms(response.text).find('meter')['serial_port'],'/dev/ttyUSB0')
            self.assertEqual(self.app.state.store.settings()['meter']['serial_port'],'')
            form.pop('operation');response=self.c.post('/ui/post',data=form)
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(self.app.state.store.settings()['meter']['serial_port'],'/dev/ttyUSB0')

    def test_only_enabled_readings_in_both_live_views(self):
        state=fixture();m=copy.deepcopy(DEFAULT_METER)
        for reg in m['registers']:reg['enabled']=reg['measurement'] in ['power_total_kw','voltage_l1_v','current_l1_a']
        state['settings']['meter']=m
        data=plant_snapshot(state)
        self.assertEqual([r['measurement'] for r in data['meter']['readings']],['power_total_kw','current_l1_a','voltage_l1_v'])
        store=self.app.state.store;s=store.settings();s['meter']=m;store.save_settings(s)
        self.app.state.engine.meter=state['meter']
        for page in ['monitor','overview']:
            response=self.c.get('/ui-data/'+page)
            text=json.dumps(response.json(),ensure_ascii=False)
            self.assertIn('Tensão L1',text);self.assertIn('Corrente L1',text)
            self.assertNotIn('Frequência',text);self.assertNotIn('Energia ativa importada',text)

    def test_delete_simulator_preserves_history_and_hides_it(self):
        self.c.post('/api/demo',json={});e=self.app.state.engine
        target=e.snapshot()['chargers'][0]['id'];port=next(p for p in e.ports.values() if p['charger']==target)
        e.start_session(port);session=port['session_id']
        self.assertEqual(self.c.delete('/api/chargers/'+target).status_code,200)
        self.assertTrue(self.app.state.store.get('session',session)['ended_at'])
        self.assertNotIn(target,[c['id'] for c in e.snapshot()['chargers']])
        self.assertTrue(e.config(target)['archived'])

    def test_mode_switch_closes_simulated_sessions_and_separates_catalog(self):
        self.c.post('/api/demo',json={});s=self.app.state.store.settings()
        s.update(mode='physical');s['meter']['host']='192.0.2.10'
        self.assertEqual(self.c.put('/api/settings',json=s).status_code,200)
        state=self.app.state.engine.snapshot()
        self.assertEqual(state['chargers'],[]);self.assertEqual(len(state['inactive_chargers']),3)
        self.assertFalse(any(p['connected'] for p in self.app.state.engine.ports.values()))
        self.assertIn('Carregadores de outro modo',self.c.get('/ui/chargers').text)

    def test_physical_deletion_refuses_active_or_online_equipment(self):
        response=self.c.post('/api/chargers',json=dict(id='PHYS',name='Real',transport='ocpp',max_kw=320,connector_max_kw=320,password='fixture-charger-password'))
        self.assertEqual(response.status_code,200,response.text)
        engine=self.app.state.engine;port=engine.ports['PHYS:1']
        engine.connections['PHYS']=object()
        self.assertEqual(self.c.delete('/api/chargers/PHYS').status_code,409)
        engine.connections.clear();port['connected']=True
        self.assertEqual(self.c.delete('/api/chargers/PHYS').status_code,409)
        port['connected']=False
        self.assertEqual(self.c.delete('/api/chargers/PHYS').status_code,200)
        self.assertEqual(self.c.post('/api/ports/PHYS:1/action',json={'action':'pause'}).status_code,404)

    def test_demo_can_be_recreated_without_overwriting_archived_identifiers(self):
        self.c.post('/api/demo',json={})
        old={c['id'] for c in self.app.state.engine.snapshot()['chargers']}
        for identifier in old:self.assertEqual(self.c.delete('/api/chargers/'+identifier).status_code,200)
        self.assertEqual(self.c.post('/api/demo',json={}).status_code,200)
        new={c['id'] for c in self.app.state.engine.snapshot()['chargers']}
        self.assertFalse(old & new)


class ImmediateDirectoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store=Store(':memory:');self.access=Access(self.store)
        self.access.configure({'url':'https://directory.example','interval_s':300,'enabled':True})
        self.actor={'role':'root','name':'root','id':'fixture-root'}

    async def asyncTearDown(self):self.store.db.close()

    async def test_queue_wakes_background_loop_without_waiting_for_interval(self):
        calls=0;sent=asyncio.Event()
        async def sync(access):
            nonlocal calls
            calls+=1
            if access.pending():sent.set()
            return True
        with patch('app.directory.synchronize',sync):
            task=asyncio.create_task(directory_loop(self.access))
            try:
                await asyncio.sleep(.05)
                self.access.create(self.actor,'tec.fast','Técnico','technician')
                await asyncio.wait_for(sent.wait(),2)
                self.assertGreaterEqual(calls,2)
            finally:
                task.cancel()
                try:await task
                except asyncio.CancelledError:pass

    async def test_edit_during_registration_survives_ack_and_failed_snapshot(self):
        identity=self.store.entities('system')[0]['controller_id'];token='fixture-device-token'
        platform=create_platform(':memory:',sheet=FakeSheet(),device_tokens={identity:hashlib.sha256(token.encode()).hexdigest()})
        account=self.access.create(self.actor,'tec.concurrent','Técnico','technician')
        edited=False;fail_snapshot=True
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=platform),base_url='https://directory.example') as remote:
            async def handle(request):
                nonlocal edited
                if request.method=='POST':
                    response=await remote.post('/v1/technicians/update',headers=request.headers,json=json.loads(request.content))
                    if not edited:
                        edited=True
                        self.access.change_password(self.access.public(self.access.by_id(account['id'])),'12345678','fixture-concurrent-new-password')
                    return httpx.Response(response.status_code,json=response.json())
                if fail_snapshot:return httpx.Response(503,json={})
                response=await remote.get('/v1/technicians/snapshot',headers=request.headers)
                return httpx.Response(response.status_code,json=response.json())
            async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
                with patch.dict(os.environ,{'DMAX_DIRECTORY_TOKEN':token}):
                    self.assertFalse(await synchronize(self.access,client))
                    self.assertTrue(self.access.pending()[0]['payload'].get('_acknowledged_base'))
                    self.access=Access(self.store)  # Reload the durable queue after a service restart.
                    fail_snapshot=False
                    self.assertTrue(await synchronize(self.access,client))
                    self.assertTrue(await synchronize(self.access,client))
        self.assertFalse(self.access.pending())
        self.assertTrue(password_matches('fixture-concurrent-new-password',platform.state.accounts.by_id(account['id'])['password']))
        platform.state.store.db.close()

class ControlTopologyTests(unittest.IsolatedAsyncioTestCase):
    async def test_addition_during_ocpp_reduction_waits_until_next_control_cycle(self):
        from app.engine import Engine
        from app.main import Charger
        store=Store(':memory:');cfg=store.settings();cfg['mode']='physical';store.save_settings(cfg)
        def charger(identifier):
            return Charger(id=identifier,name=identifier,transport='ocpp',max_kw=320,connector_max_kw=320,
                           commissioned=True,zero_supported=True).model_dump(exclude={'password'})
        store.put('charger',charger('CP1'));engine=Engine(store)
        port=engine.ports['CP1:1'];now=time.time()
        port.update(connected=True,running=True,power_kw=200,limit_kw=320,sample_at=now,ocpp_status='Charging',profile_initialized=True)
        engine.meter.update(total_kw=1000,at=now)
        requested=asyncio.Event();ack=asyncio.Event()
        class Station:
            async def limit(self,connector,kw):requested.set();await ack.wait();return True
        engine.connections['CP1']=Station()
        task=asyncio.create_task(engine.tick())
        try:
            await asyncio.wait_for(requested.wait(),2)
            store.put('charger',charger('CP2'));engine.refresh()
            ack.set();await asyncio.wait_for(task,2)
            self.assertEqual(engine.ports['CP2:1']['limit_kw'],0)
            self.assertEqual(engine.ports['CP2:1']['start_pending_at'],0)
            self.assertFalse(engine.fault)
        finally:
            task.cancel();store.db.close()
