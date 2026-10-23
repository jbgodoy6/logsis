"""Timezone regression in isolated PostgreSQL, with no production access."""
import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'dist/V36_IMPORTAR.json').read_text())
old=json.loads((ROOT/'V35_IMPORTAR.json').read_text())
assert d['timezone']=='America/Sao_Paulo' and d['uid']==old['uid']
for p in d['panels']:
 if p['id']!=1:assert p==next(x for x in old['panels'] if x['id']==p['id'])
sql=d['panels'][0]['targets'][0]['rawSql']
for v in d['templating']['list']:sql=sql.replace('${'+v['name']+':sqlstring}',"'"+v['query']+"'")
sql=sql.replace('$Id_Logsis','clock_check').replace('$__timeFilter("time")','TRUE')
parts=['BEGIN;SET LOCAL jit=off;'];expected=[]
for typ in ['timestamp with time zone','timestamp without time zone']:
 parts+=['CREATE TEMP TABLE clock_check (time '+typ+',gsm_rssi numeric,'+','.join('mdb'+str(n)+' numeric' for n in range(1,54))+');']
 for zone in ['UTC','America/Sao_Paulo','Asia/Tokyo']:
  parts+=["SET LOCAL TIME ZONE '"+zone+"';"]
  for instant,label in [('2026-10-23 14:58:00','23/10 11:58'),('2026-10-23 01:30:00','22/10 22:30')]:
   literal=instant+('+00' if typ=='timestamp with time zone' else '')
   parts+=['TRUNCATE clock_check;',"INSERT INTO clock_check(time) VALUES ('"+literal+"');",'SELECT "ULTIMA_LEITURA" FROM ('+sql+') q;']
   expected.append({'columnType':typ,'sessionTimezone':zone,'utc':instant,'brasilia':label})
 parts+=['DROP TABLE clock_check;']
parts+=['ROLLBACK;']
r=subprocess.run(['docker','exec','-i','logsis-postgres','psql','-U','postgres','-d','logsis','-X','-qAt','-v','ON_ERROR_STOP=1'],input='\n'.join(parts),text=True,capture_output=True,check=True)
assert r.stdout.splitlines()==[x['brasilia'] for x in expected],r.stdout
report={'result':'passed','timezone':d['timezone'],'cases':expected,'regression':'All panels except main unifilar identical to V35; period queries unchanged','naiveTimestampAssumption':'UTC, matching the reported three-hour difference'}
(ROOT/'V36_FUSO_VALIDACAO.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('Passed 12 full-query timezone cases, including date rollover; period panels unchanged')
