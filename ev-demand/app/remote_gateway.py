"""Loopback-only HTTP gateway. Never starts a second controller or forwards OCPP."""
import argparse
from contextlib import asynccontextmanager
from dataclasses import replace
import ipaddress
import os
import re
import ssl

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse
from starlette.background import BackgroundTask
from starlette.middleware.gzip import GZipMiddleware

from .network import load_config

MAX_BODY = 64 * 1024 * 1024
PUBLIC_HOST = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.tunnl\.gg')
HOP_HEADERS = {'connection','keep-alive','proxy-authenticate','proxy-authorization','te','trailer','transfer-encoding','upgrade'}


def backend(config='/etc/d-max/rede.ini', environment=None):
    environment = os.environ if environment is None else environment
    current = load_config(config)
    current = replace(current, host=environment.get('DMAX_HOST') or current.host,
                      port=int(environment.get('DMAX_PORT') or current.port)).validated()
    if current.host not in ('0.0.0.0','localhost','127.0.0.1','::','::1'):
        raise ValueError('Acesso remoto exige que o D-Max aceite conexões em loopback. Host restrito à interface LAN: configuração preservada; revise rede.ini.')
    host = '127.0.0.1' if current.host in ('0.0.0.0','localhost') else '::1' if current.host == '::' else current.host
    if ':' in host: host='['+host+']'
    secure = bool(environment.get('DMAX_TLS_CERT'))
    trust = ssl.create_default_context()
    if environment.get('DMAX_REMOTE_CA_FILE'):
        trust.load_verify_locations(environment['DMAX_REMOTE_CA_FILE'])
    return ('https' if secure else 'http')+'://'+host+':'+str(current.port), trust


def permitted(path, method):
    if '\\' in path or '//' in path or any(part in ('.','..') for part in path.split('/')):
        return False
    if method not in ('GET','HEAD','POST','PUT','DELETE','OPTIONS'):
        return False
    if path == '/api/setup' and method not in ('GET','HEAD'):
        return False
    return path == '/' or path == '/ui-colors.css' or bool(re.fullmatch(r'/ui/[a-z]+',path)) or path.startswith(('/api/','/ui-data/','/static/'))


def create_gateway(target, trust=True, transport=None, host_pattern=PUBLIC_HOST):
    @asynccontextmanager
    async def lifespan(app):
        yield
        await client.aclose()

    # trust_env=False prevents local application data from taking an egress proxy.
    client=httpx.AsyncClient(base_url=target,verify=trust,transport=transport,trust_env=False,
                             follow_redirects=False,timeout=httpx.Timeout(120,connect=5,pool=5),
                             limits=httpx.Limits(max_connections=50,max_keepalive_connections=10))
    app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    app.state.client=client
    class LiveCompression:
        def __init__(self,app):
            self.app=app
            self.compressed=GZipMiddleware(app,minimum_size=1024,compresslevel=5)
        async def __call__(self,scope,receive,send):
            app=self.compressed if scope.get('path','').startswith('/ui-data/') else self.app
            await app(scope,receive,send)
    app.add_middleware(LiveCompression)

    @app.api_route('/{path:path}',methods=['GET','HEAD','POST','PUT','DELETE','OPTIONS','PATCH','TRACE'])
    async def proxy(request: Request,path):
        if not permitted(request.scope['path'],request.method):
            return Response('Recurso indisponível no acesso remoto',status_code=404)
        host=request.headers.get('host','').lower()
        if not host_pattern.fullmatch(host) or request.headers.get('x-forwarded-proto')!='https':
            return Response('Origem remota inválida',status_code=400)
        peer=request.client.host if request.client else ''
        try:
            if not ipaddress.ip_address(peer).is_loopback:
                return Response('Gateway somente local',status_code=403)
        except ValueError:
            return Response('Gateway somente local',status_code=403)
        try:
            if int(request.headers.get('content-length','0'))>MAX_BODY:
                return Response('Limite remoto: 64 MiB por arquivo. Use o acesso local.',status_code=413)
        except ValueError:
            return Response('Tamanho inválido',status_code=400)
        blocked=HOP_HEADERS|{'host'}|{x.strip().lower() for x in request.headers.get('connection','').split(',')}
        headers=[(k,v) for k,v in request.headers.items() if k.lower() not in blocked and not k.lower().startswith(('x-forwarded-','cf-')) and k.lower()!='forwarded']
        # The SSH relay replaces these headers. Only its loopback forward reaches us.
        try:
            visitor=str(ipaddress.ip_address(request.headers.get('x-forwarded-for','')))
        except ValueError:
            visitor='127.0.0.1'
        headers += [('Host',host),('X-Forwarded-For',visitor),('X-Forwarded-Proto','https')]
        size=0
        async def body():
            nonlocal size
            async for chunk in request.stream():
                size+=len(chunk)
                if size>MAX_BODY: raise ValueError('Remote upload exceeds 64 MiB')
                yield chunk
        url=target+request.url.path
        if request.url.query: url+='?'+request.url.query
        try:
            outgoing=client.build_request(request.method,url,headers=headers,content=body())
            reply=await client.send(outgoing,stream=True)
        except (httpx.HTTPError,ValueError):
            if size>MAX_BODY:
                return Response('Limite remoto: 64 MiB por arquivo. Use o acesso local.',status_code=413)
            return Response('D-Max local indisponível. Tente novamente.',status_code=503)
        if reply.headers.get('content-length','').isdigit() and int(reply.headers['content-length'])>MAX_BODY:
            await reply.aclose()
            return Response('Arquivo maior que o limite remoto. Baixe pela rede local.',status_code=413)
        response=StreamingResponse(reply.aiter_raw(),status_code=reply.status_code,background=BackgroundTask(reply.aclose))
        response.raw_headers=[(k,v) for k,v in reply.headers.raw if k.decode().lower() not in HOP_HEADERS]
        return response
    return app


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',default='/etc/d-max/rede.ini')
    args=parser.parse_args(argv)
    target,trust=backend(args.config)
    uvicorn.run(create_gateway(target,trust),host='127.0.0.1',port=8766,
                proxy_headers=False,access_log=False,log_level='warning')
