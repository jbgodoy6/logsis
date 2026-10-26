import asyncio
from datetime import datetime, timezone
import os
import secrets
import struct
import time

import httpx


async def read_modbus_power(config):
    """Read a documented 0-based holding register; no meter-specific address is assumed."""
    count = 1 if config['type'] in ('uint16', 'int16') else 2
    transaction = secrets.randbelow(65536)
    request = struct.pack('>HHHBBHH', transaction, 0, 6, config['unit'], 3, config['address'], count)
    reader, writer = await asyncio.wait_for(asyncio.open_connection(config['host'], config['port']), 3)
    try:
        writer.write(request)
        await writer.drain()
        header = await asyncio.wait_for(reader.readexactly(7), 3)
        tid, protocol, length, unit = struct.unpack('>HHHB', header)
        if tid != transaction or protocol != 0 or unit != config['unit'] or not 3 <= length <= 254:
            raise ValueError('Resposta Modbus inválida')
        payload = await asyncio.wait_for(reader.readexactly(length - 1), 3)
        if payload[0] != 3 or payload[1] != count * 2 or len(payload) != count * 2 + 2:
            raise ValueError('Exceção ou tamanho Modbus inválido')
        raw = payload[2:]
        if count == 2 and config['word_order'] == 'little':
            raw = raw[2:] + raw[:2]
        formats = {'float32': '>f', 'int32': '>i', 'uint32': '>I', 'int16': '>h', 'uint16': '>H'}
        return struct.unpack(formats[config['type']], raw)[0] * config['scale']
    finally:
        writer.close()
        await writer.wait_closed()


async def meter_loop(engine):
    import math
    while True:
        settings = engine.store.settings()
        meter = settings['meter']
        if settings['mode'] == 'physical' and meter['host']:
            try:
                value = await read_modbus_power(meter)
                if not math.isfinite(value):
                    raise ValueError('Leitura não finita')
                engine.meter.update(total_kw=max(0.0, value), at=time.time(), error='')
                engine.aggregate('site', value)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                engine.meter['error'] = str(exc)[:160]
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
