"""Opt-in integration tests against an isolated PostgreSQL 16 demo container."""
import json
import os
import secrets
import subprocess
import time
import unittest
from tools.plant_demo import fixture
from app.telemetry import plant_snapshot


@unittest.skipUnless(os.getenv('DMAX_TEST_POSTGRES_CONTAINER'),'requires isolated PostgreSQL container')
class PostgresContractTests(unittest.TestCase):
    def sql(self,query,ok=True):
        env=dict(os.environ)
        for key in ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'):env.pop(key,None)
        r=subprocess.run(['docker','--host=unix:///var/run/docker.sock','exec','-i',os.environ['DMAX_TEST_POSTGRES_CONTAINER'],
            'psql','-U','postgres','-d','dmax','-At','-v','ON_ERROR_STOP=1'],input=query,text=True,capture_output=True,env=env)
        if ok:self.assertEqual(r.returncode,0,r.stderr)
        else:self.assertNotEqual(r.returncode,0)
        return r.stdout.strip()

    def setUp(self):
        self.cid='test-'+secrets.token_hex(6);self.token=secrets.token_urlsafe(32)
        self.sql("insert into dmax.controllers(id,site_name,token_hash) values ('"+self.cid+"','Test',encode(sha256(convert_to('"+self.token+"','UTF8')),'hex'));")

    def tearDown(self):
        for table in ['events','minutes','chargers','controllers']:
            self.sql('delete from dmax.'+table+" where "+('id' if table=='controllers' else 'controller_id')+"='"+self.cid+"';")

    def ingest(self,records,token=None,ok=True):
        return self.sql("set role service_role; select public.dmax_ingest('"+self.cid+"','"+(token or self.token)+"',$payload$"+json.dumps(records)+"$payload$::jsonb);",ok)

    def record(self,kind,payload):return dict(id=secrets.token_hex(16),ts=time.time(),kind=kind,payload=payload)

    def test_catalog_offline_new_charger_stale_data_and_replay(self):
        state=plant_snapshot(fixture())
        # The new dashboard remains compatible with unmodified 0.8.0 payloads.
        for charger in state['chargers']:
            for port in charger['connectors']:
                port.pop('charging',None);port.pop('display_state',None)
        record=self.record('plant_state',state)
        self.ingest([record]);self.ingest([record])
        self.assertEqual(self.sql("select count(*) from dmax.v_ports where controller_id='"+self.cid+"';"),'5')
        self.assertEqual(self.sql("select string_agg(equipment_state::text,',' order by charger_id) from dmax.v_ports where controller_id='"+self.cid+"';"),'2,3,0,0,1')
        self.assertEqual(self.sql("select status from dmax.v_ports where controller_id='"+self.cid+"' and charger_id='EC-03';"),'Offline')
        self.assertEqual(self.sql("select communication_label from dmax.v_ports where controller_id='"+self.cid+"' and charger_id='EC-03';"),'Sem comunicação OCPP')
        newer=json.loads(json.dumps(state));newer['observed_at']+=1
        extra=json.loads(json.dumps(newer['chargers'][0]));extra['id']='EC-06';extra['name']='Novo'
        extra['connectors'][0].update(id='EC-06:1',connector=1)
        newer['chargers'].append(extra)
        self.ingest([self.record('plant_state',newer)])
        self.ingest([record])
        self.assertEqual(self.sql("select count(*) from dmax.v_ports where controller_id='"+self.cid+"';"),'6')
        self.sql("update dmax.controllers set last_contact_at=now()-interval '10 minutes' where id='"+self.cid+"';")
        self.assertEqual(self.sql("select count(*) from dmax.v_ports where controller_id='"+self.cid+"' and power_kw is not null;"),'0')
        self.assertEqual(self.sql("select bool_and(communication_label='Controlador sem comunicação com a nuvem') from dmax.v_ports where controller_id='"+self.cid+"';"),'t')

    def test_auth_revocation_readonly_and_minute_idempotence(self):
        r=self.record('minute',dict(source='site',minute_utc=int(time.time()//60)*60,avg_kw=700,min_kw=650,max_kw=800,energy_kwh=1))
        self.ingest([r],token='x'*43,ok=False)
        self.sql("set role anon; select public.dmax_ingest('"+self.cid+"','"+self.token+"','[]'::jsonb);",ok=False)
        self.ingest([r]);self.ingest([r])
        self.assertEqual(self.sql("select count(*) from dmax.minutes where controller_id='"+self.cid+"';"),'1')
        self.sql("set role dmax_viewer; select token_hash from dmax.controllers;",ok=False)
        self.sql("set role dmax_viewer; delete from dmax.minutes;",ok=False)
        self.sql('set role dmax_viewer; select * from dmax.v_sites;')
        self.sql("update dmax.controllers set enabled=false where id='"+self.cid+"';")
        self.ingest([r],ok=False)
        self.assertEqual(self.sql("select count(*) from dmax.v_sites where controller_id='"+self.cid+"';"),'1')

    def test_invalid_batch_is_atomic(self):
        r=self.record('minute',dict(source='site',minute_utc=int(time.time()//60)*60,avg_kw=700))
        bad=self.record('unknown_kind',{})
        self.ingest([r,bad],ok=False)
        self.assertEqual(self.sql("select count(*) from dmax.minutes where controller_id='"+self.cid+"';"),'0')
