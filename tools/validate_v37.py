"""Regression tests against isolated Docker PostgreSQL, no production access."""
import itertools,json,pathlib,subprocess
from urllib.parse import unquote
ROOT=pathlib.Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'dist/V37_IMPORTAR.json').read_text())
old=json.loads((ROOT/'V36_IMPORTAR.json').read_text())
assert d['uid']==old['uid'] and d['timezone']=='America/Sao_Paulo'
for p in d['panels']:
 if p['id'] not in [1,14,15] and p['type']!='row':assert p==next(x for x in old['panels'] if x['id']==p['id'])
curves=[]
for row in d['panels']:
 for p in row.get('panels',[]):
  if p.get('type')=='timeseries' and 1000<=p['id']<=1007:
   c=p['fieldConfig']['defaults']['custom']
   assert c['spanNulls'] and c['showPoints']=='always' and c['lineInterpolation']=='smooth'
   curves.append(p['id'])
  if p.get('type')=='timeseries':
   prev=next(x for x in next(x for x in old['panels'] if x['type']=='row')['panels'] if x['id']==p['id'])
   assert p['targets']==prev['targets']
assert len(curves)==8
cases=[
 ('baseline_before_one_inside',[('11:59',100),('12:30',160)],60),
 ('last_baseline_only',[('11:00',1),('11:59',100),('12:30',160)],60),
 ('baseline_exact_start',[('11:59',1),('12:00',100),('13:00',160)],60),
 ('irregular',[('11:59',100),('12:19',110),('12:54',160)],60),
 ('constant',[('11:59',100),('12:30',100)],0),
 ('zero_baseline',[('11:59',0),('12:30',60)],60),
 ('reset',[('11:59',100),('12:30',10),('13:00',40)],None),
 ('reset_recovered',[('11:59',100),('12:30',10),('13:00',200)],None),
 ('no_baseline',[('12:10',100),('12:30',160)],None),
 ('baseline_only',[('11:59',100)],None),
 ('empty',[],None),
 ('null_baseline',[('11:58',100),('11:59',None),('12:30',160)],60),
 ('sentinel_baseline',[('11:58',100),('11:59',2147483647),('12:30',160)],60),
 ('negative_baseline',[('11:58',100),('11:59',-1),('12:30',160)],60),
 ('invalid_inside',[('11:59',100),('12:10',None),('12:20',2147483647),('12:30',160)],60),
 ('exclude_after_end',[('11:59',100),('13:00',160),('13:01',900)],60),
 ('baseline_conflict',[('11:59',100),('11:59',110),('12:30',160)],None),
 ('final_conflict',[('11:59',100),('12:30',160),('12:30',170)],None),
 ('same_duplicate',[('11:59',100),('11:59',100),('12:30',160)],60),
]
parts=['BEGIN;SET LOCAL jit=off;CREATE TEMP TABLE period_check (time timestamptz,mdb36 numeric,mdb37 numeric);'];expected=[]
for id,divisor in [(14,3600),(15,10)]:
 raw=next(p for p in d['panels'] if p['id']==id)['targets'][0]['rawSql']
 raw=raw.replace('$Id_Logsis','period_check').replace('${Divisor_Energia:sqlstring}',"'10'")
 raw=raw.replace('$__timeFrom()',"'2026-10-23T12:00Z'::timestamptz").replace('$__timeTo()',"'2026-10-23T13:00Z'::timestamptz")
 for name,samples,delta in cases:
  parts+=['TRUNCATE period_check;']
  for t,v in samples:
   v='NULL' if v is None else str(v)
   parts+=[f"INSERT INTO period_check VALUES ('2026-10-23T{t}Z',{v},{v});"]
  parts+=['SELECT row_to_json(q) FROM ('+raw+') q;']
  expected.append((id,name,None if delta is None else delta/divisor))
 if id==15:
  for div in [0,-10,1]:
   parts+=['TRUNCATE period_check;',"INSERT INTO period_check VALUES ('2026-10-23T11:59Z',100,100),('2026-10-23T12:30Z',160,160);",'SELECT row_to_json(q) FROM ('+raw.replace("'10'",str(div))+') q;']
   expected.append((id,'divisor_'+str(div),60 if div==1 else None))
parts+=['ROLLBACK;']
def run(parts):
 r=subprocess.run(['docker','exec','-i','logsis-postgres','psql','-U','postgres','-d','logsis','-X','-qAt','-v','ON_ERROR_STOP=1'],input='\n'.join(parts),text=True,capture_output=True,check=True)
 return [json.loads(l) for l in r.stdout.splitlines() if l.startswith('{')]
rows=run(parts);assert len(rows)==len(expected)
for row,(id,name,target) in zip(rows,expected):
 v=next(iter(row.values()));assert (v is None if target is None else abs(v-target)<1e-9),(id,name,v,target)
raw=d['panels'][0]['targets'][0]['rawSql'].replace('$Id_Logsis','alarm_check').replace('$__timeFilter("time")','TRUE')
for v in d['templating']['list']:raw=raw.replace('${'+v['name']+':sqlstring}',"'"+v['query']+"'")
parts=['BEGIN;SET LOCAL jit=off;CREATE TEMP TABLE alarm_check (time timestamptz,gsm_rssi numeric,'+','.join('mdb'+str(n)+' numeric' for n in range(1,54))+');']
combos=list(itertools.product([0,1,None],repeat=3))
for w,t,s in combos:
 vals=','.join('NULL' if v is None else str(v) for v in [w,t,s])
 parts+=['TRUNCATE alarm_check;',f'INSERT INTO alarm_check (time,mdb41,mdb42,mdb43) VALUES (now(),{vals});','SELECT row_to_json(q) FROM (SELECT "GERADOR_ALARME","GERADOR_ALARME_SVG" FROM ('+raw+') x) q;']
parts+=['ROLLBACK;'];rows=run(parts);assert len(rows)==27
normal=None
for (w,t,s),row in zip(combos,rows):
 label='GERADOR / SHUTDOWN' if s==1 else 'GERADOR / TRIP' if t==1 else 'GERADOR / WARNING' if w==1 else 'ALARMES / SEM DADOS' if None in [w,t,s] else 'GRUPO GERADOR'
 assert row['GERADOR_ALARME']==label
 svg=unquote(row['GERADOR_ALARME_SVG'].split(',',1)[1]);assert '<svg' in svg
 if label=='GRUPO GERADOR':normal=svg
 elif 'SEM DADOS' not in label:assert svg!=normal if normal else True
report={'result':'passed','periodCases':len(expected),'alarmCombinations':len(combos),'connectedCurvesWithPoints':curves,'timezone':d['timezone'],'tests':[{'panelId':id,'case':name,'expected':target} for id,name,target in expected]}
(ROOT/'V37_VALIDACAO.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('Passed',len(expected),'period cases, 27 alarm combinations, 8 connected curves with points')
