"""Account lifecycle, permissions and durable offline directory cache."""
from datetime import datetime, timezone
import hashlib
import json
import re
import time
import uuid

from .store import password_hash, password_matches

INITIAL_PASSWORD = '12345678'
ROLES = ('operator', 'admin', 'technician', 'root')
TECHNICAL = ('root', 'technician')
MANAGERS = ('root', 'technician', 'admin')
DIRECTORY_DEFAULTS = {'url': '', 'interval_s': 300, 'enabled': False}


def username(value):
    value = value.strip().lower()
    if not re.fullmatch(r'[a-z0-9._-]{3,40}', value):
        raise ValueError('Login: use de 3 a 40 letras minúsculas, números, ponto, hífen ou sublinhado')
    return value


def expiry(value):
    if value in (None, ''):
        return None
    if isinstance(value, bool):
        raise ValueError('Validade inválida')
    if isinstance(value, (float, int)):
        import math
        if not math.isfinite(value) or value < 0:
            raise ValueError('Validade inválida')
        return float(value)
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('Informe a validade com fuso horário')
        return parsed.timestamp()
    except (ValueError, TypeError):
        raise ValueError('Validade deve ser uma data/hora ISO com fuso')


def valid_hash(value):
    if not isinstance(value, str):
        return False
    parts = value.split('$')
    return (len(parts) == 4 and parts[0] == 'pbkdf2_sha256' and parts[1] == '600000'
            and bool(re.fullmatch('[0-9a-f]{32}', parts[2]))
            and bool(re.fullmatch('[0-9a-f]{64}', parts[3])))


