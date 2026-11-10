import asyncio
import copy
import json
import os
import time
import unittest
from unittest.mock import patch
from app.store import Store
from app.engine import Engine
from app.telemetry import plant_snapshot, state_signature, export_record
from app.plant_view import render_plant
from app.services import cloud_loop
from tools.plant_demo import fixture


class TelemetryTests(unittest.TestCase):
    def test_identity_freshness_and_alarms_are_independent(self):
        state=fixture();p=plant_snapshot(state)
        self.assertEqual(len(p['chargers']),5)
        self.assertTrue(p['chargers'][1]['connectors'][0]['alarm'])
        self.assertFalse(p['chargers'][2]['online'])
        self.assertIsNone(p['chargers'][2]['connectors'][0]['power_kw'])
        self.assertEqual(p['chargers'][0]['connectors'][0]['vehicle_name'],'BYD Dolphin · Frota 07')
        state['ports'][0]['vehicle_id']=None
        self.assertIsNone(plant_snapshot(state)['chargers'][0]['connectors'][0]['vehicle_name'])
        state['time']+=20
        self.assertIsNone(plant_snapshot(state)['chargers'][0]['connectors'][0]['power_kw'])
        self.assertFalse(plant_snapshot(state)['meter']['fresh'])

    def test_status_signature_ignores_power_but_tracks_new_charger_and_cable(self):
        state=fixture();before=state_signature(plant_snapshot(state))
        state['ports'][0]['power_kw']=12
        self.assertEqual(before,state_signature(plant_snapshot(state)))
        state['ports'][0]['connected']=False
        self.assertNotEqual(before,state_signature(plant_snapshot(state)))
        state=fixture();state['chargers'].append(dict(id='new',name='Novo',max_kw=100,enabled=True,online=False))
        self.assertNotEqual(before,state_signature(plant_snapshot(state)))

    def test_export_has_no_account_secrets_and_output_escapes_html(self):
        record=dict(id='a'*32,ts=1,kind='user_saved',payload={'password':'private','device_token':'private'})
        self.assertEqual(export_record(record)['payload'],{})
        state=fixture();state['chargers'][0]['password_hash']='private';state['chargers'][0]['name']='<script>alert(1)</script>'
        state['vehicles'][0]['name']='<img onerror=alert(1)>'
        self.assertNotIn('private',json.dumps(plant_snapshot(state)))
        document=render_plant(state)
        self.assertNotIn('<script>',document);self.assertNotIn('<img onerror',document)
        self.assertIn('class="plant-charger alarm"',document)
        self.assertIn('class="plant-charger idle offline"',document)

    def test_only_latest_snapshot_coalesces_and_ack_cannot_remove_replacement(self):
        store=Store(':memory:')
        event=store.record('connected',{'port':'test:1'})
        store.queue_plant({'observed_at':1});old=store.pending()[0]['id']
        store.queue_plant({'observed_at':2});store.acknowledge([old])
        self.assertEqual(store.pending_count(),2)
        self.assertEqual(store.pending()[0]['payload']['observed_at'],2)
        self.assertEqual(store.pending()[1]['id'],event)
        store.db.close()


class CloudDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_event_sent_within_seconds_and_ack_required(self):
        store=Store(':memory:');engine=Engine(store)
        cfg=store.settings();cfg['demo_cloud_url']='https://example.test/ingest';store.save_settings(cfg)
        calls=[];valid=False
        class Response:
            def raise_for_status(self): pass
            def json(self): return {'acknowledged_ids':[r['id'] for r in calls[-1]['records']]} if valid else {'acknowledged_ids':['not-sent']}
        class Client:
            def __init__(self,**kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self,*args): pass
            async def post(self,url,**kwargs): calls.append(kwargs['json']);return Response()
        with patch.dict(os.environ,{'EV_DEMO_CLOUD_TOKEN':'test-token-for-unit-tests-only'}),patch('app.services.httpx.AsyncClient',Client):
            task=asyncio.create_task(cloud_loop(engine))
            try:
                await asyncio.sleep(.05)
                self.assertGreater(store.pending_count(),0)
                valid=True
                event=store.record('connected',{'port':'test:1'})
                await asyncio.sleep(2.2)
                self.assertTrue(any(any(r['id']==event for r in c['records']) for c in calls))
                self.assertNotIn(event,[r['id'] for r in store.pending()])
                self.assertEqual(engine.cloud['status'],'Sincronizado')
            finally:
                task.cancel()
                try: await task
                except asyncio.CancelledError: pass
                store.db.close()

class AlarmTests(unittest.IsolatedAsyncioTestCase):
    async def test_ocpp_station_alarm_is_retained_until_station_clear(self):
        from app.ocpp_server import Station
        store=Store(':memory:')
        cfg=store.settings();cfg['mode']='physical';store.save_settings(cfg)
        store.put('charger',dict(id='CP',name='Teste',connectors=2,transport='ocpp',enabled=True,max_kw=320))
        engine=Engine(store);engine.connections['CP']=object()
        station=Station('CP',object(),engine)
        await station.status(0,'GroundFailure','Faulted')
        await station.status(1,'NoError','Available')
        data=plant_snapshot(engine.snapshot())
        self.assertTrue(all(p['alarm'] for p in data['chargers'][0]['connectors']))
        self.assertEqual(data['chargers'][0]['connectors'][0]['error_code'],'GroundFailure')
        await station.status(0,'NoError','Available')
        self.assertFalse(any(p['alarm'] for p in plant_snapshot(engine.snapshot())['chargers'][0]['connectors']))
        store.db.close()

class BacklogTests(unittest.TestCase):
    def test_new_session_and_current_state_bypass_old_minute_backlog(self):
        store=Store(':memory:')
        for i in range(250):store.record('minute',{'source':'site','minute_utc':i*60,'avg_kw':1},'site')
        session=store.record('session_start',{'id':'session','port':'CP:1'})
        store.queue_plant({'observed_at':time.time()})
        batch=store.pending()
        self.assertEqual(batch[0]['kind'],'plant_state')
        self.assertEqual(batch[1]['id'],session)
        self.assertEqual(len(batch),200)
        store.acknowledge([r['id'] for r in batch])
        self.assertEqual(store.pending_count(),52)
        store.db.close()


class DisplayStateTests(unittest.TestCase):
    def test_four_states_and_separate_communication(self):
        state=fixture();p=plant_snapshot(state)
        self.assertEqual([c['connectors'][0]['display_state'] for c in p['chargers']],[2,3,0,0,1])
        self.assertFalse(p['chargers'][2]['online'])
        self.assertTrue(p['chargers'][3]['online'])
        state['ports'][0]['power_kw']=0
        state['ports'][0]['manual_pause']=True
        self.assertEqual(plant_snapshot(state)['chargers'][0]['connectors'][0]['display_state'],1)
        state['ports'][0]['power_kw']=200
        state['time']+=20
        self.assertEqual(plant_snapshot(state)['chargers'][0]['connectors'][0]['display_state'],1)
