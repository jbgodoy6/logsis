import asyncio
import base64
from contextlib import asynccontextmanager, suppress
import hashlib
import os
import re
import secrets
import time
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .engine import Engine
from .ocpp_server import Socket, Station
from .services import cloud_loop, meter_loop
from .meter import Meter, MEASUREMENTS, read_meter
from .store import Store, password_hash, password_matches
from .telemetry import DEFAULT_COLORS, display_colors
from .access import Access, TECHNICAL, MANAGERS, SESSION_IDLE
from .directory import directory_loop, synchronize, validate_config
from .security import AttemptLimiter, same_origin, valid_host
from .recovery import Recovery, TTL as RECOVERY_TTL
from .root_auth import load_root_hash
from .supervision import Notifier, supervise


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Login(Model):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=200)
    activation_code: str = Field(default='', max_length=200)  # Ignored; old-client compatibility.


class Setup(Model):
    root_password: str | None = Field(default=None, max_length=200)  # Ignored; legacy setup clients.
    admin_password: str = Field(min_length=8, max_length=200)


class RecoveryAuthorization(Model):
    authorization: str = Field(min_length=1, max_length=4096)


class Vehicle(Model):
    id: str = Field(default_factory=lambda: secrets.token_hex(8), pattern=r'^[A-Za-z0-9_-]{1,40}$')
    name: str = Field(min_length=1, max_length=100)
    plate: str = Field(default='', max_length=20)
    priority: bool = False
    identifiers: list[str] = Field(default_factory=list, max_length=20)

    @field_validator('identifiers')
    @classmethod
    def validate_identifiers(cls, values):
        if any(not v or len(v) > 100 or v.startswith('EVSYS-') for v in values):
            raise ValueError('Identificador inválido ou reservado ao sistema')
        return list(dict.fromkeys(values))


class Charger(Model):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,40}$')
    name: str = Field(min_length=1, max_length=100)
    model: str = Field(default='', max_length=100)
    ip: str = Field(default='', max_length=253)
    transport: str = 'simulator'
    max_kw: float = Field(gt=0)
    connector_max_kw: float = Field(gt=0)
    min_kw: float = Field(default=6, ge=0)
    input_factor: float = Field(default=1.0, ge=1, le=2)
    connectors: int = Field(default=1, ge=1, le=8)
    circuit: str = 'principal'
    enabled: bool = True
    commissioned: bool = False
    zero_supported: bool = False
    rate_unit: str = 'W'
    voltage: float = Field(default=230, gt=0)
    phases: int = Field(default=3, ge=1, le=3)
    password: str | None = Field(default=None, min_length=8, max_length=200)

    @model_validator(mode='after')
    def validate_charger(self):
        if self.transport not in ('simulator', 'ocpp') or self.rate_unit not in ('W', 'A'):
            raise ValueError('Transporte ou unidade inválidos')
        if self.min_kw > min(self.max_kw, self.connector_max_kw):
            raise ValueError('Mínimo superior à potência máxima')
        if self.transport == 'ocpp' and self.commissioned and not self.zero_supported:
            raise ValueError('Nesta versão, operação física exige limite zero e retomada validados')
        return self


class Schedule(Model):
    days: list[int] = Field(min_length=1, max_length=7)
    start: str = Field(pattern=r'^([01][0-9]|2[0-3]):[0-5][0-9]$')
    end: str = Field(pattern=r'^([01][0-9]|2[0-3]):[0-5][0-9]$')
    enabled: bool = True

    @model_validator(mode='after')
    def validate_schedule(self):
        if any(d not in range(7) for d in self.days) or self.start == self.end:
            raise ValueError('Dias inválidos ou horário vazio')
        return self


class Circuit(Model):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,40}$')
    name: str = Field(min_length=1, max_length=100)
    limit_kw: float = Field(gt=0)


class DisplayColors(Model):
    charging: str = Field(default=DEFAULT_COLORS['charging'], pattern=r'^#[0-9a-fA-F]{6}$')
    connected: str = Field(default=DEFAULT_COLORS['connected'], pattern=r'^#[0-9a-fA-F]{6}$')
    alarm: str = Field(default=DEFAULT_COLORS['alarm'], pattern=r'^#[0-9a-fA-F]{6}$')
    disconnected: str = Field(default=DEFAULT_COLORS['disconnected'], pattern=r'^#[0-9a-fA-F]{6}$')
    communication: str = Field(default=DEFAULT_COLORS['communication'], pattern=r'^#[0-9a-fA-F]{6}$')


