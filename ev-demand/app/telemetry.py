"""Explicit, credential-free cloud contract shared with the local plant view."""
import json
import math
import re
import time


MEASUREMENTS = {
    'power_total_kw': ('Potência ativa total', 'kW'),
    'energy_import_kwh': ('Energia ativa importada', 'kWh'),
    'current_l1_a': ('Corrente L1', 'A'), 'current_l2_a': ('Corrente L2', 'A'),
    'current_l3_a': ('Corrente L3', 'A'), 'voltage_l1_v': ('Tensão L1–N', 'V'),
    'voltage_l2_v': ('Tensão L2–N', 'V'), 'voltage_l3_v': ('Tensão L3–N', 'V'),
    'frequency_hz': ('Frequência', 'Hz'), 'power_factor': ('Fator de potência', ''),
    'power_l1_kw': ('Potência ativa L1', 'kW'), 'power_l2_kw': ('Potência ativa L2', 'kW'),
    'power_l3_kw': ('Potência ativa L3', 'kW'),
}

DEFAULT_COLORS = {'charging': '#239b75', 'connected': '#338bd1', 'alarm': '#dc4c58',
                  'disconnected': '#8395a8', 'communication': '#c59138'}


def display_colors(value=None):
    value = value if isinstance(value, dict) else {}
    return {key: color.lower() if isinstance(color := value.get(key), str) and re.fullmatch(r'#[0-9a-fA-F]{6}', color)
            else default for key, default in DEFAULT_COLORS.items()}


def finite(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def plant_snapshot(state):
    now = state.get('time', time.time())
    settings = state['settings']
    vehicles = {v['id']: v for v in state['vehicles']}
    sessions = {s['id']: s for s in state.get('sessions', [])}
    chargers = []
    for charger in state['chargers']:
        ports = []
        for port in state['ports']:
            if port['charger'] != charger['id']:
                continue
            online = charger.get('online', False)
            fresh = online and 0 <= now - port.get('sample_at', 0) <= settings['freshness_s']
            error = port.get('station_error_code') if port.get('station_alarm') else port.get('error_code', 'NoError')
            error = error or 'NoError'
            alarm = port.get('station_alarm', False) or port.get('ocpp_status') == 'Faulted' or error not in ('', 'NoError', None)
            vehicle = vehicles.get(port.get('vehicle_id'), {})
            plugged = bool(port.get('connected'))
            status = ('Alarme' if alarm else 'Offline' if not online else 'Em recarga' if port.get('running')
                      else 'Pausado / aguardando' if plugged else 'Disponível')
            if plugged and online and not alarm and port.get('status') not in (None, 'Disponível'):
                status = port['status']
            if alarm and error == 'NoError':
                error = 'Faulted'
            charging = bool(online and plugged and port.get('running') and fresh and not alarm
                            and (finite(port.get('power_kw')) or 0) > 0.1)
            display_state = 3 if alarm else 0 if not online else 2 if charging else 1 if plugged else 0
            session = sessions.get(port.get('session_id'), {})
            ports.append(dict(id=port['key'], connector=port['connector'], online=online,
                plugged=plugged, charging=charging, display_state=display_state, running=bool(port.get('running')), alarm=alarm, error_code=error,
                status=status, ocpp_status=port.get('ocpp_status', ''), power_kw=finite(port.get('power_kw')) if fresh else None,
                telemetry_fresh=fresh, sample_at=port.get('sample_at', 0), limit_kw=None if port.get('native_mode') else finite(port.get('limit_kw')),
                vehicle_id=vehicle.get('id'), vehicle_name=vehicle.get('name') if plugged else None,
                session_id=port.get('session_id'), energy_kwh=finite(session.get('energy_kwh')),
                soc=finite(port.get('soc')) if plugged and fresh else None))
        chargers.append(dict(id=charger['id'], name=charger['name'], max_kw=charger['max_kw'],
            enabled=charger['enabled'], online=charger.get('online', False), connectors=ports))
    meter = state['meter']
    meter_fresh = bool(meter.get('at') and 0 <= now - meter['at'] <= settings['freshness_s'] and not meter.get('error'))
    received = {reading['measurement']: reading for reading in meter.get('readings', [])}
    mapping = settings.get('meter', {}).get('registers')
    enabled = [reg['measurement'] for reg in mapping if reg['enabled']] if mapping is not None else list(received) or ['power_total_kw']
    readings = []
    for measurement in enabled:
        reading = received.get(measurement, {})
        label, unit = MEASUREMENTS[measurement]
        value = reading.get('value')
        if not reading and measurement == 'power_total_kw' and (mapping is None or settings.get('mode') == 'simulation'):
            value = meter.get('total_kw')
        valid = meter_fresh and not reading.get('error') and finite(value) is not None
        readings.append(dict(measurement=measurement, label=label, unit=unit,
            value=finite(value) if valid else None, error=not valid,
            at=reading.get('at', meter.get('at', 0))))
    summary = state.get('summary', {})
    return dict(schema_version=1, observed_at=now, site_name=settings['site_name'], mode=settings['mode'],
        limit_kw=settings['limit_kw'], margin_kw=settings['margin_kw'], controller_fault=bool(state.get('fault')),
        ev_kw=finite(summary.get('ev_kw')), other_kw=finite(summary.get('other_kw')),
        meter=dict(fresh=meter_fresh, sampled_at=meter.get('at', 0), readings=readings), chargers=chargers)


def state_signature(payload):
    # Power, energy and timestamps are sampled once/minute, state transitions wake the sender.
    return json.dumps(dict(site=payload['site_name'], mode=payload['mode'], limit=payload['limit_kw'],
        margin=payload['margin_kw'], fault=payload['controller_fault'], meter=payload['meter']['fresh'],
        readings=[(r['measurement'], r['unit']) for r in payload['meter']['readings']],
        chargers=[dict(c, connectors=[{k: v for k, v in port.items() if k not in
            ('power_kw', 'sample_at', 'energy_kwh', 'soc', 'limit_kw')} for port in c['connectors']])
            for c in payload['chargers']]), sort_keys=True, ensure_ascii=False)


# Audit records about accounts/settings are intentionally never exported verbatim.
FIELDS = {
    'minute': ('minute_utc', 'source', 'avg_kw', 'min_kw', 'max_kw', 'samples', 'energy_kwh'),
    'session_start': ('id', 'port', 'vehicle_id', 'started_at', 'mode'),
    'session_end': ('id', 'port', 'vehicle_id', 'started_at', 'ended_at', 'energy_kwh', 'peak_kw', 'reason'),
    'connected': ('port', 'vehicle', 'mode'), 'disconnected': ('port',),
    'ocpp_status': ('port', 'status', 'error'), 'ocpp_connected': ('charger',), 'ocpp_disconnected': ('charger',), 'ocpp_boot': ('charger', 'vendor', 'model', 'firmware'),
    'limit_changed': ('port', 'from_kw', 'to_kw'),
    'reconciliation_required': ('port',), 'session_reconciled': ('port', 'transaction'),
}


def export_record(record):
    payload = record['payload']
    if record['kind'] == 'plant_state':
        return record
    fields = FIELDS.get(record['kind'], ())
    # Preserve audit locally; acknowledge an opaque placeholder in the cloud, not its sensitive contents.
    return dict(record, kind=record['kind'] if fields else 'local_audit',
                payload={key: payload[key] for key in fields if key in payload})
