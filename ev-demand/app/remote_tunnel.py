"""Cloudflare Quick Tunnel supervisor and legacy SSH compatibility."""
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
                and bool(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.(?:trycloudflare\.com|tunnl\.gg)',url.hostname or '')))
    except ValueError:return False


def public_status(path=STATUS):
    try:
        data=json.loads(Path(path).read_text())
        url=data.get('url') if valid_url(data.get('url')) else None
        recent=0<=time.time()-float(data.get('heartbeat_at',0))<90
        message='Sem sinal recente do túnel; confira o serviço' if data.get('connected') and not recent else str(data.get('message',''))[:240]
        return dict(url=url,connected=bool(data.get('connected') and recent),
                    message=message,last_connected_at=data.get('last_connected_at'),
                    heartbeat_at=data.get('heartbeat_at'),configured=True,provider=data.get('provider','cloudflare' if url and '.trycloudflare.com' in url else 'tunnl'))
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


def ssh_command():
    return ['ssh','-F','/dev/null','-n','-T','-o','BatchMode=yes','-o','IdentitiesOnly=yes',
            '-i',str(HOME/'id_ed25519'),'-o','UserKnownHostsFile='+KNOWN_HOSTS,
            '-o','GlobalKnownHostsFile=/dev/null','-o','UpdateHostKeys=no',
            '-o','StrictHostKeyChecking=yes','-o','ServerAliveInterval=15',
            '-o','ServerAliveCountMax=3','-o','ExitOnForwardFailure=yes',
            '-o','ConnectTimeout=20','-R','80:127.0.0.1:8766',
            'stable@proxy.tunnl.gg','output=json']

def command():
    return [os.getenv('DMAX_CLOUDFLARED_BIN','/opt/d-max/bin/cloudflared'),'tunnel',
            '--no-autoupdate','--protocol','http2','--url','http://127.0.0.1:8766']


async def session(state,stop,spawn=asyncio.create_subprocess_exec,status=write_status):
    process=await spawn(*ssh_command(),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,limit=16384)
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

async def cloudflare_session(state,stop,spawn=asyncio.create_subprocess_exec,status=write_status):
    state.update(url=None,connected=False,provider='cloudflare',message='Cloudflare está criando um endereço automático')
    status(state)
    process=await spawn(*command(),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,limit=65536)
    heartbeat=time.monotonic();connections=set()
    try:
        while not stop.is_set():
            try:line=await asyncio.wait_for(process.stdout.readline(),timeout=15)
            except TimeoutError:
                status(state);continue
            if not line:break
            text=line.decode(errors='replace');lower=text.lower()
            try:entry=json.loads(text)
            except ValueError:entry={}
            if not isinstance(entry,dict):entry={}
            match=re.search(r'https://[a-z0-9-]+\.trycloudflare\.com',text)
            changed=False
            if match and valid_url(match.group()):
                state.update(url=match.group(),connected=bool(connections),message='Cloudflare conectado; acesso exige login do D-Max' if connections else 'Endereço criado; aguardando conexão com a Cloudflare');changed=True
                print('D-Max remoto: endereço Cloudflare '+match.group(),flush=True)
            index=entry.get('connIndex',0)
            if not entry:
                found=re.search(r'connIndex=(\d+)',text);index=int(found.group(1)) if found else 0
            if 'registered tunnel connection' in lower and 'unregistered' not in lower:
                connections.add(str(index));state.update(connected=bool(state.get('url')),last_connected_at=time.time(),message='Cloudflare conectado; acesso exige login do D-Max');changed=True
            elif any(x in lower for x in ('unregistered tunnel connection','failed to serve tunnel connection','connection terminated')):
                connections.discard(str(index));state.update(connected=bool(connections and state.get('url')),message='Cloudflare reconectando; confira o último estado');changed=True
            elif 'x509:' in lower or 'certificate verify failed' in lower:
                state['message']='Cloudflare: certificado recusado; verificação TLS mantida. Confira a rede e a CA autorizada.';changed=True
            elif 'no such host' in lower or 'lookup ' in lower:
                state['message']='Cloudflare: falha de DNS; reconexão automática';changed=True
            elif 'timeout' in lower or 'failed to dial' in lower:
                state['message']='Cloudflare: sem conexão; confira saída TCP 7844 e a política da rede';changed=True
            if changed or time.monotonic()-heartbeat>=15:
                if state.get('connected'):state.pop('last_error',None)
                elif changed:state['last_error']=state['message']
                status(state);heartbeat=time.monotonic()
        return await process.wait()
    finally:
        if process.returncode is None:
            process.terminate()
            try:await asyncio.wait_for(process.wait(),5)
            except TimeoutError:process.kill();await process.wait()
        state.update(connected=False,message=state.get('last_error') or 'Cloudflare desconectado; reconexão automática em andamento')
        status(state)


async def supervise(stop=None,connect=None,pause=None):
    connect=connect or (session if os.getenv('DMAX_REMOTE_PROVIDER')=='tunnl' else cloudflare_session)
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
            state.update(connected=False,message='Falha no processo remoto; confira o cliente, a rede e os limites do serviço')
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
