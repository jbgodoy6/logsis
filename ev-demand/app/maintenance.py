"""Bounded uploads; the unprivileged web service never installs executable code.

An installed systemd path invokes the root-owned worker. Update trust is pinned
outside the ZIP, and a restore may not change controller identity or root access.
"""
import asyncio
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import stat
import tempfile
import zipfile
from contextlib import closing

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import Depends, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

MAX_UPLOAD = 256 * 1024 * 1024
DOMAIN = b'DMAX-UPDATE-1\n'


def validate_backup(path, identity):
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True)) as db:
        db.execute('PRAGMA trusted_schema=OFF')
        if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('Backup SQLite corrompido')
        if db.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view')").fetchone():
            raise ValueError('Backup com objetos SQL não permitidos')
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'users','settings','entities','logins','events','samples','outbox','directory_secret','directory_config'} <= tables:
            raise ValueError('Backup não contém o esquema D-Max')
        row=db.execute("SELECT payload FROM entities WHERE kind='system' AND id='identity'").fetchone()
        if not row or json.loads(row[0]).get('controller_id') != identity:
            raise ValueError('Backup pertence a outra instalação')
        settings=json.loads(db.execute('SELECT payload FROM settings WHERE id=1').fetchone()[0])
        from .main import Settings
        Settings(**settings)
        from .access import valid_hash
        for name,role,password in db.execute('SELECT name,role,password FROM users'):
            if role not in ('root','admin','technician','operator','developer','commercial') or not valid_hash(password):
                raise ValueError('Conta inválida no backup')
        if not db.execute("SELECT 1 FROM users WHERE name='root' AND role='root'").fetchone():
            raise ValueError('Credencial raiz ausente')


def verify_update(path, public_key):
    key=serialization.load_pem_public_key(Path(public_key).read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError('Chave de atualização deve ser Ed25519')
    with zipfile.ZipFile(path) as z:
        entries=z.infolist(); names=[i.filename for i in entries]
        if len(names)!=len(set(names)) or len(names)>5000 or sum(i.file_size for i in entries)>1024*1024*1024:
            raise ValueError('Pacote excedeu limites ou contém entradas duplicadas')
        for i in entries:
            p=Path(i.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in i.filename or not i.filename.startswith('D-Max-Raspberry/') or stat.S_ISLNK(i.external_attr>>16):
                raise ValueError('Caminho não permitido no ZIP')
        prefix='D-Max-Raspberry/'
        manifest=z.read(prefix+'SHA256SUMS.txt')
        key.verify(z.read(prefix+'SHA256SUMS.sig'), DOMAIN+manifest)
        seen=set()
        for line in manifest.decode().splitlines():
            digest,name=line.split('  ',1)
            if name in seen or hashlib.sha256(z.read(prefix+name)).hexdigest()!=digest:
                raise ValueError('Integridade do pacote inválida')
            seen.add(name)
        if set(names)!={prefix+n for n in seen|{'SHA256SUMS.txt','SHA256SUMS.sig'}}:
            raise ValueError('Arquivo fora do manifesto')
        if not {'run.py','requirements.lock','instalar-raspberry.sh','app/main.py','deploy/manage.py'} <= seen:
            raise ValueError('Pacote incompleto')
    return len(seen)


def install(app, user, technician, root):
    signing_key=secrets.token_bytes(32)
    queue=Path(os.getenv('DMAX_MAINTENANCE_DIR','/var/lib/d-max/maintenance'))
    def csrf(request):
        return hmac.new(signing_key,request.cookies.get('ev_session','').encode(),hashlib.sha256).hexdigest()

    @app.get('/api/maintenance')
    async def status(request: Request, u=Depends(technician)):
        result={'csrf':csrf(request),'available':Path('/etc/systemd/system/d-max-maintenance.path').is_file(), 'message':'Aguardando operação'}
        try:
            result.update(json.loads((queue/'status.json').read_text()))
        except (OSError,ValueError):
            pass
        return result

    @app.get('/api/maintenance/backup')
    async def backup(u=Depends(technician)):
        folder=Path(tempfile.mkdtemp(prefix='dmax-backup-'))
        path=folder/'controller.sqlite3'
        database=app.state.store.db.execute('PRAGMA database_list').fetchone()['file']
        def copy_backup():
            source=sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True) if database else app.state.store.db
            try:
                with closing(sqlite3.connect(path)) as target:
                    source.backup(target,pages=256,sleep=.01)
                    target.execute('DELETE FROM logins');target.commit()
            finally:
                if database:source.close()
        try:
            await asyncio.to_thread(copy_backup)
        except Exception:
            path.unlink(missing_ok=True);folder.rmdir()
            raise HTTPException(500,'Não foi possível criar backup consistente') from None
        os.chmod(path,0o600)
        app.state.store.record('backup_downloaded',{'actor':u['name']})
        return FileResponse(path,filename='D-Max-backup.sqlite3',media_type='application/octet-stream',
                headers={'Cache-Control':'no-store'},background=BackgroundTask(lambda:(path.unlink(),folder.rmdir())))

    @app.post('/api/maintenance/{action}')
    async def upload(action: str, request: Request, u=Depends(root)):
        if action not in ('restore','update'):
            raise HTTPException(404,'Operação desconhecida')
        if not hmac.compare_digest(request.headers.get('X-DMax-Maintenance',''),csrf(request)):
            raise HTTPException(403,'Atualize a página de manutenção')
        engine=app.state.engine
        if engine.connections or any(p['connected'] or p['running'] for p in engine.ports.values() if engine.config(p['charger'])['transport']=='ocpp'):
            raise HTTPException(409,'Encerre as sessões e desconecte os equipamentos físicos antes da manutenção')
        if not Path('/etc/systemd/system/d-max-maintenance.path').is_file():
            raise HTTPException(409,'Instale esta versão pelo terminal para habilitar a manutenção pelo navegador')
        queue.mkdir(mode=0o700,parents=True,exist_ok=True)
        if (queue/'request.json').exists():
            raise HTTPException(409,'Já existe manutenção pendente')
        identifier=secrets.token_hex(16);path=queue/(identifier+'.upload');size=0
        try:
            with path.open('xb') as f:
                os.chmod(path,0o600)
                async for chunk in request.stream():
                    size+=len(chunk)
                    if size>MAX_UPLOAD:
                        raise HTTPException(413,'Arquivo excede 256 MiB')
                    f.write(chunk)
            if action=='update':
                await asyncio.to_thread(verify_update,path,'/etc/d-max/update-public.pem')
            else:
                await asyncio.to_thread(validate_backup,path,app.state.store.entities('system')[0]['controller_id'])
            app.state.store.record('maintenance_requested',{'actor':u['name'],'action':action,'id':identifier})
            # Only one atomic request can win concurrent uploads.
            fd=os.open(queue/'pending.json',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,'w') as f:
                json.dump({'action':action,'id':identifier},f);f.flush();os.fsync(f.fileno())
            os.replace(queue/'pending.json',queue/'request.json')
            return {'ok':True,'message':'Pacote validado. Manutenção solicitada; aguarde a reinicialização e entre novamente.'}
        except HTTPException:
            path.unlink(missing_ok=True);raise
        except Exception:
            path.unlink(missing_ok=True)
            raise HTTPException(422,'Arquivo inválido, incompatível ou assinatura não confiável') from None
