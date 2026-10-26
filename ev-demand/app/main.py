import asyncio
import base64
from contextlib import asynccontextmanager, suppress
import hashlib
import re
import secrets
import time
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .engine import Engine
from .ocpp_server import Socket, Station
from .services import cloud_loop, meter_loop
from .meter import Meter, MEASUREMENTS, read_meter
from .store import Store, password_hash, password_matches


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Login(Model):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=200)


class Setup(Model):
    root_password: str = Field(min_length=8, max_length=200)
    admin_password: str = Field(min_length=8, max_length=200)


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


class Settings(Model):
    site_name: str = Field(min_length=1, max_length=100)
    mode: str
    limit_kw: float = Field(gt=0)
    margin_kw: float = Field(ge=0)
    timezone: str
    freshness_s: float = Field(ge=2, le=120)
    ramp_kw_s: float = Field(gt=0)
    schedules: list[Schedule] = Field(max_length=50)
    blocked_policy: str
    circuits: list[Circuit] = Field(min_length=1, max_length=60)
    meter: Meter
    cloud_url: str = Field(default='', max_length=1000)
    retain_days: int = Field(default=7, ge=1, le=30)

    @model_validator(mode='after')
    def validate_settings(self):
        if self.mode not in ('simulation', 'physical') or self.blocked_policy not in ('zero', 'minimum'):
            raise ValueError('Modo ou política inválidos')
        if self.margin_kw >= self.limit_kw:
            raise ValueError('Margem deve ser menor que o limite')
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            raise ValueError('Fuso horário desconhecido')
        if len({c.id for c in self.circuits}) != len(self.circuits):
            raise ValueError('Circuitos duplicados')
        if self.cloud_url:
            url = urlsplit(self.cloud_url)
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


