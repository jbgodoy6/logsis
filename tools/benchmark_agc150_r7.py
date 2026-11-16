"""Compare R6/R7 on a separate local synthetic table; never production data."""
from pathlib import Path
import json
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
CURRENT = 'AGC150_ECU_MITSUBISHI_R7_CORRIGIDO'
PREVIOUS = 'AGC150_ECU_MITSUBISHI_R6_ULTIMAS_LEITURAS'
TABLE = 'agc150_r7_synthetic_benchmark'
N = 40000
new = json.loads((ROOT/(CURRENT+'.json')).read_text())
old = json.loads((ROOT/(PREVIOUS+'.json')).read_text())


def psql(sql, check=True):
    result = subprocess.run(['docker', '--host=unix:///var/run/docker.sock', 'exec', '-i',
        'logsis-postgres', 'psql', '-U', 'postgres', '-d', 'logsis', '-XqAt',
        '-v', 'ON_ERROR_STOP=1'], input='SET jit=off;'+sql,
        text=True, capture_output=True)
    if check:
        assert result.returncode == 0, result.stderr[:2000]
    return result


def resolve(sql):
    for v in new['templating']['list']:
        value = v.get('current', {}).get('value', v.get('query', ''))
        sql = sql.replace('${'+v['name']+':sqlstring}', "'"+str(value).replace("'", "''")+"'")
    return sql.replace('${Id_Logsis:raw}', TABLE).replace('$Id_Logsis', TABLE).replace(
        '$__timeFilter("time")', '"time" BETWEEN \'2026-10-29T19:00Z\' AND \'2026-10-29T20:00Z\'')


values = {7: 6000, 11: 45, 14: 95, 22: 6000, 23: 100,
          30: 2114, 31: 72, 39: 65535, 40: 65535, 43: 450,
          44: 1500, 45: 234, 51: 125, 71: 868, 72: 584}
columns = ','.join('mdb'+str(i)+' numeric' for i in range(1, 101))
selects = [f'CASE WHEN g%19={i%19} THEN {values.get(i, 220 if i<=21 else 0)} END'
           if i<=72 else 'NULL::numeric' for i in range(1, 101)]
psql(f'''DROP TABLE IF EXISTS {TABLE};CREATE TABLE {TABLE}(time timestamptz,
    gsm_rssi numeric,"WiFi_rssi" numeric,{columns});
    INSERT INTO {TABLE} SELECT '2026-10-29T19:00Z'::timestamptz+
    g*interval '0.05 second',-53,NULL::numeric,{','.join(selects)}
    FROM generate_series(0,{N-1}) g;ANALYZE {TABLE};''')


def plan(sql, timeout):
    start = time.monotonic()
    r = psql(f"SET statement_timeout='{timeout}ms';EXPLAIN(ANALYZE,TIMING OFF,FORMAT JSON) "+resolve(sql), False)
    elapsed = (time.monotonic()-start)*1000
    if r.returncode:
        assert 'statement timeout' in r.stderr, r.stderr[:2000]
        return {'timedOut': True, 'limitMs': timeout, 'wallMs': round(elapsed, 1)}
    result = json.loads(r.stdout[r.stdout.index('['):])[0]
    return {'timedOut': False, 'executionMs': result['Execution Time'],
            'planningMs': result['Planning Time']}


def history(d):
    return next(t['rawSql'] for p in d['panels'] for q in p.get('panels', [])
                if q.get('type')=='timeseries' and 'consumo' in q['title'].lower()
                for t in q['targets'])


results = {'rows': N, 'source': 'synthetic sparse telemetry, isolated PostgreSQL 16',
           'productionBenchmark': False}
results['r7Snapshot'] = plan(new['panels'][0]['targets'][0]['rawSql'], 30000)
results['r7ConsumptionHistory'] = plan(history(new), 10000)
assert not results['r7Snapshot']['timedOut']
assert not results['r7ConsumptionHistory']['timedOut']
results['r6ConsumptionHistory'] = plan(history(old), 3000)
# A common time index does not remove the repeated per-point work in R6.
psql(f'CREATE INDEX ON {TABLE}(time);ANALYZE {TABLE};')
results['r7ConsumptionWithTimeIndex'] = plan(history(new), 10000)
results['r6ConsumptionWithTimeIndex'] = plan(history(old), 3000)
(ROOT/(CURRENT+'_DESEMPENHO.json')).write_text(json.dumps(results, indent=2)+'\n')
print(json.dumps(results, indent=2))
