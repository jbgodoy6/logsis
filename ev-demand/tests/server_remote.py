"""Local HTTPS relay fixture. Never connects to tunnl.gg or customer equipment."""
import asyncio
import os
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import uvicorn
from app.main import create_app
from app.remote_gateway import create_gateway
from app.store import password_hash

async def main():
    if not os.getenv('DMAX_TEST_REMOTE_ROOT'):raise RuntimeError('Use the isolated browser runner')
    controller=create_app(os.environ['DMAX_TEST_REMOTE_DB'],root_password_hash=password_hash(os.environ['DMAX_TEST_REMOTE_ROOT']))
    gateway=create_gateway('http://127.0.0.1:8123',host_pattern=re.compile(r'127\.0\.0\.1:8447'))
    class Relay:
        async def __call__(self,scope,receive,send):
            if scope['type']=='http':
                scope=dict(scope)
                scope['headers']=[(k,v) for k,v in scope['headers'] if not k.lower().startswith(b'x-forwarded-')]+[(b'x-forwarded-proto',b'https'),(b'x-forwarded-for',b'203.0.113.12')]
            await gateway(scope,receive,send)
    local=uvicorn.Server(uvicorn.Config(controller,host='127.0.0.1',port=8123,log_level='warning'))
    remote=uvicorn.Server(uvicorn.Config(Relay(),host='127.0.0.1',port=8447,proxy_headers=False,
        ssl_certfile=os.environ['DMAX_TEST_REMOTE_CERT'],ssl_keyfile=os.environ['DMAX_TEST_REMOTE_KEY'],log_level='warning'))
    await asyncio.gather(local.serve(),remote.serve())

if __name__=='__main__':asyncio.run(main())
