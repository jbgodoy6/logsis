"""Per-controller signed subscription notices. No internet dependency after receipt.

The trust boundary is the managed OS/database; this is not DRM against a root OS
administrator. A battery RTC is required to measure powered-off offline time.
"""
import hashlib
import hmac
import json
import math
import time

DOMAIN = b'DMAX-LICENSE-1\n'
NOTICE_SECONDS = 10 * 86400


class Subscription:
    def __init__(self, store):
        self.store = store
        self.row = store.get('subscription', 'current') or {'id': 'current', 'revision': 0}
        self.highwater = self.row.get('highwater', 0.0)
        self.anchor = time.monotonic()
        self.saved = self.anchor

    def clock(self):
        monotonic = time.monotonic()
        wall = time.time()
        expected = self.highwater + max(0, monotonic - self.anchor)
        if self.row.get('state') == 'pending' and wall < self.highwater - 300:
            # A rollback must never grant a fresh grace period.
            self.row['clock_suspect'] = True
        self.highwater = max(expected, wall)
        self.anchor = monotonic
        if monotonic - self.saved >= 15 and self.row.get('revision'):
            self.persist()
        return self.highwater

    def persist(self):
        self.row['highwater'] = self.highwater
        self.store.put('subscription', self.row)
        self.saved = time.monotonic()

    def receive(self, envelope, token):
        if not isinstance(envelope, dict) or set(envelope) != {'payload', 'signature'}:
            raise ValueError('Aviso de assinatura inválido')
        raw, signature = envelope['payload'], envelope['signature']
        if not isinstance(raw, str) or len(raw) > 6000 or not isinstance(signature, str):
            raise ValueError('Aviso de assinatura inválido')
        key = hashlib.sha256(token.encode()).hexdigest().encode()
        expected = hmac.new(key, DOMAIN + raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError('Assinatura do aviso inválida')
        data = json.loads(raw)
        identity = self.store.entities('system')[0]['controller_id']
        if (set(data) != {'controller_id', 'revision', 'state', 'issued_at', 'deadline', 'server_time', 'message'}
                or data['controller_id'] != identity or type(data['revision']) is not int or data['revision'] < 1
                or data['state'] not in ('regular', 'pending') or not isinstance(data['message'], str)
                or len(data['message']) > 300):
            raise ValueError('Conteúdo do aviso inválido')
        for name in ('issued_at', 'server_time'):
            if type(data[name]) not in (int, float) or not math.isfinite(data[name]) or data[name] < 1:
                raise ValueError('Data do aviso inválida')
        if data['server_time'] < data['issued_at']:
            raise ValueError('Data do aviso inválida')
        if data['state'] == 'pending':
            if type(data['deadline']) not in (int, float) or data['deadline'] != data['issued_at'] + NOTICE_SECONDS:
                raise ValueError('Prazo deve ser exatamente dez dias')
        elif data['deadline'] is not None:
            raise ValueError('Prazo inesperado')
        if data['revision'] < self.row['revision']:
            raise ValueError('Aviso antigo recusado')
        same = data['revision'] == self.row['revision']
        if same and any(data[k] != self.row.get(k) for k in ('state', 'issued_at', 'deadline', 'message')):
            raise ValueError('Revisão de aviso conflitante')
        self.clock()
        if not same:
            still_expired = (self.row.get('expired', False) and data['state'] == 'pending'
                             and data['issued_at'] == self.row.get('issued_at'))
            self.row = {'id': 'current', **data, 'expired': bool(still_expired), 'clock_suspect': False}
            self.store.record('subscription_received', {k: data[k] for k in ('revision', 'state', 'deadline')})
        self.highwater = data['server_time'] if not same and data['state'] == 'regular' else max(self.highwater, data['server_time'])
        self.anchor = time.monotonic()
        self.persist()
        return self.status()

    def status(self):
        now = self.clock()
        if self.row.get('state') == 'pending' and not self.row.get('expired') and (
                now >= self.row['deadline'] or self.row.get('clock_suspect')):
            self.row['expired'] = True
            self.persist()
            self.store.record('subscription_expired', {'revision': self.row['revision'], 'deadline': self.row['deadline']})
        expired = bool(self.row.get('expired'))
        return {'state': 'native' if expired else self.row.get('state', 'unconfigured'),
                'native': expired, 'deadline': self.row.get('deadline'),
                'remaining_days': max(0, math.ceil((self.row.get('deadline', now) - now) / 86400)) if self.row.get('deadline') else None,
                'message': self.row.get('message') or 'Regularize sua assinatura com o fornecedor.',
                'clock_suspect': bool(self.row.get('clock_suspect')), 'revision': self.row['revision']}
