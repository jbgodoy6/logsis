"""AGC150 ECU + independent ME96SS: bounded snapshots and linear histories.

Changes only this exported dashboard. No BIN or Studio profile is changed.
"""
from pathlib import Path
import copy
import json
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from logsis_studio.core import load_profile
from logsis_studio import electronic_dashboard as ecu
from logsis_studio import manual_dashboard as ui, deif_dashboard as deif

STEM = 'AGC150_ECU_MITSUBISHI_R7_CORRIGIDO'
PREVIOUS = 'AGC150_ECU_MITSUBISHI_R6_ULTIMAS_LEITURAS'
TABLE = '${Id_Logsis:raw}'
FILTER = '$__timeFilter("time")'
PROFILE = load_profile('AGC150_GEN_ECU')
ROLES = {c.role: c for c in PROFILE.channels}


def latest_sql(channel_count=72):
    """One bounded table scan, constant aggregate state, no per-field sorts.

    Prefix each raw value by a fixed-width UTC timestamp. max() with the C
    collation selects the last received value, including zero/invalid values.
    NULL and empty fields mean no transmission. Prefixes are stripped before
    the existing typed decoders run. All application dates use AD years 1-9999.
    """
    assert 1 <= channel_count <= 100
    fields = [ui.sq('mdb'+str(i)) for i in range(1, channel_count+1)]
    fields += [ui.sq('gsm_rssi'), ui.var('Campo_WiFi_RSSI')]
    utc = '''CASE WHEN pg_typeof(t."time")='timestamp without time zone'::regtype
        THEN t."time"::timestamp
        ELSE t."time"::timestamptz AT TIME ZONE 'UTC' END'''
    aggregates, cells = [], []
    for i, key in enumerate(fields):
        value = f'payload->>{key}'
        aggregates.append(f'''max((stamp||({value})) COLLATE "C")
          FILTER(WHERE nullif(btrim({value}),'') IS NOT NULL) AS k{i}''')
        cells.append(f'({key},p.k{i})')
    observed = '''make_timestamp(substring(c.value,1,4)::int,
      substring(c.value,5,2)::int,substring(c.value,7,2)::int,
      substring(c.value,9,2)::int,substring(c.value,11,2)::int,
      substring(c.value,13,9)::double precision) AT TIME ZONE 'UTC' '''
    return f'''WITH ranged AS MATERIALIZED (
      SELECT to_char(({utc}),'YYYYMMDDHH24MISS.US') AS stamp,
        to_jsonb(t) AS payload FROM {TABLE} t WHERE {FILTER}
    ), packed AS (SELECT {','.join(aggregates)} FROM ranged), unpacked AS (
      SELECT c.field,substring(c.value FROM 22) AS value,
        ({observed}) AS observed FROM packed p
      CROSS JOIN LATERAL (VALUES {','.join(cells)}) c(field,value)
      WHERE c.value IS NOT NULL
    ) SELECT max(observed) AS "time",
      coalesce(jsonb_object_agg(field,value),'{{}}'::jsonb) AS payload,
      coalesce(jsonb_object_agg(field,to_jsonb(observed)),'{{}}'::jsonb) AS observed_at
      FROM unpacked'''


def raw_numeric(field):
    return ui.numeric('payload->>'+ui.sq(field))


def word(expr):
    return f'''CASE WHEN {expr}=trunc({expr}) AND {expr} BETWEEN -32768 AND 65535
      THEN mod({expr}+65536,65536) END'''


