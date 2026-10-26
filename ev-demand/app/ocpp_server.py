"""OCPP 1.6J adapter. A physical unit must be explicitly commissioned before admission."""
import asyncio
from datetime import datetime, timezone
import logging
import time

from ocpp.routing import on
from ocpp.v16 import ChargePoint, call, call_result
from ocpp.v16.enums import Action
from .control import blocked_at

# Raw OCPP frames can contain authorization identifiers. Persist selected events instead.
logging.getLogger('ocpp').setLevel(logging.WARNING)


def utc():
    return datetime.now(timezone.utc).isoformat()


class Socket:
    def __init__(self, ws):
        self.ws = ws

    async def recv(self):
        return await self.ws.receive_text()

    async def send(self, message):
        await self.ws.send_text(message)


class Station(ChargePoint):
    def __init__(self, identifier, socket, engine):
        super().__init__(identifier, socket, response_timeout=10)
        self.engine = engine

    def port(self, number):
        return self.engine.ports.get(f'{self.id}:{number}')

    @on(Action.boot_notification)
    async def boot(self, charge_point_vendor, charge_point_model, **kwargs):
        for p in self.engine.ports.values():
            if p['charger'] == self.id:
                p.update(profile_initialized=False, sample_at=0, start_pending_at=0)
        self.engine.store.record('ocpp_boot', {'charger': self.id, 'vendor': charge_point_vendor,
                                             'model': charge_point_model, 'firmware': kwargs.get('firmware_version')})
        return call_result.BootNotification(current_time=utc(), interval=30, status='Accepted')

    @on(Action.heartbeat)
    async def heartbeat(self, **kwargs):
        return call_result.Heartbeat(current_time=utc())

    @on(Action.status_notification)
    async def status(self, connector_id, error_code, status, **kwargs):
        p = self.port(connector_id)
        if p:
            p['ocpp_status'] = status
            if status == 'Available':
                self.engine.disconnect(p['key'])
            elif status in ('Preparing', 'Charging', 'SuspendedEV', 'SuspendedEVSE'):
                if not p['connected']:
                    p.update(connected=True, arrival=time.time())
                if status == 'Charging' and not p['running']:
                    p['manual_pause'] = True
                    self.engine.store.record('reconciliation_required', {'port': p['key'], 'note': 'Sessão existente; aguardando MeterValues com transactionId'})
            self.engine.store.record('ocpp_status', {'port': p['key'], 'status': status, 'error': error_code})
        return call_result.StatusNotification()

    @on(Action.authorize)
    async def authorize(self, id_tag, **kwargs):
        # Autocharge identity alone is not permission to bypass the admission queue.
        # Bind only with an unambiguous pending connector. Authorize has no connectorId.
        candidates = [p for p in self.engine.ports.values() if p['charger'] == self.id
                      and p['connected'] and not p['running']]
        if len(candidates) == 1:
            self.engine.identify(candidates[0], id_tag)
        self.engine.store.record('authorization_observed', {'charger': self.id, 'identifier': id_tag,
                                                           'association': 'unambiguous' if len(candidates) == 1 else 'unknown'})
        reserved = [p for p in candidates if p['start_pending_at'] and time.time() - p['start_pending_at'] < 45
                    and p['limit_kw'] > 0 and id_tag == (p['identifier'] or ('EVSYS-' + self.id[:8] + '-' + str(p['connector']))[:20])]
        return call_result.Authorize(id_tag_info={'status': 'Accepted' if reserved else 'Blocked'})

    @on(Action.start_transaction)
    async def start_transaction(self, connector_id, id_tag, meter_start, timestamp, **kwargs):
        p = self.port(connector_id)
        transaction_id = time.time_ns() % 2_000_000_000
        if not p:
            return call_result.StartTransaction(transaction_id=transaction_id, id_tag_info={'status': 'Invalid'})
        settings = self.engine.store.settings()
        now = time.time()
        blocked = blocked_at(datetime.now(timezone.utc), settings['schedules'], settings['timezone'])
        allowed = bool(p['start_pending_at'] and now - p['start_pending_at'] < 45 and p['limit_kw'] > 0
                       and not p['manual_pause'] and self.engine.config(self.id)['enabled']
                       and self.engine.config(self.id)['commissioned']
                       and self.engine.meter['at'] and now - self.engine.meter['at'] <= settings['freshness_s']
                       and self.engine.meter['total_kw'] <= settings['limit_kw'] - settings['margin_kw'] + 0.001
                       and (not blocked or p['emergency_until'] > now))
        if not allowed:
            self.engine.store.record('unexpected_start', {'port': p['key'], 'action': 'rejected; inspect physical equipment'})
            # Run after sending the response, never await a call from inside an OCPP request handler.
            async def stop_unexpected():
                await asyncio.sleep(0.1)
                try:
                    await self.call(call.RemoteStopTransaction(transaction_id=transaction_id))
                except Exception:
                    pass
            asyncio.create_task(stop_unexpected())
            return call_result.StartTransaction(transaction_id=transaction_id, id_tag_info={'status': 'Blocked'})
        if not id_tag.startswith('EVSYS-'):
            self.engine.identify(p, id_tag)
        p['meter_kwh'] = meter_start / 1000
        p['connected'] = True
        self.engine.start_session(p, transaction_id)
        return call_result.StartTransaction(transaction_id=transaction_id, id_tag_info={'status': 'Accepted'})

    @on(Action.stop_transaction)
    async def stop_transaction(self, meter_stop, timestamp, transaction_id, **kwargs):
        p = next((p for p in self.engine.ports.values() if p['charger'] == self.id and p['transaction_id'] == transaction_id), None)
        if p:
            self.engine.telemetry(p, energy_kwh=meter_stop / 1000)
            self.engine.finish(p, kwargs.get('reason', 'Sessão encerrada pelo carregador'))
            # Do not immediately restart a completed session on the same cable connection.
            p['manual_pause'] = True
        return call_result.StopTransaction(id_tag_info={'status': 'Accepted'})

    @on(Action.meter_values)
    async def meter_values(self, connector_id, meter_value, **kwargs):
        p = self.port(connector_id)
        if p:
            transaction_id = kwargs.get('transaction_id')
            for item in meter_value:
                try:
                    sampled_at = datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00')).timestamp()
                except (ValueError, KeyError):
                    continue
                # Replayed/offline measurements must not confirm a real-time decrease.
                age = time.time() - sampled_at
                if age > self.engine.store.settings()['freshness_s'] or age < -5 or sampled_at <= p['last_telemetry_at']:
                    continue
                p['last_telemetry_at'] = sampled_at
                power = energy = soc = None
                phases = {}
                for value in item.get('sampled_value', []):
                    try:
                        number = float(value['value'])
                    except (ValueError, KeyError):
                        continue
                    measurand = value.get('measurand', 'Energy.Active.Import.Register')
                    unit = value.get('unit', 'Wh' if measurand.startswith('Energy') else 'W')
                    location = value.get('location', 'Outlet')
                    if measurand == 'Power.Active.Import':
                        converted = number if unit == 'kW' else number / 1000
                        if value.get('phase') in ('L1', 'L2', 'L3'):
                            phases[value['phase']] = converted
                        elif not value.get('phase'):
                            power = converted
                    elif measurand == 'Energy.Active.Import.Register' and not value.get('phase'):
                        energy = number if unit == 'kWh' else number / 1000
                    elif measurand == 'SoC':
                        soc = number
                if power is None and set(phases) == {'L1', 'L2', 'L3'}:
                    power = sum(phases.values())
                self.engine.telemetry(p, power, energy, soc, sampled_at=sampled_at)
                if transaction_id is not None and not p['running'] and p['connected']:
                    p['manual_pause'] = True
                    self.engine.start_session(p, transaction_id)
                    p['profile_initialized'] = False
                    self.engine.store.record('session_reconciled', {'port': p['key'], 'transaction': transaction_id,
                                                                   'note': 'Recuperada a partir de leitura atual; retomada manual necessária'})
        return call_result.MeterValues()

    @on(Action.data_transfer)
    async def data_transfer(self, vendor_id, **kwargs):
        self.engine.store.record('vendor_extension', {'charger': self.id, 'vendor': vendor_id,
                                                     'message': kwargs.get('message_id'),
                                                     'note': 'Integração específica ainda não homologada'})
        return call_result.DataTransfer(status='UnknownMessageId')

    def profile(self, connector, kw, purpose='TxDefaultProfile'):
        c = self.engine.config(self.id)
        if c['rate_unit'] == 'A':
            limit = kw * 1000 / (c['voltage'] * c['phases'])
        else:
            limit = kw * 1000
        schedule = {'startSchedule': utc(), 'chargingRateUnit': c['rate_unit'], 'chargingSchedulePeriod': [
            {'startPeriod': 0, 'limit': round(limit, 1)}]}
        return {'chargingProfileId': connector, 'stackLevel': 1,
                'chargingProfilePurpose': purpose, 'chargingProfileKind': 'Absolute',
                'chargingSchedule': schedule}

    async def limit(self, connector, kw):
        p = self.port(connector)
        active = p and p['transaction_id'] is not None
        profile = self.profile(connector, kw, 'TxProfile' if active else 'TxDefaultProfile')
        if active:
            profile['transactionId'] = p['transaction_id']
        response = await self.call(call.SetChargingProfile(connector_id=connector,
                                   cs_charging_profiles=profile))
        return response.status == 'Accepted'

    async def remote_start(self, p):
        identifier = p['identifier'] or ('EVSYS-' + self.id[:8] + '-' + str(p['connector']))[:20]
        result = await self.call(call.RemoteStartTransaction(connector_id=p['connector'], id_tag=identifier,
                                 charging_profile=self.profile(p['connector'], p['limit_kw'], 'TxProfile')))
        if result.status != 'Accepted':
            self.engine.store.record('start_rejected', {'port': p['key']})
