"""Private Google Sheets directory. No passwords or hashes are written to cells."""
from datetime import datetime, time, timedelta
import os
import threading
from urllib.parse import quote
from zoneinfo import ZoneInfo

from app.access import expiry, username

HEADERS = ['id', 'nome', 'login', 'situacao', 'valido_ate']


def sheet_expiry(value):
    if value in ('', None):
        return None
    text = str(value).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            day = datetime.strptime(text, fmt).date()
            end = datetime.combine(day + timedelta(days=1), time.min,
                                   ZoneInfo(os.getenv('GOOGLE_SHEET_TIMEZONE', 'America/Sao_Paulo')))
            return end.timestamp()
        except ValueError:
            pass
    return expiry(text)


def parse_rows(values):
    if not values or [str(v).strip().lower() for v in values[0]] != HEADERS:
        raise ValueError('A aba deve conter os cabeçalhos id, nome, login, situacao, valido_ate')
    rows, ids, names = [], set(), set()
    for number, cells in enumerate(values[1:], 2):
        if not any(str(x).strip() for x in cells):
            continue
        if len(cells) > 5:
            raise ValueError(f'Linha {number}: colunas extras não são aceitas')
        cells = list(cells) + [''] * (5 - len(cells))
        identifier, full_name, login, status, until = [str(x).strip() for x in cells]
        login = username(login)
        import re
        if not re.fullmatch('[A-Za-z0-9_-]{1,100}', identifier) or not 1 <= len(full_name) <= 100:
            raise ValueError(f'Linha {number}: id ou nome inválido')
        if login in ('root', 'admin') or identifier in ids or login in names:
            raise ValueError(f'Linha {number}: id/login duplicado ou reservado')
        if status.lower() not in ('ativo', 'bloqueado', 'excluido', 'excluído'):
            raise ValueError(f'Linha {number}: situação inválida')
        rows.append({'id': identifier, 'name': login, 'full_name': full_name,
                     'active': status.lower() == 'ativo', 'deleted': status.lower() in ('excluido', 'excluído'),
                     'expires_at': sheet_expiry(until)})
        ids.add(identifier);names.add(login)
    if len(rows) > 5000:
        raise ValueError('Limite de 5.000 técnicos excedido; lista não aplicada')
    return rows


class GoogleSheet:
    def __init__(self):
        self.spreadsheet = os.getenv('GOOGLE_SHEET_ID', '17HCp2CX3eUZXqQsTkTNDZvrLkGqzZQrJkCfeHo-toPQ')
        self.tab = os.getenv('GOOGLE_SHEET_TAB', 'Tecnicos')
        self.lock = threading.Lock()
        self.session = None

    def _client(self):
        if self.session is None:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
            credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/spreadsheets'])
            self.session = AuthorizedSession(credentials)
        return self.session

    def _url(self, suffix=''):
        sheet_range = quote("'" + self.tab.replace("'", "''") + "'!A:E", safe='')
        return f'https://sheets.googleapis.com/v4/spreadsheets/{quote(self.spreadsheet, safe="")}/values/{sheet_range}' + suffix

    def read(self):
        with self.lock:
            response = self._client().get(self._url(), params={'valueRenderOption': 'FORMATTED_VALUE'}, timeout=15)
            response.raise_for_status()
            return parse_rows(response.json().get('values', []))

    def write(self, record):
        """Only called for a root-authorized device change; RAW prevents formula injection."""
        with self.lock:
            client = self._client()
            response = client.get(self._url(), params={'valueRenderOption': 'FORMATTED_VALUE'}, timeout=15)
            response.raise_for_status()
            values = response.json().get('values', [])
            parse_rows(values)  # Do not write into an unexpected or malformed sheet.
            index = next((i for i, row in enumerate(values) if row and row[0] == record['id']), None)
            if any(len(row) > 2 and row[2].strip().lower() == record['name'] and row[0] != record['id'] for row in values[1:]):
                raise ValueError('Login já pertence a outro técnico')
            row = [record['id'], record['full_name'], record['name'],
                   'excluido' if record['deleted'] else 'ativo' if record['active'] else 'bloqueado',
                   datetime.fromtimestamp(record['expires_at'], ZoneInfo('UTC')).isoformat() if record['expires_at'] else '']
            if index is None:
                result = client.post(self._url(':append'), params={'valueInputOption': 'RAW', 'insertDataOption': 'INSERT_ROWS'},
                                     json={'values': [row]}, timeout=15)
            else:
                quoted = quote("'" + self.tab.replace("'", "''") + f"'!A{index+1}:E{index+1}", safe='')
                url = f'https://sheets.googleapis.com/v4/spreadsheets/{quote(self.spreadsheet, safe="")}/values/{quoted}'
                result = client.put(url, params={'valueInputOption': 'RAW'}, json={'values': [row]}, timeout=15)
            result.raise_for_status()
