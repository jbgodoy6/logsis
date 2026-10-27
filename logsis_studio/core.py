from __future__ import annotations

import copy
import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import tempfile
import zipfile

from . import __version__

RESOURCES = Path(__file__).resolve().parent / 'resources'
MDB_FIELDS = ('DH', 'DM', 'DL', 'ID', 'FNC', 'ADDR', 'BIT', 'H', 'VR', 'TH', 'TL', 'SM')
DEFAULT_MDB = dict(zip(MDB_FIELDS, ('', '', '', '-1', '-1', '-1', '-1', '1000', '-1', '32767', '-32767', '0')))
MDB_KEY = re.compile(r'MDBA_(' + '|'.join(MDB_FIELDS) + r')(\d+)\Z')
MODES = {0: 'STOP', 1: 'AUTO', 2: 'MANUAL', 3: 'TESTE COM CARGA', 6: 'TESTE SEM CARGA', 7: 'OFF'}


def number(value, label='Valor') -> Decimal:
    try:
        result = Decimal(str(value).strip().replace(',', '.'))
    except InvalidOperation as exc:
        raise ValueError(f'{label}: informe um número válido.') from exc
    if not result.is_finite():
        raise ValueError(f'{label}: o número deve ser finito.')
    return result


def integer(value, label='Valor', minimum=None, maximum=None) -> int:
    result = number(value, label)
    if result != result.to_integral_value():
        raise ValueError(f'{label}: use um número inteiro.')
    value = int(result)
    if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
        raise ValueError(f'{label}: valor fora do intervalo {minimum} a {maximum}.')
    return value


def safe_text(value, label='Texto') -> str:
    value = str(value)
    if any(c in value for c in ';\r\n\x00'):
        raise ValueError(f'{label}: não use ponto e vírgula, quebra de linha ou caractere nulo.')
    return value


def safe_value(value, label='Valor') -> str:
    # The format splits at the first semicolon, so punctuation in passwords is valid.
    value = str(value)
    if any(c in value for c in '\r\n\x00'):
        raise ValueError(f'{label}: não use quebra de linha ou caractere nulo.')
    return value


@dataclass(frozen=True)
class Channel:
    number: int
    column: str
    name: str
    group: str
    unit: str
    divisor: int
    params: dict
    role: str = ''
    signed_value: bool | None = None
    label_variable: str = ''
    codec: str = 'integer'
    source_reference: str = ''

    @property
    def index(self):
        return self.number - 1

    @property
    def input_letter(self):
        if self.role.startswith('input_'):
            return self.role.removeprefix('input_').replace('flex_', 'Flex_')
        if self.role:
            return None
        if self.group == 'Entradas' and 44 <= self.number <= 51:
            return chr(65 + self.number - 44)
        if self.group == 'Entradas flexíveis':
            return {'43553': 'Q', '43555': 'R', '43557': 'S'}.get(self.params['ADDR'])
        return None

    @property
    def signed(self):
        if self.signed_value is not None:
            return self.signed_value
        return self.number in [2, 3] or 19 <= self.number <= 28 or (self.group == 'Manutenção' and self.number >= 53)


@dataclass(frozen=True)
class Profile:
    model: str
    version: str
    count: int
    dashboard: str
    dashboard_version: str
    channels: tuple[Channel, ...]
    label: str = ''
    kind: str = 'legacy'
    manual_family: str = ''
    manual_notes: list[str] | None = None
    vendor: str = 'DSE'
    application: str = ''
    topology: str = ''
    source_document: str = ''


def available_models():
    return tuple(json.loads((RESOURCES / 'profiles.json').read_text(encoding='utf-8')))


def load_profile(model: str) -> Profile:
    profiles = json.loads((RESOURCES / 'profiles.json').read_text(encoding='utf-8'))
    if model not in profiles:
        raise ValueError('Controlador não reconhecido. Selecione um dos perfis disponíveis.')
    raw = profiles[model]
    channels = tuple(Channel(**entry) for entry in raw['channels'])
    if [c.number for c in channels] != list(range(1, raw['count'] + 1)):
        raise ValueError('Perfil inconsistente: a sequência MDB não é contínua.')
    return Profile(**{k: v for k, v in raw.items() if k != 'channels'}, channels=channels)


