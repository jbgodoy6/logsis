"""Performance comparison on an isolated synthetic DSE8660 table."""
from pathlib import Path
import ast
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
from tools.build_dse8660_r1 import STEM, SOURCE, PROFILE, history_sql

TABLE = 'dse8660_r1_synthetic_benchmark'
N = 40000
d = json.loads((ROOT/(STEM+'.json')).read_text())
old = json.loads((ROOT/SOURCE).read_text())


def psql(sql, check=True):
    r = subprocess.run(['docker', '--host=unix:///var/run/docker.sock', 'exec', '-i',
        'logsis-postgres', 'psql', '-U', 'postgres', '-d', 'logsis', '-XqAt',
        '-v', 'ON_ERROR_STOP=1'], input='SET jit=off;'+sql,
        text=True, capture_output=True)
    if check:
        assert r.returncode == 0, r.stderr[:2000]
    return r


def resolve(sql):
    for v in d['templating']['list']:
        value = v.get('current', {}).get('value', v.get('query', ''))
        sql = sql.replace('${'+v['name']+':sqlstring}', "'"+str(value).replace("'", "''")+"'")
    return sql.replace('${Id_Logsis:raw}', TABLE).replace('$Id_Logsis', TABLE).replace(
        '$__timeFilter("time")', '"time" BETWEEN \'2026-11-16T19:00Z\' AND \'2026-11-16T20:00Z\'').replace(
        '$__timeFrom()', "'2026-11-16T19:00Z'::timestamptz").replace('$__timeTo()', "'2026-11-16T20:00Z'::timestamptz")


def plan(sql, limit=12000):
    r = psql(f"SET statement_timeout='{limit}ms';EXPLAIN(ANALYZE,TIMING OFF,FORMAT JSON) "+resolve(sql), False)
    if r.returncode:
        assert 'statement timeout' in r.stderr, r.stderr[:2000]
        return {'timedOut': True, 'limitMs': limit}
    result = json.loads(r.stdout[r.stdout.index('['):])[0]
    return {'timedOut': False, 'executionMs': result['Execution Time'], 'planningMs': result['Planning Time']}


tree = ast.parse((ROOT/'tools/validate_manual_profiles.py').read_text())
node = next(n for n in tree.body if isinstance(n, ast.Assign) and
            any(isinstance(t, ast.Name) and t.id == 'registers' for t in n.targets))
registers = eval(compile(ast.Expression(node.value), 'fixed_fixture', 'eval'), {'__builtins__': {}})
values = []
for c in PROFILE.channels:
    value = str(registers[int(c.params['ADDR'])])
    if c.role.startswith('energy_'):
        value += '+g/100'
    if c.role in ['warning', 'shutdown']:
        value = '0'
    values.append(value)
psql(f'DROP TABLE IF EXISTS {TABLE};CREATE TABLE {TABLE}(time timestamptz,gsm_rssi numeric,"WiFi_rssi" numeric,'+
     ','.join(c.column+' numeric' for c in PROFILE.channels)+');'+
     f'''INSERT INTO {TABLE} SELECT '2026-11-16T19:00Z'::timestamptz+
        g*interval '0.05 second',-53,-67,{','.join(values)}
        FROM generate_series(0,{N-1}) g;ANALYZE {TABLE};''')
old_history = next(x for p in old['panels'] for x in p.get('panels', []) if x['id'] == 1000)['targets'][0]['rawSql']
same_channels = [c for c in PROFILE.channels if c.group == 'Rede']
assert len(same_channels) == 21
report = {'rows': N, 'source': 'synthetic local PostgreSQL 16; no production access',
    'r1Snapshot': plan(d['panels'][0]['targets'][0]['rawSql']),
    'r1Same21MainsSeries': plan(history_sql(same_channels)),
    'oldSame21MainsSeries': plan(old_history, 3000),
    'r1MainsPeriod': plan(next(p for p in d['panels'] if p['id'] == 14)['targets'][0]['rawSql'])}
assert not report['r1Snapshot']['timedOut']
assert not report['r1Same21MainsSeries']['timedOut']
assert not report['r1MainsPeriod']['timedOut']
(ROOT/(STEM+'_DESEMPENHO.json')).write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
