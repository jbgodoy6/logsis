"""Root-owned worker for the fixed local maintenance queue; no shell input."""
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
from contextlib import closing

sys.path.insert(0,'/opt/d-max')
from app.maintenance import validate_backup, verify_update

QUEUE=Path('/var/lib/d-max/maintenance')
DB=Path('/var/lib/d-max/controller.sqlite3')

def run(*args):
    subprocess.run(args,check=True,timeout=900)

def copy_regular(source,target):
    fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as src:
        if not stat.S_ISREG(os.fstat(src.fileno()).st_mode) or os.fstat(src.fileno()).st_size>256*1024*1024:
            raise ValueError('Arquivo inválido')
        with open(target,'xb') as dst:
            shutil.copyfileobj(src,dst)
    os.chmod(target,0o600)

def status(message):
    # Replace links instead of following attacker-controlled output files.
    fd,name=tempfile.mkstemp(dir=QUEUE,prefix='.status-')
    with os.fdopen(fd,'w') as f:json.dump({'message':message,'at':time.time()},f)
    os.chown(name,__import__('pwd').getpwnam('dmax').pw_uid,__import__('grp').getgrnam('dmax').gr_gid)
    os.replace(name,QUEUE/'status.json')

def restore(source,backup_dir):
    run('systemctl','stop','d-max.service')
    try:
        with closing(sqlite3.connect(DB)) as current:
            identity=json.loads(current.execute("SELECT payload FROM entities WHERE kind='system' AND id='identity'").fetchone()[0])['controller_id']
            validate_backup(source,identity)
            with closing(sqlite3.connect(backup_dir/'controller.sqlite3')) as saved:current.backup(saved)
            protected=list(current.execute("SELECT kind,id,payload FROM entities WHERE kind IN ('subscription','system','remote_registration')"))
            root=current.execute("SELECT password FROM users WHERE name='root'").fetchone()[0]
            secret=list(current.execute('SELECT * FROM directory_secret'))
            directory=list(current.execute('SELECT * FROM directory_config'))
            current.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        with closing(sqlite3.connect(source)) as incoming:
            incoming.execute('PRAGMA trusted_schema=OFF')
            incoming.execute('DELETE FROM logins')
            incoming.execute("UPDATE users SET password=?,active=1,deleted=0,role='root',must_change=0,expires_at=NULL WHERE name='root'",(root,))
            for kind,identifier,payload in protected:
                incoming.execute('INSERT OR REPLACE INTO entities(kind,id,payload) VALUES (?,?,?)',(kind,identifier,payload))
            incoming.execute('DELETE FROM directory_secret');incoming.executemany('INSERT INTO directory_secret VALUES (?,?)',secret)
            incoming.execute('DELETE FROM directory_config');incoming.executemany('INSERT INTO directory_config VALUES (?,?)',directory)
            # Do not replay old cloud records or duplicate restored aggregate events.
            incoming.execute('DELETE FROM outbox')
            incoming.commit();incoming.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        for suffix in ('-wal','-shm'):Path(str(DB)+suffix).unlink(missing_ok=True)
        os.chown(source,DB.stat().st_uid,DB.stat().st_gid)
        os.replace(source,DB)
        run('systemctl','start','d-max.service')
        time.sleep(3);run('systemctl','is-active','--quiet','d-max.service')
    except BaseException:
        # A failed health check can happen after the new process started.
        # Stop it before replacing SQLite and its WAL files during rollback.
        run('systemctl','stop','d-max.service')
        if (backup_dir/'controller.sqlite3').exists():
            for suffix in ('-wal','-shm'):Path(str(DB)+suffix).unlink(missing_ok=True)
            shutil.copy2(backup_dir/'controller.sqlite3',DB)
            owner=__import__('pwd').getpwnam('dmax');os.chown(DB,owner.pw_uid,owner.pw_gid)
        run('systemctl','start','d-max.service')
        raise

def main():
    if os.geteuid()!=0:raise RuntimeError('Worker requer root')
    for path in (QUEUE,QUEUE.parent,DB,Path('/opt/d-max')):
        if path.is_symlink():raise ValueError('Destino de manutenção em link simbólico')
    with tempfile.TemporaryDirectory(prefix='dmax-maintenance-') as temporary:
        folder=Path(temporary);copy_regular(QUEUE/'request.json',folder/'request.json')
        request=json.loads((folder/'request.json').read_text())
        if set(request)!={'action','id'} or request['action'] not in ('restore','update') or not re.fullmatch('[0-9a-f]{32}',request['id']):
            raise ValueError('Solicitação inválida')
        source=QUEUE/(request['id']+'.upload')
        try:
            copy_regular(source,folder/'upload')
            backups=Path('/var/backups/d-max')/('web-'+str(time.time_ns()));backups.mkdir(mode=0o700,parents=True)
            if request['action']=='update':
                verify_update(folder/'upload','/etc/d-max/update-public.pem')
                import zipfile
                with zipfile.ZipFile(folder/'upload') as z:z.extractall(folder/'package')
                run('bash',str(folder/'package/D-Max-Raspberry/instalar-raspberry.sh'),'--no-hardware-watchdog')
            else:
                Path('/run/d-max-maintenance').mkdir(mode=0o700,exist_ok=True)
                with open('/run/d-max-maintenance/lock','a') as lock:
                    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    restore(folder/'upload',backups)
            status('Manutenção concluída. Entre novamente e confira a versão e os dados.')
        except Exception:
            status('Manutenção falhou. Confira o serviço e o backup em /var/backups/d-max. Detalhes no journal de manutenção.')
            raise
        finally:
            source.unlink(missing_ok=True);(QUEUE/'request.json').unlink(missing_ok=True)

if __name__=='__main__':main()
