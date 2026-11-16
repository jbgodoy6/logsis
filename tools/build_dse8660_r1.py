"""Standalone DSE8660 MkII MAINS/BUS performance fix for the approved 58-slot map.

BIN, register allocation, decoder scales and the approved switch drawing are
preserved. Missing transmissions no longer erase earlier values in the filter.
"""
from pathlib import Path
import copy
import json
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from logsis_studio.core import load_profile
from logsis_studio import manual_dashboard as ui
from tools.build_agc150_r7 import latest_sql

STEM = 'DSE8660_REDE_BUS_R1_OTIMIZADO'
SOURCE = 'DSE8660_PADRAO_DSE7420_9_1_3.json'
PROFILE = load_profile('DSE8660')
ROLES = {c.role: c for c in PROFILE.channels}
TABLE = '${Id_Logsis:raw}'
FILTER = '$__timeFilter("time")'


def history_sql(channels):
    """Each panel scans bounded packets once, parses each numeric value once."""
    raw = [ui.numeric('payload->>'+ui.sq(c.column))+f' AS r{c.number}' for c in channels]
    values = [ui.scaled(c, f'r{c.number}')+' AS '+ui.ref(c) for c in channels]
    return f'''WITH packets AS MATERIALIZED (
      SELECT t."time",to_jsonb(t) AS payload FROM {TABLE} t WHERE {FILTER}
    ), raw AS MATERIALIZED (SELECT "time",{','.join(raw)} FROM packets)
    SELECT "time",{','.join(values)} FROM raw ORDER BY "time"'''


def period_sql(old, channel):
    """Preserve the approved baseline/reset/conflict calculations verbatim.

    The previous query repeated the full-record decoder in first_inside and
    samples. Decode in-range counters once; add only the valid prior baseline
    to samples. There cannot be another valid value between that prior sample
    and the beginning of the filter by definition of 'prior'.
    """
    clean = ui.clean(channel, ui.numeric('to_jsonb(t)->>'+ui.sq(channel.column)))
    source = f'(SELECT t."time",({clean}) AS mdb37 FROM $Id_Logsis t) contador'
    pieces = old.split(source)
    assert len(pieces) == 4, 'Expected prior, first_inside and samples sources.'
    samples = ('(SELECT "time",mdb37 FROM period_values UNION ALL '
               'SELECT "time",value AS mdb37 FROM prior) contador')
    body = pieces[0]+source+pieces[1]+'period_values'+pieces[2]+samples+pieces[3]
    prefix = f'''WITH period_packets AS MATERIALIZED (
      SELECT t."time",to_jsonb(t) AS payload FROM {TABLE} t WHERE {FILTER}
    ), period_raw AS MATERIALIZED (
      SELECT "time",{ui.numeric('payload->>'+ui.sq(channel.column))} AS r FROM period_packets
    ), period_values AS MATERIALIZED (
      SELECT "time",{ui.clean(channel, 'r')} AS mdb37 FROM period_raw
    ), prior AS ('''
    assert body.startswith('WITH prior AS (')
    return body.replace('WITH prior AS (', prefix, 1)


