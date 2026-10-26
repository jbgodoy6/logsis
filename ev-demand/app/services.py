import asyncio
from datetime import datetime, timezone
import os
import secrets
import struct
import time

import httpx
from .meter import read_meter, read_modbus_power


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
    while True:
        settings = engine.store.settings()
        url = settings['cloud_url']
        token = os.getenv('EV_CLOUD_TOKEN')
        if url:
            if not token:
                engine.cloud['status'] = 'Pendente: configurar EV_CLOUD_TOKEN'
            else:
                try:
                    records = engine.store.pending()
                    if records:
                        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                            response = await client.post(url, headers={'Authorization': f'Bearer {token}'},
                                                         json={'controller_id': os.getenv('EV_CONTROLLER_ID') or engine.store.entities('system')[0]['controller_id'],
                                                               'records': records})
                            response.raise_for_status()
                            ids = response.json()['acknowledged_ids']
                            sent = {r['id'] for r in records}
                            if not isinstance(ids, list) or any(not isinstance(i, str) or i not in sent for i in ids):
                                raise ValueError('Confirmação inválida do servidor')
                            engine.store.acknowledge(ids)
                    engine.cloud.update(status='Sincronizado' if not engine.store.pending_count() else 'Enviando histórico pendente', last_sync=time.time())
                except asyncio.CancelledError:
                    raise
                except Exception:
                    # URL/token/server output must never leak through diagnostics.
                    engine.cloud['status'] = 'Sem confirmação de envio; dados preservados'
        engine.store.cleanup()
        await asyncio.sleep(60)
