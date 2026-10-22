"""Regression tests for the dedicated synthetic Docker lab; never production."""
import itertools
import json
import pathlib
import subprocess

ROOT=pathlib.Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'dist/V26_IMPORTAR.json').read_text())
v25=json.loads((ROOT/'V25_IMPORTAR.json').read_text())
sql=d['panels'][0]['targets'][0]['rawSql']
assert v25['panels'][0]['targets'][0]['rawSql'].rstrip().rstrip(';') in sql
assert d['panels'][1]['targets']==v25['panels'][1]['targets']
assert d['panels'][1]['fieldConfig']==v25['panels'][1]['fieldConfig']
assert [{k:v for k,v in p.items() if k!='gridPos'} for p in d['panels'][2]['panels']]==[{k:v for k,v in p.items() if k!='gridPos'} for p in v25['panels'][2]['panels']]
sql=sql.replace('$Id_Logsis','id_255880306351140').replace('$__timeFilter("time")', '"time" BETWEEN \'2026-01-01T00:00Z\' AND \'2026-01-01T01:00Z\'')
parts=['BEGIN; CREATE TEMP TABLE id_255880306351140 (LIKE public.id_255880306351140);']
def row(values,time='2026-01-01T00:30Z'):
    return f"INSERT INTO id_255880306351140 SELECT '{time}'::timestamptz,22,"+','.join('NULL' if values.get(i) is None else str(values[i]) for i in range(1,57))+';'
def query():return 'SELECT row_to_json(q) FROM ('+sql+') q;'
cases=list(itertools.product([0,1,None],repeat=4))
for a,b,k1,k2 in cases:
    values={i:0 for i in range(1,57)}
    for nums,state in [(range(30,36),a),(range(9,15),b)]:
        for n in nums:values[n]=None if state is None else (2200 if state else 0)
    values[55],values[56]=k1,k2
    parts+=['TRUNCATE id_255880306351140;',row(values),query()]
# Edge cases: empty window, sentinel voltages, and no backfill of latest missing signals.
parts+=['TRUNCATE id_255880306351140;',query()]
values={i:0 for i in range(1,57)}
for n in list(range(9,15))+list(range(30,36)):values[n]=32763
parts+=[row(values),query()]
old_values={i:0 for i in range(1,57)}
for n in list(range(9,15))+list(range(30,36)):old_values[n]=2200
old_values[55]=1
missing={i:None for i in range(1,57)}
parts+=['TRUNCATE id_255880306351140;',row(old_values,'2026-01-01T00:10Z'),row(missing,'2026-01-01T00:20Z'),query()]
one_phase={i:0 for i in range(1,57)}
one_phase[9]=1;one_phase[56]=1
parts+=['TRUNCATE id_255880306351140;',row(one_phase),query(),'ROLLBACK;']
p=subprocess.run(['docker','exec','-i','logsis-postgres','psql','-U','postgres','-d','logsis','-X','-v','ON_ERROR_STOP=1','-At'],input='\n'.join(parts),capture_output=True,text=True,check=True)
rows=[json.loads(x) for x in p.stdout.splitlines() if x.startswith('{')]
assert len(rows)==85
for case,result in zip(cases,rows):
    possibilities=[([False,True] if x is None else [bool(x)]) for x in case]
    outcomes={int((a and k1) or (b and k2)) for a,b,k1,k2 in itertools.product(*possibilities)}
    expected=next(iter(outcomes)) if len(outcomes)==1 else None
    assert result['TENSAO_REDE_PRESENTE']==case[0],case
    assert result['TENSAO_GMG_PRESENTE']==case[1],case
    assert result['TENSAO_SAIDA_PRESENTE']==expected,(case,expected,result['TENSAO_SAIDA_PRESENTE'])
for result in [rows[81],rows[83]]:
    assert all(result[k] is None for k in ['TENSAO_REDE_PRESENTE','TENSAO_GMG_PRESENTE','TENSAO_SAIDA_PRESENTE'])
assert rows[82]['TENSAO_REDE_PRESENTE'] is None and rows[82]['TENSAO_GMG_PRESENTE'] is None
# With both contacts explicitly open, the inferred bus is disconnected even if source sensors are invalid.
assert rows[82]['TENSAO_SAIDA_PRESENTE']==0
assert rows[84]['TENSAO_GMG_PRESENTE']==1 and rows[84]['TENSAO_SAIDA_PRESENTE']==1
report={'truthTableCases':81,'edgeCases':4,'result':'passed','checks':['all source/contact combinations including unknown','empty interval','sentinel voltage invalid','latest missing row not forward-filled','single positive phase detects presence','existing measurement SQL preserved','instrumentation queries/mappings preserved','13 history panels preserved apart from position']}
(ROOT/'dist/V26_SQL_VALIDACAO.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('85 cenários SQL aprovados; regressões de consultas e históricos aprovadas.')
