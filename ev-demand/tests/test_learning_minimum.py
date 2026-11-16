import json
import tempfile
import time
import unittest
from pathlib import Path
from app.engine import Engine
from app.store import Store
from app.learning import context,key,effective_minimum,electrical_floor
from app.ocpp_server import Station


class MinimumLearningTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(str(Path(self.temp.name)/'fixture.sqlite3'))
        self.c=dict(id='DC',name='DC',model='fixture',transport='ocpp',charge_type='DC',rate_unit='W',voltage=400,phases=1,max_kw=22,connector_max_kw=22,min_kw=6,connectors=2,circuit='principal',enabled=True,commissioned=True,zero_supported=True,input_factor=1)
        self.store.put('charger',self.c);self.engine=Engine(self.store);self.p=self.engine.ports['DC:1']
        self.p.update(running=True,connected=True,session_id='S1',vehicle_id='V1',ocpp_status='Charging',limit_kw=6)

    def tearDown(self):self.store.db.close();self.temp.cleanup()

    def candidate(self,cap,**changes):
        self.store.put('charger',self.c)
        now=time.time()
        test=dict(cap_kw=cap,started_at=now-40,accepted_at=now-30,until=now,seconds=30,context=context(self.c,self.p),session_id='S1',vehicle_id='V1',observations=[{'at':now-age,'kw':cap,'valid':True,'amps':self.p.get('accepted_profile_current_a')} for age in (20,10,1)])
        test.update(changes);self.p['test']=test;return now

    def test_remembers_tested_setpoint_not_lowest_measurement_and_survives_restart(self):
        now=self.candidate(1);self.p['test']['observations'][0]['kw']=.9;self.engine.finish_learning(self.p,now)
        self.assertEqual(self.store.get('minimum',key(self.p))['minimum_kw'],1)
        self.store.db.close();self.store=Store(str(Path(self.temp.name)/'fixture.sqlite3'))
        restarted=Engine(self.store);p=restarted.ports['DC:1'];p['vehicle_id']='V1'
        self.assertEqual(effective_minimum(self.store,self.c,p),(1,1))
        p['vehicle_id']='V2';self.assertEqual(effective_minimum(self.store,self.c,p),(6,None))
        self.assertEqual(effective_minimum(self.store,self.c,restarted.ports['DC:2']),(6,None))
        self.c['model']='another';self.assertEqual(effective_minimum(self.store,self.c,self.p),(6,None))

    def test_inconclusive_zero_rejected_taper_stale_and_interrupted_do_not_replace(self):
        self.engine.finish_learning(self.p,self.candidate(1))
        for change in [{'accepted_at':None},{'interrupted':True},{'observations':[{'at':time.time()-1,'kw':.1,'valid':True}]*3}]:
            self.engine.finish_learning(self.p,self.candidate(.5,**change));self.assertEqual(self.store.get('minimum',key(self.p))['minimum_kw'],1)
        self.engine.finish_learning(self.p,self.candidate(0));self.assertEqual(self.store.get('minimum',key(self.p))['minimum_kw'],1)
        now=self.candidate(.5);self.p['test']['observations'][-1]['at']=now-60;self.engine.finish_learning(self.p,now)
        self.assertEqual(self.store.get('minimum',key(self.p))['minimum_kw'],1)

    def test_ac_six_amps_and_dc_no_universal_six_amp_floor(self):
        self.c.update(charge_type='AC',voltage=230,phases=3);self.assertAlmostEqual(electrical_floor(self.c),4.14)
        self.engine.finish_learning(self.p,self.candidate(4));self.assertIsNone(self.store.get('minimum',key(self.p)))
        self.engine.finish_learning(self.p,self.candidate(4.14));self.assertAlmostEqual(effective_minimum(self.store,self.c,self.p)[0],4.14)

    def test_dc_amp_profile_uses_live_output_voltage_not_three_ac_phases(self):
        self.c.update(rate_unit='A',voltage=230,phases=3);self.store.put('charger',self.c);station=Station('DC',None,self.engine)
        with self.assertRaises(ValueError):station.profile(1,1)
        self.p.update(voltage_v=400,voltage_at=time.time())
        self.assertEqual(station.profile(1,1)['chargingSchedule']['chargingSchedulePeriod'][0]['limit'],2.5)
        self.p['voltage_v']=800;self.assertEqual(station.profile(1,1)['chargingSchedule']['chargingSchedulePeriod'][0]['limit'],1.2)
        self.p['voltage_at']=0
        with self.assertRaises(ValueError):station.profile(1,1)

    def test_dc_amp_memory_reserves_more_power_when_output_voltage_rises(self):
        self.c['rate_unit']='A';self.p.update(voltage_v=400,voltage_at=time.time(),accepted_profile_current_a=2.5)
        self.engine.finish_learning(self.p,self.candidate(1));self.p['voltage_v']=800
        self.assertEqual(effective_minimum(self.store,self.c,self.p)[0],2)

    def test_dc_voltage_changes_update_authorized_power_for_next_control_tick(self):
        self.c['rate_unit']='A';self.store.put('charger',self.c);self.p['accepted_profile_current_a']=2.5
        self.engine.telemetry(self.p,voltage_v=400);self.assertEqual(self.p['limit_kw'],1)
        self.engine.telemetry(self.p,voltage_v=800);self.assertEqual(self.p['limit_kw'],2)

    def test_disconnect_cancels_test_without_teaching_next_vehicle(self):
        self.c['transport']='simulator';self.store.put('charger',self.c);self.candidate(1)
        self.engine.disconnect(self.p['key']);self.assertNotIn('test',self.p);self.assertIsNone(self.store.get('minimum',key(self.p)))


class LearnedAllocationTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejected_known_minimum_is_retained_for_audit_but_requires_revalidation(self):
        fixture=MinimumLearningTests();fixture.setUp()
        try:
            fixture.engine.finish_learning(fixture.p,fixture.candidate(1))
            class CP:
                async def limit(self,connector,value):return False
            fixture.engine.connections['DC']=CP()
            self.assertFalse(await fixture.engine.set_limit(fixture.p,1))
            self.assertTrue(fixture.store.get('minimum',key(fixture.p))['needs_revalidation'])
            self.assertEqual(effective_minimum(fixture.store,fixture.c,fixture.p),(6,None))
        finally:fixture.tearDown()

    async def test_demand_reduction_uses_learned_minimum_and_never_allocates_below_it(self):
        fixture=MinimumLearningTests();fixture.setUp()
        try:
            store,c,e,p=fixture.store,fixture.c,fixture.engine,fixture.p
            e.finish_learning(p,fixture.candidate(1))
            settings=store.settings();settings.update(mode='physical',limit_kw=10,margin_kw=0)
            with store.db:store.db.execute('UPDATE settings SET payload=?',(json.dumps(settings),))
            class CP:
                async def limit(self,connector,value):return True
            e.connections['DC']=CP();p.update(power_kw=6,sample_at=time.time(),profile_initialized=True)
            e.meter.update(total_kw=14.5,at=time.time(),error='');await e.tick()
            self.assertAlmostEqual(p['target_kw'],1.5);self.assertAlmostEqual(p['limit_kw'],1.5)
            settings['limit_kw']=9
            with store.db:store.db.execute('UPDATE settings SET payload=?',(json.dumps(settings),))
            p['last_command_at']=0;await e.tick();self.assertEqual(p['target_kw'],0)
        finally:fixture.tearDown()