class BinDocument:
    """Preserve unrelated settings, ordering, encoding and original line endings."""
    def __init__(self, text: str, encoding='utf-8', bom=False):
        self.text, self.encoding, self.bom = text, encoding, bom
        self.params = {}
        self.duplicates = []
        for line in text.splitlines():
            if ';' in line:
                key, value = line.split(';', 1)
                key = key.strip()
                if key in self.params:
                    self.duplicates.append(key)
                self.params[key] = value
        self.newline = '\r\n' if '\r\n' in text else '\n'

    @classmethod
    def from_bytes(cls, data):
        bom = data.startswith(b'\xef\xbb\xbf')
        if bom:
            return cls(data[3:].decode('utf-8'), 'utf-8', True)
        try:
            return cls(data.decode('utf-8'))
        except UnicodeDecodeError:
            return cls(data.decode('cp1252'), 'cp1252')

    def without_mdbs(self):
        lines = [line for line in self.text.splitlines(keepends=True)
                 if not MDB_KEY.fullmatch(line.rstrip('\r\n').partition(';')[0].strip())]
        return BinDocument(''.join(lines), self.encoding, self.bom)

    def render(self, updates: dict[str, str]) -> bytes:
        updates = {safe_text(k, 'Chave'): safe_value(v, k) for k, v in updates.items()}
        result, seen = [], set()
        for line in self.text.splitlines(keepends=True):
            body = line.rstrip('\r\n')
            ending = line[len(body):]
            key, sep, _ = body.partition(';')
            if sep and key.strip() in updates:
                key = key.strip()
                # Keeping identical lines also preserves whitespace in imported files.
                if self.params.get(key) == updates[key] and key not in self.duplicates:
                    result.append(line)
                else:
                    result.append(key + ';' + updates[key] + ending)
                seen.add(key)
            else:
                result.append(line)
        missing = [(key, value) for key, value in updates.items() if key not in seen]
        if missing and result and not result[-1].endswith(('\r', '\n')):
            result[-1] += self.newline
        result.extend(key + ';' + value + self.newline for key, value in missing)
        text = ''.join(result)
        try:
            data = text.encode(self.encoding)
        except UnicodeEncodeError as exc:
            raise ValueError('O BIN usa Windows-1252. Use textos compatíveis com essa codificação.') from exc
        return (b'\xef\xbb\xbf' if self.bom else b'') + data


@dataclass(frozen=True)
class Issue:
    channel: int | None
    message: str


def nominal_limits(channel: Channel, nominal: dict) -> tuple[str, str] | None:
    n = channel.number
    if channel.role:
        role = channel.role
        if '_v_' in role:
            ll = float(number(nominal['voltage'], 'Tensão nominal'))
            base = ll / math.sqrt(3) if role.endswith(('l1n','l2n','l3n')) else ll
            low, high = base*.9*channel.divisor, base*1.1*channel.divisor
        elif role.endswith('_frequency'):
            base = number(nominal['frequency']); low, high = base*Decimal('.9')*channel.divisor, base*Decimal('1.1')*channel.divisor
        elif role == 'battery':
            base = number(nominal['battery']); low, high = base*Decimal('.8')*channel.divisor, base*Decimal('1.2')*channel.divisor
        elif role == 'rpm':
            base = number(nominal['rpm']); low, high = base*Decimal('.9'), base*Decimal('1.1')
        else:
            return None
        return tuple(str(number(v).quantize(Decimal('1'), rounding=ROUND_HALF_UP)) for v in (low, high))
    if n in range(9, 15) or n in range(30, 36):
        ll = float(number(nominal['voltage'], 'Tensão nominal'))
        base = ll / math.sqrt(3) if n in [9, 10, 11, 30, 31, 32] else ll
        low, high = base * .9 * 10, base * 1.1 * 10
    elif n in [8, 29]:
        base = number(nominal['frequency'], 'Frequência nominal')
        low, high = base * Decimal('.9') * 10, base * Decimal('1.1') * 10
    elif n == 6:
        base = number(nominal['battery'], 'Bateria nominal')
        low, high = base * Decimal('.8') * 10, base * Decimal('1.2') * 10
    elif n == 7:
        base = number(nominal['rpm'], 'RPM nominal')
        low, high = base * Decimal('.9'), base * Decimal('1.1')
    else:
        return None
    return tuple(str(number(v).quantize(Decimal('1'), rounding=ROUND_HALF_UP)) for v in (low, high))