def build():
    original = json.loads((ROOT/SOURCE).read_text(encoding='utf-8'))
    d = copy.deepcopy(original)
    first = next(p for p in d['panels'] if p['id'] == 1)
    old_main = first['targets'][0]['rawSql']
    # Keep the already approved downstream decoders, modes, contact vectors,
    # common-output wiring, alarm mappings and power diagnostic verbatim.
    _, downstream = old_main.split('), dados AS (', 1)
    raw = [ui.numeric('payload->>'+ui.sq(c.column))+f' AS r{c.number}'
           for c in PROFILE.channels]
    raw += [ui.numeric("payload->>'gsm_rssi'")+' AS gsm',
            ui.numeric('payload->>'+ui.var('Campo_WiFi_RSSI'))+' AS wifi',
            '''to_char("time" AT TIME ZONE 'America/Sao_Paulo','DD/MM HH24:MI')
               AS "ULTIMA_LEITURA"''']
    main = ('WITH latest_values AS MATERIALIZED ('+latest_sql(PROFILE.count)+'), '
            'raw AS MATERIALIZED (SELECT '+','.join(raw)+' FROM latest_values), '
            'dados AS ('+downstream)
    main = main.replace('), sinais AS (', '), sinais AS MATERIALIZED (', 1)
    main = main.replace('SELECT sinais.*,',
        'SELECT sinais.*,(SELECT observed_at FROM latest_values) AS "OBSERVED_AT",', 1)
    first['targets'][0]['rawSql'] = main
    for p in d['panels']:
        if p['id'] in [14, 15]:
            channel = ROLES['energy_mains' if p['id'] == 14 else 'energy_bus']
            p['targets'][0]['rawSql'] = period_sql(p['targets'][0]['rawSql'], channel)
    for e in first['options']['root']['elements']:
        text = e.get('config', {}).get('text', {})
        if text.get('fixed') == 'ÚLTIMO REGISTRO / BRASÍLIA':
            text['fixed'] = 'ÚLTIMA ATUALIZAÇÃO / BRASÍLIA'
    for v in d['templating']['list']:
        v['hide'] = 2
        if v['name'] == 'Id_Logsis':
            v['query'] = 'id_194057949800264'
            v['current'] = {'text': v['query'], 'value': v['query']}

    old_row = next(p for p in d['panels'] if p['type'] == 'row')
    template = old_row['panels'][0]

    def panel(pid, title, channels, power=False):
        p = copy.deepcopy(template)
        p.update(id=pid, title=title)
        p['targets'] = [{'refId': 'A', 'rawQuery': True, 'format': 'time_series',
                        'editorMode': 'code', 'rawSql': history_sql(channels)}]
        # Reuse all existing type/units/input-name mappings; add human labels.
        p['fieldConfig'] = ui.properties(PROFILE)
        p['fieldConfig']['defaults']['color'] = {'mode': 'palette-classic'}
        p['fieldConfig']['defaults']['custom'] = {
            'drawStyle': 'line', 'lineInterpolation': 'linear', 'lineWidth': 2,
            'fillOpacity': 5, 'showPoints': 'always', 'pointSize': 3, 'spanNulls': True,
            'axisBorderShow': False}
        for c in channels:
            name = '${'+c.label_variable+'}' if c.label_variable else c.name
            p['fieldConfig']['overrides'].append({'matcher': {'id': 'byName', 'options': ui.field(c)},
                'properties': [{'id': 'displayName', 'value': name}]})
        p['options']['legend'] = {'displayMode': 'table', 'placement': 'bottom',
                                  'calcs': ['lastNotNull', 'min', 'max']}
        p['description'] = ('Consulta única do período; cada leitura permanece no seu horário real. '
            'As leituras e os estados das chaves podem ter sido recebidos em horários diferentes.')
        if power:
            p['fieldConfig']['defaults']['custom']['axisLabel'] = 'Potência · kW / kvar / kVA'
            # Explicit units in names + one common scale; no hidden rescaling.
            p['fieldConfig']['overrides'] = []
            p['fieldConfig']['defaults']['unit'] = 'none'
            p['fieldConfig']['defaults']['decimals'] = 2
            for c, name, color in zip(channels,
                ['Ativa (kW)', 'Reativa (kvar)', 'Aparente (kVA)'],
                ['#f2bf70', '#60c5d8', '#9bcf82']):
                p['fieldConfig']['overrides'].append({'matcher': {'id': 'byName', 'options': ui.field(c)},
                    'properties': [{'id': 'displayName', 'value': name},
                        {'id': 'color', 'value': {'mode': 'fixed', 'fixedColor': color}}]})
        return p

    def cs(prefix, fragment):
        return [c for c in PROFILE.channels if c.role.startswith(prefix+fragment)]

    specifications = [
        ('TENSÕES', [panel(1100, 'Rede · tensões', cs('mains', '_v_')),
                     panel(1101, 'BUS · tensões', cs('bus', '_v_'))]),
        ('CORRENTES', [panel(1110, 'Rede · correntes', cs('mains', '_i_')),
                       panel(1111, 'BUS · correntes', cs('bus', '_i_'))]),
        ('POTÊNCIAS', [panel(1120, 'Rede · potências',
                            [ROLES['mains_'+s] for s in ['kw', 'kvar', 'kva']], True),
                       panel(1121, 'BUS · potências',
                            [ROLES['bus_'+s] for s in ['kw', 'kvar', 'kva']], True)]),
        ('DETALHES ELÉTRICOS', [
            panel(1130, 'Rede e BUS · frequências', [ROLES['mains_frequency'], ROLES['bus_frequency']]),
            panel(1131, 'Rede · fator de potência', cs('mains', '_fp')),
            panel(1132, 'BUS · fator de potência', cs('bus', '_fp')),
            panel(1133, 'Rede · potência ativa por fase', cs('mains', '_kw_')),
            panel(1134, 'BUS · potência ativa por fase', cs('bus', '_kw_'))]),
        ('ENERGIA', [panel(1140, 'Rede e BUS · energia acumulada', cs('energy', '_'))]),
        ('ESTADOS E ALERTAS', [
            panel(1150, 'Modo e alarmes', [c for c in PROFILE.channels if c.role in ['mode', 'warning', 'trip', 'shutdown']]),
            panel(1151, 'Entradas digitais', cs('input', '_')),
            panel(1152, 'Chaves · aberto / fechado', cs('led', '_'))])]
    covered = {c.number for group in specifications for p in group[1]
               for c in PROFILE.channels if f' AS "MDB{c.number:02}"' in p['targets'][0]['rawSql']}
    assert covered == set(range(1, PROFILE.count+1)), 'Every original telemetry series must be retained.'
    d['panels'] = [p for p in d['panels'] if p['type'] != 'row']
    start = max(p['gridPos']['y']+p['gridPos']['h'] for p in d['panels'])
    for i, (title, children) in enumerate(specifications):
        for j, p in enumerate(children):
            p['gridPos'] = {'x': 0, 'y': start+i+1+j*8, 'w': 24, 'h': 8}
        d['panels'].append({'id': 1200+i, 'type': 'row', 'title': 'CURVAS / '+title,
            'collapsed': True, 'gridPos': {'x': 0, 'y': start+i, 'w': 24, 'h': 1}, 'panels': children})
    d['version'] = max(2, d['version']+1)
    d['description'] += (' R1 otimizada: mapa de 58 canais e desenho rede/BUS aprovados preservados. '
        'Tabela id_194057949800264. Última observação de cada variável dentro do período; '
        'campos ausentes não apagam valores anteriores, zero é válido e estouro recebido '
        'aparece como traço. A visão geral pode reunir horários diferentes; OBSERVED_AT '
        'contém o horário de cada sinal. Consultas dos históricos convertidas em etapas '
        'materializadas para evitar conversões repetidas do registro inteiro. Tensões, '
        'correntes e potências separadas. Ativa/reativa/aparente juntas por origem. '
        'Potência medida com disjuntor aberto é preservada, com o diagnóstico existente. '
        'Não contém motor/gerador desenhado nem leituras de motor.')
    # Same UID enables an overwrite of the approved export, not a duplicate.
    assert d['uid'] == original['uid']
    path = ROOT/(STEM+'.json')
    path.write_text(json.dumps(d, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
    with zipfile.ZipFile(ROOT/(STEM+'.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(path, path.name)
    with zipfile.ZipFile(ROOT/(STEM+'.zip')) as z:
        assert z.testzip() is None and json.loads(z.read(path.name)) == d
    print('Created', STEM+'.zip')
    return d


if __name__ == '__main__':
    build()
