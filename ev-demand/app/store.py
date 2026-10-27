import hashlib
import json
import os
import re
from pathlib import Path
import secrets
import sqlite3
import time
import uuid
from .meter import DEFAULT_METER, normalize_meter


DEFAULT_SETTINGS = {
    'site_name': 'Minha instalação', 'mode': 'simulation', 'limit_kw': 1000.0,
    'margin_kw': 50.0, 'timezone': 'America/Sao_Paulo', 'freshness_s': 15,
    'ramp_kw_s': 10.0, 'schedules': [], 'blocked_policy': 'zero',
    'circuits': [{'id': 'principal', 'name': 'Quadro principal', 'limit_kw': 1000.0}],
    'meter': DEFAULT_METER,
    'cloud_url': '', 'retain_days': 7,
}


def password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600_000)
    return f'pbkdf2_sha256$600000${salt}${digest.hex()}'


def password_matches(password: str, encoded: str) -> bool:
    # Never accept attacker-selected algorithms or unbounded PBKDF2 iterations.
    if not isinstance(password, str) or len(password) > 200 or not isinstance(encoded, str):
        return False
    if not re.fullmatch(r'pbkdf2_sha256\$600000\$[0-9a-f]{32}\$[0-9a-f]{64}', encoded):
        return False
    try:
        _, iterations, salt, expected = encoded.split('$')
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(iterations)).hex()
        return secrets.compare_digest(expected, actual)
    except (ValueError, TypeError):
        return False


class Store:
    def __init__(self, path=None):
        path = path or os.getenv('EV_DB_PATH', str(Path(__file__).resolve().parents[1] / 'data/controller.sqlite3'))
        if path != ':memory:':
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        if path != ':memory:' and os.name == 'posix':
            os.chmod(path, 0o600)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS entities (kind TEXT, id TEXT, payload TEXT NOT NULL, PRIMARY KEY(kind,id));
            CREATE TABLE IF NOT EXISTS users (name TEXT PRIMARY KEY, password TEXT NOT NULL, role TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS logins (token TEXT PRIMARY KEY, username TEXT, expires REAL);
            CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, ts REAL, kind TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS samples (id TEXT PRIMARY KEY, ts REAL, source TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS outbox (id TEXT PRIMARY KEY, ts REAL, kind TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS receipts (id TEXT PRIMARY KEY, ack_at REAL);
            CREATE INDEX IF NOT EXISTS events_time ON events(ts);
            CREATE INDEX IF NOT EXISTS samples_time ON samples(ts);
        ''')
        self.db.execute('INSERT OR IGNORE INTO settings VALUES (1,?)', (json.dumps(DEFAULT_SETTINGS),))
        self.db.commit()
        if not self.entities('system'):
            self.put('system', {'id': 'identity', 'controller_id': uuid.uuid4().hex})

    def settings(self):
        data = json.loads(self.db.execute('SELECT payload FROM settings WHERE id=1').fetchone()[0])
        data['meter'] = normalize_meter(data['meter'])
        data.setdefault('technical_limit_kw', data['limit_kw'])
        return data

    def save_settings(self, data):
        with self.db:
            self.db.execute('UPDATE settings SET payload=? WHERE id=1', (json.dumps(data),))

    def entities(self, kind):
        return [json.loads(r[0]) for r in self.db.execute('SELECT payload FROM entities WHERE kind=? ORDER BY id', (kind,))]

    def put(self, kind, data):
        with self.db:
            self.db.execute('INSERT INTO entities VALUES (?,?,?) ON CONFLICT(kind,id) DO UPDATE SET payload=excluded.payload',
                            (kind, data['id'], json.dumps(data)))

    def record(self, kind, payload, source=None):
        identifier, now = uuid.uuid4().hex, time.time()
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        with self.db:
            if kind == 'minute':
                self.db.execute('INSERT INTO samples VALUES (?,?,?,?)', (identifier, now, source, data))
            else:
                self.db.execute('INSERT INTO events VALUES (?,?,?,?)', (identifier, now, kind, data))
            self.db.execute('INSERT INTO outbox VALUES (?,?,?,?)', (identifier, now, kind, data))
        return identifier

    def pending(self):
        return [dict(r) | {'payload': json.loads(r['payload'])} for r in
                self.db.execute('SELECT * FROM outbox ORDER BY ts LIMIT 200')]

    def acknowledge(self, identifiers):
        with self.db:
            for identifier in identifiers:
                if self.db.execute('SELECT 1 FROM outbox WHERE id=?', (identifier,)).fetchone():
                    self.db.execute('INSERT OR IGNORE INTO receipts VALUES (?,?)', (identifier, time.time()))
                    self.db.execute('DELETE FROM outbox WHERE id=?', (identifier,))

    def cleanup(self):
        """No unacknowledged record may be purged, even if offline longer than 30 days."""
        now = time.time()
        with self.db:
            self.db.execute('DELETE FROM samples WHERE ts<? AND id IN (SELECT id FROM receipts)',
                            (now - self.settings()['retain_days'] * 86400,))
            self.db.execute('DELETE FROM events WHERE ts<? AND id IN (SELECT id FROM receipts)', (now - 30 * 86400,))
            self.db.execute('DELETE FROM receipts WHERE id NOT IN (SELECT id FROM samples UNION SELECT id FROM events)')
            self.db.execute('DELETE FROM logins WHERE expires<?', (now,))

    def history(self):
        events = [dict(r) | {'payload': json.loads(r['payload'])} for r in
                  self.db.execute('SELECT * FROM events ORDER BY ts DESC LIMIT 150')]
        return {'events': events, 'sessions': sorted(self.entities('session'), key=lambda s: s['started_at'], reverse=True)[:100],
                'learning': sorted(self.entities('learning'), key=lambda s: s['started_at'], reverse=True)[:100]}

    def pending_count(self):
        return self.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0]
