"""Central service: private spreadsheet metadata plus protected SQLite credentials."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import time

from fastapi import FastAPI, HTTPException, Request

from app.access import Access, INITIAL_PASSWORD, valid_hash
from app.store import Store, password_hash
from .sheets import GoogleSheet


def create_platform(database=None, sheet=None, device_tokens=None):
    store = Store(database or os.getenv('DIRECTORY_DB_PATH', 'platform-data/directory.sqlite3'))
    accounts = Access(store)
    store.db.execute('CREATE TABLE IF NOT EXISTS registration_pending(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
    store.db.commit()
    sheet = sheet or GoogleSheet()
    lock = asyncio.Lock()
    last_refresh = 0.0
    cache_seconds = 15 if isinstance(sheet, GoogleSheet) else 0
    app = FastAPI(title='D-Max · Plataforma global de técnicos', docs_url=None, redoc_url=None, openapi_url=None)
    app.state.accounts, app.state.store = accounts, store

    def authenticate(request):
        if not request.headers.get('authorization', '').startswith('Bearer '):
            raise HTTPException(401, 'Equipamento não autorizado')
        token = request.headers.get('authorization', '').removeprefix('Bearer ')
        controller = request.headers.get('x-dmax-controller', '')
        tokens = device_tokens
        if tokens is None:
            path = os.getenv('DIRECTORY_DEVICE_TOKENS_FILE')
            if not path:
                raise HTTPException(503, 'Autenticação de equipamentos não configurada')
            try:
                tokens = json.loads(Path(path).read_text())
            except (OSError, ValueError):
                raise HTTPException(503, 'Cadastro de equipamentos indisponível')
        expected = tokens.get(controller)
        if not expected or not secrets.compare_digest(hashlib.sha256(token.encode()).hexdigest(), expected):
            raise HTTPException(401, 'Equipamento não autorizado')

    async def refresh(force=False):
        nonlocal last_refresh
        if not force and time.time() - last_refresh < cache_seconds:
            return
        rows = await asyncio.to_thread(sheet.read)
        # Validate all metadata before updating even a single account.
        incoming = {r['id']: r for r in rows}
        for row in rows:
            conflict = accounts.by_name(row['name'])
            if conflict and conflict['id'] != row['id']:
                raise ValueError('Login duplicado em identidade histórica')
            old = accounts.by_id(row['id'])
            if old and old['name'] != row['name']:
                raise ValueError('Não renomeie login/id de uma identidade; edite apenas o nome exibido')
        with store.db:
            for row in rows:
                old = accounts.by_id(row['id'])
                if not old:
                    pending = store.db.execute('SELECT payload FROM registration_pending WHERE id=?', (row['id'],)).fetchone()
                    draft = json.loads(pending['payload']) if pending else None
                    if draft and draft['name'] == row['name']:
                        store.db.execute('''INSERT INTO users(name,password,role,id,full_name,active,deleted,expires_at,
                            source,must_change,activation_hash,credential_version,meta_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)''',
                            (row['name'],draft['password'],'technician',row['id'],row['full_name'],int(row['active']),
                             int(row['deleted']),row['expires_at'],'directory',int(draft['must_change']),
                             draft.get('activation_hash'),draft['credential_version']))
                        continue
                    store.db.execute('''INSERT INTO users(name,password,role,id,full_name,active,deleted,expires_at,
                        source,must_change,activation_hash,meta_version) VALUES (?,?,?,?,?,?,?,?,?,1,?,1)''',
                        (row['name'],password_hash(INITIAL_PASSWORD),'technician',row['id'],row['full_name'],
                         int(row['active']),int(row['deleted']),row['expires_at'],'directory',password_hash(secrets.token_urlsafe(24))))
                else:
                    changed = any(old[k] != row[k] for k in ('full_name','active','deleted','expires_at'))
                    if changed:
                        store.db.execute('UPDATE users SET full_name=?,active=?,deleted=?,expires_at=?,meta_version=meta_version+1 WHERE id=?',
                                         (row['full_name'],int(row['active']),int(row['deleted']),row['expires_at'],row['id']))
            for old in store.db.execute("SELECT * FROM users WHERE role='technician'").fetchall():
                if old['id'] not in incoming and (old['active'] or not old['deleted']):
                    store.db.execute('UPDATE users SET active=0,deleted=1,meta_version=meta_version+1 WHERE id=?', (old['id'],))
        last_refresh = time.time()

    @app.get('/v1/technicians/snapshot')
    async def snapshot(request: Request):
        authenticate(request)
        async with lock:
            try:
                await refresh()
            except Exception:
                raise HTTPException(503, 'Não foi possível obter um cadastro completo e válido do Google Planilhas')
            records = []
            for row in store.db.execute("SELECT * FROM users WHERE role='technician' ORDER BY id"):
                record = accounts.directory_record(dict(row))
                for key in ('active','deleted','must_change'): record[key] = bool(record[key])
                records.append(record)
            return {'complete': True, 'generated_at': time.time(), 'technicians': records}

    @app.post('/v1/technicians/update')
    async def update(request: Request):
        nonlocal last_refresh
        authenticate(request)
        data = await request.json()
        r = data.get('record', {})
        operations = set(r.get('operations', []))
        if not operations or not operations <= {'register','credential','metadata'}:
            raise HTTPException(422, 'Operação inválida')
        if not valid_hash(r.get('password')) or (r.get('activation_hash') is not None and not valid_hash(r['activation_hash'])):
            raise HTTPException(422, 'Formato de credencial inválido')
        from .sheets import parse_rows
        try:
            # Reuse the exact sheet metadata validation; role is never accepted from clients.
            from datetime import datetime, timezone
            until = datetime.fromtimestamp(r['expires_at'], timezone.utc).isoformat() if r.get('expires_at') else ''
            parse_rows([['id','nome','login','situacao','valido_ate'],[r['id'],r['full_name'],r['name'],
                'excluido' if r.get('deleted') else 'ativo' if r['active'] else 'bloqueado',until]])
        except Exception:
            raise HTTPException(422, 'Metadados inválidos')
        async with lock:
            try:
                await refresh(force=True)
            except Exception:
                raise HTTPException(503, 'Google Planilhas indisponível; alteração não aplicada')
            old = accounts.by_id(r['id'])
            conflict = accounts.by_name(r['name'])
            if conflict and conflict['id'] != r['id']:
                raise HTTPException(409, 'Login já existe')
            if 'register' in operations and old:
                # Retrying an acknowledged-but-disconnected registration is idempotent.
                if old['password'] == r['password'] and old['name'] == r['name']:
                    with store.db:
                        store.db.execute('DELETE FROM registration_pending WHERE id=?', (r['id'],))
                    return {'acknowledged_id': r['id']}
                raise HTTPException(409, 'Identidade já existe')
            if 'register' not in operations:
                if not old or old['name'] != r['name']:
                    raise HTTPException(409, 'Identidade não encontrada')
                if 'credential' in operations:
                    if not accounts.usable(old) or old['credential_version'] != r.get('base_version'):
                        if old['password'] == r['password'] and old['credential_version'] == r['credential_version']:
                            return {'acknowledged_id': r['id']}
                        raise HTTPException(409, 'Credencial alterada ou acesso revogado na plataforma')
                metadata_matches = all(old[k] == r.get(k) for k in ('full_name','active','deleted','expires_at'))
                if 'metadata' in operations and old['meta_version'] != r.get('base_meta_version') and not metadata_matches:
                    raise HTTPException(409, 'Cadastro alterado na planilha')
            if 'register' in operations:
                with store.db:
                    store.db.execute('INSERT INTO registration_pending VALUES (?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                                     (r['id'],json.dumps(r)))
            if operations & {'register','metadata'}:
                try:
                    await asyncio.to_thread(sheet.write, r)
                    last_refresh = 0
                except Exception:
                    raise HTTPException(503, 'Não foi possível gravar o cadastro na planilha')
            if not old:
                with store.db:
                    store.db.execute('''INSERT INTO users(name,password,role,id,full_name,active,deleted,expires_at,
                        source,must_change,activation_hash,credential_version,meta_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (r['name'],r['password'],'technician',r['id'],r['full_name'],int(r['active']),int(r['deleted']),
                         r.get('expires_at'),'directory',int(r['must_change']),r.get('activation_hash'),r['credential_version'],1))
            elif 'credential' in operations:
                with store.db:
                    store.db.execute('UPDATE users SET password=?,activation_hash=?,must_change=?,credential_version=? WHERE id=?',
                                     (r['password'],r.get('activation_hash'),int(r['must_change']),r['credential_version'],r['id']))
            with store.db:
                store.db.execute('DELETE FROM registration_pending WHERE id=?', (r['id'],))
            return {'acknowledged_id': r['id']}

    return app
