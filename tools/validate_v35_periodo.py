"""Validate period queries in the isolated local Docker PostgreSQL lab."""
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
d = json.loads((ROOT / 'dist/V35_IMPORTAR.json').read_text())
old = json.loads((ROOT / 'V34_IMPORTAR.json').read_text())
assert d['uid'] == old['uid']
for p in old['panels']:
    actual = next(x for x in d['panels'] if x['id'] == p['id'])
    expected = json.loads(json.dumps(p))
    if p['id'] in [10, 11, 12, 13]:
        expected['gridPos'].update(x=(p['id']-10)*4, w=4)
    assert actual == expected, p['id']

cases = [
    ('normal', [('12:00', 100), ('12:30', 130), ('13:00', 160)], 60),
    ('irregular', [('12:03', 100), ('12:19', 110), ('12:54', 160)], 60),
    ('stationary', [('12:00', 100), ('13:00', 100)], 0),
    ('zero_start', [('12:00', 0), ('13:00', 60)], 60),
    ('reset', [('12:00', 100), ('12:30', 10), ('13:00', 40)], None),
    ('reset_recovers', [('12:00', 100), ('12:30', 10), ('13:00', 200)], None),
    ('single', [('12:30', 100)], None),
    ('empty', [], None),
    ('sentinel', [('12:00', 100), ('12:30', 2147483647), ('13:00', 160)], 60),
    ('null', [('12:00', 100), ('12:30', None), ('13:00', 160)], 60),
    ('outside', [('11:59', 1), ('12:00', 100), ('13:00', 160), ('13:01', 900)], 60),
    ('conflict', [('12:00', 100), ('12:00', 110), ('13:00', 160)], None),
    ('same_duplicate', [('12:00', 100), ('12:00', 100), ('13:00', 160)], 60),
]
parts = ['BEGIN; SET LOCAL jit=off; CREATE TEMP TABLE period_check (time timestamptz,mdb36 numeric,mdb37 numeric);']
expected = []
for id, divisor in [(14, 3600), (15, 10)]:
    query = next(p for p in d['panels'] if p['id'] == id)['targets'][0]['rawSql']
    query = query.replace('$Id_Logsis', 'period_check').replace('${Divisor_Energia:sqlstring}', "'10'")
    query = query.replace('$__timeFilter("time")', '"time" BETWEEN \'2026-10-23T12:00Z\' AND \'2026-10-23T13:00Z\'')
    for name, samples, delta in cases:
        parts.append('TRUNCATE period_check;')
        for t, value in samples:
            v = 'NULL' if value is None else str(value)
            parts.append(f"INSERT INTO period_check VALUES ('2026-10-23T{t}Z',{v},{v});")
        parts.append('SELECT row_to_json(q) FROM (' + query + ') q;')
        expected.append((id, name, None if delta is None else delta/divisor))
    if id == 15:
        for div in ['0', '-10', '1']:
            parts += ['TRUNCATE period_check;', "INSERT INTO period_check VALUES ('2026-10-23T12:00Z',100,100),('2026-10-23T13:00Z',160,160);",
                      'SELECT row_to_json(q) FROM ('+query.replace("'10'", "'"+div+"'")+') q;']
            expected.append((id, 'divisor_'+div, 60 if div == '1' else None))
parts.append('ROLLBACK;')
r = subprocess.run(['docker','exec','-i','logsis-postgres','psql','-U','postgres','-d','logsis','-X','-qAt','-v','ON_ERROR_STOP=1'],input='\n'.join(parts),text=True,capture_output=True,check=True)
rows = [json.loads(line) for line in r.stdout.splitlines() if line.startswith('{')]
assert len(rows) == len(expected)
for actual, (id, name, target) in zip(rows, expected):
    value = next(iter(actual.values()))
    assert value is None if target is None else abs(value-target)<1e-9, (id,name,value,target)
report = {'result':'passed','cases':len(expected),'regression':'Existing panels unchanged except four stat widths/positions',
          'results':[{'panelId':id,'case':name,'expected':target} for id,name,target in expected]}
(ROOT/'V35_PERIODO_VALIDACAO.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('Passed:',len(expected),'period SQL cases and existing panel regression')
