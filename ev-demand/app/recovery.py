"""Offline root recovery using owner-held Ed25519 signatures.

Controllers never generate, store or receive the owner's private key. Challenges
are bound to one browser, one controller and one pinned public key, for 15 minutes.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import time

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

TTL = 900
DOMAIN = b'EnergyCube D-Max root recovery v1\x00'
FIELDS = {'purpose', 'controller', 'key', 'nonce', 'issued', 'expires'}


def encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def decode(value, maximum=2048):
    if not isinstance(value, str) or not 1 <= len(value) <= maximum or not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise ValueError('Código de recuperação inválido')
    result = base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)
    if encode(result) != value:
        raise ValueError('Código de recuperação inválido')
    return result


def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def payload_from(encoded, now=None):
    now = time.time() if now is None else now
    raw = decode(encoded)
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise ValueError('Desafio de recuperação inválido') from None
    if not isinstance(payload, dict) or set(payload) != FIELDS:
        raise ValueError('Desafio de recuperação inválido')
    if payload['purpose'] != 'root-recovery-v1':
        raise ValueError('Finalidade de recuperação inválida')
    if any(not isinstance(payload[k], str) or not re.fullmatch(r'[0-9a-f]{32}', payload[k]) for k in ('controller', 'key', 'nonce')):
        raise ValueError('Identidade de recuperação inválida')
    if any(type(payload[k]) is not int for k in ('issued', 'expires')):
        raise ValueError('Validade de recuperação inválida')
    if canonical(payload) != raw:
        raise ValueError('Desafio de recuperação inválido')
    if payload['expires'] - payload['issued'] != TTL or payload['issued'] > now + 60 or now >= payload['expires']:
        raise ValueError('Desafio expirado ou relógio incorreto; gere outro desafio')
    return payload


def fingerprint(key):
    return hashlib.sha256(key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).hexdigest()[:32]


class Recovery:
    def __init__(self, store, public_pem=None):
        self.store, self.db = store, store.db
        self.key = None
        self.status = 'Instale recovery-public.pem no servidor para habilitar a recuperação'
        self.db.execute('''CREATE TABLE IF NOT EXISTS recovery_challenges (
            nonce TEXT PRIMARY KEY, payload TEXT NOT NULL, binding TEXT NOT NULL,
            expires REAL NOT NULL, used INTEGER NOT NULL DEFAULT 0)''')
        self.db.commit()
        try:
            if public_pem is None:
                path = Path(os.getenv('DMAX_RECOVERY_PUBLIC_KEY', str(Path(__file__).resolve().parents[1] / 'recovery-public.pem')))
                if path.exists():
                    if path.stat().st_size > 4096:
                        raise ValueError('Chave pública inválida')
                    public_pem = path.read_bytes()
            if public_pem is not None:
                key = serialization.load_pem_public_key(public_pem)
                if not isinstance(key, Ed25519PublicKey):
                    raise ValueError('A recuperação exige chave pública Ed25519')
                self.key = key
                self.status = 'Recuperação por assinatura habilitada'
        except (ValueError, TypeError, OSError, UnsupportedAlgorithm):
            # Fail closed without exposing file contents or paths from exceptions.
            self.status = 'Chave pública inválida; recuperação desabilitada'
        current = fingerprint(self.key) if self.key else ''
        with self.db:
            self.db.execute('CREATE TABLE IF NOT EXISTS recovery_policy (id INTEGER PRIMARY KEY CHECK(id=1), fingerprint TEXT NOT NULL)')
            previous = self.db.execute('SELECT fingerprint FROM recovery_policy WHERE id=1').fetchone()
            if previous and previous['fingerprint'] != current:
                # Replacing/removing a trusted key invalidates pending codes and
                # root sessions immediately, without changing ordinary users.
                self.db.execute('DELETE FROM recovery_challenges')
                self.db.execute("DELETE FROM logins WHERE username='root'")
                self.db.execute("UPDATE users SET epoch=epoch+1 WHERE name='root'")
            self.db.execute('INSERT INTO recovery_policy VALUES (1,?) ON CONFLICT(id) DO UPDATE SET fingerprint=excluded.fingerprint', (current,))

    def public(self):
        return {'enabled': self.key is not None, 'fingerprint': fingerprint(self.key) if self.key else '',
                'controller_id': self.store.entities('system')[0]['controller_id'], 'message': self.status}

    def issue(self, binding):
        if self.key is None:
            raise ValueError(self.status)
        now = int(time.time())
        digest = hashlib.sha256(binding.encode()).hexdigest()
        with self.db:
            self.db.execute('DELETE FROM recovery_challenges WHERE expires<=? OR used=1', (now,))
            old = self.db.execute('SELECT payload FROM recovery_challenges WHERE binding=?', (digest,)).fetchone()
            if old:
                payload = json.loads(old['payload'])
            else:
                if self.db.execute('SELECT COUNT(*) FROM recovery_challenges').fetchone()[0] >= 256:
                    raise ValueError('Recuperação ocupada; aguarde alguns minutos')
                payload = {'purpose': 'root-recovery-v1', 'controller': self.store.entities('system')[0]['controller_id'],
                           'key': fingerprint(self.key), 'nonce': secrets.token_hex(16), 'issued': now, 'expires': now + TTL}
                self.db.execute('INSERT INTO recovery_challenges(nonce,payload,binding,expires) VALUES(?,?,?,?)',
                                (payload['nonce'], canonical(payload).decode(), digest, payload['expires']))
        return {'challenge': 'DMAX-C1.' + encode(canonical(payload)), 'expires': payload['expires'], 'fingerprint': payload['key']}

    def consume(self, authorization, binding):
        if self.key is None:
            raise ValueError(self.status)
        try:
            prefix, encoded, signature = authorization.split('.')
            if prefix != 'DMAX-R1':
                raise ValueError('Autorização inválida')
            payload = payload_from(encoded)
            if payload['controller'] != self.store.entities('system')[0]['controller_id'] or payload['key'] != fingerprint(self.key):
                raise ValueError('Autorização pertence a outro equipamento ou chave')
            self.key.verify(decode(signature, 100), DOMAIN + canonical(payload))
            with self.db:
                result = self.db.execute('''UPDATE recovery_challenges SET used=1
                    WHERE nonce=? AND payload=? AND binding=? AND used=0 AND expires>?''',
                    (payload['nonce'], canonical(payload).decode(), hashlib.sha256(binding.encode()).hexdigest(), time.time()))
                if result.rowcount != 1:
                    raise ValueError('Desafio expirado, utilizado ou de outro navegador')
        except InvalidSignature:
            raise ValueError('Assinatura de recuperação inválida') from None
        except (TypeError, AttributeError):
            raise ValueError('Autorização de recuperação inválida') from None
