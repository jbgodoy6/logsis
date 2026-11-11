"""Disposable per-browser controllers. No production state or I/O workers are shared."""
import asyncio
import hashlib
from http.cookies import SimpleCookie
import secrets
import time

from fastapi.responses import JSONResponse

IDLE_SECONDS=900
MAX_DEMOS=32

class Demonstrations:
    def __init__(self,access):
        self.access=access
        self.sessions={}

    def discard(self,token):
        session=self.sessions.pop(token,None)
        if session:
            session['discarded']=True
            if not session['lock'].locked():self.close_session(session)

    @staticmethod
    def close_session(session):
        if not session.get('db_closed'):
            session['app'].state.store.db.close();session['db_closed']=True

    def expire(self):
        now=time.monotonic()
        for token,s in list(self.sessions.items()):
            row=self.access.by_id(s['identity'])
            if now-s['last']>=IDLE_SECONDS or not self.access.usable(row) or row['epoch']!=s['epoch'] or row['role']!='commercial':
                self.discard(token)

    async def create(self,row):
        from .main import create_app
        self.expire()
        if len(self.sessions)>=MAX_DEMOS:raise ValueError('Limite de demonstrações simultâneas atingido')
        app=create_app(':memory:',background=False,root_password_hash='',demonstration=True)
        store=app.state.store
        internal=secrets.token_urlsafe(32);token=secrets.token_urlsafe(32)
        with store.db:
            store.db.execute("INSERT INTO users(name,password,role,id,full_name) VALUES ('apresentador','','technician','demo-owner','Demonstração comercial')")
            store.db.execute('INSERT INTO logins(token,username,expires,epoch,renewable) VALUES (?,?,?,?,?)',(hashlib.sha256(internal.encode()).hexdigest(),'apresentador',time.time()+86400,0,0))
        # Use the same validated simulator setup endpoint, entirely in memory.
        import httpx
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost') as client:
            result=await client.post('/api/demo',cookies={'ev_session':internal})
            result.raise_for_status()
        self.sessions[token]=dict(app=app,internal=internal,identity=row['id'],epoch=row['epoch'],last=time.monotonic(),lock=asyncio.Lock(),discarded=False)
        return token

    async def run(self):
        while True:
            self.expire()
            for session in list(self.sessions.values()):
                async with session['lock']:
                    try:
                        if not session['discarded']:await session['app'].state.engine.tick()
                    finally:
                        if session['discarded']:self.close_session(session)
            await asyncio.sleep(1)

    def close(self):
        for token in list(self.sessions):self.discard(token)


def permitted(path,method):
    """Deny by default, including new future endpoints and all hardware APIs."""
    import re
    reads={'/','/ui-colors.css','/api/setup','/api/me','/api/state','/api/history','/api/curve','/api/curve/export.csv','/api/curve/report.pdf','/api/reports/sessions.pdf','/api/users','/api/audit','/api/meter/measurements'}
    if method in ('GET','HEAD'):
        return path in reads or bool(re.fullmatch(r'/ui/(overview|monitor|chargers|vehicles|users|settings|schedules|simulation|audit|reports)',path)) or path in ('/ui-data/overview','/ui-data/monitor') or path.startswith('/static/')
    return (method,path) in {('POST','/ui/post'),('POST','/api/logout'),('POST','/api/chargers'),('POST','/api/vehicles'),('POST','/api/users'),('POST','/api/simulation'),('POST','/api/demo'),('PUT','/api/settings'),('PUT','/api/appearance')} or bool(re.fullmatch(r'/api/(users/[A-Za-z0-9_-]+(?:/reset)?|chargers/[A-Za-z0-9_-]+|vehicles/[A-Za-z0-9_-]+|ports/[^/]+/(action|learn))',path)) and method in ('POST','PUT','DELETE')

class DemoRouter:
    def __init__(self,app,manager):self.app,self.manager=app,manager
    async def __call__(self,scope,receive,send):
        if scope['type'] not in ('http','websocket'):return await self.app(scope,receive,send)
        headers=dict(scope.get('headers',[]));cookies=SimpleCookie()
        try:cookies.load(headers.get(b'cookie',b'').decode('latin1'))
        except Exception:pass
        token=cookies['dmax_demo'].value if 'dmax_demo' in cookies else ''
        if not token:return await self.app(scope,receive,send)
        if scope['type']=='websocket':return await send({'type':'websocket.close','code':1008})
        self.manager.expire();session=self.manager.sessions.get(token)
        if not session:
            result=JSONResponse({'detail':'Demonstração encerrada. Entre novamente.'},status_code=401)
            result.delete_cookie('dmax_demo');return await result(scope,receive,send)
        if not permitted(scope['path'],scope['method']):
            return await JSONResponse({'detail':'Recurso indisponível na demonstração'},status_code=403)(scope,receive,send)
        session['last']=time.monotonic()
        rewritten=dict(scope);rewritten['headers']=[(k,v) for k,v in scope['headers'] if k!=b'cookie']
        # Preserve only UI CSRF cookies; production/recovery sessions never enter here.
        selected=[f'ev_session={session["internal"]}']+[f'{k}={v.value}' for k,v in cookies.items() if k in ('dmax_ui_nonce','dmax_saved')]
        rewritten['headers'].append((b'cookie','; '.join(selected).encode()))
        logging_out=False
        async def filtered(message):
            nonlocal logging_out
            if message['type']=='http.response.start':
                out=[]
                for k,v in message.get('headers',[]):
                    if k.lower()==b'set-cookie' and v.startswith(b'ev_session='):
                        if b'Max-Age=0' in v:logging_out=True
                        continue
                    out.append((k,v))
                if not logging_out:
                    secure='; Secure' if scope['scheme']=='https' else ''
                    out.append((b'set-cookie',f'dmax_demo={token}; Max-Age=900; Path=/; HttpOnly; SameSite=strict{secure}'.encode()))
                if logging_out:out.append((b'set-cookie',b'dmax_demo=""; Max-Age=0; Path=/; HttpOnly; SameSite=strict'))
                message['headers']=out
            await send(message)
        async with session['lock']:
            try:
                if session['discarded']:
                    return await JSONResponse({'detail':'Demonstração encerrada'},status_code=401)(scope,receive,send)
                await session['app'](rewritten,receive,filtered)
                if logging_out:self.manager.discard(token)
            finally:
                if session['discarded']:self.manager.close_session(session)
