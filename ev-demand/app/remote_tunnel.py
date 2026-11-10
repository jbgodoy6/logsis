"""One persistent SSH identity per installation; bounded reconnection and public status."""
import asyncio
import json
import os
from pathlib import Path
import random
import re
import signal
import tempfile
import time
from urllib.parse import urlsplit

HOME=Path('/var/lib/d-max-remote')
STATUS=HOME/'public/status.json'
KNOWN_HOSTS='/etc/d-max-remote/known_hosts'
HOST_FINGERPRINT='SHA256:5uQ6VobmUpY4wyMmm5jnAwFtt3aX06WYDDM4ER+2WUw'


def valid_url(value):
    if not isinstance(value,str):return False
    try:
        url=urlsplit(value)
        return (url.scheme=='https' and not url.username and not url.password and url.port is None
                and url.path in ('','/') and not url.query and not url.fragment
                and bool(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.tunnl\.gg',url.hostname or '')))
    except ValueError:return False


def public_status(path=STATUS):
    try:
        data=json.loads(Path(path).read_text())
        url=data.get('url') if valid_url(data.get('url')) else None
        recent=0<=time.time()-float(data.get('heartbeat_at',0))<90
        message='Sem sinal recente do túnel; confira o serviço' if data.get('connected') and not recent else str(data.get('message',''))[:240]
        return dict(url=url,connected=bool(data.get('connected') and recent),
                    message=message,last_connected_at=data.get('last_connected_at'),
                    heartbeat_at=data.get('heartbeat_at'),configured=True)
    except (OSError,ValueError,TypeError):
        return dict(url=None,connected=False,message='Acesso remoto não ativado ou sem status disponível',configured=False)


def write_status(data,path=STATUS):
    path=Path(path)
    fd,temporary=tempfile.mkstemp(prefix='.status-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:
            json.dump(dict(data,heartbeat_at=time.time()),f);f.flush();os.fsync(f.fileno())
        os.chmod(temporary,0o640)
        os.replace(temporary,path)
    finally:Path(temporary).unlink(missing_ok=True)


def command():
    return ['ssh','-F','/dev/null','-n','-T','-o','BatchMode=yes','-o','IdentitiesOnly=yes',
            '-i',str(HOME/'id_ed25519'),'-o','UserKnownHostsFile='+KNOWN_HOSTS,
            '-o','GlobalKnownHostsFile=/dev/null','-o','UpdateHostKeys=no',
            '-o','StrictHostKeyChecking=yes','-o','ServerAliveInterval=15',
            '-o','ServerAliveCountMax=3','-o','ExitOnForwardFailure=yes',
            '-o','ConnectTimeout=20','-R','80:127.0.0.1:8766',
            'stable@proxy.tunnl.gg','output=json']


async def session(state,stop,spawn=asyncio.create_subprocess_exec,status=write_status):
    process=await spawn(*command(),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,limit=16384)
    heartbeat=time.monotonic()
    try:
        while not stop.is_set():
            try:line=await asyncio.wait_for(process.stdout.readline(),timeout=15)
            except TimeoutError:
                status(state)
                continue
            if not line:break
            if time.monotonic()-heartbeat>=15:
                status(state);heartbeat=time.monotonic()
            try:data=json.loads(line)
            except (ValueError,UnicodeError):continue
            if data.get('event')=='tunnel' and data.get('stable') is True and valid_url(data.get('url')):
                state.update(url=data['url'].rstrip('/'),connected=True,last_connected_at=time.time(),
                             message='Túnel conectado; acesso continua exigindo login do D-Max')
                status(state)
        return await process.wait()
    finally:
        if process.returncode is None:
            process.terminate()
            try:await asyncio.wait_for(process.wait(),5)
            except TimeoutError:
                process.kill();await process.wait()
        state.update(connected=False,message='Conexão remota encerrada; reconexão automática em andamento')
        status(state)


async def supervise(stop=None,connect=session,pause=None):
    stop=stop or asyncio.Event()
    loop=asyncio.get_running_loop()
    for sig in (signal.SIGTERM,signal.SIGINT):
        loop.add_signal_handler(sig,stop.set)
    old=public_status()
    state=dict(url=old.get('url'),connected=False,message='Conectando ao serviço remoto',last_connected_at=old.get('last_connected_at'))
    failures=0
    while not stop.is_set():
        write_status(state)
        started=time.monotonic()
        try:await connect(state,stop)
        except (OSError,ValueError,asyncio.LimitOverrunError):
            state.update(connected=False,message='Falha na conexão SSH; confira rede, chave do servidor e limites do serviço')
            write_status(state)
        failures=0 if time.monotonic()-started>60 else min(failures+1,4)
        delay=min(60,5*2**failures)*random.uniform(.9,1.1)
        if pause is not None:await pause(delay)
        else:
            try:await asyncio.wait_for(stop.wait(),timeout=delay)
            except TimeoutError:pass
    state.update(connected=False,message='Acesso remoto parado')
    write_status(state)


def main():asyncio.run(supervise())
