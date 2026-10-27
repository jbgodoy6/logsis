"""Authenticated global technician sync, independent of telemetry uploads."""
import asyncio
import os
import random
import time
from urllib.parse import urlsplit

import httpx


def validate_config(data):
    if set(data) != {'url', 'interval_s', 'enabled'} or type(data['enabled']) is not bool:
        raise ValueError('Configuração de plataforma inválida')
    if type(data['interval_s']) is not int or not 30 <= data['interval_s'] <= 86400:
        raise ValueError('Intervalo deve ficar entre 30 segundos e 24 horas')
    if data['url']:
        url = urlsplit(data['url'])
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError('Informe a URL HTTPS da plataforma, sem chave ou parâmetros')
        if url.hostname in ('docs.google.com','sheets.google.com'):
            raise ValueError('Cole a URL publicada do Apps Script, não o link de edição da planilha')
    if data['enabled'] and not data['url']:
        raise ValueError('Informe o endereço da plataforma')
    return data


async def synchronize(access, client=None):
    if access.lock is None:
        access.lock = asyncio.Lock()
    async with access.lock:
        config = access.config()
        if not config['enabled'] or not config['url']:
            access.status['message'] = 'Não configurada'
            return False
        token = access.device_token()
        if not token:
            access.status['message'] = 'Configure DMAX_DIRECTORY_TOKEN no equipamento'
            return False
        access.status['last_attempt'] = time.time()
        identity = access.store.entities('system')[0]['controller_id']
        headers = {'Authorization': 'Bearer ' + token, 'X-DMax-Controller': identity}
        own = client is None
        if own:
            client = httpx.AsyncClient(timeout=30, follow_redirects=False)
        try:
            base = config['url'].rstrip('/')
            async def request(action, payload=None):
                if urlsplit(base).hostname == 'script.google.com':
                    reply = await client.post(base, json={'action': action, 'controller_id': identity,
                                                         'key': token, **(payload or {})})
                    # Apps Script ContentService redirects to a Google-hosted result.
                    # Follow only GET 302/303 to this exact HTTPS host, without keys/headers.
                    if reply.status_code in (302,303):
                        location = reply.headers.get('location','')
                        target = urlsplit(location)
                        if target.scheme != 'https' or target.hostname != 'script.googleusercontent.com' or target.username or target.password:
                            raise ValueError('Redirecionamento Google inesperado')
                        reply = await client.get(location)
                    reply.raise_for_status()
                    data = reply.json()
                    if data.get('ok') is False:
                        code = data.get('code',503)
                        if type(code) is not int or not 400 <= code <= 599:
                            raise ValueError('Código de resposta inválido')
                        return httpx.Response(code,json={'detail':'Operação recusada'},request=reply.request)
                    return reply
                if action == 'update':
                    return await client.post(base + '/v1/technicians/update', headers=headers, json=payload)
                return await client.get(base + '/v1/technicians/snapshot', headers=headers)
            pending_failed = False
            # Apply locally authorized offline changes before refreshing the global copy.
            for pending in access.pending():
                try:
                    response = await request('update', {'kind': pending['kind'], 'record': pending['payload']})
                    if response.status_code != 409:
                        response.raise_for_status()
                        if response.json().get('acknowledged_id') != pending['user_id']:
                            raise ValueError('Confirmação de usuário inválida')
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pending_failed = True
                    continue
                if response.status_code == 409:
                    # The central version wins. No silent resurrection of a revoked user.
                    with access.db:
                        access.db.execute('DELETE FROM directory_pending WHERE user_id=?', (pending['user_id'],))
                        old = access.by_id(pending['user_id'])
                        if old:
                            access.revoke(old['name'])
                            if pending['kind'] == 'register':
                                # Preserve the rejected local identity's audit without
                                # retaining a login which belongs to another global ID.
                                access.db.execute("UPDATE users SET name=?,active=0,deleted=1,source='conflict' WHERE id=?",
                                    ('conflict-' + old['id'], old['id']))
                    access.store.record('directory_conflict', {'user_id': pending['user_id'], 'action': 'central_version_preserved'})
                    continue
                with access.db:
                    access.db.execute('DELETE FROM directory_pending WHERE user_id=?', (pending['user_id'],))
                    access.db.execute("UPDATE users SET source='directory' WHERE id=?", (pending['user_id'],))
            response = await request('snapshot')
            response.raise_for_status()
            if len(response.content) > 5_000_000:
                raise ValueError('Snapshot excedeu o limite de tamanho')
            data = response.json()
            if data.get('complete') is not True:
                raise ValueError('Uma lista parcial não pode atualizar os acessos')
            access.apply_snapshot(data['technicians'])
            access.status.update(message='Cadastro atualizado; alterações locais ainda pendentes' if pending_failed else 'Sincronizado', last_success=time.time())
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            # Preserve the last complete snapshot and exactly its original expiration.
            # Never leak remote error bodies, tokens or password hashes into the audit.
            access.status['message'] = 'Sem sincronização; mantida a última validade recebida'
            return False
        finally:
            if own:
                await client.aclose()


async def directory_loop(access):
    access.wakeup = asyncio.Event()
    while True:
        await synchronize(access)
        delay = access.config()['interval_s'] * random.uniform(.95, 1.05)
        access.status['next_attempt'] = time.time() + delay
        try:
            await asyncio.wait_for(access.wakeup.wait(), timeout=delay)
            access.wakeup.clear()
        except TimeoutError:
            pass