class Access:
    def __init__(self, store):
        self.store, self.db = store, store.db
        columns = {r['name'] for r in self.db.execute('PRAGMA table_info(users)')}
        if 'id' not in columns and self.db.execute('SELECT COUNT(*) FROM users').fetchone()[0]:
            # A stable SQLite backup protects pre-existing users before schema migration.
            import sqlite3
            from pathlib import Path
            path = self.db.execute('PRAGMA database_list').fetchone()['file']
            if path:
                backup = Path(path).with_name(Path(path).name + f'.before-users-v03-{time.time_ns()}.sqlite3')
                backup.touch(mode=0o600, exist_ok=False)
                destination = sqlite3.connect(backup)
                try:
                    self.db.backup(destination)
                finally:
                    destination.close()
        additions = {'id': 'TEXT', 'full_name': "TEXT NOT NULL DEFAULT ''", 'active': 'INTEGER NOT NULL DEFAULT 1',
                     'deleted': 'INTEGER NOT NULL DEFAULT 0', 'expires_at': 'REAL', 'source': "TEXT NOT NULL DEFAULT 'local'",
                     'must_change': 'INTEGER NOT NULL DEFAULT 0', 'activation_hash': 'TEXT',
                     'can_emergency': 'INTEGER NOT NULL DEFAULT 0', 'epoch': 'INTEGER NOT NULL DEFAULT 0',
                     'credential_version': 'INTEGER NOT NULL DEFAULT 1', 'meta_version': 'INTEGER NOT NULL DEFAULT 0'}
        for name, declaration in additions.items():
            if name not in columns:
                self.db.execute(f'ALTER TABLE users ADD COLUMN {name} {declaration}')
        login_columns = {r['name'] for r in self.db.execute('PRAGMA table_info(logins)')}
        if 'epoch' not in login_columns:
            self.db.execute('ALTER TABLE logins ADD COLUMN epoch INTEGER NOT NULL DEFAULT 0')
        for row in self.db.execute('SELECT name FROM users WHERE id IS NULL').fetchall():
            self.db.execute('UPDATE users SET id=?,full_name=? WHERE name=?', (uuid.uuid4().hex, row['name'], row['name']))
        self.db.executescript('''
            CREATE UNIQUE INDEX IF NOT EXISTS users_identity ON users(id);
            CREATE TABLE IF NOT EXISTS directory_config (id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS directory_pending (user_id TEXT PRIMARY KEY,kind TEXT NOT NULL,payload TEXT NOT NULL,queued_at REAL);
            CREATE TABLE IF NOT EXISTS directory_secret (id INTEGER PRIMARY KEY CHECK(id=1),token TEXT NOT NULL);
        ''')
        self.db.execute('INSERT OR IGNORE INTO directory_config VALUES (1,?)', (json.dumps(DIRECTORY_DEFAULTS),))
        self.db.commit()
        self.status = {'message': 'Não configurada', 'last_success': None, 'last_attempt': None, 'next_attempt': None}
        self.lock = None  # Bound lazily to the serving event loop.
        self.wakeup = None

    def config(self):
        return json.loads(self.db.execute('SELECT payload FROM directory_config WHERE id=1').fetchone()[0])

    def configure(self, data):
        with self.db:
            self.db.execute('UPDATE directory_config SET payload=? WHERE id=1', (json.dumps(data),))
        if self.wakeup:
            self.wakeup.set()

    def device_token(self):
        import os
        configured = os.getenv('DMAX_DIRECTORY_TOKEN')
        row = self.db.execute('SELECT token FROM directory_secret WHERE id=1').fetchone()
        return configured or (row['token'] if row else None)

    def set_device_token(self, token):
        with self.db:
            self.db.execute('INSERT INTO directory_secret VALUES (1,?) ON CONFLICT(id) DO UPDATE SET token=excluded.token', (token,))

    def by_name(self, name):
        row = self.db.execute('SELECT * FROM users WHERE name=?', (name,)).fetchone()
        return dict(row) if row else None

    def by_id(self, identifier):
        row = self.db.execute('SELECT * FROM users WHERE id=?', (identifier,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def usable(row):
        return bool(row and row['active'] and not row['deleted']
                    and (row['expires_at'] is None or time.time() < row['expires_at']))

    @staticmethod
    def public(row):
        data = {k: row[k] for k in ('id', 'name', 'full_name', 'role', 'active', 'deleted', 'expires_at',
                                    'source', 'must_change', 'can_emergency')}
        for key in ('active','deleted','must_change','can_emergency'):
            data[key] = bool(data[key])
        return data

    def list_for(self, actor):
        allowed = {'root': ROLES, 'technician': ('operator', 'admin'), 'admin': ('operator',)}.get(actor['role'], ())
        return [self.public(dict(r)) for r in self.db.execute('SELECT * FROM users ORDER BY full_name,name') if r['role'] in allowed]

    def session(self, token):
        if not token:
            return None
        row = self.db.execute('''SELECT u.*,l.expires AS session_expires,l.epoch AS session_epoch
            FROM logins l JOIN users u ON u.name=l.username WHERE l.token=?''',
                              (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if not row:
            return None
        data = dict(row)
        if not self.usable(data) or data['epoch'] != data['session_epoch'] or data['session_expires'] <= time.time():
            return None
        return self.public(data)

    def revoke(self, name):
        self.db.execute('DELETE FROM logins WHERE username=?', (name,))
        self.db.execute('UPDATE users SET epoch=epoch+1 WHERE name=?', (name,))

    def authorize_management(self, actor, target_role, target=None):
        allowed = {'root': ('operator', 'admin', 'technician'), 'technician': ('operator', 'admin'), 'admin': ('operator',)}
        roles = allowed.get(actor['role'], ())
        if target_role not in roles or (target and target['role'] not in roles):
            raise PermissionError('Seu perfil não pode gerenciar essa conta')
        if target and target['id'] == actor['id']:
            raise PermissionError('Use a alteração de senha da própria conta')

    def create(self, actor, name, full_name, role, expires_at=None, can_emergency=False):
        self.authorize_management(actor, role)
        name = username(name)
        if self.by_name(name):
            raise ValueError('Login já existe, inclusive em conta desativada')
        identifier = uuid.uuid4().hex
        source = 'local_pending' if role == 'technician' else 'local'
        with self.db:
            self.db.execute('''INSERT INTO users (name,password,role,id,full_name,expires_at,source,must_change,activation_hash,can_emergency)
                VALUES (?,?,?,?,?,?,?,1,?,?)''', (name, password_hash(INITIAL_PASSWORD), role, identifier, full_name,
                expiry(expires_at), source, None, int(can_emergency)))
            if role == 'technician':
                self.queue(identifier, 'register', self.directory_record(self.by_id(identifier)))
        self.store.record('user_created', {'actor': actor['name'], 'user_id': identifier, 'login': name, 'role': role})
        return self.public(self.by_id(identifier))

    @staticmethod
    def directory_record(row):
        data = {k: row[k] for k in ('id', 'name', 'full_name', 'active', 'deleted', 'expires_at', 'password',
                                    'activation_hash', 'must_change', 'credential_version', 'meta_version')}
        data['activation_hash'] = None
        return data

    def queue(self, identifier, kind, payload):
        # This protected local table is deliberately separate from telemetry/audit.
        existing = self.db.execute('SELECT * FROM directory_pending WHERE user_id=?', (identifier,)).fetchone()
        old = json.loads(existing['payload']) if existing else {}
        operations = set(old.get('operations', [])) | {kind}
        payload = dict(payload)
        payload['operations'] = sorted(operations)
        payload['base_version'] = old.get('base_version', payload.get('base_version', payload['credential_version']))
        payload['base_meta_version'] = old.get('base_meta_version', payload.get('meta_version', 0))
        kind = 'register' if 'register' in operations else 'update'
        self.db.execute('''INSERT INTO directory_pending VALUES (?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
            kind=excluded.kind,payload=excluded.payload,queued_at=excluded.queued_at''',
                        (identifier, kind, json.dumps(payload), time.time()))

    def update(self, actor, identifier, data):
        target = self.by_id(identifier)
        if not target:
            raise ValueError('Conta não encontrada')
        self.authorize_management(actor, data.get('role', target['role']), target)
        if target['source'] != 'local' and data.get('role', target['role']) != 'technician':
            raise ValueError('Não altere o perfil de uma conta global de técnico')
        if data.get('role') == 'technician' and target['name'] in ('root','admin'):
            raise ValueError('Cadastre um login individual para o técnico')
        with self.db:
            self.db.execute('UPDATE users SET full_name=?,role=?,active=?,expires_at=?,can_emergency=?,deleted=? WHERE id=?',
                (data['full_name'], data.get('role', target['role']), int(data['active']), expiry(data.get('expires_at')),
                 int(data.get('can_emergency', False)), int(data.get('deleted', False)), identifier))
            self.revoke(target['name'])
            updated = self.by_id(identifier)
            if updated['role'] == 'technician':
                pending = self.db.execute('SELECT kind FROM directory_pending WHERE user_id=?', (identifier,)).fetchone()
                promoted = target['role'] != 'technician'
                if promoted:
                    self.db.execute("UPDATE users SET source='local_pending' WHERE id=?", (identifier,))
                self.queue(identifier, 'register' if promoted or (pending and pending['kind'] == 'register') else 'metadata', self.directory_record(updated))
        self.store.record('user_updated', {'actor': actor['name'], 'user_id': identifier, 'active': bool(updated['active']),
                                          'deleted': bool(updated['deleted']), 'role': updated['role']})
        return self.public(updated)

    def reset_password(self, actor, identifier):
        target = self.by_id(identifier)
        if not target:
            raise ValueError('Conta não encontrada')
        self.authorize_management(actor, target['role'], target)
        with self.db:
            self.db.execute('UPDATE users SET password=?,activation_hash=?,must_change=1,credential_version=credential_version+1 WHERE id=?',
                            (password_hash(INITIAL_PASSWORD), None, identifier))
            self.revoke(target['name'])
            if target['role'] == 'technician':
                pending = self.db.execute('SELECT kind FROM directory_pending WHERE user_id=?', (identifier,)).fetchone()
                self.queue(identifier, 'register' if pending and pending['kind'] == 'register' else 'credential', self.directory_record(self.by_id(identifier)) | {'base_version': target['credential_version']})
        self.store.record('password_reset', {'actor': actor['name'], 'user_id': identifier})
        return {'ok': True, 'must_change': True}

    def change_password(self, actor, current, new):
        row = self.by_id(actor['id'])
        if not password_matches(current, row['password']):
            raise ValueError('Senha atual incorreta')
        if len(new) < 8 or len(new) > 200 or new == INITIAL_PASSWORD or new == current:
            raise ValueError('Escolha outra senha com pelo menos oito caracteres')
        with self.db:
            self.db.execute('UPDATE users SET password=?,must_change=0,activation_hash=NULL,credential_version=credential_version+1 WHERE id=?',
                            (password_hash(new), row['id']))
            self.revoke(row['name'])
            if row['role'] == 'technician':
                pending = self.db.execute('SELECT kind FROM directory_pending WHERE user_id=?', (row['id'],)).fetchone()
                self.queue(row['id'], 'register' if pending and pending['kind'] == 'register' else 'credential',
                           self.directory_record(self.by_id(row['id'])) | {'base_version': row['credential_version']})
        self.store.record('password_changed', {'user_id': row['id'], 'user': row['name']})

    def apply_snapshot(self, records, central_ids=None):
        """Validate a complete snapshot first; malformed responses never revoke a partial set."""
        if not isinstance(records, list) or len(records) > 5000:
            raise ValueError('Snapshot de técnicos inválido')
        seen_ids, seen_names, normalized = set(), set(), []
        for item in records:
            r = dict(item)
            if not re.fullmatch('[A-Za-z0-9_-]{1,100}', r.get('id', '')):
                raise ValueError('ID global inválido')
            r['name'] = username(r['name'])
            # Retained wire field for compatibility; no account requires a code.
            r['activation_hash'] = None
            if r['name'] in ('root', 'admin') or r['id'] in seen_ids or r['name'] in seen_names:
                raise ValueError('ID/login global duplicado ou reservado')
            r['expires_at'] = expiry(r.get('expires_at'))
            if not isinstance(r.get('full_name'), str) or not 1 <= len(r['full_name']) <= 100:
                raise ValueError('Nome global inválido')
            if type(r.get('must_change')) is not bool or not isinstance(r.get('meta_version', 0), int):
                raise ValueError('Metadados globais inválidos')
            if not isinstance(r.get('active'), bool) or not isinstance(r.get('deleted', False), bool):
                raise ValueError('Situação global inválida')
            if not valid_hash(r.get('password')) or (r.get('activation_hash') is not None and not valid_hash(r['activation_hash'])):
                raise ValueError('Credencial global inválida')
            if not isinstance(r.get('credential_version'), int) or r['credential_version'] < 1:
                raise ValueError('Versão de credencial inválida')
            conflict = self.by_name(r['name'])
            old = self.by_id(r['id'])
            if conflict and conflict['id'] != r['id']:
                raise ValueError('Login global conflita com conta local; intervenção do raiz necessária')
            if old and (old['role'] != 'technician' or old['name'] != r['name']):
                raise ValueError('Identidade global alterada; não é permitido assumir conta local')
            seen_ids.add(r['id']);seen_names.add(r['name']);normalized.append(r)
        audit = []
        with self.db:
            for r in normalized:
                old = self.by_id(r['id'])
                pending = self.db.execute('SELECT 1 FROM directory_pending WHERE user_id=?', (r['id'],)).fetchone()
                if old and pending:
                    # A revocation still wins over a pending offline password edit.
                    if not r['active'] or r.get('deleted'):
                        self.db.execute('UPDATE users SET active=0,deleted=? WHERE id=?', (int(r.get('deleted', False)), r['id']))
                        self.revoke(old['name'])
                    if old['expires_at'] != r['expires_at']:
                        self.db.execute('UPDATE users SET expires_at=? WHERE id=?', (r['expires_at'], r['id']))
                        self.revoke(old['name'])
                    continue
                changed = old and any(old.get(k) != r.get(k, 0) for k in
                                      ('password', 'active', 'deleted', 'expires_at', 'must_change', 'credential_version'))
                self.db.execute('''INSERT INTO users(name,password,role,id,full_name,active,deleted,expires_at,source,
                    must_change,activation_hash,credential_version,meta_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(name) DO UPDATE SET password=excluded.password,full_name=excluded.full_name,
                    active=excluded.active,deleted=excluded.deleted,expires_at=excluded.expires_at,source=excluded.source,
                    must_change=excluded.must_change,activation_hash=excluded.activation_hash,
                    credential_version=excluded.credential_version,meta_version=excluded.meta_version''',
                    (r['name'],r['password'],'technician',r['id'],r['full_name'],int(r['active']),int(r.get('deleted',False)),
                     r['expires_at'],'directory',int(r.get('must_change',False)),r.get('activation_hash'),
                     r['credential_version'],r.get('meta_version',0)))
                if changed:
                    self.revoke(r['name'])
                    audit.append({'user_id': r['id'], 'active': r['active'], 'deleted': r.get('deleted', False)})
            for old in self.db.execute("SELECT * FROM users WHERE source='directory' AND role='technician'").fetchall():
                if old['id'] not in seen_ids:
                    self.db.execute('UPDATE users SET active=0,deleted=1 WHERE id=?', (old['id'],))
                    self.revoke(old['name'])
        for event in audit:
            self.store.record('directory_access_changed', event)

    def pending(self):
        return [dict(r) | {'payload': json.loads(r['payload'])} for r in self.db.execute('SELECT * FROM directory_pending ORDER BY queued_at')]
