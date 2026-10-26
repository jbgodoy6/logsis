import asyncio
from datetime import datetime, timezone
import random
import time
import unittest

from app.control import Demand, admission_ready, allocate, blocked_at
from app.engine import Engine
from app.store import Store


class AllocationTests(unittest.TestCase):
    def test_priority_320kw_on_large_site(self):
        ds = [Demand('vip', 320, 6, 'a', 'main', True), Demand('regular', 320, 6, 'b', 'main')]
        result = allocate(ds, 550, {'a': 320, 'b': 320}, {'main': 1000})
        self.assertAlmostEqual(result['vip'], 320)
        self.assertAlmostEqual(result['regular'], 230)

    def test_two_minimums_do_not_fit(self):
        ds = [Demand('first', 60, 6, 'a', 'main', arrival=1), Demand('second', 60, 6, 'b', 'main', arrival=2)]
        r = allocate(ds, 8, {'a': 60, 'b': 60}, {'main': 1000})
        self.assertEqual(r, {'first': 8, 'second': 0})

    def test_shared_charger_and_circuit(self):
        ds = [Demand('a1', 320, 6, 'a', 'main'), Demand('a2', 320, 6, 'a', 'main'),
              Demand('b', 320, 6, 'b', 'main')]
        r = allocate(ds, 1000, {'a': 320, 'b': 320}, {'main': 450})
        self.assertLessEqual(r['a1'] + r['a2'], 320.001)
        self.assertLessEqual(sum(r.values()), 450.001)

    def test_sixty_chargers_above_one_megawatt(self):
        ds = [Demand(str(i), 320, 6, str(i), 'main') for i in range(60)]
        r = allocate(ds, 15000, {str(i): 320 for i in range(60)}, {'main': 20000})
        self.assertEqual(len([v for v in r.values() if v > 0]), 60)
        self.assertAlmostEqual(sum(r.values()), 15000, places=2)

    def test_randomized_budget_and_minimum_invariants(self):
        rng = random.Random(16)
        for _ in range(200):
            n = rng.randint(1, 60)
            ds = [Demand(str(i), rng.choice([22, 60, 180, 320, 500]), rng.choice([0, 6, 10]), str(i // 2), str(i % 3), bool(i % 5 == 0), i) for i in range(n)]
            chargers = {d.charger: 400 for d in ds}
            circuits = {str(i): rng.uniform(100, 1000) for i in range(3)}
            budget = rng.uniform(0, 5000)
            r = allocate(ds, budget, chargers, circuits)
            self.assertLessEqual(sum(r.values()), budget + .01)
            for d in ds:
                self.assertTrue(r[d.key] == 0 or d.minimum - .001 <= r[d.key] <= d.maximum + .001)
            for key, limit in chargers.items():
                self.assertLessEqual(sum(r[d.key] for d in ds if d.charger == key), limit + .01)
            for key, limit in circuits.items():
                self.assertLessEqual(sum(r[d.key] for d in ds if d.circuit == key), limit + .01)

    def test_command_acceptance_does_not_confirm_decrease(self):
        now = time.time()
        p = {'key': 'a', 'running': True, 'power_kw': 60, 'limit_kw': 40, 'sample_at': now, 'reduction_at': now - 1}
        self.assertFalse(admission_ready([p], {'a': 40}, now, 15))
        p.update(power_kw=40, sample_at=now-2)
        self.assertFalse(admission_ready([p], {'a': 40}, now, 15))
        p['sample_at'] = now
        self.assertTrue(admission_ready([p], {'a': 40}, now, 15))
        p['limit_kw'] = 60
        self.assertFalse(admission_ready([p], {'a': 40}, now, 15))

    def test_overnight_schedule_and_timezone(self):
        rules = [{'days': [0], 'start': '22:00', 'end': '06:00'}]
        # Monday 23:00 and Tuesday 05:00 in São Paulo.
        self.assertTrue(blocked_at(datetime(2026, 10, 27, 2, tzinfo=timezone.utc), rules, 'America/Sao_Paulo'))
        self.assertTrue(blocked_at(datetime(2026, 10, 27, 8, tzinfo=timezone.utc), rules, 'America/Sao_Paulo'))
        self.assertFalse(blocked_at(datetime(2026, 10, 27, 9, tzinfo=timezone.utc), rules, 'America/Sao_Paulo'))


class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = Store(':memory:')
        for i in ('a', 'b'):
            self.store.put('charger', {'id': i, 'name': i, 'transport': 'simulator', 'max_kw': 320,
                                      'connector_max_kw': 320, 'min_kw': 6, 'connectors': 1,
                                      'circuit': 'principal', 'enabled': True, 'commissioned': True,
                                      'input_factor': 1.0})
        self.engine = Engine(self.store)

    async def asyncTearDown(self):
        self.store.db.close()

    async def tick(self, n=1):
        for _ in range(n):
            self.engine.last_tick -= 1
            await self.engine.tick()

    async def test_new_vehicle_waits_for_confirmed_decrease(self):
        e = self.engine
        e.other_kw = 400
        e.connect_simulated('a:1')
        await self.tick(40)
        self.assertAlmostEqual(e.ports['a:1']['power_kw'], 320, places=1)
        e.connect_simulated('b:1')
        await self.tick()
        self.assertFalse(e.ports['b:1']['running'])
        self.assertAlmostEqual(e.ports['a:1']['limit_kw'], 275, places=1)
        await self.tick(40)
        self.assertTrue(e.ports['b:1']['running'])
        self.assertLessEqual(e.meter['total_kw'], 950.1)

    async def test_customer_load_increase_reduces_existing_sessions(self):
        e = self.engine
        e.connect_simulated('a:1');e.connect_simulated('b:1')
        await self.tick(40)
        e.other_kw = 850
        await self.tick(3)
        self.assertLessEqual(sum(p['power_kw'] for p in e.ports.values()), 100.1)

    async def test_blocked_new_arrival_waits_emergency_and_disconnect_clear(self):
        settings = self.store.settings()
        settings['schedules'] = [{'days': list(range(7)), 'start': '00:00', 'end': '23:59'}, {'days': list(range(7)), 'start': '23:59', 'end': '00:00'}]
        self.store.save_settings(settings)
        e = self.engine;e.connect_simulated('a:1')
        await self.tick(3)
        self.assertFalse(e.ports['a:1']['running'])
        self.assertEqual(e.ports['a:1']['limit_kw'], 0)
        e.ports['a:1']['emergency_until'] = time.time() + 60
        await self.tick(3)
        self.assertTrue(e.ports['a:1']['running'])
        e.disconnect('a:1')
        self.assertEqual(e.ports['a:1']['emergency_until'], 0)

    async def test_missing_meter_stops_new_admission(self):
        settings = self.store.settings();settings['mode'] = 'physical';self.store.save_settings(settings)
        self.engine.connect_simulated('a:1')
        await self.tick(2)
        self.assertFalse(self.engine.ports['a:1']['running'])
        self.assertEqual(self.engine.summary['budget_kw'], 0)

    async def test_energy_counter_reset_does_not_make_negative_energy(self):
        e = self.engine;e.connect_simulated('a:1');await self.tick(3)
        p = e.ports['a:1']
        e.telemetry(p, energy_kwh=10)
        before = self.store.entities('session')[0]['energy_kwh']
        e.telemetry(p, energy_kwh=0)
        self.assertEqual(self.store.entities('session')[0]['energy_kwh'], before)
        self.assertTrue(any(r['kind'] == 'meter_reset' for r in self.store.history()['events']))

    async def test_minimum_larger_than_ramp_can_start(self):
        c = self.store.entities('charger')[0];c['min_kw'] = 60;self.store.put('charger', c)
        self.engine.connect_simulated('a:1');await self.tick(3)
        self.assertTrue(self.engine.ports['a:1']['running'])

    async def test_assisted_zero_test_keeps_session_and_resumes(self):
        e = self.engine;e.connect_simulated('a:1');await self.tick(5)
        p = e.ports['a:1'];session = p['session_id']
        p['test'] = {'cap_kw': 0, 'started_at': time.time(), 'until': time.time() + 30, 'observations': []}
        await self.tick(3)
        self.assertEqual(p['power_kw'], 0)
        self.assertEqual(p['session_id'], session)
        p['test']['until'] = time.time() - 1
        await self.tick(3)
        self.assertGreater(p['power_kw'], 0)
        self.assertEqual(len(self.store.entities('learning')), 1)

    async def test_blocked_existing_session_zero_then_safe_return(self):
        e = self.engine;e.connect_simulated('a:1');await self.tick(5)
        settings = self.store.settings();settings['schedules'] = [{'days': list(range(7)), 'start': '00:00', 'end': '23:59'}, {'days': list(range(7)), 'start': '23:59', 'end': '00:00'}]
        self.store.save_settings(settings)
        await self.tick(3)
        self.assertEqual(e.ports['a:1']['power_kw'], 0)
        settings['schedules'] = [];self.store.save_settings(settings)
        await self.tick(3)
        self.assertGreater(e.ports['a:1']['power_kw'], 0)

    async def test_reduction_requires_updated_site_meter(self):
        e = self.engine;e.connect_simulated('a:1');await self.tick(5)
        p = e.ports['a:1'];p['reduction_at'] = time.time() + 30
        before = p['limit_kw']
        await self.tick()
        self.assertEqual(p['limit_kw'], before)


class ProtocolProfileTests(unittest.IsolatedAsyncioTestCase):
    async def test_active_limits_use_transaction_profile(self):
        from app.ocpp_server import Station
        from unittest.mock import AsyncMock
        from types import SimpleNamespace
        store = Store(':memory:')
        store.put('charger', {'id': 'a', 'connectors': 1, 'transport': 'ocpp', 'rate_unit': 'W'})
        engine = Engine(store)
        station = Station('a', None, engine)
        station.call = AsyncMock(return_value=SimpleNamespace(status='Accepted'))
        p = engine.ports['a:1'];p['transaction_id'] = 123
        self.assertTrue(await station.limit(1, 40))
        call = station.call.call_args.args[0]
        self.assertEqual(call.cs_charging_profiles['chargingProfilePurpose'], 'TxProfile')
        self.assertEqual(call.cs_charging_profiles['transactionId'], 123)
        self.assertEqual(call.cs_charging_profiles['chargingSchedule']['chargingSchedulePeriod'][0]['limit'], 40000)
        store.db.close()

    async def test_modbus_tcp_register_decode(self):
        import struct
        from app.services import read_modbus_power
        async def reply(reader, writer):
            request = await reader.readexactly(12)
            tid = request[:2]
            writer.write(tid + struct.pack('>HHB', 0, 7, 1) + bytes([3, 4]) + struct.pack('>f', 1234.5))
            await writer.drain();writer.close();await writer.wait_closed()
        server = await asyncio.start_server(reply, '127.0.0.1', 0)
        async with server:
            port = server.sockets[0].getsockname()[1]
            value = await read_modbus_power({'host': '127.0.0.1', 'port': port, 'unit': 1, 'address': 0,
                                              'type': 'float32', 'word_order': 'big', 'scale': 1})
            self.assertAlmostEqual(value, 1234.5)


if __name__ == '__main__':
    unittest.main()
