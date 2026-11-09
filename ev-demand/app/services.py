import asyncio
from datetime import datetime, timezone
import os
import secrets
import struct
import time

import httpx
from .meter import read_meter, read_modbus_power
from .telemetry import plant_snapshot, state_signature, export_record


async def meter_loop(engine):
    import math
    while True:
        settings = engine.store.settings()
        meter = settings['meter']
        configured = meter['host'] if meter['transport'] == 'tcp' else meter['serial_port']
        if settings['mode'] == 'physical' and configured:
            try:
                async with engine.meter_io_lock:
                    readings = await read_meter(meter)
                if engine.store.settings()['meter'] != meter:
                    continue
                engine.meter['readings'] = readings
                power = next((r for r in readings if r['measurement'] == 'power_total_kw'), None)
                energy = next((r for r in readings if r['measurement'] == 'energy_import_kwh' and not r['error']), None)
                if not power or power['error']:
                    raise ValueError(power['error'] if power else 'Potência total não configurada')
                delta = None
                if energy:
                    old = engine.meter.get('energy_kwh')
                    if old is not None and energy['value'] < old:
                        engine.store.record('site_meter_reset', {'previous_kwh': old, 'new_kwh': energy['value']})
                    delta = max(0.0, energy['value'] - old) if old is not None else 0.0
                    engine.meter['energy_kwh'] = energy['value']
                engine.meter.update(total_kw=max(0.0, power['value']), at=power['at'], error='')
                engine.aggregate('site', power['value'], delta)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                engine.meter.update(error=str(exc)[:160], at=0)
        await asyncio.sleep(max(0.5, meter['poll_s']))


async def cloud_loop(engine):
    signature, sampled, next_send, next_cleanup = None, 0.0, 0.0, 0.0
    failures = 0
    while True:
        now = time.monotonic()
        settings = engine.store.settings()
        url, token = settings['cloud_url'], os.getenv('EV_CLOUD_TOKEN')
        if now >= next_cleanup:
            engine.store.cleanup()
            next_cleanup = now + 60
        if url and token:
            plant = plant_snapshot(engine.snapshot())
            changed = state_signature(plant)
            if changed != signature or now - sampled >= 60:
                engine.store.queue_plant(plant)
                signature, sampled = changed, now
            if now >= next_send:
                records = engine.store.pending()
                if records:
                    try:
                        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                            response = await client.post(url, headers={'Authorization': f'Bearer {token}'},
                                json={'controller_id': os.getenv('EV_CONTROLLER_ID') or engine.store.entities('system')[0]['controller_id'],
                                      'records': [export_record(record) for record in records]})
                            response.raise_for_status()
                            ids = response.json()['acknowledged_ids']
                            sent = {r['id'] for r in records}
                            if not isinstance(ids, list) or any(not isinstance(i, str) or i not in sent for i in ids):
                                raise ValueError('Confirmação inválida do servidor')
                            if not ids:
                                raise ValueError('Servidor não confirmou os registros')
                            engine.store.acknowledge(ids)
                        failures = 0
                        engine.cloud.update(status='Sincronizado' if not engine.store.pending_count() else 'Enviando histórico pendente', last_sync=time.time())
                        next_send = time.monotonic() + 1
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        failures += 1
                        engine.cloud['status'] = 'Sem confirmação de envio; dados preservados'
                        next_send = time.monotonic() + min(60, 2 ** min(failures, 6))
        else:
            engine.cloud['status'] = 'Pendente: configurar EV_CLOUD_TOKEN' if url else 'Não configurada'
            signature = None
        await asyncio.sleep(1)