class Project:
    def __init__(self, model='DSE7420', document=None, rows=None):
        self.profile = load_profile(model)
        self.document = document or BinDocument((RESOURCES / 'template.bin').read_text(encoding='utf-8'))
        self.general = {k: v for k, v in self.document.params.items() if not MDB_KEY.fullmatch(k)}
        self.rows = rows or [dict(DEFAULT_MDB) for _ in range(100)]
        self.slave = '10'
        self.nominal = {'voltage': '380', 'frequency': '60', 'battery': '24', 'rpm': '1800'}
        self.energy_divisor = '1' if self.profile.vendor == 'DEIF' else '10'
        self.maintenance_alert_hours = '50'
        self.source = None

    @classmethod
    def new(cls, model='DSE7420'):
        project = cls(model)
        project.apply_profile()
        return project

    @classmethod
    def open(cls, path, fallback_model='DSE7420'):
        path = Path(path)
        return cls.from_bytes(path.read_bytes(), fallback_model, path)

    @classmethod
    def from_bytes(cls, data, fallback_model='DSE7420', source=None):
        document = BinDocument.from_bytes(data)
        rows = []
        for index in range(100):
            rows.append({field: document.params.get(f'MDBA_{field}{index}', DEFAULT_MDB[field]) for field in MDB_FIELDS})
        # Distinguishing source roles matters more than the number of active channels.
        candidates = []
        for key in available_models():
            profile = load_profile(key)
            if all(all(rows[c.index][field].strip() == c.params[field].strip() for field in ['ADDR','FNC','BIT']) for c in profile.channels) and all(row['ID'].strip() in ['', '-1'] for row in rows[profile.count:]):
                candidates.append(key)
        if len(candidates) == 1:
            model = candidates[0]
        elif candidates:
            if fallback_model not in candidates:
                raise ValueError('Mapa compartilhado por ' + ', '.join(candidates) + '. Selecione o modelo do equipamento antes de abrir este BIN.')
            model = fallback_model
        else:
            candidate = rows[28]['ADDR'].strip()
            model = fallback_model if fallback_model not in ['DSE7420','DSE8610'] else 'DSE8610' if candidate == '1091' else 'DSE7420' if candidate == '1059' else fallback_model
            # Studio 8 exported a 59-channel DSE8620. Recognize its complete
            # signature rather than misidentifying it as a DSE7420 by frequency.
            expanded=load_profile('DSE8620')
            if expanded.count>59 and all(all(rows[c.index][field].strip()==c.params[field].strip() for field in ['ADDR','FNC','BIT']) for c in expanded.channels[:59]) and all(row['ID'].strip() in ['', '-1'] for row in rows[59:]):
                model='DSE8620'
                for c in expanded.channels[59:]:
                    rows[c.index]=dict(c.params)
                    rows[c.index]['ID']=rows[0]['ID']
        project = cls(model, document, rows)
        ids = {row['ID'].strip() for row in rows[:project.profile.count] if row['ID'].strip() not in ['', '-1']}
        project.slave = next(iter(ids)) if len(ids) == 1 else '10'
        project.model_candidates = candidates
        project.source = Path(source) if source else None
        return project

    def apply_profile(self):
        slave = integer(self.slave, 'Slave ID', 1, 247)
        for key in ['voltage', 'frequency', 'battery', 'rpm']:
            if number(self.nominal[key], key) <= 0:
                raise ValueError('Os valores nominais devem ser positivos.')
        rows = [dict(DEFAULT_MDB) for _ in range(100)]
        for channel in self.profile.channels:
            params = dict(channel.params)
            params['ID'] = str(slave)
            limits = nominal_limits(channel, self.nominal)
            if limits:
                params['TL'], params['TH'] = limits
            rows[channel.index] = params
        # Only explicit profile application clears conflicting/extra MDB entries.
        self.document = self.document.without_mdbs()
        self.rows = rows

    def row_issues(self, channel: Channel) -> list[str]:
        row, expected = self.rows[channel.index], channel.params
        issues = []
        for field, label in [('ADDR', 'Endereço'), ('FNC', 'Função'), ('BIT', 'Bit')]:
            try:
                if integer(row[field]) != integer(expected[field]):
                    issues.append(f'{label}: {row[field]} → esperado {expected[field]}')
            except ValueError:
                issues.append(f'{label} inválido: {row[field]}')
        try:
            if integer(row['ID'], 'Slave ID', 1, 247) != integer(self.slave, 'Slave ID', 1, 247):
                issues.append('Slave ID diferente do projeto.')
        except ValueError as exc:
            issues.append(str(exc))
        try:
            for field in MDB_FIELDS:
                safe_text(row[field], field)
            for field in ['H', 'VR', 'TH', 'TL', 'SM']:
                integer(row[field], field, -2147483648, 2147483647)
            if integer(row['TL']) > integer(row['TH']):
                issues.append('TL não pode ser maior que TH.')
        except ValueError as exc:
            issues.append(str(exc))
        return issues

    def validate(self) -> list[Issue]:
        issues = [Issue(c.number, message) for c in self.profile.channels for message in self.row_issues(c)]
        for i, row in enumerate(self.rows[self.profile.count:], self.profile.count):
            if any(row[field].strip() not in ['', '-1'] for field in ['ID', 'FNC', 'ADDR']):
                issues.append(Issue(i + 1, 'Slot reservado está ativo; o perfil não prevê este canal.'))
        for key in self.document.duplicates:
            if MDB_KEY.fullmatch(key):
                issues.append(Issue(None, f'Chave MDB duplicada no BIN: {key}. Aplique o perfil para normalizar.'))
        for key in self.document.params:
            match = MDB_KEY.fullmatch(key)
            if match and int(match[2]) >= 100:
                issues.append(Issue(None, f'Índice fora dos 100 slots: {key}.'))
        try:
            if number(self.energy_divisor, 'Divisor de energia') <= 0:
                issues.append(Issue(None, 'O divisor de energia deve ser positivo.'))
            for key, value in self.general.items():
                safe_text(key, 'Chave'); safe_value(value, key)
            for key, low, high in [('MDB_BAUD', 1, 4000000), ('MDB_TOUT', 0, 2147483647), ('MDB_R_DELAY', 0, 2147483647), ('MDB_RST_FAILURE', 0, 1), ('SYS_USE_WIFI', 0, 1), ('SYS_USE_GSM', 0, 1)]:
                if key in self.general:
                    integer(self.general[key], key, low, high)
        except ValueError as exc:
            issues.append(Issue(None, str(exc)))
        return issues

    def bin_bytes(self) -> bytes:
        issues = self.validate()
        if issues:
            raise ValueError(f'Corrija as {len(issues)} divergências antes de exportar. Primeira: {issues[0].message}')
        updates = dict(self.general)
        for index, row in enumerate(self.rows):
            updates.update({f'MDBA_{field}{index}': row[field] for field in MDB_FIELDS})
        return self.document.render(updates)

    def set_channel_metadata(self, index: int, changes: dict):
        allowed = {'DH', 'DM', 'DL', 'H', 'VR', 'TH', 'TL', 'SM'}
        if not 0 <= index < self.profile.count:
            raise ValueError('Canal reservado pelo perfil.')
        if set(changes) - allowed:
            raise ValueError('Posição, endereço, função, bit e Slave ID são definidos pelo perfil.')
        row = dict(self.rows[index])
        for key, value in changes.items():
            row[key] = safe_text(value, key)
        for key in ['H', 'VR', 'TH', 'TL', 'SM']:
            integer(row[key], key, -2147483648, 2147483647)
        if integer(row['TL']) > integer(row['TH']):
            raise ValueError('TL não pode ser maior que TH.')
        self.rows[index] = row

    def change_slave(self, value):
        value = str(integer(value, 'Slave ID', 1, 247))
        self.slave = value
        for row in self.rows[:self.profile.count]:
            row['ID'] = value

    def channel_name(self, channel):
        edited = self.rows[channel.index]['DM'].strip()
        return edited if edited and edited != channel.params['DM'] else channel.name

    def channel_divisor(self, channel):
        if self.profile.vendor == 'DEIF':
            return Decimal(channel.divisor)
        energy = channel.role.startswith('energy_') if channel.role else channel.number == 37
        return number(self.energy_divisor) if energy else Decimal(channel.divisor)

    def dashboard_template(self):
        if self.profile.vendor == 'DEIF':
            from .deif_dashboard import build_dashboard
            from .standard_layout import apply
            return apply(self.profile,build_dashboard(self.profile))
        if self.profile.kind != 'legacy':
            from .manual_dashboard import build_dashboard
            from .standard_layout import apply
            return apply(self.profile,build_dashboard(self.profile))
        from .standard_layout import apply
        return apply(self.profile,json.loads((RESOURCES / self.profile.dashboard).read_text(encoding='utf-8')))

    def csv_bytes(self):
        output = io.StringIO(newline='')
        writer = csv.writer(output, delimiter=';')
        writer.writerow(['Canal Grafana', 'Coluna SQL', 'Índice BIN', 'Medição', 'Grupo', 'Slave ID', 'Endereço', 'Função LogSis', 'Função Modbus', 'Bit', 'Divisor Grafana', 'Unidade', 'Compatibilidade']+(['Codec anterior à escala','Fonte documental'] if self.profile.vendor=='DEIF' else []))
        for c in self.profile.channels:
            row = self.rows[c.index]
            writer.writerow([f'MDB{c.number:02}', c.column, c.index, c.name, c.group, row['ID'], row['ADDR'], row['FNC'], '02' if row['FNC']=='2' else '03' if row['FNC'] in ['3', '30'] else '04', row['BIT'], str(self.channel_divisor(c)), c.unit, ('OK · decodificar FLOAT32/CDAB antes da escala' if c.codec=='float32_cdab' else 'OK') if not self.row_issues(c) else 'DIVERGENTE']+([c.codec,c.source_reference] if self.profile.vendor=='DEIF' else []))
        return ('\ufeff' + output.getvalue()).encode('utf-8')

    def dashboard(self, table: str, plant: str, datasource: str, uid=''):
        if not re.fullmatch(r'[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?', table):
            raise ValueError('Tabela inválida. Use id_planta ou public.id_planta, sem espaços.')
        if not plant.strip():
            raise ValueError('Informe o nome da planta.')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', datasource):
            raise ValueError('Informe um UID válido do datasource PostgreSQL.')
        uid = uid.strip() or f'logsis-{self.profile.model.lower()}-' + hashlib.sha256(table.encode()).hexdigest()[:10]
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', uid):
            raise ValueError('UID do dashboard: use até 40 letras, números, _ ou -.')
        alert_hours = number(self.maintenance_alert_hours, 'Aviso de manutenção')
        if alert_hours < 0:
            raise ValueError('O aviso de manutenção não pode ser negativo.')
        dashboard = self.dashboard_template()
        dashboard.update(id=None, uid=uid, title=f'LOGSIS / {plant.strip()} — {self.profile.model}', version=1)
        labels = {}
        for channel in self.profile.channels:
            variable_name = None
            if channel.label_variable:
                variable_name = channel.label_variable
            elif channel.input_letter:
                variable_name = 'Nome_Entrada_' + channel.input_letter
            elif not channel.role and channel.group == 'Manutenção' and channel.number >= 53:
                first = 54 if self.profile.model == 'DSE7420' else 53
                variable_name = 'Nome_Manutencao_' + str(channel.number - first + 1)
            if variable_name:
                labels[variable_name] = self.channel_name(channel)
        for variable in dashboard['templating']['list']:
            if variable['name'] in labels:
                variable['query'] = labels[variable['name']]
                variable.pop('current', None)
            elif variable['name'] == 'Manutencao_Alerta_h':
                variable['query'] = str(alert_hours)
                variable.pop('current', None)
            if variable['name'] == 'Id_Logsis':
                variable['query'] = table
                variable.pop('current', None)
            elif variable['name'] == 'Divisor_Energia':
                variable['query'] = str(number(self.energy_divisor))
                variable.pop('current', None)
        def bind(item):
            if isinstance(item, dict):
                ds = item.get('datasource')
                if isinstance(ds, dict) and ds.get('type') == 'grafana-postgresql-datasource':
                    ds['uid'] = datasource
                for value in item.values():
                    bind(value)
            elif isinstance(item, list):
                for value in item:
                    bind(value)
        bind(dashboard)
        return dashboard

    def bundle_bytes(self, table, plant, datasource='zKW_ld27k', uid=''):
        binary = self.bin_bytes()
        dashboard = self.dashboard(table, plant, datasource, uid)
        report = {
            'studio_version': __version__, 'model': self.profile.model,
            'dashboard_reference': self.profile.dashboard_version, 'channels': self.profile.count,
            'table': table, 'dashboard_uid': dashboard['uid'], 'datasource_uid': datasource,
            'sha256_bin': hashlib.sha256(binary).hexdigest(), 'compatible': True,
            'mode_field': next((c.column for c in self.profile.channels if c.role=='mode'), 'mdb40'), 'mode_codes': ({**MODES,4:'AUTO / RETORNO MANUAL',5:'CONFIGURAÇÃO'} if self.profile.kind!='legacy' else MODES),
            'alarm_fields': {'warning': 'mdb41 / bit 10', 'trip': 'mdb42 / bit 11', 'shutdown': 'mdb43 / bit 12'},
            'breaker': 'mdb52 / 0 aberto, 1 fechado',
            'transfer_generator': 'mdb53 / 0 aberto, 1 fechado' if self.profile.model == 'DSE7420' else None,
            'energy_divisor': str(number(self.energy_divisor)),
            'maintenance_alert_hours': str(number(self.maintenance_alert_hours)),
            'profile_version': self.profile.version,
            'channels_map': [{'mdb': c.number, 'bin_index': c.index, 'sql_column': c.column,
                              'address': integer(self.rows[c.index]['ADDR']), 'fnc': integer(self.rows[c.index]['FNC']),
                              'bit': integer(self.rows[c.index]['BIT']), 'divisor': str(self.channel_divisor(c)), 'unit': c.unit}
                             for c in self.profile.channels],
        }
        if self.profile.kind != 'legacy':
            report.update(manual_family=self.profile.manual_family, verification_basis='GenComm 2.93 / 13-04-2015; document-based, no physical controller test', manual_notes=self.profile.manual_notes,
                          signal_semantics='LED indicators, not physical breaker feedback',
                          alarm_fields={c.role:f'{c.column} / bit {c.params["BIT"]}' for c in self.profile.channels if c.role in ['warning','trip','shutdown']},
                          breaker={c.role:c.column for c in self.profile.channels if c.role.startswith('led_')},transfer_generator=None,
                          role_columns={c.role:c.column for c in self.profile.channels if c.role})
        if self.profile.vendor == 'DEIF':
            report.update(vendor='DEIF', application=self.profile.application, topology=self.profile.topology,
                          verification_basis=self.profile.source_document+'; validação documental e simulada, sem teste físico',
                          signal_semantics='Retornos ON/OFF, ou estado lógico de alimentação quando explicitamente identificado. Dados desconhecidos não confirmam posição.',
                          mode_codes=None, mode_field='MODO_LOCAL derivado de bits documentados',
                          alarm_fields='Derivados dos registros nativos; severidade não documentada permanece sem classificação',
                          breaker='Verificar semântica por aplicação no dashboard e no mapa',
                          raw_contract='O coletor envia os bits como inteiro. FLOAT32/CDAB é reinterpretado no SQL; nenhuma conversão float é exigida do LogSis.',
                          codecs={c.column:{'codec':c.codec,'divisor':c.divisor,'source':c.source_reference} for c in self.profile.channels})
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
            prefix = self.profile.model
            archive.writestr(prefix + '.bin', binary)
            archive.writestr(prefix + '_GRAFANA.json', json.dumps(dashboard, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
            archive.writestr(prefix + '_MAPA.csv', self.csv_bytes())
            archive.writestr('COMPATIBILIDADE.json', json.dumps(report, ensure_ascii=False, indent=2) + '\n')
            note = ('DEIF: estados, escalas e codecs seguem o perfil específico. FLOAT32/CDAB é decodificado no SQL a partir dos 32 bits brutos. Para CGC, entradas FC02 exigem suporte FNC2 no coletor. Consulte COMPATIBILIDADE.json.\n' if self.profile.vendor=='DEIF' else 'Os campos de alarme têm BIT10/11/12 configurados para extração pelo coletor.\n')
            archive.writestr('LEIA-ME.txt', f'LogSis Studio {__version__} / {prefix}\n\n1. O BIN é a configuração do equipamento LogSis.\n2. Importe o arquivo GRAFANA.json no Grafana.\n3. Tabela: {table}\n4. UID do dashboard: {dashboard["uid"]}\n5. O CSV relaciona o índice zero do BIN com MDB01/mdb1 e os demais canais.\n\nEscalas e endereços seguem os perfis desta versão. O teste local não certifica a variante/firmware em campo.\n'+note)
        return stream.getvalue()


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