class Settings(Model):
    site_name: str = Field(min_length=1, max_length=100)
    mode: str
    limit_kw: float = Field(gt=0)
    technical_limit_kw: float = Field(default=1000, gt=0)
    margin_kw: float = Field(ge=0)
    timezone: str
    freshness_s: float = Field(ge=2, le=120)
    ramp_kw_s: float = Field(gt=0)
    schedules: list[Schedule] = Field(max_length=50)
    blocked_policy: str
    circuits: list[Circuit] = Field(min_length=1, max_length=60)
    meter: Meter
    cloud_url: str = Field(default='', max_length=1000)
    demo_cloud_url: str = Field(default='', max_length=1000)
    retain_days: int = Field(default=7, ge=1, le=30)
    display_colors: DisplayColors | None = None

    @model_validator(mode='after')
    def validate_settings(self):
        if self.mode not in ('simulation', 'physical') or self.blocked_policy not in ('zero', 'minimum'):
            raise ValueError('Modo ou política inválidos')
        if self.limit_kw > self.technical_limit_kw:
            raise ValueError('Demanda operacional superior ao teto técnico')
        if self.margin_kw >= self.limit_kw:
            raise ValueError('Margem deve ser menor que o limite')
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            raise ValueError('Fuso horário desconhecido')
        if len({c.id for c in self.circuits}) != len(self.circuits):
            raise ValueError('Circuitos duplicados')
        if self.cloud_url and self.cloud_url == self.demo_cloud_url:
            raise ValueError('Nuvem real e demonstração exigem destinos separados')
        for destination in (self.cloud_url, self.demo_cloud_url):
            if not destination:
                continue
            url = urlsplit(destination)
            if url.scheme != 'https' or not url.hostname or url.username or url.password or url.fragment:
                raise ValueError('Nuvem exige URL HTTPS sem credenciais ou fragmento')
        return self


class PortAction(Model):
    action: str
    vehicle_id: str | None = None
    acceptance_kw: float | None = Field(default=None, gt=0)
    minutes: int = Field(default=30, ge=1, le=1440)
    reason: str = Field(default='', max_length=200)


class Simulation(Model):
    other_kw: float = Field(ge=0)


class Learning(Model):
    cap_kw: float = Field(ge=0)
    seconds: int = Field(default=30, ge=10, le=300)


class NewUser(Model):
    name: str = Field(min_length=3, max_length=40)
    full_name: str = Field(min_length=1, max_length=100)
    role: str
    expires_at: str | float | None = None
    can_emergency: bool = False


class EditUser(Model):
    full_name: str = Field(min_length=1, max_length=100)
    role: str
    active: bool = True
    deleted: bool = False
    expires_at: str | float | None = None
    can_emergency: bool = False


class PasswordChange(Model):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class DirectoryConfig(Model):
    url: str = Field(default='', max_length=1000)
    interval_s: int = Field(default=300, ge=30, le=86400)
    enabled: bool = False
    device_token: str | None = Field(default=None, min_length=32, max_length=512)


