"""A real WebSocket client validates profiles, remote start and measurement-gated admission."""
import asyncio
import base64
from contextlib import suppress
from datetime import datetime, timezone
import socket
import time
import unittest

import uvicorn
from websockets.asyncio.client import connect
from ocpp.routing import on
from ocpp.v16 import ChargePoint, call, call_result
from ocpp.v16.enums import Action

from app.main import create_app
from app.store import password_hash


class FakeCharger(ChargePoint):
    def __init__(self, identifier, ws):
        super().__init__(identifier, ws, response_timeout=4)
        self.limit_kw = 0
        self.running = False
        self.energy = 0.0
        self.actions = []
        self.tasks = []

    @on(Action.set_charging_profile)
    async def profile(self, connector_id, cs_charging_profiles, **kwargs):
        self.limit_kw = float(cs_charging_profiles['charging_schedule']['charging_schedule_period'][0]['limit']) / 1000
        self.actions.append(('limit', self.limit_kw, time.time()))
        return call_result.SetChargingProfile(status='Accepted')

    @on(Action.remote_start_transaction)
    async def remote(self, id_tag, connector_id, charging_profile, **kwargs):
        self.actions.append(('start', self.limit_kw, time.time()))
        async def start():
            await asyncio.sleep(.05)
            result = await self.call(call.StartTransaction(connector_id=1, id_tag=id_tag,
                                        meter_start=round(self.energy * 1000), timestamp=datetime.now(timezone.utc).isoformat()))
            self.running = result.id_tag_info['status'] == 'Accepted'
            self.transaction = result.transaction_id
        self.tasks.append(asyncio.create_task(start()))
        return call_result.RemoteStartTransaction(status='Accepted')

    async def measurements(self):
        while True:
            if self.running:
                self.energy += self.limit_kw * .2 / 3600
                await self.call(call.MeterValues(connector_id=1, transaction_id=self.transaction, meter_value=[{
                    'timestamp': datetime.now(timezone.utc).isoformat(), 'sampledValue': [
                        {'value': str(self.limit_kw * 1000), 'measurand': 'Power.Active.Import', 'unit': 'W'},
                        {'value': str(self.energy * 1000), 'measurand': 'Energy.Active.Import.Register', 'unit': 'Wh'}]}]))
            await asyncio.sleep(.2)


class OCPPFlowTest(unittest.IsolatedAsyncioTestCase):
    async def test_real_remote_start_and_reduction_before_second_start(self):
        app = create_app(':memory:', background=False)
        store, engine = app.state.store, app.state.engine
        settings = store.settings()
        settings.update(mode='physical', limit_kw=500, margin_kw=20, ramp_kw_s=10000)
        store.save_settings(settings)
        credential = 'fixture-ocpp-only'
        for identifier in ('a', 'b'):
            store.put('charger', {'id': identifier, 'name': identifier, 'connectors': 1, 'transport': 'ocpp',
                                  'max_kw': 320, 'connector_max_kw': 320, 'min_kw': 6, 'circuit': 'principal',
                                  'enabled': True, 'commissioned': True, 'zero_supported': True, 'rate_unit': 'W',
                                  'input_factor': 1, 'password_hash': password_hash(credential)})
        engine.refresh()
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0));sock.setblocking(False)
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level='critical', lifespan='off', ws='websockets'))
        server_task = asyncio.create_task(server.serve(sockets=[sock]))
        tasks = []
        clients = []

        async def wait_for(predicate, timeout=15):
            async with asyncio.timeout(timeout):
                while not predicate():
                    await asyncio.sleep(.05)

        async def controller():
            while True:
                engine.meter.update(total_kw=100 + sum(c.limit_kw for c in clients if c.running), at=time.time())
                await engine.tick()
                await asyncio.sleep(.2)

        try:
            await wait_for(lambda: server.started)
            async with connect(f'ws://127.0.0.1:{port}/ocpp/a', subprotocols=['ocpp1.6'], additional_headers={
                'Authorization': 'Basic ' + base64.b64encode(('a:' + credential).encode()).decode()}) as ws_a:
                a = FakeCharger('a', ws_a);clients.append(a)
                tasks.extend([asyncio.create_task(a.start()), asyncio.create_task(a.measurements()), asyncio.create_task(controller())])
                await a.call(call.BootNotification(charge_point_vendor='Test', charge_point_model='320kW'))
                await a.call(call.StatusNotification(connector_id=1, error_code='NoError', status='Preparing'))
                await wait_for(lambda: a.running and a.limit_kw >= 319)
                async with connect(f'ws://127.0.0.1:{port}/ocpp/b', subprotocols=['ocpp1.6'], additional_headers={
                    'Authorization': 'Basic ' + base64.b64encode(('b:' + credential).encode()).decode()}) as ws_b:
                    b = FakeCharger('b', ws_b);clients.append(b)
                    tasks.extend([asyncio.create_task(b.start()), asyncio.create_task(b.measurements())])
                    await b.call(call.BootNotification(charge_point_vendor='Test', charge_point_model='320kW'))
                    await b.call(call.StatusNotification(connector_id=1, error_code='NoError', status='Preparing'))
                    try:
                        await wait_for(lambda: b.running)
                    except TimeoutError:
                        self.fail(str({'a_actions': a.actions, 'b_actions': b.actions,
                                       'ports': list(engine.ports.values()),
                                       'events': store.history()['events'][:8],
                                       'tasks': [str(t.exception()) for t in tasks if t.done() and not t.cancelled()]}))
                    starts = [x for x in b.actions if x[0] == 'start']
                    decreases = [x for x in a.actions if x[0] == 'limit' and x[1] <= 190.01 and x[1] > 0]
                    self.assertTrue(decreases)
                    self.assertLess(decreases[-1][2], starts[0][2])
                    self.assertLessEqual(a.limit_kw + b.limit_kw, 380.1)
                    self.assertTrue(engine.ports['a:1']['session_id'])
                    self.assertTrue(engine.ports['b:1']['session_id'])
        finally:
            for c in clients:
                tasks.extend(c.tasks)
            for task in tasks:
                task.cancel()
            for task in tasks:
                with suppress(asyncio.CancelledError, Exception):
                    await task
            server.should_exit = True
            await server_task
            store.db.close()
