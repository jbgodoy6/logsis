import asyncio
from datetime import datetime, timezone
import math
import time
import uuid

from .control import Demand, admission_ready, allocate, blocked_at


class Engine:
    def __init__(self, store):
        self.store = store
        self.ports = {}
        self.connections = {}
        self.meter = {'total_kw': 0.0, 'at': 0.0, 'error': '', 'readings': [], 'energy_kwh': None}
        self.meter_io_lock = asyncio.Lock()
        self.other_kw = 400.0
        self.cloud = {'status': 'Não configurada', 'last_sync': None}
        self.trace = []
        self.bucket = {}
        self.bucket_minute = int(time.time() // 60)
        self.last_tick = time.time()
        self.fault = ''
        self.refresh()
        # Never restore stale telemetry or authorization after reboot.
        for session in self.store.entities('session'):
            if not session.get('ended_at'):
                session.update(ended_at=time.time(), reason='Reinício: conferir estado físico', quality='interrupted')
                self.store.put('session', session)
                self.store.record('session_recovery', session)

    def refresh(self):
        for charger in self.store.entities('charger'):
            for number in range(1, charger['connectors'] + 1):
                key = f"{charger['id']}:{number}"
                if key not in self.ports:
                    self.ports[key] = {
                        'key': key, 'charger': charger['id'], 'connector': number,
                        'connected': False, 'running': False, 'power_kw': 0.0,
                        'limit_kw': 0.0, 'target_kw': 0.0, 'sample_at': 0.0,
                        'reduction_at': 0.0, 'arrival': 0.0, 'status': 'Disponível',
                        'vehicle_id': None, 'session_id': None, 'emergency_until': 0,
                        'manual_pause': False, 'transaction_id': None,
                        'ocpp_status': 'Unavailable', 'meter_kwh': None,
                        'identifier': None, 'start_pending_at': 0.0,
                        'last_command_at': 0.0, 'last_telemetry_at': 0.0,
                        'profile_initialized': charger['transport'] == 'simulator',
                    }

    def config(self, charger_id):
        return next((c for c in self.store.entities('charger') if c['id'] == charger_id), None)

    def identify(self, p, identifier):
        p['identifier'] = identifier
        vehicle = next((v for v in self.store.entities('vehicle') if identifier in v.get('identifiers', [])), None)
        p['vehicle_id'] = vehicle['id'] if vehicle else None
        if identifier and not identifier.startswith('EVSYS-'):
            known = {x['id']: x for x in self.store.entities('identifier')}
            item = known.get(identifier, {'id': identifier, 'first_seen': time.time()})
            item.update(last_seen=time.time(), charger=p['charger'], vehicle_id=p['vehicle_id'],
                        source='simulation' if self.config(p['charger'])['transport'] == 'simulator' else 'OCPP idTag — origem a confirmar')
            self.store.put('identifier', item)

    def connect_simulated(self, key, vehicle_id=None, acceptance_kw=None):
        p = self.ports[key]
        c = self.config(p['charger'])
        if c['transport'] != 'simulator':
            raise ValueError('Esta ação é exclusiva do simulador')
        if p['connected']:
            raise ValueError('Conector já ocupado')
        p.update(connected=True, arrival=time.time(), manual_pause=False, emergency_until=0,
                 acceptance_kw=acceptance_kw or c['max_kw'], meter_kwh=0.0)
        vehicle = next((v for v in self.store.entities('vehicle') if v['id'] == vehicle_id), None)
        self.identify(p, vehicle['identifiers'][0] if vehicle and vehicle.get('identifiers') else None)
        p['vehicle_id'] = vehicle_id
        self.store.record('connected', {'port': key, 'vehicle': vehicle_id, 'mode': 'simulation'})

    def finish(self, p, reason):
        if p.get('session_id'):
            sessions = {s['id']: s for s in self.store.entities('session')}
            session = sessions.get(p['session_id'])
            if session:
                session.update(ended_at=time.time(), reason=reason)
                self.store.put('session', session)
                self.store.record('session_end', session)
        p.update(running=False, session_id=None, transaction_id=None, limit_kw=0.0, target_kw=0.0)

    def disconnect(self, key):
        p = self.ports[key]
        self.finish(p, 'Veículo desconectado')
        p.update(connected=False, vehicle_id=None, identifier=None, power_kw=0.0,
                 emergency_until=0, manual_pause=False, status='Disponível', start_pending_at=0.0)
        self.store.record('disconnected', {'port': key})

    def start_session(self, p, transaction_id=None):
        if p['session_id']:
            return
        session = {'id': uuid.uuid4().hex, 'port': p['key'], 'vehicle_id': p['vehicle_id'],
                   'started_at': time.time(), 'ended_at': None, 'energy_kwh': 0.0,
                   'meter_start_kwh': p['meter_kwh'], 'peak_kw': 0.0,
                   'mode': self.config(p['charger'])['transport'], 'quality': 'measured'}
        p.update(session_id=session['id'], running=True, transaction_id=transaction_id, start_pending_at=0.0)
        self.store.put('session', session)
        self.store.record('session_start', session)

    def telemetry(self, p, power_kw=None, energy_kwh=None, soc=None, sampled_at=None):
        now = time.time()
        if power_kw is not None and math.isfinite(power_kw) and power_kw >= 0:
            p.update(power_kw=power_kw, sample_at=sampled_at or now)
            if p.get('test') and p['sample_at'] > p['test']['started_at']:
                p['test']['observations'].append({'at': p['sample_at'], 'kw': power_kw})
        if soc is not None and math.isfinite(soc) and 0 <= soc <= 100:
            p['soc'] = soc
        delta = 0.0
        if energy_kwh is not None and math.isfinite(energy_kwh) and energy_kwh >= 0:
            old = p.get('meter_kwh')
            if old is not None:
                if energy_kwh >= old:
                    delta = energy_kwh - old
                else:
                    self.store.record('meter_reset', {'port': p['key'], 'previous_kwh': old, 'new_kwh': energy_kwh})
            p['meter_kwh'] = energy_kwh
        if p.get('session_id'):
            session = next((s for s in self.store.entities('session') if s['id'] == p['session_id']), None)
            if session:
                session['energy_kwh'] += delta
                session['peak_kw'] = max(session['peak_kw'], p['power_kw'])
                self.store.put('session', session)
        self.aggregate(p['key'], p['power_kw'], delta)

    def aggregate(self, source, power, energy_delta=None):
        b = self.bucket.setdefault(source, {'sum': 0.0, 'count': 0, 'min_kw': power, 'max_kw': power, 'energy_kwh': 0.0, 'energy_samples': 0})
        b['sum'] += power
        b['count'] += 1
        b['min_kw'] = min(b['min_kw'], power)
        b['max_kw'] = max(b['max_kw'], power)
        if energy_delta is not None:
            b['energy_kwh'] += energy_delta
            b['energy_samples'] += 1

    def flush(self):
        for source, b in self.bucket.items():
            self.store.record('minute', {'minute_utc': self.bucket_minute * 60, 'source': source,
                                        'avg_kw': b['sum'] / b['count'], 'min_kw': b['min_kw'],
                                        'max_kw': b['max_kw'], 'samples': b['count'],
                                        'energy_kwh': b['energy_kwh'] if b['energy_samples'] else None}, source)
        self.bucket.clear()
        self.bucket_minute = int(time.time() // 60)

    async def set_limit(self, p, value):
        value = round(max(0.0, value), 3)
        if abs(p['limit_kw'] - value) < 0.01 and p.get('profile_initialized', False):
            return True
        c = self.config(p['charger'])
        previous = p['limit_kw']
        if c['transport'] == 'ocpp':
            cp = self.connections.get(c['id'])
            if not cp or time.time() - p['last_command_at'] < 3:
                return False
            p['last_command_at'] = time.time()
            try:
                if not await cp.limit(p['connector'], value):
                    raise RuntimeError('Perfil rejeitado pelo carregador')
            except Exception as exc:
                self.store.record('command_failed', {'port': p['key'], 'command': 'SetChargingProfile', 'error': str(exc)[:200]})
                return False
        p['limit_kw'] = value
        p['profile_initialized'] = True
        if value < previous:
            p['reduction_at'] = time.time()
        self.store.record('limit_changed', {'port': p['key'], 'from_kw': previous, 'to_kw': value})
        return True

    async def tick(self):
        now = time.time()
        elapsed = min(max(now - self.last_tick, 0), 5)
        self.last_tick = now
        settings = self.store.settings()
        simulation = settings['mode'] == 'simulation'
        for p in self.ports.values():
            c = self.config(p['charger'])
            if p.get('test') and now >= p['test']['until']:
                test = p.pop('test')
                values = [x['kw'] for x in test['observations']]
                result = {'id': uuid.uuid4().hex, 'port': p['key'], 'cap_kw': test['cap_kw'],
                          'started_at': test['started_at'], 'samples': len(values),
                          'observed_min_kw': min(values) if values else None,
                          'observed_max_kw': max(values) if values else None,
                          'result': 'observado; validação manual necessária' if values else 'inconclusivo: sem medições',
                          'vehicle_id': p['vehicle_id']}
                self.store.put('learning', result)
                self.store.record('test_finished', result)
            if c['transport'] == 'simulator' and simulation:
                power = min(p['limit_kw'], p.get('acceptance_kw', c['max_kw'])) if p['running'] and p['connected'] else 0.0
                self.telemetry(p, power, (p.get('meter_kwh') or 0) + power * elapsed / 3600)
        if simulation:
            total = self.other_kw + sum(p['power_kw'] * self.config(p['charger']).get('input_factor', 1.0) for p in self.ports.values())
            self.meter.update(total_kw=total, at=now, error='')
            self.aggregate('site', total)
        fresh = bool(self.meter['at']) and now - self.meter['at'] <= settings['freshness_s']
        fresh = fresh and not self.fault
        # Subtract only contemporaneous EV measurements from the incoming meter.
        measured_ev = sum(p['power_kw'] for p in self.ports.values()
                          if now - p['sample_at'] <= settings['freshness_s'] and p['sample_at'])
        other = max(0.0, self.meter['total_kw'] - measured_ev)
        budget = max(0.0, settings['limit_kw'] - settings['margin_kw'] - other) if fresh else 0.0
        blocked = blocked_at(datetime.now(timezone.utc), settings['schedules'], settings['timezone'])
        chargers = {c['id']: c for c in self.store.entities('charger')}
        vehicles = {v['id']: v for v in self.store.entities('vehicle')}
        circuits = {c['id']: c['limit_kw'] for c in settings['circuits']}
        demands = []
        for p in self.ports.values():
            c = chargers[p['charger']]
            if not p['connected'] or not c['enabled'] or not c['commissioned'] or p['manual_pause']:
                continue
            if (c['transport'] == 'simulator') != simulation:
                continue
            if c['transport'] == 'ocpp' and (c['id'] not in self.connections or p['ocpp_status'] in ('Faulted', 'Unavailable', 'SuspendedEV')):
                continue
            emergency = p['emergency_until'] > now
            maximum = min(c['max_kw'], c['connector_max_kw'])
            minimum = c['min_kw']
            if blocked and not emergency:
                if not p['running'] or settings['blocked_policy'] != 'minimum':
                    maximum = 0
                else:
                    maximum = c['min_kw']
            if p.get('test'):
                maximum = min(maximum, p['test']['cap_kw'])
                minimum = min(minimum, maximum)
            if c['transport'] == 'simulator':
                maximum = min(maximum, p.get('acceptance_kw', maximum))
            if maximum > 0:
                vehicle = vehicles.get(p['vehicle_id'], {})
                factor = c.get('input_factor', 1.0)
                demands.append(Demand(p['key'], maximum * factor, minimum * factor, c['id'], c['circuit'],
                                      vehicle.get('priority', False), p['arrival']))
        inputs = allocate(demands, budget, {k: v['max_kw'] * v.get('input_factor', 1.0) for k, v in chargers.items()}, circuits)
        targets = {p['key']: inputs.get(p['key'], 0) / chargers[p['charger']].get('input_factor', 1.0)
                   for p in self.ports.values()}
        for p in self.ports.values():
            p['target_kw'] = targets.get(p['key'], 0.0)
        # Phase 1: all necessary decreases must be issued before any increase/start.
        reductions = [self.set_limit(p, p['target_kw']) for p in self.ports.values() if p['limit_kw'] > p['target_kw'] + 0.01]
        if reductions:
            await asyncio.gather(*reductions)
        initial_profiles = [self.set_limit(p, min(p['limit_kw'], p['target_kw'])) for p in self.ports.values()
                            if p['connected'] and not p['profile_initialized'] and p['charger'] in self.connections]
        if initial_profiles:
            await asyncio.gather(*initial_profiles)
        ready = fresh and admission_ready(list(self.ports.values()), targets, now, settings['freshness_s'])
        ready = ready and self.meter['at'] >= max((p['reduction_at'] for p in self.ports.values()), default=0)
        # Reserve increases against measured site headroom, shared chargers and circuits.
        # Current high authorizations are retained in reservations even if consumption is low.
        headroom = max(0.0, settings['limit_kw'] - settings['margin_kw'] - self.meter['total_kw'])
        for p in sorted(self.ports.values(), key=lambda q: (not vehicles.get(q['vehicle_id'], {}).get('priority', False), q['arrival'])):
            c = chargers[p['charger']]
            target = p['target_kw']
            if target > p['limit_kw'] + 0.01 and ready:
                factor = c.get('input_factor', 1.0)
                peers = [q for q in self.ports.values() if q['charger'] == p['charger'] and q['key'] != p['key']]
                circuit_peers = [q for q in self.ports.values() if chargers[q['charger']]['circuit'] == c['circuit'] and q['key'] != p['key']]
                minimum = min(c['min_kw'], p.get('test', {}).get('cap_kw', c['min_kw']))
                ramp = max(settings['ramp_kw_s'] * elapsed, minimum if not p['running'] else 0)
                delta = min(target - p['limit_kw'], headroom / factor, ramp,
                            max(0.0, c['max_kw'] - sum(q['limit_kw'] for q in peers) - p['limit_kw']),
                            max(0.0, circuits[c['circuit']] - sum(q['limit_kw'] * chargers[q['charger']].get('input_factor', 1.0)
                                                                for q in circuit_peers) - p['limit_kw'] * factor) / factor)
                value = p['limit_kw'] + delta
                if value + 0.001 >= minimum and delta > 0.01:
                    if await self.set_limit(p, value):
                        headroom -= delta * factor
            pending_input = sum(q['limit_kw'] * chargers[q['charger']].get('input_factor', 1.0)
                                for q in self.ports.values() if q['connected'] and not q['running'])
            current_settings = self.store.settings()
            start_headroom = self.meter['total_kw'] + pending_input <= current_settings['limit_kw'] - current_settings['margin_kw'] + 0.001
            if p['connected'] and not p['running'] and p['limit_kw'] > 0 and ready and start_headroom:
                if c['transport'] == 'simulator':
                    self.start_session(p)
                elif now - p['start_pending_at'] > 45:
                    # Only a real StartTransaction confirms session creation.
                    p['start_pending_at'] = now
                    cp = self.connections.get(c['id'])
                    if cp:
                        try:
                            await cp.remote_start(p)
                        except Exception as exc:
                            self.store.record('start_failed', {'port': p['key'], 'error': str(exc)[:200]})
            if not p['connected']:
                p['status'] = 'Disponível'
            elif not c['commissioned']:
                p['status'] = 'Aguardando comissionamento'
            elif not fresh:
                p['status'] = 'Proteção: medição indisponível'
            elif p['manual_pause']:
                p['status'] = 'Pausa manual'
            elif blocked and p['emergency_until'] <= now:
                p['status'] = 'Mínimo no horário bloqueado' if p['limit_kw'] > 0 else 'Aguardando horário permitido'
            elif target <= 0:
                p['status'] = 'Aguardando potência'
            elif p['power_kw'] > 0.1:
                p['status'] = 'Carregando'
            elif not ready:
                p['status'] = 'Confirmando redução dos demais'
            else:
                p['status'] = 'Preparando recarga'
        self.trace.append({'ts': now, 'total': self.meter['total_kw'], 'ev': measured_ev, 'limit': settings['limit_kw']})
        self.trace = self.trace[-180:]
        if int(now // 60) != self.bucket_minute:
            self.flush()
        self.summary = {'budget_kw': budget, 'other_kw': other, 'ev_kw': measured_ev,
                        'blocked': blocked, 'meter_fresh': fresh, 'total_kw': self.meter['total_kw']}

    def snapshot(self):
        chargers = [{k: v for k, v in c.items() if k != 'password_hash'} for c in self.store.entities('charger')]
        return {'settings': self.store.settings(), 'chargers': chargers, 'vehicles': self.store.entities('vehicle'),
                'identifiers': self.store.entities('identifier'), 'ports': list(self.ports.values()),
                'meter': self.meter, 'summary': getattr(self, 'summary', {}), 'trace': self.trace,
                'cloud': self.cloud | {'pending': self.store.pending_count()}, 'fault': self.fault,
                'time': time.time()}

    async def run(self):
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.fault = f'Falha no controle: {type(exc).__name__}'
                self.store.record('controller_fault', {'error': str(exc)[:300]})
            await asyncio.sleep(1)
