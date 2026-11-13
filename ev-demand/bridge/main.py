"""D-Max Acesso Windows 1.0.1: local company portal, never a demand controller.

Python standard library only. Google Sheets remains the account authority.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import hmac
import html
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import math
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

VERSION = '1.0.1'
ROLES = {'developer': 'Desenvolvedor', 'commercial': 'Comercial', 'technician': 'Técnico'}
LEASE = {'developer': 3600, 'commercial': 300, 'technician': 3600}
HASH_RE = re.compile(r'pbkdf2_sha256\$600000\$[0-9a-f]{32}\$[0-9a-f]{64}')
ID_RE = re.compile(r'[A-Za-z0-9_-]{1,100}')
LOGIN_RE = re.compile(r'[a-z0-9._-]{3,40}')
ROOT = Path(__file__).resolve().parent


def esc(value):
    return html.escape(str(value if value is not None else ''), quote=True)


def verifier(password):
    if not isinstance(password, str) or not 8 <= len(password) <= 200:
        raise ValueError('A senha deve ter de 8 a 200 caracteres.')
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
    return 'pbkdf2_sha256$600000$' + salt + '$' + digest


def matches(password, encoded):
    if not isinstance(encoded, str) or not HASH_RE.fullmatch(encoded) or not isinstance(password, str) or len(password) > 200:
        return False
    _, _, salt, expected = encoded.split('$')
    actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
    return hmac.compare_digest(actual, expected)


def google_url(url):
    p = urlsplit(url)
    return (p.scheme == 'https' and p.hostname == 'script.google.com' and p.port in (None, 443)
            and re.fullmatch(r'/macros/s/[A-Za-z0-9_-]+/exec', p.path)
            and not p.username and not p.password and not p.query and not p.fragment)


def remote_url(url):
    p = urlsplit(url)
    return (p.scheme == 'https' and p.port in (None, 443) and not p.username and not p.password
            and p.path in ('', '/') and not p.query and not p.fragment
            and re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.trycloudflare\.com', p.hostname or '')
            and p.hostname not in ('api.trycloudflare.com', 'www.trycloudflare.com'))


class PlatformError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class GooglePlatform:
    def request(self, config, action, **payload):
        if not google_url(config['url']):
            raise PlatformError('Informe a URL publicada do Apps Script terminada em /exec.')
        opener = build_opener(NoRedirect())
        data = json.dumps(dict(action=action, controller_id=config['controller_id'], key=config['key'], **payload)).encode()
        request = Request(config['url'], data=data, headers={'Content-Type': 'application/json'}, method='POST')
        try:
            try:
                response = opener.open(request, timeout=120 if action == 'manage_user' else 30)
            except HTTPError as redirect:
                if redirect.code not in (302, 303):
                    raise
                location = redirect.headers.get('Location', '')
                p = urlsplit(location)
                if p.scheme != 'https' or p.hostname != 'script.googleusercontent.com' or p.port not in (None, 443) or p.username or p.password:
                    raise PlatformError('O Google redirecionou para login. Confira o acesso da implantação.') from None
                # Separate GET: no password, key or custom headers in the redirect.
                response = opener.open(Request(location, method='GET'), timeout=30)
            with response:
                body = response.read(5000001)
                if len(body) > 5000000:
                    raise PlatformError('Resposta da plataforma excedeu o limite.')
                result = json.loads(body)
            if not isinstance(result, dict) or result.get('ok') is not True:
                code = result.get('code') if isinstance(result, dict) else None
                messages = {401: 'Credenciais recusadas pela plataforma.', 403: 'Perfil sem permissão para esta operação.',
                            409: 'Conflito de ID/login. Preserve identidades existentes ou use novo ID para uma nova conta.',
                            422: 'Dados de usuário inválidos. Confira os campos e a validade.',
                            429: 'Muitas tentativas. Aguarde cinco minutos.'}
                raise PlatformError(messages.get(code, 'A plataforma recusou a consulta. Confira a implantação e a planilha.'))
            return result
        except PlatformError:
            raise
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            raise PlatformError('Não foi possível consultar a plataforma. Confira a conexão e a implantação Google.') from None


class Simulator:
    def __init__(self):
        self.at = time.monotonic()
        self.limit = 60.0
        self.speed = 60
        self.other = 10.0
        self.ports = [dict(id=i, name='Carregador ' + str(i + 1), soc=20.0 + i * 10, capacity=60.0,
                           connected=i < 2, paused=False, kw=0.0, energy=0.0) for i in range(4)]

    def advance(self):
        now = time.monotonic()
        elapsed = max(0, now - self.at) * self.speed
        self.at = now
        active = [p for p in self.ports if p['connected'] and not p['paused'] and p['soc'] < 100]
        power = min(22.0, max(0.0, self.limit - self.other) / max(1, len(active)))
        for p in self.ports:
            p['kw'] = power if p in active else 0.0
            energy = min((100 - p['soc']) * p['capacity'] / 100, p['kw'] * elapsed / 3600)
            p['energy'] += energy
            p['soc'] = min(100.0, p['soc'] + energy / p['capacity'] * 100)
            if p['soc'] >= 100:
                p['kw'] = 0.0
        return dict(limit=self.limit, other=self.other, total=self.other + sum(p['kw'] for p in self.ports), ports=self.ports)

    def action(self, operation, port=None, other=None):
        self.advance()
        if operation == 'load':
            value = float(other)
            if not math.isfinite(value) or not 0 <= value <= 1000:
                raise ValueError('Carga inválida.')
            self.other = value
        else:
            if port not in range(len(self.ports)):
                raise ValueError('Carregador inválido.')
            p = self.ports[port]
            if operation == 'connect':
                if p['connected']:
                    raise ValueError('Desconecte antes de iniciar uma nova sessão.')
                p.update(connected=True, paused=False, soc=20.0, energy=0.0)
            elif operation == 'disconnect':
                p.update(connected=False, paused=False, kw=0.0)
            elif operation == 'pause':
                p['paused'] = not p['paused']
            else:
                raise ValueError('Ação inválida.')
        return self.advance()


class Bridge:
    def __init__(self, database=None, platform=None):
        self.lock = threading.RLock()
        self.sync_lock = threading.Lock()
        self.db = sqlite3.connect(str(database or ROOT / 'data' / 'bridge.sqlite3'), check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS snapshot (id INTEGER PRIMARY KEY, payload TEXT NOT NULL, at REAL NOT NULL)')
        self.db.commit()
        self.platform = platform or GooglePlatform()
        self.sessions = {}
        self.secret = secrets.token_bytes(32)
        self.attempts = {}
        self.db.execute('CREATE TABLE IF NOT EXISTS installation (id INTEGER PRIMARY KEY, identity TEXT NOT NULL)')
        self.db.execute('INSERT OR IGNORE INTO installation VALUES (1,?)', ('WIN-' + secrets.token_hex(12),))
        self.db.commit()
        self.identity = self.db.execute('SELECT identity FROM installation WHERE id=1').fetchone()[0]
        self.stop = threading.Event()
        self.last_error = ''
        self.clients = []
        self.clients_at = 0.0
        self.client_lock = threading.Lock()

    def config(self):
        with self.lock:
            row = self.db.execute('SELECT payload FROM config WHERE id=1').fetchone()
            return json.loads(row[0]) if row else None

    def configure(self, url, key, controller_id):
        if not google_url(url) or not ID_RE.fullmatch(controller_id) or not 32 <= len(key) <= 512:
            raise ValueError('Confira a URL /exec, o identificador e a chave da central.')
        config = dict(url=url, key=key, controller_id=controller_id)
        # Validate the credentials and roster before replacing working config.
        snapshot = self.platform.request(config, 'snapshot')
        self.validate_snapshot(snapshot)
        with self.lock, self.db:
            self.db.execute('INSERT OR REPLACE INTO config VALUES (1,?)', (json.dumps(config),))
            self.save_snapshot(snapshot)
            self.clients, self.clients_at = [], 0
            self.sessions.clear()
        return True

    @staticmethod
    def validate_snapshot(data):
        if data.get('complete') is not True or not isinstance(data.get('accounts'), list) or not isinstance(data.get('technicians'), list):
            raise PlatformError('Atualize a implantação do Apps Script para o cadastro unificado de usuários.')
        ids, names = set(), set()
        for r in data['accounts'] + data['technicians']:
            if (not isinstance(r, dict) or not ID_RE.fullmatch(str(r.get('id', ''))) or not LOGIN_RE.fullmatch(str(r.get('name', '')))
                or r.get('role') not in ROLES or not HASH_RE.fullmatch(str(r.get('password', '')))
                or r['id'] in ids or r['name'] in names or r['name'] in ('root', 'admin')
                or type(r.get('active')) is not bool or type(r.get('deleted')) is not bool
                or (r.get('expires_at') is not None and (type(r['expires_at']) not in (int, float) or not math.isfinite(r['expires_at'])))):
                raise PlatformError('Cadastro inválido ou duplicado na plataforma; última lista preservada.')
            ids.add(r['id']); names.add(r['name'])

    def save_snapshot(self, data):
        minimal = dict(accounts=data['accounts'], technicians=data['technicians'])
        self.db.execute('INSERT OR REPLACE INTO snapshot VALUES (1,?,?)', (json.dumps(minimal), time.time()))

    def sync(self):
        with self.sync_lock:
            config = self.config()
            if not config:
                return False
            try:
                data = self.platform.request(config, 'snapshot')
                self.validate_snapshot(data)
                with self.lock, self.db:
                    self.save_snapshot(data)
                    self.last_error = ''
                    self.prune_sessions()
                return True
            except (PlatformError, ValueError):
                self.last_error = 'Sem sincronização. A última autorização não foi renovada.'
                return False

    def users(self):
        with self.lock:
            row = self.db.execute('SELECT payload,at FROM snapshot WHERE id=1').fetchone()
            if not row:
                return [], 0
            data = json.loads(row[0])
            return data['accounts'] + data['technicians'], row[1]

    def usable(self, row):
        _, at = self.users()
        return bool(row and row['role'] in ROLES and row['active'] and not row['deleted']
                    and not row.get('must_change') and (row.get('expires_at') is None or time.time() < row['expires_at'])
                    and 0 <= time.time() - at < LEASE[row['role']])

    def prune_sessions(self):
        users = {r['id']: r for r in self.users()[0]}
        now = time.time()
        for token, session in list(self.sessions.items()):
            row = users.get(session['id'])
            if (not self.usable(row) or self.fingerprint(row) != session['fingerprint']
                    or now - session['seen'] > (900 if row and row['role'] == 'commercial' else 3600)):
                del self.sessions[token]

    @staticmethod
    def fingerprint(row):
        return hashlib.sha256(json.dumps([row.get(k) for k in ('id', 'name', 'role', 'password', 'active', 'deleted', 'expires_at')]).encode()).hexdigest()

    def limited(self, address):
        with self.lock:
            now = time.monotonic()
            self.attempts = {k: [t for t in v if now - t < 300] for k, v in self.attempts.items() if any(now - t < 300 for t in v)}
            entries = self.attempts.setdefault(address, [])
            if len(entries) >= 8:
                raise ValueError('Muitas tentativas. Aguarde cinco minutos.')
            entries.append(now)

    def login(self, name, password, address='local'):
        self.limited(address)
        self.sync()
        with self.lock:
            row = next((r for r in self.users()[0] if r['name'] == name.strip().lower()), None)
        # Equal-cost invalid credential check, including unknown usernames.
        encoded = row['password'] if row else 'pbkdf2_sha256$600000$' + '0' * 32 + '$' + '0' * 64
        verified = matches(password, encoded)
        with self.lock:
            latest = next((r for r in self.users()[0] if row and r['id'] == row['id']), None)
            if not verified or not self.usable(latest) or self.fingerprint(latest) != self.fingerprint(row):
                raise ValueError('Login, senha, situação ou validade inválidos. Contas com troca inicial pendente devem ser regularizadas no D-Max.')
            token = secrets.token_urlsafe(32)
            self.sessions[token] = dict(id=row['id'], fingerprint=self.fingerprint(row), seen=time.time(), simulator=Simulator())
            return token

    def session(self, token, touch=True):
        with self.lock:
            self.prune_sessions()
            session = self.sessions.get(token)
            if session:
                if touch:
                    session['seen'] = time.time()
                row = next((r for r in self.users()[0] if r['id'] == session['id']), None)
                return row, session
            return None, None

    def catalog(self, force=False):
        with self.client_lock:
            if not force and time.time() - self.clients_at < 30:
                return self.clients
            data = self.platform.request(self.config(), 'remote_directory')
            entries = data.get('clients')
            if not isinstance(entries, list) or len(entries) > 1000:
                raise PlatformError('Catálogo inválido.')
            seen, clients = set(), []
            for r in entries:
                if (not isinstance(r, dict) or not isinstance(r.get('controller_id'), str) or not ID_RE.fullmatch(r['controller_id'])
                        or r['controller_id'] in seen or not isinstance(r.get('site_name'), str) or not 1 <= len(r['site_name']) <= 100
                        or not isinstance(r.get('url'), str) or not remote_url(r['url']) or type(r.get('connected')) is not bool
                        or type(r.get('updated_at')) not in (int, float) or not math.isfinite(r['updated_at'])
                        or not 0 < r['updated_at'] <= time.time() + 300):
                    raise PlatformError('Registro inválido no catálogo de clientes.')
                seen.add(r['controller_id']); clients.append(r)
            self.clients = sorted(clients, key=lambda r: r['site_name'].casefold())
            self.clients_at = time.time()
            return self.clients

    def manage(self, token, fields):
        row, _ = self.session(token)
        if not row or row['role'] != 'developer':
            raise ValueError('Somente desenvolvedor pode gerenciar usuários.')
        self.limited('manage:' + row['id'])
        password = fields.get('actor_password', '')
        if not matches(password, row['password']):
            raise ValueError('Senha do desenvolvedor inválida.')
        identifier = fields.get('id') or 'USR-' + secrets.token_hex(8)
        name, full = fields.get('name', '').strip().lower(), fields.get('full_name', '').strip()
        role, status = fields.get('role'), fields.get('status')
        if (not ID_RE.fullmatch(identifier) or not LOGIN_RE.fullmatch(name) or name in ('root', 'admin') or not 1 <= len(full) <= 100
                or role not in ROLES or status not in ('ativo', 'bloqueado', 'excluido')):
            raise ValueError('Confira nome, login, perfil e situação.')
        old = next((r for r in self.users()[0] if r['id'] == identifier), None)
        if old and old['name'] != name:
            raise ValueError('Para outro login, crie uma nova conta e exclua a anterior. O histórico será preservado.')
        new_password = fields.get('password', '')
        if new_password != fields.get('confirmation', ''):
            raise ValueError('As senhas novas não coincidem.')
        encoded = verifier(new_password) if new_password else old['password'] if old else None
        if not encoded:
            raise ValueError('Defina uma senha para a nova conta.')
        until = fields.get('expires', '').strip()
        if until:
            try:
                datetime.strptime(until, '%Y-%m-%d')
            except ValueError:
                raise ValueError('Validade deve ser uma data válida.') from None
        record = dict(id=identifier, name=name, full_name=full, role=role, status=status, expires=until, password=encoded)
        result = self.platform.request(self.config(), 'manage_user', actor_login=row['name'], actor_password=password, record=record)
        if result.get('acknowledged_id') != identifier:
            raise PlatformError('Confirmação inválida. Atualize a lista antes de repetir.')
        with self.lock:
            self.attempts.pop('manage:' + row['id'], None)
        self.sync()
        return record

    def loop(self):
        while not self.stop.wait(60):
            self.sync()
            with self.lock:
                self.prune_sessions()


def field(label, name, value='', kind='text', extra=''):
    return '<label>' + esc(label) + '<input name="' + esc(name) + '" type="' + esc(kind) + '" value="' + esc(value) + '" ' + extra + '></label>'


def choose(label, name, options, selected):
    return '<label>' + esc(label) + '<select name="' + esc(name) + '">' + ''.join('<option value="' + esc(k) + '"' + (' selected' if k == selected else '') + '>' + esc(v) + '</option>' for k, v in options.items()) + '</select></label>'


def handler_for(bridge):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'D-Max-Acesso/1.0.1'

        def log_message(self, format, *args):
            # No query strings, request bodies, credentials or remote addresses.
            pass

        def cookie(self, name):
            jar = cookies.SimpleCookie()
            try:
                jar.load(self.headers.get('Cookie', ''))
                return jar[name].value if name in jar else ''
            except cookies.CookieError:
                return ''

        def context(self):
            self.nonce = secrets.token_urlsafe(32)
            self.token = ''
            self.user, self.current = None, None
            self.path_only = urlsplit(self.path).path
            expected = {'127.0.0.1:' + str(self.server.server_port), 'localhost:' + str(self.server.server_port)}
            if self.headers.get('Host', '').lower() not in expected or self.client_address[0] not in ('127.0.0.1', '::1'):
                raise ValueError('A central aceita somente acesso local neste computador.')
            self.nonce = self.cookie('bridge_nonce')
            if not re.fullmatch(r'[A-Za-z0-9_-]{32,64}', self.nonce):
                self.nonce = secrets.token_urlsafe(32)
            self.token = self.cookie('bridge_session')
            self.user, self.current = bridge.session(self.token)
            self.path_only = urlsplit(self.path).path
            self.query = parse_qs(urlsplit(self.path).query)

        def csrf(self, action):
            return hmac.new(bridge.secret, (self.nonce + '\n' + self.token + '\n' + action).encode(), hashlib.sha256).hexdigest()

        def form(self, action, content='', button='Salvar'):
            return '<form method="post" action="' + esc(action) + '"><input type="hidden" name="csrf" value="' + self.csrf(action) + '">' + content + '<button>' + esc(button) + '</button></form>'

        def response(self, body='', status=200, content_type='text/html; charset=utf-8', location=None, session=None):
            payload = body.encode() if isinstance(body, str) else body
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'same-origin')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'; object-src 'none'; require-trusted-types-for 'script'; trusted-types 'none'")
            self.send_header('Set-Cookie', 'bridge_nonce=' + self.nonce + '; HttpOnly; SameSite=Strict; Path=/')
            if session is not None or self.user:
                value = session if session is not None else self.token
                lifetime = '900' if self.user and self.user['role'] == 'commercial' else '3600'
                self.send_header('Set-Cookie', 'bridge_session=' + value + '; HttpOnly; SameSite=Strict; Path=/; Max-Age=' + (lifetime if value else '0'))
            if location:
                self.send_header('Location', location)
            self.end_headers()
            self.wfile.write(payload)

        def page(self, title, content, note='', status=200):
            if self.user:
                nav = '<a href="/">Visão geral</a><a href="/simulation">Simulação</a>'
                if self.user['role'] == 'developer':
                    nav += '<a href="/users">Usuários</a><a href="/settings">Configurações</a>'
                nav += '<div class="identity"><b>' + esc(self.user['full_name']) + '</b><span>' + ROLES[self.user['role']] + '</span>' + self.form('/logout', button='Sair') + '</div>'
                sidebar = '<aside><div class="brand">D-Max<span>by EnergyCube</span></div><p>ACESSO WINDOWS · v1.0.1</p><nav>' + nav + '</nav></aside>'
            else:
                sidebar = ''
            markup = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>' + esc(title) + ' · D-Max Acesso</title><link rel="stylesheet" href="/style.css"><script src="/portal.js" defer></script></head><body>' + sidebar + '<main><header><h1>' + esc(title) + '</h1><span>D-Max Acesso · v1.0.1</span></header>' + ('<p class="notice" role="status">' + esc(note) + '</p>' if note else '') + content + '</main></body></html>'
            self.response(markup, status)

        def settings(self, note=''):
            config = bridge.config()
            if config and (not self.user or self.user['role'] != 'developer'):
                return self.page('Acesso negado', '<p>Somente desenvolvedor pode configurar esta central.</p>', status=403)
            identifier = config['controller_id'] if config else bridge.identity
            fields = field('Identificador desta central', 'controller_id', identifier, extra='required readonly')
            fields += '<p>Na planilha, use D-Max → Autorizar um D-Max e informe o identificador acima. Cada computador deve ter sua própria chave.</p>'
            fields += field('URL publicada do Apps Script', 'url', config['url'] if config else '', 'url', 'required maxlength="1000"')
            fields += field('Chave desta central' + (' · vazio mantém' if config else ''), 'key', '', 'password', 'autocomplete="new-password" maxlength="512"')
            if config:
                fields += field('Sua senha de desenvolvedor', 'actor_password', '', 'password', 'required autocomplete="current-password"')
            self.page('Configuração inicial' if not config else 'Configurações', '<section>' + self.form('/settings', fields, 'Validar e salvar') + '</section>', note)

        def login_page(self, note='', status=200):
            fields = field('Login', 'name', extra='required autocomplete="username" maxlength="40"')
            fields += field('Senha', 'password', '', 'password', 'required autocomplete="current-password" maxlength="200"')
            self.page('Entrar na central', '<section class="login"><div class="brand">D-Max<span>by EnergyCube</span></div><p>Acesso aos clientes e demonstração local de funcionamento.</p>' + self.form('/login', fields, 'Entrar') + '</section>', note, status)

        def overview(self, note=''):
            text = '<section><form method="get" action="/"><label>Buscar cliente<input name="q" value="' + esc(self.query.get('q', [''])[0][:100]) + '"></label><button>Buscar</button></form><a class="button secondary" href="/?refresh=1">Atualizar clientes</a></section><div class="cards" id="clients">'
            try:
                clients = bridge.catalog(force='refresh' in self.query)
                q = self.query.get('q', [''])[0][:100].casefold()
                rows = [r for r in clients if q in (r['site_name'] + ' ' + r['controller_id']).casefold()]
                for r in rows:
                    recent = time.time() - r['updated_at'] <= 900
                    connected = recent and r['connected']
                    text += '<section class="client"><span class="badge ' + ('online' if connected else '') + '">' + ('Conectado · último informe' if connected else 'Sem conexão recente confirmada') + '</span><h2>' + esc(r['site_name']) + '</h2><small>Último informe: ' + esc(datetime.fromtimestamp(r['updated_at']).strftime('%d/%m/%Y %H:%M')) + '</small><a class="button" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer" href="/open?' + esc(urlencode({'id': r['controller_id']})) + '">Acessar cliente</a></section>'
                if not rows:
                    text += '<section>Nenhum cliente encontrado.</section>'
                text += '</div><p>O botão abre o D-Max do cliente em outra aba. Entre nele com seu login. O estado listado é o último informado pelo equipamento.</p>'
            except PlatformError as e:
                text += '<section>' + esc(e) + '</section></div>'
            if self.user['role'] == 'commercial':
                text += '<p>Comercial: use Simulação para demonstrar. Ao entrar como comercial no D-Max 0.14.x, a demonstração também fica isolada dos carregamentos reais.</p>'
            self.page('Visão geral', text, note or bridge.last_error)

        def users_page(self, note='', generated=None):
            if self.user['role'] != 'developer':
                return self.page('Acesso negado', '', status=403)
            users = bridge.users()[0]
            text = '<section><h2>Membros da empresa</h2><p>Contas gerenciadas na planilha. Mudanças exigem sua senha de desenvolvedor.</p><div class="table"><table><tr><th>Nome</th><th>Login</th><th>Perfil</th><th>Situação</th><th></th></tr>'
            for r in users:
                text += '<tr><td>' + esc(r['full_name']) + '</td><td>' + esc(r['name']) + '</td><td>' + ROLES[r['role']] + '</td><td>' + ('Excluído' if r['deleted'] else 'Ativo' if r['active'] else 'Bloqueado') + '</td><td><a href="/users?' + esc(urlencode({'edit': r['id']})) + '">Editar</a></td></tr>'
            text += '</table></div><a href="/users">Criar novo membro</a></section>'
            old = next((r for r in users if r['id'] == self.query.get('edit', [''])[0]), None)
            r = old or dict(id='', name='', full_name='', role='commercial', expires_at=None, active=True, deleted=False)
            fields = field('ID · gerado automaticamente para novos membros', 'id', r['id'], extra='readonly')
            fields += field('Nome completo', 'full_name', r['full_name'], extra='required maxlength="100"')
            fields += field('Login', 'name', r['name'], extra='required minlength="3" maxlength="40"' + (' readonly' if old else ''))
            fields += choose('Perfil', 'role', ROLES, r['role'])
            fields += choose('Situação', 'status', {'ativo': 'Ativo', 'bloqueado': 'Bloqueado', 'excluido': 'Excluído'}, 'excluido' if r['deleted'] else 'ativo' if r['active'] else 'bloqueado')
            fields += field('Validade · vazio não expira', 'expires', datetime.fromtimestamp(r['expires_at']).strftime('%Y-%m-%d') if r['expires_at'] else '', 'date')
            fields += field('Nova senha · 8 a 200 caracteres' + (' · vazio mantém' if old else ''), 'password', '', 'password', 'minlength="8" maxlength="200" autocomplete="new-password"' + ('' if old else ' required'))
            fields += field('Confirme a nova senha', 'confirmation', '', 'password', 'maxlength="200" autocomplete="new-password"')
            fields += field('Sua senha de desenvolvedor · autorizar alteração', 'actor_password', '', 'password', 'required maxlength="200" autocomplete="current-password"')
            text += '<section><h2>' + ('Editar membro' if old else 'Novo membro') + '</h2>' + self.form('/users', fields, 'Salvar na planilha e gerar verificador') + '<p>Para mudar um login, crie uma nova conta e marque a anterior como excluída. IDs anteriores preservam a auditoria.</p></section>'
            if generated:
                output = io.StringIO(); csv.writer(output, delimiter='\t', lineterminator='').writerow([generated['id'], generated['full_name'], generated['name'], generated['role'], generated['status'], generated['expires'], generated['password']])
                text += '<section><h2>Cadastro confirmado na planilha</h2><p>Verificador gerado, sem armazenar a senha em texto. Guarde este dado como uma credencial.</p><textarea readonly rows="4">' + esc(output.getvalue()) + '</textarea></section>'
            self.page('Usuários', text, note)

        def simulation(self):
            with bridge.lock:
                state = self.current['simulator'].advance()
            text = '<section><h2>Demonstração local</h2><p>Dados fictícios desta sessão. Nenhuma conexão com carregadores reais. Ao sair, a demonstração é descartada.</p><p>Bateria fictícia de 60 kWh; encerra em 100%. Tempo acelerado 60× para demonstração.</p><strong id="sim-total">' + format(state['total'], '.1f') + ' kW</strong><span> de 60 kW disponíveis</span>'
            text += self.form('/simulation', '<input type="hidden" name="operation" value="load">' + field('Outras cargas · kW', 'other', state['other'], 'number', 'min="0" max="1000" step="0.1" required'), 'Aplicar carga') + '</section><div class="cards">'
            for p in state['ports']:
                text += '<section><h2>' + p['name'] + '</h2><p id="sim-status-' + str(p['id']) + '">' + self.sim_status(p) + '</p><strong id="sim-soc-' + str(p['id']) + '">' + format(p['soc'], '.1f') + '%</strong><p id="sim-power-' + str(p['id']) + '">' + format(p['kw'], '.1f') + ' kW</p>'
                text += self.form('/simulation', '<input type="hidden" name="port" value="' + str(p['id']) + '"><input type="hidden" name="operation" value="' + ('disconnect' if p['connected'] else 'connect') + '">', 'Desconectar' if p['connected'] else 'Conectar veículo')
                if p['connected']:
                    text += self.form('/simulation', '<input type="hidden" name="port" value="' + str(p['id']) + '"><input type="hidden" name="operation" value="pause">', 'Retomar' if p['paused'] else 'Pausar')
                text += '</section>'
            self.page('Simulação', text + '</div><div id="sim-live" role="status"></div>')

        @staticmethod
        def sim_status(p):
            return 'Sem veículo' if not p['connected'] else 'Carga completa' if p['soc'] >= 100 else 'Pausado' if p['paused'] else 'Carregando' if p['kw'] > 0 else 'Aguardando potência'

        def do_GET(self):
            try:
                self.context()
                static = {'/style.css': ('style.css', 'text/css'), '/portal.js': ('portal.js', 'application/javascript')}
                if self.path_only in static:
                    name, kind = static[self.path_only]
                    return self.response((ROOT / name).read_bytes(), content_type=kind)
                if self.path_only not in ('/', '/settings', '/users', '/simulation', '/open', '/api/simulation'):
                    return self.page('Página não encontrada', '', status=404)
                if not bridge.config():
                    return self.settings()
                if not self.user:
                    if self.path_only.startswith('/api/'):
                        return self.response('{"error":"Sessão encerrada"}', 401, 'application/json')
                    return self.login_page()
                if self.path_only == '/settings':
                    return self.settings()
                if self.path_only == '/users':
                    return self.users_page()
                if self.path_only == '/simulation':
                    return self.simulation()
                if self.path_only == '/api/simulation':
                    with bridge.lock:
                        data = self.current['simulator'].advance()
                        payload = json.dumps(data)
                    return self.response(payload, content_type='application/json')
                if self.path_only == '/open':
                    target = next((r for r in bridge.catalog() if r['controller_id'] == self.query.get('id', [''])[0]), None)
                    if not target:
                        return self.page('Cliente indisponível', '<a href="/">Voltar</a>', status=404)
                    return self.response('', 302, location=target['url'])
                return self.overview()
            except (ValueError, PlatformError) as e:
                return self.page('Não foi possível concluir', '<a href="/">Voltar</a>', str(e), 400)

        def do_POST(self):
            try:
                self.context()
                origin = self.headers.get('Origin')
                if origin and origin != 'http://' + self.headers['Host']:
                    raise ValueError('Origem recusada.')
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 20000 or self.headers.get('Transfer-Encoding'):
                    raise ValueError('Formulário inválido.')
                data = parse_qs(self.rfile.read(size).decode(), keep_blank_values=True)
                fields = {k: v[0] for k, v in data.items()}
                if not hmac.compare_digest(fields.get('csrf', ''), self.csrf(self.path_only)):
                    raise ValueError('Formulário expirou. Atualize a página.')
                if self.path_only == '/login' and bridge.config():
                    token = bridge.login(fields.get('name', ''), fields.get('password', ''))
                    return self.response('', 303, location='/', session=token)
                if self.path_only == '/logout':
                    with bridge.lock:
                        bridge.sessions.pop(self.token, None)
                    return self.response('', 303, location='/', session='')
                if self.path_only == '/settings':
                    config = bridge.config()
                    if config and (not self.user or self.user['role'] != 'developer' or not matches(fields.get('actor_password', ''), self.user['password'])):
                        raise ValueError('Somente desenvolvedor autenticado pode configurar.')
                    bridge.configure(fields.get('url', '').strip(), fields.get('key') or (config['key'] if config else ''), config['controller_id'] if config else bridge.identity)
                    return self.response('', 303, location='/', session='')
                if not self.user:
                    raise ValueError('Entre novamente na central.')
                if self.path_only == '/users':
                    generated = bridge.manage(self.token, fields)
                    self.user, self.current = bridge.session(self.token)
                    if not self.user:
                        return self.response('', 303, location='/', session='')
                    return self.users_page('Alteração confirmada na planilha.', generated)
                if self.path_only == '/simulation':
                    with bridge.lock:
                        self.current['simulator'].action(fields.get('operation'), int(fields['port']) if fields.get('port') else None, fields.get('other'))
                    return self.response('', 303, location='/simulation')
                raise ValueError('Operação não disponível nesta central.')
            except (ValueError, PlatformError) as e:
                if self.path_only == '/login':
                    return self.login_page(str(e), 400)
                return self.page('Não foi possível concluir', '<a href="/">Voltar</a>', str(e), 400)

    return Handler


def verify_package():
    manifest = ROOT / 'SHA256SUMS.txt'
    if not manifest.is_file():
        raise ValueError('SHA256SUMS.txt ausente. Extraia o ZIP completo antes de iniciar.')
    expected_names = {'DMaxAcesso.py', 'style.css', 'portal.js', 'LEIA-ME.md'}
    entries = {}
    for line in manifest.read_text(encoding='utf-8').splitlines():
        digest, name = line.split('  ', 1)
        if name not in expected_names or name in entries or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Manifesto inválido. Obtenha novamente o pacote completo.')
        path = ROOT / name
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Arquivo ausente ou alterado: ' + name)
        entries[name] = digest
    if set(entries) != expected_names:
        raise ValueError('Manifesto incompleto.')


def main():
    parser = argparse.ArgumentParser(description='D-Max Acesso Windows 1.0.1')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    verify_package()
    (ROOT / 'data').mkdir(exist_ok=True)
    bridge = Bridge()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(bridge))
    server.daemon_threads = True
    threading.Thread(target=bridge.loop, daemon=True).start()
    url = 'http://127.0.0.1:' + str(server.server_port)
    print('D-Max Acesso Windows v1.0.1 · ' + url, flush=True)
    print('Abra o endereço acima no navegador deste computador.', flush=True)
    print('Central de acesso e simulação. Ctrl+C encerra. Não é controlador de demanda.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        bridge.stop.set()
        server.server_close()


if __name__ == '__main__':
    main()