def create_app(database=None, background=True):
    store = Store(database)
    engine = Engine(store)
    attempts = {}

    @asynccontextmanager
    async def lifespan(app):
        tasks = []
        if background:
            tasks = [asyncio.create_task(engine.run()), asyncio.create_task(meter_loop(engine)),
                     asyncio.create_task(cloud_loop(engine))]
        yield
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
        engine.flush()
        store.db.close()

    app = FastAPI(title='EnergyCube D-Max · Controle de demanda', version='0.2.3', lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store, app.state.engine = store, engine

    def get_user(token):
        if not token:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        row = store.db.execute('SELECT u.name,u.role FROM logins l JOIN users u ON u.name=l.username WHERE l.token=? AND l.expires>?',
                               (digest, time.time())).fetchone()
        return dict(row) if row else None

    async def user(request: Request):
        u = get_user(request.cookies.get('ev_session'))
        if not u:
            raise HTTPException(401, 'Faça login para continuar')
        return u

    async def administrator(u=Depends(user)):
        if u['role'] not in ('root', 'admin'):
            raise HTTPException(403, 'Acesso administrativo necessário')
        return u

    @app.middleware('http')
    async def protect_origin(request, call_next):
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('origin')
            if (origin and urlsplit(origin).netloc != request.headers.get('host')) or request.headers.get('sec-fetch-site') == 'cross-site':
                return Response('Origem não permitida', status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
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
        if request.client and request.client.host not in ('127.0.0.1', '::1', 'testclient'):
            raise HTTPException(403, 'Primeira configuração deve ser feita no próprio servidor')
        with store.db:
            store.db.execute('INSERT INTO users VALUES (?,?,?)', ('root', password_hash(data.root_password), 'root'))
            store.db.execute('INSERT INTO users VALUES (?,?,?)', ('admin', password_hash(data.admin_password), 'admin'))
        store.record('setup', {'note': 'Credenciais iniciais configuradas; valores não registrados'})
        return {'ok': True}

    @app.post('/api/login')
    async def login(data: Login, response: Response, request: Request):
        address = request.client.host if request.client else 'unknown'
        recent = [t for t in attempts.get(address, []) if time.time() - t < 300]
        if len(recent) >= 8:
            raise HTTPException(429, 'Muitas tentativas. Aguarde cinco minutos.')
        attempts[address] = recent + [time.time()]
        row = store.db.execute('SELECT * FROM users WHERE name=?', (data.username,)).fetchone()
        if not row or not password_matches(data.password, row['password']):
            raise HTTPException(401, 'Usuário ou senha incorretos')
        attempts.pop(address, None)
        token = secrets.token_urlsafe(32)
        with store.db:
            store.db.execute('INSERT INTO logins VALUES (?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), row['name'], time.time() + 28800))
        response.set_cookie('ev_session', token, httponly=True, secure=request.url.scheme == 'https', samesite='strict', max_age=28800)
        store.record('login', {'user': row['name']})
        return {'name': row['name'], 'role': row['role']}

    @app.post('/api/logout')
    async def logout(request: Request, response: Response, u=Depends(user)):
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
    async def me(u=Depends(user)):
        return u

    @app.get('/api/state')
    async def state(u=Depends(user)):
        return engine.snapshot()

    @app.get('/api/history')
    async def history(u=Depends(user)):
        return store.history()

    @app.put('/api/settings')
    async def settings(data: Settings, u=Depends(administrator)):
        current = store.settings()
        if data.mode != current['mode'] and any(p['connected'] for p in engine.ports.values()):
            raise HTTPException(409, 'Desconecte as sessões antes de trocar o modo')
        ids = {c.id for c in data.circuits}
        if any(c['circuit'] not in ids for c in store.entities('charger')):
            raise HTTPException(409, 'Um circuito em uso não pode ser removido')
        if data.mode == 'physical':
            if (data.meter.transport == 'tcp' and not data.meter.host) or (data.meter.transport == 'rtu' and not data.meter.serial_port):
                raise HTTPException(422, 'Configure a conexão do multimedidor antes da operação física')
            if not any(r.enabled and r.measurement == 'power_total_kw' for r in data.meter.registers):
                raise HTTPException(422, 'Configure a leitura da potência ativa total para o controle de demanda')
        store.save_settings(data.model_dump())
        if data.mode != current['mode'] or data.meter.model_dump() != current['meter']:
            engine.meter.update(at=0, total_kw=0, readings=[], energy_kwh=None, error='')
        store.record('settings_changed', {'actor': u['name'], 'mode': data.mode, 'limit_kw': data.limit_kw,
                                          'margin_kw': data.margin_kw, 'schedules': [s.model_dump() for s in data.schedules]})
        return {'ok': True}

    @app.get('/api/meter/ports')
    async def serial_ports(u=Depends(administrator)):
        from serial.tools import list_ports
        ports = await asyncio.to_thread(list_ports.comports)
        return {'ports': [{'device': p.device, 'description': p.description} for p in ports]}

    @app.get('/api/meter/measurements')
    async def measurements(u=Depends(administrator)):
        return {'measurements': [{'key': k, 'label': v[0], 'unit': v[1]} for k, v in MEASUREMENTS.items()]}

    @app.post('/api/meter/test')
    async def test_meter(data: Meter, u=Depends(administrator)):
        try:
            async with engine.meter_io_lock:
                readings = await read_meter(data.model_dump())
            return {'ok': all(not r['error'] for r in readings), 'readings': readings}
        except Exception as exc:
            return {'ok': False, 'error': str(exc)[:240], 'readings': []}

    @app.post('/api/chargers')
    async def charger(data: Charger, u=Depends(administrator)):
        old = engine.config(data.id)
        chargers = store.entities('charger')
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

    @app.post('/api/vehicles')
    async def vehicle(data: Vehicle, u=Depends(administrator)):
        others = [v for v in store.entities('vehicle') if v['id'] != data.id]
        if any(set(v['identifiers']) & set(data.identifiers) for v in others):
            raise HTTPException(409, 'Identificador já associado a outro veículo')
        store.put('vehicle', data.model_dump())
        for p in engine.ports.values():
            if p['identifier']:
                engine.identify(p, p['identifier'])
        store.record('vehicle_configured', {'actor': u['name'], 'vehicle': data.id, 'priority': data.priority})
        return {'ok': True}

    @app.post('/api/ports/{key}/action')
    async def action(key: str, data: PortAction, u=Depends(user)):
        if key not in engine.ports:
            raise HTTPException(404, 'Conector desconhecido')
        p = engine.ports[key]
        c = engine.config(p['charger'])
        if data.vehicle_id and not any(v['id'] == data.vehicle_id for v in store.entities('vehicle')):
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
    async def simulation(data: Simulation, u=Depends(administrator)):
        if store.settings()['mode'] != 'simulation':
            raise HTTPException(409, 'Simulador desativado')
        engine.other_kw = data.other_kw
        return {'ok': True}

    @app.post('/api/ports/{key}/learn')
    async def learn(key: str, data: Learning, u=Depends(administrator)):
        p = engine.ports.get(key)
        if not p or not p['running'] or data.cap_kw > p['limit_kw']:
            raise HTTPException(409, 'É necessário estar em recarga; o teste só pode reduzir o limite atual')
        if p.get('test'):
            raise HTTPException(409, 'Já existe um teste em andamento neste conector')
        p['test'] = {'cap_kw': data.cap_kw, 'started_at': time.time(),
                     'until': time.time() + data.seconds, 'observations': []}
        store.record('test_started', {'actor': u['name'], 'port': key, 'cap_kw': data.cap_kw, 'seconds': data.seconds})
        return {'ok': True}

    @app.post('/api/demo')
    async def demo(u=Depends(administrator)):
        if store.entities('charger') or store.settings()['mode'] != 'simulation':
            raise HTTPException(409, 'Demonstração disponível somente em uma instalação vazia em simulação')
        for identifier, name, power in [('DC-01', 'Estação rápida 01', 320), ('DC-02', 'Estação rápida 02', 320), ('AC-03', 'Estação AC 03', 22)]:
            c = Charger(id=identifier, name=name, max_kw=power, connector_max_kw=power, min_kw=6).model_dump(exclude={'password'})
            c.update(password_hash=None, commissioned=True, zero_supported=True)
            store.put('charger', c)
        for identifier, name, priority in [('frota-01', 'Veículo da diretoria', True), ('frota-02', 'Veículo operacional', False)]:
            store.put('vehicle', {'id': identifier, 'name': name, 'priority': priority, 'plate': '', 'identifiers': ['SIM-' + identifier]})
        engine.refresh()
        engine.connect_simulated('DC-01:1', 'frota-02')
        engine.connect_simulated('DC-02:1', 'frota-01')
        store.record('demo_created', {'actor': u['name']})
        return {'ok': True}

    @app.websocket('/ws/live')
    async def live(ws: WebSocket):
        origin = ws.headers.get('origin')
        if (origin and urlsplit(origin).netloc != ws.headers.get('host')) or not get_user(ws.cookies.get('ev_session')):
            await ws.close(code=1008)
            return
        await ws.accept()
        try:
            while get_user(ws.cookies.get('ev_session')):
                await ws.send_json(engine.snapshot())
                await asyncio.sleep(1)
            await ws.close(code=1008)
        except (WebSocketDisconnect, RuntimeError):
            pass

    @app.websocket('/ocpp/{identifier}')
    async def ocpp(ws: WebSocket, identifier: str):
        c = engine.config(identifier)
        if not c or c['transport'] != 'ocpp' or store.settings()['mode'] != 'physical':
            await ws.close(code=1008)
            return
        auth = ws.headers.get('authorization', '')
        try:
            username, password = base64.b64decode(auth.split(' ', 1)[1], validate=True).decode().split(':', 1)
        except (ValueError, IndexError, UnicodeDecodeError):
            username = password = ''
        if username != identifier or not password_matches(password, c.get('password_hash')):
            await ws.close(code=1008)
            return
        if identifier in engine.connections or 'ocpp1.6' not in ws.scope.get('subprotocols', []):
            await ws.close(code=1008)
            return
        await ws.accept(subprotocol='ocpp1.6')
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

    @app.get('/')
    async def index():
        return FileResponse(Path(__file__).parent / 'static/index.html')

    return app