def history_sql(channels=(), meter=None):
    """One query per panel. Window groups carry only availability dependencies.

    Sensor values keep their own real observation time; there is no future
    lookahead and no synthetic pressure zero for an absent packet.
    """
    flags = {c.validity_role for c in channels if c.validity_role}
    deps = {'mdb'+str(ROLES[role].number) for role in flags}
    fields = {'mdb'+str(c.number) for c in channels}
    if meter == 'energy':
        deps |= {'mdb71', 'mdb72'}
    if meter == 'voltage':
        fields |= {'mdb64', 'mdb65', 'mdb66'}
    if meter == 'current':
        fields |= {'mdb60', 'mdb61', 'mdb62'}
    power_meter = {'active': (68, 'P', 'Potência ativa'),
                   'reactive': (69, 'Q', 'Potência reativa'),
                   'apparent': (70, 'S', 'Potência aparente')}
    if meter in power_meter:
        fields.add('mdb'+str(power_meter[meter][0]))
    if meter == 'power':
        fields |= {'mdb68', 'mdb69', 'mdb70'}
    raw = [raw_numeric(f)+' AS "R_'+f+'"' for f in sorted(fields)]
    raw += ['nullif(btrim(payload->>'+ui.sq(f)+'),\'\') AS "T_'+f+'"'
            for f in sorted(deps)]
    parts = [f'''packets AS MATERIALIZED (SELECT t."time",to_jsonb(t) AS payload
        FROM {TABLE} t WHERE {FILTER})''',
        'raw AS MATERIALIZED (SELECT "time",'+','.join(raw)+' FROM packets)']
    source = 'raw'
    if deps:
        counts = [f'count("T_{f}") OVER(ORDER BY "time") AS "G_{f}"'
                  for f in sorted(deps)]
        carry = [f'max("T_{f}") OVER(PARTITION BY "G_{f}") AS "C_{f}"'
                 for f in sorted(deps)]
        parts += ['grouped AS (SELECT raw.*,'+','.join(counts)+' FROM raw)',
                  'carried AS (SELECT grouped.*,'+','.join(carry)+' FROM grouped)']
        source = 'carried'
    values = []
    for c in channels:
        raw_value = '"R_mdb'+str(c.number)+'"'
        value = ecu.decode_sql(c, raw_value)
        if c.validity_role:
            flag = ROLES[c.validity_role]
            flag_value = ecu.decode_sql(flag, ui.numeric('"C_mdb'+str(flag.number)+'"'))
            value = f'CASE WHEN (({flag_value})::bigint >> {c.validity_bit} & 1)=1 THEN {value} END'
        if 'pressure' in c.role:
            # User request: overflow is zero ONLY on pressure curves.
            width = 32 if c.params['FNC'] in ['30', '40'] else 16
            wrap, half = 1 << width, 1 << (width-1)
            invalid = [half-1, half-2, half-3, half, wrap-1] if c.signed else [wrap-1]
            overflow = (f'{raw_value}=trunc({raw_value}) AND {raw_value} BETWEEN {-half} AND {wrap-1}'
                        f' AND mod({raw_value}+{wrap},{wrap}) IN ('+','.join(map(str, invalid))+')')
            value = f'CASE WHEN {overflow} THEN 0 ELSE ({value}) END'
        values.append(value+' AS '+deif.ident(c.name))
    if meter in ['voltage', 'current']:
        nums = [64, 65, 66] if meter == 'voltage' else [60, 61, 62]
        names = ['V12', 'V23', 'V31'] if meter == 'voltage' else ['I1', 'I2', 'I3']
        divisor = ui.var('MM_Divisor_V' if meter == 'voltage' else 'MM_Divisor_I')
        for n, name in zip(nums, names):
            values.append('('+word('"R_mdb'+str(n)+'"')+')/NULLIF('+divisor+'::numeric,0) AS '+deif.ident('ME96SS '+name))
    if meter == 'energy':
        lo = '('+word(ui.numeric('"C_mdb71"'))+')'
        hi = '('+word(ui.numeric('"C_mdb72"'))+')'
        base = ui.var('MM_Base_Energia')+'::numeric'
        divisor = ui.var('MM_Divisor_kWh')+'::numeric'
        values.append(f'CASE WHEN {base}>1 AND {lo}<{base} THEN ({hi}*{base}+{lo})/NULLIF({divisor},0) END AS "ME96SS ENERGY"')
    selected_power = list(power_meter.values()) if meter == 'power' else (
        [power_meter[meter]] if meter in power_meter else [])
    for n, key, label in selected_power:
        divisor = ui.var('MM_Divisor_'+key)
        values.append('('+word('"R_mdb'+str(n)+'"')+')/NULLIF('+divisor+
                      '::numeric,0) AS '+deif.ident('ME96SS · '+label))
    return 'WITH '+','.join(parts)+' SELECT "time",'+','.join(values)+' FROM '+source+' ORDER BY "time"'