def create_app(database=None, background=True, recovery_public_key=None, root_password_hash=None):
    web_ui = os.getenv('DMAX_WEB_UI', 'server')
    store = Store(database)
    engine = Engine(store)
    root_hash_error = False
    if root_password_hash is None:
        try:
            root_password_hash = load_root_hash()
        except (ValueError, OSError):
            root_password_hash = ''
            root_hash_error = True
    access = Access(store, root_password_hash=root_password_hash)
    access.subscription = engine.subscription
    recovery = Recovery(store, recovery_public_key)
    recovery_issues = AttemptLimiter()
    recovery_attempts = AttemptLimiter()
    attempts = AttemptLimiter()
    password_attempts = AttemptLimiter()
    ocpp_attempts = AttemptLimiter()
    verification_slots = asyncio.Semaphore(2)

    async def verify_password(value, encoded):
        if verification_slots.locked():
            return None
        # PBKDF2 must not block the loop running the demand controller.
        async with verification_slots:
            return await asyncio.to_thread(password_matches, value, encoded)

    @asynccontextmanager
    async def lifespan(app):
        tasks = []
        if background:
            from .remote_registry import watch as watch_remote
            tasks = [asyncio.create_task(engine.run()), asyncio.create_task(meter_loop(engine)),
                     asyncio.create_task(cloud_loop(engine)), asyncio.create_task(directory_loop(access)),asyncio.create_task(watch_remote(access))]
        network = getattr(app.state, 'web_network', None)
        if background and network is not None:
            await asyncio.to_thread(network.start)
            print('D-Max · ' + network.status, flush=True)
            for url in network.public()['ip_urls']:
                print('Acesso por IP: ' + url, flush=True)
        notifier = Notifier.from_environment() if background else None
        if notifier is not None:
            tasks.append(asyncio.create_task(supervise(engine, tuple(tasks), notifier)))
        try:
            yield
        finally:
            if notifier is not None:
                notifier.send('STOPPING=1')
            for task in tasks:
                task.cancel()
            for task in tasks:
                with suppress(asyncio.CancelledError):
                    await task
            engine.flush()
            if background and network is not None:
                await asyncio.to_thread(network.close)
            store.db.close()

    app = FastAPI(title='EnergyCube D-Max · Controle de demanda', version='0.13.0', lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store, app.state.engine, app.state.access = store, engine, access
    app.state.recovery = recovery
    app.state.root_password_enabled = bool(root_password_hash)
    app.state.root_hash_error = root_hash_error

    def get_user(token):
        return access.session(token)

    async def authenticated(request: Request):
        u = get_user(request.cookies.get('ev_session'))
        if not u:
            raise HTTPException(401, 'Faça login para continuar')
        return u

    async def user(u=Depends(authenticated)):
        if u['must_change']:
            raise HTTPException(403, 'Troque a senha inicial antes de usar o sistema')
        return u

    async def administrator(u=Depends(user)):
        if u['role'] not in MANAGERS:
            raise HTTPException(403, 'Acesso administrativo necessário')
        return u

    async def technician(u=Depends(user)):
        if u['role'] not in TECHNICAL:
            raise HTTPException(403, 'Configuração restrita ao técnico/instalador e ao raiz')
        return u

    async def root(u=Depends(user)):
        if u['role'] != 'root':
            raise HTTPException(403, 'Função exclusiva do raiz')
        return u

    @app.middleware('http')
    async def protect_origin(request, call_next):
        host = request.headers.get('host', '')
        if not valid_host(host):
            return Response('Host inválido', status_code=400)
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('origin')
            if (origin and not same_origin(origin, host, request.scope['scheme'])) or request.headers.get('sec-fetch-site') == 'cross-site':
                return Response('Origem não permitida', status_code=403)
        response = await call_next(request)
        token = request.cookies.get('ev_session')
        if token and not any('ev_session=' in h for h in response.headers.getlist('set-cookie')):
            row = store.db.execute('SELECT username,expires,renewable FROM logins WHERE token=?', (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
            if row and row['renewable'] and row['expires'] > time.time():
                response.set_cookie('ev_session', token, httponly=True, secure=request.url.scheme == 'https', samesite='strict', max_age=max(1,int(row['expires']-time.time())))
        response.headers['X-Content-Type-Options'] = 'nosniff'
        live_document = response.headers.get('X-DMax-Live') == '1'
        if 'X-DMax-Live' in response.headers:
            del response.headers['X-DMax-Live']
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; connect-src 'self'; style-src 'self'; script-src "
            + ("'none'; " if web_ui == 'server' and not live_document else "'self'; ") +
            "img-src 'self' data:; frame-ancestors 'none'; form-action 'self'; "
            "base-uri 'none'; object-src 'none'; require-trusted-types-for 'script'; trusted-types 'none'"
        )
        if request.url.path.startswith('/api'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/api/setup')
    async def setup_status():
        return {'required': not bool(store.db.execute('SELECT 1 FROM users LIMIT 1').fetchone())}

    @app.post('/api/setup')
    async def setup(data: Setup, request: Request):
        if store.db.execute('SELECT 1 FROM users LIMIT 1').fetchone():
            raise HTTPException(409, 'Instalação já configurada')
        address = request.client.host if request.client else ''
        hostname = urlsplit('http://' + request.headers.get('host', '')).hostname
        test_client = database == ':memory:' and address == 'testclient' and hostname == 'testserver'
        if not test_client and (address not in ('127.0.0.1', '::1') or hostname not in ('localhost', '127.0.0.1', '::1')):
            raise HTTPException(403, 'Primeira configuração deve ser feita no próprio servidor, usando localhost ou 127.0.0.1')
        with store.db:
            store.db.execute('INSERT INTO users(name,password,role,id,full_name) VALUES (?,?,?,?,?)', ('root', root_password_hash, 'root', secrets.token_hex(16), 'Raiz'))
            store.db.execute('INSERT INTO users(name,password,role,id,full_name) VALUES (?,?,?,?,?)', ('admin', password_hash(data.admin_password), 'admin', secrets.token_hex(16), 'Administrador'))
        store.record('setup', {'note': 'Credenciais iniciais configuradas; valores não registrados'})
        return {'ok': True}

    @app.post('/api/login')
    async def login(data: Login, response: Response, request: Request):
        address = request.client.host if request.client else 'unknown'
        if not attempts.allow(address):
            raise HTTPException(429, 'Muitas tentativas. Aguarde cinco minutos.')
        name = data.username.strip().lower()
        row = access.by_name(name)
        if name == 'root' and not root_password_hash:
            raise HTTPException(401, 'Acesso raiz exige autorização de recuperação; não aceita senha')
        if access.config()['enabled'] and (not row or row['role'] == 'technician'):
            try:
                await asyncio.wait_for(synchronize(access), timeout=5)
            except TimeoutError:
                pass
            row = access.by_name(name)
        if not access.usable(row):
            raise HTTPException(401, 'Usuário, senha, situação ou validade inválidos')
        verified = await verify_password(data.password, row['password'])
        if verified is None:
            raise HTTPException(429, 'Autenticação ocupada. Tente novamente em instantes.')
        if not verified:
            raise HTTPException(401, 'Usuário, senha, situação ou validade inválidos')
        # An account can be revoked while PBKDF2 runs in the worker thread.
        latest = access.by_id(row['id'])
        if not access.usable(latest) or any(latest[k] != row[k] for k in ('epoch','password')):
            raise HTTPException(401, 'Acesso alterado durante a autenticação. Faça login novamente.')
        row = latest
        return open_session(row, response, request, lifetime=SESSION_IDLE[row['role']], renewable=True)

    def open_session(row, response, request, lifetime=28800, renewable=False):
        token = secrets.token_urlsafe(32)
        with store.db:
            store.db.execute('INSERT INTO logins(token,username,expires,epoch,renewable) VALUES (?,?,?,?,?)',
                (hashlib.sha256(token.encode()).hexdigest(), row['name'], time.time() + lifetime, row['epoch'], int(renewable)))
        response.set_cookie('ev_session', token, httponly=True, secure=request.url.scheme == 'https', samesite='strict', max_age=lifetime)
        store.record('login', {'user': row['name'], 'role': row['role']})
        return access.public(row)

    @app.get('/api/recovery')
    async def recovery_status():
        return recovery.public()

    @app.post('/api/recovery/challenge')
    async def recovery_challenge(response: Response, request: Request):
        address = request.client.host if request.client else 'unknown'
        if not recovery_issues.allow(address):
            raise HTTPException(429, 'Muitos desafios. Aguarde cinco minutos.')
        if not access.by_name('root'):
            raise HTTPException(409, 'Configure primeiro a senha do administrador no servidor')
        binding = request.cookies.get('dmax_recovery', '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}', binding):
            binding = secrets.token_urlsafe(32)
        try:
            challenge = recovery.issue(binding)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
        response.set_cookie('dmax_recovery', binding, httponly=True, secure=request.url.scheme == 'https',
                            samesite='strict', max_age=RECOVERY_TTL)
        return challenge

    @app.post('/api/recovery/authorize')
    async def recovery_authorize(data: RecoveryAuthorization, response: Response, request: Request):
        address = request.client.host if request.client else 'unknown'
        if not recovery_attempts.allow(address):
            raise HTTPException(429, 'Muitas tentativas. Aguarde cinco minutos.')
        row = access.by_name('root')
        if not access.usable(row):
            raise HTTPException(401, 'Recuperação indisponível')
        binding = request.cookies.get('dmax_recovery', '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}', binding):
            raise HTTPException(401, 'Gere o desafio neste navegador')
        try:
            recovery.consume(data.authorization.strip(), binding)
        except ValueError as exc:
            raise HTTPException(401, str(exc)) from None
        response.delete_cookie('dmax_recovery')
        store.record('root_recovery_authorized', {'key_fingerprint': recovery.public()['fingerprint']})
        return open_session(row, response, request, lifetime=RECOVERY_TTL)

    @app.post('/api/logout')
    async def logout(request: Request, response: Response, u=Depends(authenticated)):
        with store.db:
            store.db.execute('DELETE FROM logins WHERE token=?', (hashlib.sha256(request.cookies['ev_session'].encode()).hexdigest(),))
        response.delete_cookie('ev_session')
        return {'ok': True}

    @app.post('/api/recover-admin')
    async def recover(data: Login, u=Depends(user)):
        if u['role'] != 'root' or data.username != 'admin' or len(data.password) < 8:
            raise HTTPException(403, 'Somente root pode redefinir a senha do administrador; mínimo de oito caracteres')
        with store.db:
            store.db.execute('UPDATE users SET password=? WHERE name=?', (password_hash(data.password), 'admin'))
            store.db.execute('DELETE FROM logins WHERE username=?', ('admin',))
        store.record('password_recovery', {'actor': u['name'], 'target': 'admin'})
        return {'ok': True}

    @app.get('/api/me')
    async def me(u=Depends(authenticated)):
        return u

    @app.get('/api/state')
    async def state(u=Depends(user)):
        return engine.snapshot()

    def access_error(exc):
        return HTTPException(403 if isinstance(exc, PermissionError) else 422, str(exc))

    @app.post('/api/change-password')
    async def change_password(data: PasswordChange, response: Response, u=Depends(authenticated)):
        if not password_attempts.allow(u['id']):
            raise HTTPException(429, 'Muitas tentativas. Aguarde cinco minutos.')
        try:
            access.change_password(u, data.current_password, data.new_password)
        except (ValueError, PermissionError) as exc:
            raise access_error(exc)
        response.delete_cookie('ev_session')
        return {'ok': True, 'login_required': True}

    @app.get('/api/users')
    async def users(u=Depends(administrator)):
        return {'users': access.list_for(u)}

    @app.post('/api/users')
    async def add_user(data: NewUser, u=Depends(administrator)):
        try:
            return access.create(u, **data.model_dump())
        except (ValueError, PermissionError) as exc:
            raise access_error(exc)

    @app.put('/api/users/{identifier}')
    async def edit_user(identifier: str, data: EditUser, u=Depends(administrator)):
        try:
            return access.update(u, identifier, data.model_dump())
        except (ValueError, PermissionError) as exc:
            raise access_error(exc)

    @app.post('/api/users/{identifier}/reset')
    async def reset_user(identifier: str, u=Depends(administrator)):
        try:
            return access.reset_password(u, identifier)
        except (ValueError, PermissionError) as exc:
            raise access_error(exc)

    @app.get('/api/directory')
    async def directory_settings(u=Depends(root)):
        return {'config': access.config(), 'status': access.status,
                'pending': len(access.pending()), 'token_present': bool(access.device_token()),
                'controller_id': store.entities('system')[0]['controller_id']}

    @app.get('/api/remote-clients')
    async def remote_clients(u=Depends(root)):
        from .remote_clients import fetch,DirectoryUnavailable
        try:data=await fetch(access)
        except DirectoryUnavailable as exc:raise HTTPException(503,str(exc)) from None
        store.record('remote_clients_consulted',{'actor':u['name'],'count':len(data['clients'])})
        return JSONResponse(data,headers={'Cache-Control':'no-store'})

    @app.put('/api/directory')
    async def save_directory(data: DirectoryConfig, u=Depends(root)):
        try:
            access.configure(validate_config(data.model_dump(exclude={'device_token'})))
            if data.device_token:
                access.set_device_token(data.device_token)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        store.record('directory_configured', {'actor': u['name'], 'interval_s': data.interval_s, 'enabled': data.enabled})
        return {'ok': True}

    @app.post('/api/directory/sync')
    async def directory_now(u=Depends(root)):
        ok = await synchronize(access)
        return {'ok': ok, 'status': access.status}

    @app.put('/api/appearance')
    async def appearance(data: DisplayColors, u=Depends(administrator)):
        settings = store.settings()
        settings['display_colors'] = data.model_dump()
        store.save_settings(settings)
        store.record('appearance_changed', {'actor': u['name']})
        return {'ok': True}

    @app.get('/ui-colors.css')
    async def appearance_css(u=Depends(user)):
        palette = display_colors(store.settings().get('display_colors'))
        css = ':root{' + ''.join('--plant-' + key + ':' + color + ';' for key, color in palette.items()) + '}'
        return Response(css, media_type='text/css', headers={'Cache-Control': 'no-store'})

    @app.get('/api/history')
    async def history(u=Depends(user)):
        return store.history()

    @app.get('/api/remote')
    async def remote_status(u=Depends(technician)):
        from .remote_tunnel import public_status
        from .remote_registry import publication
        return dict(public_status(),publication=publication(access),controller_id=store.entities('system')[0]['controller_id'])

    curve_cache=OrderedDict()
    curve_lock=asyncio.Lock()
    async def curve_data(start,end,mode):
        from .curve import query,parameters
        settings=store.settings();now=time.time()
        parameters(settings,start,end,mode,now)
        period=60 if end else 5
        key=(start,end,mode or settings['mode'],settings['site_name'],settings['timezone'],int(now//period))
        async with curve_lock:
            if key not in curve_cache:
                curve_cache[key]=await asyncio.to_thread(query,store,settings,start,end,mode,now)
                while len(curve_cache)>24:curve_cache.popitem(last=False)
            return curve_cache[key]

    @app.get('/api/curve')
    async def curve_history(start: str=Query('',max_length=64),end: str=Query('',max_length=64),mode: str=Query('',max_length=16),u=Depends(user)):
        try:return await curve_data(start,end,mode)
        except ValueError as exc:raise HTTPException(422,str(exc)) from None

    @app.get('/api/curve/report.pdf')
    async def curve_report(start: str='',end: str='',mode: str='',u=Depends(user)):
        from .curve import pdf
        from .server_ui import VERSION
        try:
            data=await curve_data(start,end,mode)
            payload=await asyncio.to_thread(pdf,data,VERSION)
        except ValueError as exc:raise HTTPException(422,str(exc)) from None
        store.record('curve_export',{'actor':u['name'],'format':'pdf','start':data['start'],'end':data['end'],'mode':data['mode'],'samples':data['total_samples']})
        return Response(payload,media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="D-Max-curva.pdf"','Cache-Control':'no-store'})

    @app.get('/api/curve/export.csv')
    async def curve_csv(start: str='',end: str='',mode: str='',u=Depends(user)):
        import tempfile
        from .curve import export_csv,parameters
        from starlette.background import BackgroundTask
        settings=store.settings()
        try:parameters(settings,start,end,mode)
        except ValueError as exc:raise HTTPException(422,str(exc)) from None
        folder=Path(tempfile.mkdtemp(prefix='dmax-curve-'));path=folder/'curva.csv'
        try:count=await asyncio.to_thread(export_csv,store,settings,path,start,end,mode)
        except BaseException:
            path.unlink(missing_ok=True);folder.rmdir();raise
        store.record('curve_export',{'actor':u['name'],'format':'csv','start':start,'end':end,'mode':mode or settings['mode'],'samples':count})
        return FileResponse(path,filename='D-Max-curva.csv',media_type='text/csv',headers={'Cache-Control':'no-store'},
                            background=BackgroundTask(lambda:(path.unlink(),folder.rmdir())))

    @app.get('/api/audit')
    async def audit(actor: str = '', offset: int = 0, u=Depends(administrator)):
        import json
        kinds=('settings_changed','operator_action','appearance_changed','charger_configured','vehicle_configured','user_created','user_updated','directory_configured','maintenance_requested','backup_downloaded','curve_export','remote_clients_consulted')
        rows=[]
        for row in store.db.execute('SELECT * FROM events WHERE kind IN ('+','.join('?' for _ in kinds)+') ORDER BY ts DESC', kinds):
            payload=json.loads(row['payload'])
            if actor and payload.get('actor')!=actor:
                continue
            rows.append(dict(ts=row['ts'],kind=row['kind'],payload=payload))
        return {'events':rows[max(0,offset):max(0,offset)+100], 'total':len(rows)}

    @app.get('/api/reports/sessions.pdf')
    async def sessions_pdf(start: str = '', end: str = '', vehicle_id: str = '', charger_id: str = '', report_type: str = 'detailed', vehicles: str = '', energy_scope: str = 'all', vehicle_selection: list[str] = Query(default=[]), u=Depends(user)):
        from .reports import report_data, build_pdf
        from .server_ui import VERSION
        try:
            data = report_data(store, start, end, vehicle_id, charger_id, report_type, ','.join(vehicle_selection) or vehicles, energy_scope)
        except (ValueError, OverflowError) as exc:
            raise HTTPException(422, str(exc))
        payload = await asyncio.to_thread(build_pdf, data, VERSION)
        store.record('report_generated', {'actor': u['name'], 'sessions': len(data['sessions']), 'start': data['start'], 'end': data['end'],
                                        'vehicle': vehicle_id, 'charger': charger_id})
        return Response(payload, media_type='application/pdf', headers={
            'Content-Disposition': 'attachment; filename="D-Max-relatorio-recargas.pdf"', 'Cache-Control': 'no-store'})

    @app.put('/api/settings')
    async def settings(data: Settings, u=Depends(administrator)):
        current = store.settings()
        if data.display_colors is None:
            data.display_colors = DisplayColors(**current['display_colors'])
        if u['role'] == 'admin':
            allowed = {'site_name', 'limit_kw', 'schedules', 'blocked_policy', 'display_colors'}
            submitted = data.model_dump()
            if any(submitted.get(k) != value for k, value in current.items() if k not in allowed):
                raise HTTPException(403, 'Administrador não altera multimedidor, teto técnico, circuitos ou parâmetros técnicos')
        if data.mode != current['mode'] and any(engine.config(p['charger'])['transport'] == 'ocpp' and (p['connected'] or p['running'] or p['charger'] in engine.connections) for p in engine.ports.values()):
            raise HTTPException(409, 'Desconecte as sessões antes de trocar o modo')
        ids = {c.id for c in data.circuits}
        if any(c['circuit'] not in ids for c in store.entities('charger') if not c.get('archived')):
            raise HTTPException(409, 'Um circuito em uso não pode ser removido')
        if data.mode == 'physical':
            if (data.meter.transport == 'tcp' and not data.meter.host) or (data.meter.transport == 'rtu' and not data.meter.serial_port):
                raise HTTPException(422, 'Configure a conexão do multimedidor antes da operação física')
            if not any(r.enabled and r.measurement == 'power_total_kw' for r in data.meter.registers):
                raise HTTPException(422, 'Configure a leitura da potência ativa total para o controle de demanda')
        if data.mode != current['mode']:
            engine.flush()
            engine.trace.clear()
            for port in list(engine.ports.values()):
                if engine.config(port['charger'])['transport'] == 'simulator':
                    engine.disconnect(port['key'])
        store.save_settings(data.model_dump())
        if data.mode != current['mode'] or data.meter.model_dump() != current['meter']:
            engine.meter.update(at=0, total_kw=0, readings=[], energy_kwh=None, error='')
        store.record('settings_changed', {'actor': u['name'], 'mode': data.mode, 'limit_kw': data.limit_kw,
                                          'margin_kw': data.margin_kw, 'schedules': [s.model_dump() for s in data.schedules]})
        return {'ok': True}

    @app.get('/api/meter/ports')
    async def serial_ports(u=Depends(technician)):
        from serial.tools import list_ports
        ports = await asyncio.to_thread(list_ports.comports)
        aliases = list(Path('/dev/serial/by-id').glob('*')) if os.name == 'posix' else []
        return {'ports': [{'device': p.device, 'description': p.description,
            'stable_path': next((str(alias) for alias in aliases if alias.resolve() == Path(p.device).resolve()), None)} for p in ports]}

    @app.get('/api/meter/measurements')
    async def measurements(u=Depends(technician)):
        return {'measurements': [{'key': k, 'label': v[0], 'unit': v[1]} for k, v in MEASUREMENTS.items()]}

    @app.post('/api/meter/test')
    async def test_meter(data: Meter, u=Depends(technician)):
        try:
            async with engine.meter_io_lock:
                readings = await read_meter(data.model_dump())
            return {'ok': all(not r['error'] for r in readings), 'readings': readings}
        except Exception as exc:
            return {'ok': False, 'error': str(exc)[:240], 'readings': []}

    @app.post('/api/chargers')
    async def charger(data: Charger, u=Depends(technician)):
        old = engine.config(data.id)
        if old and old.get('archived'):
            raise HTTPException(409, 'Identificador já usado no histórico; cadastre outro identificador')
        chargers = [c for c in store.entities('charger') if not c.get('archived')]
        if not old and len(chargers) >= 60:
            raise HTTPException(422, 'Esta versão está dimensionada para até 60 carregadores')
        if data.circuit not in {c['id'] for c in store.settings()['circuits']}:
            raise HTTPException(422, 'Circuito desconhecido')
        if old and (old['connectors'] != data.connectors or old['transport'] != data.transport):
            raise HTTPException(409, 'Quantidade de conectores e transporte são fixos nesta versão; cadastre outra identificação')
        if data.transport == 'ocpp' and not data.password and not (old and old.get('password_hash')):
            raise HTTPException(422, 'Defina a senha de conexão OCPP')
        record = data.model_dump(exclude={'password'})
        record['password_hash'] = password_hash(data.password) if data.password else (old or {}).get('password_hash')
        if data.transport == 'simulator':
            record.update(commissioned=True, zero_supported=True)
        store.put('charger', record)
        engine.refresh()
        store.record('charger_configured', {'actor': u['name'], 'charger': data.id, 'commissioned': record['commissioned']})
        return {'ok': True}

    @app.delete('/api/chargers/{identifier}')
    async def delete_charger(identifier: str, u=Depends(technician)):
        charger = engine.config(identifier)
        if not charger or charger.get('archived'):
            raise HTTPException(404, 'Carregador não encontrado')
        ports = [port for port in engine.ports.values() if port['charger'] == identifier]
        if charger['transport'] == 'ocpp' and (identifier in engine.connections or any(
            port['connected'] or port['running'] or port['power_kw'] > .1 or port['limit_kw'] > 0 for port in ports)):
            raise HTTPException(409, 'Encerre a recarga, confirme a desconexão do veículo e desconecte a comunicação OCPP antes de excluir')
        if charger['transport'] == 'simulator':
            for port in ports:
                engine.disconnect(port['key'])
        charger.update(archived=True, enabled=False)
        store.put('charger', charger)
        store.record('charger_removed', {'actor': u['name'], 'charger': identifier, 'history_preserved': True})
        return {'ok': True}

    @app.post('/api/vehicles')
    async def vehicle(data: Vehicle, u=Depends(administrator)):
        if (store.get('vehicle', data.id) or {}).get('archived'):
            raise HTTPException(409, 'Identificador de veículo excluído; cadastre com um novo identificador')
        others = [v for v in store.entities('vehicle') if v['id'] != data.id and not v.get('archived')]
        if any(set(v['identifiers']) & set(data.identifiers) for v in others):
            raise HTTPException(409, 'Identificador já associado a outro veículo')
        store.put('vehicle', data.model_dump())
        for p in engine.ports.values():
            if p['identifier']:
                engine.identify(p, p['identifier'])
        store.record('vehicle_configured', {'actor': u['name'], 'vehicle': data.id, 'priority': data.priority})
        return {'ok': True}

    @app.delete('/api/vehicles/{identifier}')
    async def delete_vehicle(identifier: str, u=Depends(administrator)):
        row = store.get('vehicle', identifier)
        if not row or row.get('archived'):
            raise HTTPException(404, 'Veículo não encontrado')
        if any(p.get('vehicle_id') == identifier and (p['connected'] or p['running'] or p.get('session_id')) for p in engine.ports.values()):
            raise HTTPException(409, 'Desconecte o veículo e encerre a recarga antes de excluí-lo')
        row.update(archived=True, archived_at=time.time())
        store.put('vehicle', row)
        for item in store.entities('identifier'):
            if item.get('vehicle_id') == identifier:
                item['vehicle_id'] = None
                store.put('identifier', item)
        store.record('vehicle_removed', {'actor': u['name'], 'vehicle': identifier, 'history_preserved': True})
        return {'ok': True}

    @app.post('/api/ports/{key}/action')
    async def action(key: str, data: PortAction, u=Depends(user)):
        if engine.subscription.status()['native'] and data.action in ('pause', 'resume', 'emergency', 'cancel_emergency'):
            raise HTTPException(409, 'Controle de recarga desativado pela assinatura; funcionamento nativo')
        if data.action in ('emergency', 'cancel_emergency') and u['role'] == 'operator' and not u['can_emergency']:
            raise HTTPException(403, 'Operador sem permissão de emergência')
        if data.action in ('connect', 'disconnect') and u['role'] not in TECHNICAL:
            raise HTTPException(403, 'Simulação restrita à administração')
        if key not in engine.ports:
            raise HTTPException(404, 'Conector desconhecido')
        p = engine.ports[key]
        c = engine.config(p['charger'])
        if c['transport'] == 'simulator' and u['role'] not in TECHNICAL:
            raise HTTPException(403, 'Simulação restrita ao técnico/instalador e raiz')
        if c.get('archived'):
            raise HTTPException(404, 'Carregador excluído')
        if data.vehicle_id and not any(v['id'] == data.vehicle_id and not v.get('archived') for v in store.entities('vehicle')):
            raise HTTPException(422, 'Veículo desconhecido')
        if data.action in ('connect', 'disconnect'):
            if store.settings()['mode'] != 'simulation' or c['transport'] != 'simulator':
                raise HTTPException(409, 'Ação disponível apenas no simulador')
            try:
                if data.action == 'connect':
                    engine.connect_simulated(key, data.vehicle_id, data.acceptance_kw)
                else:
                    engine.disconnect(key)
            except ValueError as exc:
                raise HTTPException(409, str(exc))
        elif data.action == 'pause':
            p['manual_pause'] = True
        elif data.action == 'resume':
            p['manual_pause'] = False
        elif data.action == 'emergency':
            if not p['connected'] or not data.reason.strip():
                raise HTTPException(422, 'Conecte o veículo e informe o motivo da emergência')
            p.update(emergency_until=time.time() + data.minutes * 60, manual_pause=False)
        elif data.action == 'cancel_emergency':
            p['emergency_until'] = 0
        elif data.action == 'assign_vehicle':
            if not p['connected']:
                raise HTTPException(409, 'Conector desocupado')
            p['vehicle_id'] = data.vehicle_id
            if p['session_id']:
                session = next(s for s in store.entities('session') if s['id'] == p['session_id'])
                session['vehicle_id'] = data.vehicle_id
                store.put('session', session)
        else:
            raise HTTPException(422, 'Ação desconhecida')
        store.record('operator_action', {'actor': u['name'], 'port': key, 'action': data.action,
                                         'reason': data.reason, 'minutes': data.minutes, 'vehicle': data.vehicle_id})
        return {'ok': True}

    @app.post('/api/simulation')
    async def simulation(data: Simulation, u=Depends(technician)):
        if store.settings()['mode'] != 'simulation':
            raise HTTPException(409, 'Simulador desativado')
        engine.other_kw = data.other_kw
        store.record('simulation_load_changed', {'actor': u['name'], 'other_kw': data.other_kw})
        return {'ok': True}

    @app.post('/api/ports/{key}/learn')
    async def learn(key: str, data: Learning, u=Depends(technician)):
        if engine.subscription.status()['native']:
            raise HTTPException(409, 'Aprendizado indisponível durante funcionamento nativo')
        p = engine.ports.get(key)
        if p and engine.config(p['charger'])['transport'] == 'simulator' and store.settings()['mode'] != 'simulation':
            raise HTTPException(409, 'Simulador desativado')
        if not p or not p['running'] or data.cap_kw > p['limit_kw']:
            raise HTTPException(409, 'É necessário estar em recarga; o teste só pode reduzir o limite atual')
        if p.get('test'):
            raise HTTPException(409, 'Já existe um teste em andamento neste conector')
        p['test'] = {'cap_kw': data.cap_kw, 'started_at': time.time(),
                     'until': time.time() + data.seconds, 'observations': []}
        store.record('test_started', {'actor': u['name'], 'port': key, 'cap_kw': data.cap_kw, 'seconds': data.seconds})
        return {'ok': True}

    @app.post('/api/demo')
    async def demo(u=Depends(technician)):
        if any(not c.get('archived') for c in store.entities('charger')) or store.settings()['mode'] != 'simulation':
            raise HTTPException(409, 'Demonstração disponível somente em uma instalação vazia em simulação')
        suffix = '-' + secrets.token_hex(3) if store.entities('charger') else ''
        for identifier, name, power in [('DC-01', 'Estação rápida 01', 320), ('DC-02', 'Estação rápida 02', 320), ('AC-03', 'Estação AC 03', 22)]:
            c = Charger(id=identifier + suffix, name=name, max_kw=power, connector_max_kw=power, min_kw=6).model_dump(exclude={'password'})
            c.update(password_hash=None, commissioned=True, zero_supported=True)
            store.put('charger', c)
        for identifier, name, priority in [('frota-01', 'Veículo da diretoria', True), ('frota-02', 'Veículo operacional', False)]:
            store.put('vehicle', {'id': identifier + suffix, 'name': name, 'priority': priority, 'plate': '', 'identifiers': ['SIM-' + identifier + suffix]})
        engine.refresh()
        engine.connect_simulated('DC-01' + suffix + ':1', 'frota-02' + suffix)
        engine.connect_simulated('DC-02' + suffix + ':1', 'frota-01' + suffix)
        store.record('demo_created', {'actor': u['name']})
        return {'ok': True}

    @app.websocket('/ws/live')
    async def live(ws: WebSocket):
        origin = ws.headers.get('origin')
        if not valid_host(ws.headers.get('host', '')) or (origin and not same_origin(origin, ws.headers.get('host', ''), 'https' if ws.scope['scheme'] == 'wss' else 'http')) or not get_user(ws.cookies.get('ev_session')) or get_user(ws.cookies.get('ev_session'))['must_change']:
            await ws.close(code=1008)
            return
        await ws.accept()
        try:
            while (current_user := get_user(ws.cookies.get('ev_session'))) and not current_user['must_change']:
                await ws.send_json(engine.snapshot())
                await asyncio.sleep(1)
            await ws.close(code=1008)
        except (WebSocketDisconnect, RuntimeError):
            pass

    @app.websocket('/ocpp/{identifier}')
    async def ocpp(ws: WebSocket, identifier: str):
        c = engine.config(identifier)
        if not c or c.get('archived') or c['transport'] != 'ocpp' or store.settings()['mode'] != 'physical':
            await ws.close(code=1008)
            return
        if not ocpp_attempts.allow(identifier):
            await ws.close(code=1008)
            return
        auth = ws.headers.get('authorization', '')
        try:
            if len(auth) > 1024 or auth.split(' ', 1)[0].lower() != 'basic':
                raise ValueError('Autenticação inválida')
            username, password = base64.b64decode(auth.split(' ', 1)[1], validate=True).decode().split(':', 1)
        except (ValueError, IndexError, UnicodeDecodeError):
            username = password = ''
        if username != identifier or await verify_password(password, c.get('password_hash')) is not True:
            await ws.close(code=1008)
            return
        if identifier in engine.connections or 'ocpp1.6' not in ws.scope.get('subprotocols', []):
            await ws.close(code=1008)
            return
        await ws.accept(subprotocol='ocpp1.6')
        for p in engine.ports.values():
            if p['charger'] == identifier:
                p.update(native_released=False, native_attempt=0, profile_initialized=False)
        station = Station(identifier, Socket(ws), engine)
        engine.connections[identifier] = station
        store.record('ocpp_connected', {'charger': identifier})
        try:
            await station.start()
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            engine.connections.pop(identifier, None)
            store.record('ocpp_disconnected', {'charger': identifier})

    app.mount('/static', StaticFiles(directory=Path(__file__).parent / 'static'), name='static')

    from .maintenance import install as install_maintenance
    install_maintenance(app, user, technician, root)

    if web_ui == 'server':
        from .server_ui import install
        install(app)
    else:
        @app.get('/')
        async def index():
            return FileResponse(Path(__file__).parent / 'static/index.html')

    return app
