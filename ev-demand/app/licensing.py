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
WARNING_SECONDS = 15 * 86400
OFFLINE_PENDING_SECONDS = 30 * 86400
OFFLINE_NATIVE_SECONDS = 40 * 86400


class Subscription:
    def __init__(self, store):
        self.store = store
        self.row = store.get('subscription', 'current') or {'id': 'current', 'revision': 0}
        self.highwater = self.row.get('highwater', 0.0)
        self.anchor = time.monotonic()
        self.saved = self.anchor
        if 'contact_anchor' not in self.row:
            self.row['contact_anchor'] = max(self.highwater, time.time())
            self.highwater = self.row['contact_anchor']
            self.persist()

    def clock(self):
        monotonic = time.monotonic()
        wall = time.time()
        expected = self.highwater + max(0, monotonic - self.anchor)
        if self.row.get('state') == 'pending' and wall < self.highwater - 300:
            # A rollback must never grant a fresh grace period.
            self.row['clock_suspect'] = True
        self.highwater = max(expected, wall)
        self.anchor = monotonic
        if monotonic - self.saved >= 15:
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
        # Only a fresh, authenticated supplier timestamp can renew contact.
        # Replaying a signed response cannot reset the offline counter.
        contact = self.row.get('last_valid_contact', 0)
        fresh_contact = data['server_time'] > contact and data['server_time'] >= self.highwater - 300
        contact_anchor = self.row.get('contact_anchor', self.highwater)
        if not same:
            still_expired = (self.row.get('expired', False) and data['state'] == 'pending'
                             and data['issued_at'] == self.row.get('issued_at'))
            self.row = {'id': 'current', **data, 'expired': bool(still_expired), 'clock_suspect': False}
            self.store.record('subscription_received', {k: data[k] for k in ('revision', 'state', 'deadline')})
        self.row['contact_anchor'] = contact_anchor
        self.row['last_valid_contact'] = data['server_time'] if fresh_contact else contact
        if fresh_contact:
            self.row['offline_expired'] = False
        self.highwater = max(self.highwater, data['server_time'])
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
        last_contact = self.row.get('last_valid_contact') or self.row['contact_anchor']
        offline_seconds = max(0, now - last_contact)
        offline = ('native' if offline_seconds >= OFFLINE_NATIVE_SECONDS or self.row.get('offline_expired')
                   else 'pending' if offline_seconds >= OFFLINE_PENDING_SECONDS
                   else 'warning' if offline_seconds >= WARNING_SECONDS else 'connected')
        if offline == 'native' and not self.row.get('offline_expired'):
            self.row['offline_expired'] = True
            self.persist()
            self.store.record('platform_contact_expired', {'last_contact': last_contact})
        financial = bool(self.row.get('expired'))
        expired = financial or offline == 'native'
        offline_deadline = last_contact + OFFLINE_NATIVE_SECONDS
        deadline = self.row.get('deadline') if self.row.get('state') == 'pending' else None
        if offline in ('pending', 'native'):
            deadline = min(deadline, offline_deadline) if deadline else offline_deadline
        message = self.row.get('message') or 'Regularize sua assinatura com o fornecedor.'
        if offline != 'connected':
            message += ' Sem contato autenticado com o fornecedor: reconecte à internet. Controle ativo até o prazo de 40 dias, salvo pendência financeira anterior.'
        return {'state': 'native' if expired else 'pending' if offline == 'pending' else self.row.get('state', 'unconfigured'),
                'native': expired, 'deadline': deadline,
                'financial_expired': financial, 'offline_state': offline,
                'last_valid_contact': self.row.get('last_valid_contact'), 'offline_days': int(offline_seconds // 86400),
                'remaining_days': max(0, math.ceil((deadline - now) / 86400)) if deadline else None,
                'message': message,
                'clock_suspect': bool(self.row.get('clock_suspect')), 'revision': self.row['revision']}