def build():
    original = json.loads((ROOT/(PREVIOUS+'.json')).read_text(encoding='utf-8'))
    d = copy.deepcopy(original)
    old_main = d['panels'][0]['targets'][0]['rawSql']
    prefix = 'WITH latest_values AS MATERIALIZED ('
    assert old_main.startswith(prefix)
    _, tail = old_main.split('), controller AS (', 1)
    main = prefix+latest_sql()+'), controller AS ('+tail

    def replace_main(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == 'rawSql' and isinstance(v, str):
                    obj[k] = v.replace(old_main, main)
                else:
                    replace_main(v)
        elif isinstance(obj, list):
            for v in obj:
                replace_main(v)
    replace_main(d)
    for p in d['panels']:
        if p['id'] == 40:
            p['datasource'] = {'type': 'datasource', 'uid': '-- Dashboard --'}
            p['targets'] = [{'refId': 'A', 'panelId': 1, 'withTransforms': False}]
        for panel in p.get('panels', []):
            if panel.get('type') != 'timeseries':
                continue
            if panel['id'] in [140, 141, 142]:
                sql = history_sql(meter={140: 'voltage', 141: 'current', 142: 'energy'}[panel['id']])
            else:
                channels = []
                for target in panel['targets']:
                    matches = [c for c in PROFILE.channels if (' AS '+deif.ident(c.name)) in target['rawSql']]
                    assert len(matches) == 1, (panel['title'], len(matches))
                    channels.append(matches[0])
                sql = history_sql(channels)
            panel['targets'] = [{'refId': 'A', 'rawQuery': True, 'format': 'time_series',
                                  'editorMode': 'code', 'rawSql': sql}]
            panel['description'] = (panel.get('description', '')+
                ' Consulta única por painel, com validade ECU acompanhada no tempo por janelas. '
                'Nas curvas de pressão, estouro é zero; amostra ausente continua sem valor.')
    # Flat, collapsible rows are supported by Grafana; nested rows are not.
    # Keep sources separate; P/Q/S share one chart per instrument as requested.
    old_row = next(p for p in d['panels'] if p['type'] == 'row')
    curves = {p['id']: p for p in old_row['panels']}
    curves[102]['title'] = 'Companhia · tensões'
    meter_panel = copy.deepcopy(curves[103])
    meter_panel.update(id=152, title='Rede / ME96SS independente · potências')
    curves[152] = meter_panel
    curves[103]['title'] = 'Gerador · potências'
    gen_power = [ROLES[r] for r in ['gen_kw', 'gen_kvar', 'gen_kva']]
    curves[103]['targets'][0]['rawSql'] = history_sql(gen_power)
    curves[152]['targets'][0]['rawSql'] = history_sql(meter='power')
    for pid, names in [(103, [c.name for c in gen_power]),
                       (152, ['ME96SS · Potência ativa', 'ME96SS · Potência reativa',
                              'ME96SS · Potência aparente'])]:
        panel = curves[pid]
        # A common numeric axis compares the three magnitudes directly. Their
        # units are explicit in the series names/legend/tooltip rather than
        # letting Grafana silently autoscale three independent unit axes.
        panel['fieldConfig']['defaults']['unit'] = 'none'
        panel['fieldConfig']['defaults']['decimals'] = 2
        panel['fieldConfig']['defaults']['custom']['axisLabel'] = 'Potência · kW / kvar / kVA'
        panel['fieldConfig']['overrides'] = []
        for name, label, color in zip(names, ['Ativa (kW)', 'Reativa (kvar)', 'Aparente (kVA)'],
                                      ['#f2bf70', '#60c5d8', '#9bcf82']):
            panel['fieldConfig']['overrides'].append({'matcher': {'id': 'byName', 'options': name},
                'properties': [{'id': 'displayName', 'value': label},
                               {'id': 'color', 'value': {'mode': 'fixed', 'fixedColor': color}}]})
        panel['description'] = ('Ativa, reativa e aparente juntas, em escala numérica comum; '
            'unidades indicadas na legenda e no tooltip. Instrumentos separados. '
            'O ME96SS é independente do unifilar do AGC150.')
    d['panels'] = [p for p in d['panels'] if p['type'] != 'row']
    start = max(p['gridPos']['y']+p['gridPos']['h'] for p in d['panels'])
    groups = [('TENSÕES', [100, 102, 140]), ('CORRENTES', [101, 141]),
              ('POTÊNCIAS', [103, 152]),
              ('MOTOR ECU', [104, 105, 106]), ('ENERGIA', [142])]
    for i, (title, ids) in enumerate(groups):
        children = [curves[pid] for pid in ids]
        for j, panel in enumerate(children):
            panel['gridPos'] = {'x': 0, 'y': start+i+1+j*8, 'w': 24, 'h': 8}
        d['panels'].append({'id': 900+i, 'type': 'row', 'title': 'CURVAS / '+title,
            'collapsed': True, 'gridPos': {'x': 0, 'y': start+i, 'w': 24, 'h': 1},
            'panels': children})
    d['version'] = 8
    for v in d['templating']['list']:
        v['hide'] = 2
    d['description'] += (' R7: consultas otimizadas para mensagens parciais: uma leitura do período '
        'para a visão geral e uma consulta por painel histórico. Última observação de cada variável '
        'preservada dentro dos limites do filtro. Apenas nas curvas de pressão, estouros são zero. '
        'Curvas organizadas em tensões, correntes, potências, motor ECU e energia; '
        'ativa, reativa e aparente ficam juntas em um gráfico por equipamento. '
        'Compatível com o BIN R5. UID preservado para sobrescrever a dashboard anterior.')
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
