"""Validate optimized DSE8660 export in local synthetic PostgreSQL/Grafana."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import copy
import json
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from logsis_studio.core import load_profile
from logsis_studio import manual_dashboard as ui
from tools.build_dse8660_r1 import STEM, SOURCE

d = json.loads((ROOT/(STEM+'.json')).read_text())
original = json.loads((ROOT/SOURCE).read_text())
profile = load_profile('DSE8660')
roles = {c.role: c for c in profile.channels}
TABLE = 'dse8660_async_r1_test'
start, end = '2026-11-16T19:00Z', '2026-11-16T20:00Z'


def run(sql):
    r = subprocess.run(['docker', '--host=unix:///var/run/docker.sock', 'exec', '-i',
        'logsis-postgres', 'psql', '-U', 'postgres', '-d', 'logsis', '-XqAt',
        '-v', 'ON_ERROR_STOP=1'], input='SET jit=off;'+sql, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr[:2500]
    return [json.loads(line) for line in r.stdout.splitlines() if line.startswith('{')]


def resolve(sql):
    for v in d['templating']['list']:
        value = v.get('current', {}).get('value', v.get('query', ''))
        sql = sql.replace('${'+v['name']+':sqlstring}', "'"+str(value).replace("'", "''")+"'")
    return sql.replace('${Id_Logsis:raw}', TABLE).replace('$Id_Logsis', TABLE).replace(
        '$__timeFilter("time")', f'"time" BETWEEN \'{start}\' AND \'{end}\'').replace(
        '$__timeFrom()', f"'{start}'::timestamptz").replace('$__timeTo()', f"'{end}'::timestamptz")


def query(sql):
    return run('SELECT row_to_json(q) FROM ('+resolve(sql)+') q;')


def insert(when, values):
    cols = ['time']+list(values)
    vals = ["'"+when+"'"]+[str(v) if v is not None else 'NULL' for v in values.values()]
    run(f'INSERT INTO {TABLE}('+','.join('"'+c+'"' for c in cols)+') VALUES ('+','.join(vals)+');')


def packet(when, **values):
    insert(when, {roles[r].column: v for r, v in values.items()})


# Independent documentary register fixture, not regenerated from the profile.
tree = ast.parse((ROOT/'tools/validate_manual_profiles.py').read_text())
node = next(n for n in tree.body if isinstance(n, ast.Assign) and
            any(isinstance(t, ast.Name) and t.id == 'registers' for t in n.targets))
# This assignment is our own fixed numeric fixture (including bitwise OR).
registers = eval(compile(ast.Expression(node.value), 'fixed_numeric_fixture', 'eval'),
                 {'__builtins__': {}})
run(f'DROP TABLE IF EXISTS {TABLE};CREATE TABLE {TABLE}(time timestamptz,gsm_rssi numeric,"WiFi_rssi" numeric,'+
    ','.join(c.column+' numeric' for c in profile.channels)+');')
packet('2026-11-16T18:59Z', energy_mains=5000, energy_bus=10000)
values = {c.column: registers[int(c.params['ADDR'])] for c in profile.channels
          if c.role not in ['mode', 'warning', 'trip', 'shutdown', 'led_mains', 'led_bus']}
values.update(gsm_rssi=-53, WiFi_rssi=-67)
insert('2026-11-16T19:10Z', values)
packet('2026-11-16T19:15Z', mode=1, warning=0, trip=0, shutdown=0, led_mains=1, led_bus=0)
main = d['panels'][0]['targets'][0]['rawSql']


def snap():
    return query(main)[0]


def check_wires(r, mains_voltage, bus_voltage, common):
    for prefix, on in [('mains', mains_voltage), ('bus', bus_voltage)]:
        assert r['WIRE_'+prefix+'_V'] == ui.wire(ui.RED if on else ui.MUTED, True)
    for alias, vertical in [('WIRE_OUT_MAINS_V', True), ('WIRE_OUT_BUS_V', True),
                            ('WIRE_OUT_H', False), ('WIRE_OUT_V', True)]:
        assert r[alias] == ui.wire(ui.RED if common else ui.MUTED, vertical)


r = snap()
for key, value in {'MDB05': 416.2, 'MDB26': 398.7, 'MDB08': 120,
    'MDB15': 33, 'MDB16': 34, 'MDB17': 1, 'MDB36': 45, 'MDB37': 46,
    'MDB38': 2, 'MDB43': 527, 'MDB44': 1045, 'MODO_LOCAL': 'AUTO',
    'ULTIMA_LEITURA': '16/11 16:15', 'GSM_LOCAL': -53, 'WIFI_LOCAL': -67,
    'CONTACT_LED_MAINS_LABEL': 'FECHADO', 'CONTACT_LED_BUS_LABEL': 'ABERTO',
    'DIAGNOSTICO_8660': 'BUS: POTÊNCIA COM CHAVE ABERTA'}.items():
    assert r[key] == value, (key, r[key], value)
assert r['OBSERVED_AT']['mdb36'].startswith('2026-11-16T19:10:00')
assert r['OBSERVED_AT']['mdb58'].startswith('2026-11-16T19:15:00')
check_wires(r, True, True, True)
queries = 0
for parent in d['panels']:
    for p in [parent]+parent.get('panels', []):
        for t in p.get('targets', []):
            if 'rawSql' not in t:
                continue
            results = query(t['rawSql'])
            queries += 1
            if p['id'] in [14, 15]:
                assert results[0]['KWH_PERIODO'] == (27 if p['id'] == 14 else 45), results
            if p['id'] == 1120:
                assert any(x['MDB15'] == 33 and x['MDB17'] == 1 and x['MDB16'] == 34 for x in results)
            if p['id'] == 1121:
                assert any(x['MDB36'] == 45 and x['MDB38'] == 2 and x['MDB37'] == 46 for x in results)
# The optimized counter sources must preserve the approved calculation and
# its diagnostics, including resets, conflicts, missing baseline and zero.
counter_cases = {
    'monotonic': [('18:59', 1000), ('19:10', 1010), ('19:20', 1020)],
    'single_inside': [('18:59', 1000), ('19:10', 1010)],
    'no_prior': [('19:10', 1010), ('19:20', 1020)],
    'reset_inside': [('18:59', 1000), ('19:10', 1010), ('19:20', 10), ('19:30', 20)],
    'incompatible_prior': [('18:59', 1000), ('19:10', 10), ('19:20', 20)],
    'conflicting_same_time': [('18:59', 1000), ('19:10', 1010), ('19:10', 1020), ('19:20', 1030)],
    'invalid_latest': [('18:59', 1000), ('19:10', 1010), ('19:20', 4294967295)],
    'empty_window': [('18:59', 1000)],
    'zero_valid': [('18:59', 0), ('19:10', 0), ('19:20', 1)],
}
for name, readings in counter_cases.items():
    sql = f'BEGIN;TRUNCATE {TABLE};'
    for clock, value in readings:
        sql += f"INSERT INTO {TABLE}(time,mdb43,mdb44) VALUES ('2026-11-16T{clock}Z',{value},{value*2});"
    for pid in [14, 15]:
        for dashboard in [original, d]:
            target = next(p for p in dashboard['panels'] if p['id'] == pid)['targets'][0]['rawSql']
            sql += 'SELECT row_to_json(q) FROM ('+resolve(target)+') q;'
    results = run(sql+'ROLLBACK;')
    assert len(results) == 4 and results[0] == results[1] and results[2] == results[3], (name, results)
# Partial contact updates retain independently timed measurements and contacts.
packet('2026-11-16T19:16Z', led_mains=None, bus_kw=None)
assert snap()['CONTACT_LED_MAINS_LABEL'] == 'FECHADO' and snap()['MDB36'] == 45
packet('2026-11-16T19:17Z', led_mains=0, led_bus=1)
r = snap()
assert r['CONTACT_LED_MAINS_LABEL'] == 'ABERTO' and r['CONTACT_LED_BUS_LABEL'] == 'FECHADO'
check_wires(r, True, True, True)
packet('2026-11-16T19:18Z', led_mains=0, led_bus=0)
r = snap()
check_wires(r, True, True, False)
assert r['MDB36'] == 45  # measured power is never fabricated from breaker position
packet('2026-11-16T19:19Z', led_mains=1, led_bus=1)
check_wires(snap(), True, True, True)
packet('2026-11-16T19:20Z', led_bus=65535, bus_kw=2147483647, mains_i_l1=-1)
r = snap()
assert r['CONTACT_LED_BUS_LABEL'] == 'SEM DADOS' and r['MDB36'] is None and r['MDB08'] is None
packet('2026-11-16T19:21Z', bus_kw=0, mains_i_l1=0, led_bus=0, mains_kw=-500)
r = snap()
assert r['MDB36'] == 0 and r['MDB08'] == 0 and r['MDB15'] == -.5
zero = {c.column: 0 for c in profile.channels if '_v_' in c.role}
zero.update(mdb57=1, mdb58=1)
insert('2026-11-16T19:22Z', zero)
check_wires(snap(), False, False, False)
for i, (code, label) in enumerate([(0, 'STOP'), (1, 'AUTO'), (2, 'MANUAL'),
    (3, 'TESTE C/ CARGA'), (6, 'TESTE S/ CARGA'), (7, 'OFF')]):
    packet(f'2026-11-16T19:{23+i:02}Z', mode=code)
    assert snap()['MODO_LOCAL'] == label
packet('2026-11-16T19:30Z', warning=1)
assert snap()['MDB46'] == 1 and snap()['MDB47'] == 0
# UI drawings, allocations, and all prior telemetry series are retained.
old_elements = copy.deepcopy(original['panels'][0]['options']['root']['elements'])
for e in old_elements:
    if e.get('config', {}).get('text', {}).get('fixed') == 'ÚLTIMO REGISTRO / BRASÍLIA':
        e['config']['text']['fixed'] = 'ÚLTIMA ATUALIZAÇÃO / BRASÍLIA'
assert d['panels'][0]['options']['root']['elements'] == old_elements
assert d['uid'] == original['uid']
assert all(v['hide'] == 2 for v in d['templating']['list'])
assert next(v for v in d['templating']['list'] if v['name'] == 'Id_Logsis')['query'] == 'id_194057949800264'
for side in [0, 1]:
    captions = [e['config']['text'].get('fixed') for e in old_elements
                if e['name'].startswith('Fonte rótulo '+str(side)+' ')]
    assert captions == ['L1–L2', 'L2–L3', 'L3–L1', 'Freq.', 'Potência']
# Filter bounds apply to every carried observation.
start = '2026-11-16T19:14Z'
assert snap()['MDB26'] == 0 and snap()['MDB16'] is None
start, end = '2026-11-16T20:01Z', '2026-11-16T21:00Z'
r = snap()
assert r['MDB36'] is None and r['MODO_LOCAL'] == 'SEM DADOS' and r['ULTIMA_LEITURA'] is None
start, end = '2026-11-16T19:00Z', '2026-11-16T20:00Z'
sp = run("SET TIME ZONE 'America/Sao_Paulo';SELECT row_to_json(q) FROM ("+resolve(main)+') q;')[0]
assert sp['ULTIMA_LEITURA'] == '16/11 16:30'
assert datetime.fromisoformat(sp['OBSERVED_AT']['mdb36']).astimezone(timezone.utc).hour == 19
naive = run('BEGIN;ALTER TABLE '+TABLE+' ALTER COLUMN time TYPE timestamp USING time AT TIME ZONE \'UTC\';'
    'SET TIME ZONE \'America/Sao_Paulo\';SELECT row_to_json(q) FROM ('+resolve(main)+') q;ROLLBACK;')[0]
assert naive['ULTIMA_LEITURA'] == sp['ULTIMA_LEITURA']
# Restore an informative local preview; never changes the production table.
insert('2026-11-16T19:40Z', values)
packet('2026-11-16T19:41Z', mode=1, warning=0, trip=0, shutdown=0, led_mains=1, led_bus=0)
preview = copy.deepcopy(d)
for v in preview['templating']['list']:
    if v['name'] == 'Id_Logsis':
        v.update(query=TABLE, current={'text': TABLE, 'value': TABLE})
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
request = urllib.request.Request('http://127.0.0.1:3300/api/dashboards/db',
    data=json.dumps({'dashboard': preview, 'overwrite': True}).encode(),
    headers={'Content-Type': 'application/json'})
with opener.open(request) as response:
    assert json.load(response)['status'] == 'success'
report = {'result': 'passed', 'queriesExecuted': queries, 'channels': profile.count,
    'table': 'id_194057949800264', 'testDatabase': TABLE,
    'lastObservationPerVariable': True, 'filterBoundaries': True, 'missingFieldPreserves': True,
    'receivedInvalidDoesNotResurrectOlderValue': True, 'zeroRemainsZero': True,
    'commonOutputWiring': True, 'bothOpenAndBothClosed': True,
    'receivedPowerWithOpenBreakerRetained': True, 'drawingsUnchanged': True,
    'lineLineFrequencyAndPowerOnlyUnderSources': True, 'periodEnergyBothSources': True,
    'periodAlgorithmEquivalenceCasesBothSources': len(counter_cases),
    'separateVoltageCurrentPowerCharts': True, 'powerTriplesPerSource': True,
    'brasiliaAndTimestampTypes': True, 'hiddenVariables': True,
    'grafanaLocalImport': True, 'productionDatabaseAccess': False, 'physicalControllerTest': False}
(ROOT/(STEM+'_VALIDACAO.json')).write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
