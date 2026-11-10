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
import urllib.request
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
                and url.hostname not in ('api.trycloudflare.com','www.trycloudflare.com')
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

READY_URL='http://127.0.0.1:20246/ready'

def command():
    protocol=os.getenv('DMAX_REMOTE_PROTOCOL','auto')
    if protocol not in ('auto','http2','quic'):raise ValueError('Protocolo Cloudflare inválido')
    return [os.getenv('DMAX_CLOUDFLARED_BIN','/opt/d-max/bin/cloudflared'),'tunnel',
            '--no-autoupdate','--protocol',protocol,'--edge-ip-version','4',
            '--output','json','--metrics','127.0.0.1:20246','--grace-period','5s',
            '--url','http://127.0.0.1:8766']

def connector_ready():
    # This is cloudflared's local readiness, not a public availability guarantee.
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(READY_URL,timeout=2) as reply:return reply.status==200
    except (OSError,ValueError):return False

async def close_process(process):
    if process.returncode is not None:return
    try:process.terminate()
    except ProcessLookupError:return
    # communicate drains stderr/stdout: wait alone can deadlock on a full pipe.
    try:await asyncio.wait_for(process.communicate(),8)
    except TimeoutError:
        try:process.kill()
        except ProcessLookupError:pass
        try:await asyncio.wait_for(process.communicate(),3)
        except TimeoutError:pass



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

async def cloudflare_session(state,stop,spawn=asyncio.create_subprocess_exec,status=write_status,
                             ready=connector_ready,stall_s=180,check_s=5):
    state.update(url=None,connected=False,provider='cloudflare',message='Cloudflare está criando um endereço automático')
    state.pop('last_error',None);status(state)
    process=await spawn(*command(),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,limit=65536)
    line_task=asyncio.create_task(process.stdout.readline());stop_task=asyncio.create_task(stop.wait())
    checked=time.monotonic();last_ready=checked;connections=set();last_note=None
    def publish():
        nonlocal last_note
        note=(state.get('connected'),state.get('message'))
        if note!=last_note:
            print('D-Max remoto: '+state['message'],flush=True);last_note=note
        status(state)
    async def check():
        nonlocal checked,last_ready
        checked=time.monotonic()
        available=await asyncio.to_thread(ready)
        state['connected']=bool(available and state.get('url'))
        if state['connected']:
            last_ready=time.monotonic();state['last_connected_at']=time.time()
            state.pop('last_error',None)
            state['message']='Conector Cloudflare pronto; confirme o acesso público no navegador e faça login'
        elif state.get('url'):
            state['message']=state.get('last_error') or 'Cloudflare sem conexão pronta; tentativa automática em andamento'
        publish()
    try:
        while not stop.is_set():
            done,_=await asyncio.wait((line_task,stop_task),timeout=max(.001,check_s-(time.monotonic()-checked)),return_when=asyncio.FIRST_COMPLETED)
            if stop_task in done:break
            if line_task in done:
                line=line_task.result()
                if not line:break
                line_task=asyncio.create_task(process.stdout.readline())
                text=line.decode(errors='replace')
                try:entry=json.loads(text)
                except ValueError:entry={}
                if not isinstance(entry,dict):entry={}
                message=str(entry.get('message',text));lower=message.lower();details=text.lower()
                changed=False
                for match in re.finditer(r'https://[a-z0-9-]+\.trycloudflare\.com(?:[^\s"|<>]*)',message):
                    candidate=match.group().rstrip('/')
                    if valid_url(candidate):
                        if candidate!=state.get('url'):print('D-Max remoto: endereço Cloudflare '+candidate,flush=True)
                        state['url']=candidate;changed=True
                found=re.search(r'connIndex=(\d+)',text)
                index=str(entry.get('connIndex',found.group(1) if found else 0))
                if re.search(r'\bregistered tunnel connection\b',lower):
                    connections.add(index)
                    print('D-Max remoto: conexão registrada com a Cloudflare; verificando prontidão local',flush=True)
                    await check();changed=False
                elif any(x in lower for x in ('unregistered tunnel connection','failed to serve tunnel connection','connection terminated','lost connection with the edge','connection with edge closed')):
                    connections.discard(index)
                    if not connections:state['connected']=False
                    state['last_error']='Cloudflare perdeu conexão com a borda; reconexão automática'
                    state['message']=state['last_error'];changed=True
                elif 'x509:' in details or 'certificate verify failed' in details:
                    state['last_error']='Cloudflare: certificado recusado; verificação TLS mantida. Confira a rede e a CA autorizada.';changed=True
                elif 'no such host' in details or 'lookup ' in details:
                    state['last_error']='Cloudflare: falha de consulta DNS; confira os servidores DNS da conexão';changed=True
                elif 'timeout' in details or 'deadline exceeded' in details or 'failed to dial' in details:
                    state['last_error']='Cloudflare: tempo limite na conexão ou requisição; confira os testes de conectividade';changed=True
                elif 'hard_fail=true' in details or entry.get('hard_fail') is True:
                    state['last_error']='Cloudflare: pré-teste encontrou falhas de conectividade; veja os destinos no registro';changed=True
                if entry.get('status')=='fail' and entry.get('target') in ('region1.v2.argotunnel.com','region2.v2.argotunnel.com'):
                    component=entry.get('component')
                    if component in ('DNS Resolution','UDP Connectivity','TCP Connectivity'):
                        print('D-Max remoto: pré-teste falhou: '+component+' / '+entry['target'],flush=True)
                if changed:
                    if not state.get('connected') and state.get('last_error'):state['message']=state['last_error']
                    elif not state.get('connected'):state['message']='Endereço criado; aguardando conexão pronta com a Cloudflare'
                    publish()
            if time.monotonic()-checked>=check_s:await check()
            if time.monotonic()-last_ready>=stall_s:
                state.update(connected=False,last_error='Cloudflare sem prontidão por '+str(stall_s)+' s; recriando o túnel automaticamente')
                state['message']=state['last_error'];publish();break
        return process.returncode
    finally:
        line_task.cancel();stop_task.cancel()
        await asyncio.gather(line_task,stop_task,return_exceptions=True)
        await close_process(process)
        state.update(connected=False,message='Acesso remoto parado' if stop.is_set() else state.get('last_error') or 'Cloudflare desconectado; reconexão automática em andamento')
        publish()


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
