"""DSE8610 V3: SQL and artifact checks in isolated Docker PostgreSQL."""
import ast,itertools,json,pathlib,re,subprocess
from urllib.parse import unquote
ROOT=pathlib.Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'dist/DSE8610_V3_IMPORTAR.json').read_text())
assert d['uid']=='logsis-dse8610-v1-bus' and d['timezone']=='America/Sao_Paulo'
assert d['refresh']=='5s' and not d['links']
assert not re.search(r'\bmdb(?:5[3-9]|[6-9]\d|100)\b',json.dumps(d),re.I)
assert '###' not in json.dumps(d)
main=d['panels'][0];names=[e['name'] for e in main['options']['root']['elements']]
assert names.count('Gerador vetorial')==1 and names.count('Símbolo do barramento BUS')==1
assert not any('Torre' in n for n in names)
channels=set()
for p in d['panels']:
 if p['type']=='canvas':
  for e in p['options']['root']['elements']:
   if e['name'].startswith(('Fonte leitura MDB','Leitura MDB')):channels.add(int(re.search(r'MDB(\d+)',e['name'])[1]))
assert channels==set(range(1,53))
variables={v['name']:v['query'] for v in d['templating']['list']}
def resolve(sql,overrides=None,filter=True):
 for name,value in (variables| (overrides or {})).items():sql=sql.replace('${'+name+':sqlstring}',"'"+str(value).replace("'","''")+"'")
 sql=sql.replace('$Id_Logsis','check8610')
 sql=sql.replace('$__timeFilter("time")','"time" BETWEEN \'2026-10-23T12:00Z\' AND \'2026-10-23T13:00Z\'')
 return sql.replace('$__timeFrom()',"'2026-10-23T12:00Z'::timestamptz").replace('$__timeTo()',"'2026-10-23T13:00Z'::timestamptz")
def table(typ='timestamptz',radio=True):
 return 'CREATE TEMP TABLE check8610 (time '+typ+','+','.join(f'mdb{n} numeric' for n in range(1,53))+(',gsm_rssi text,"WiFi_rssi" text,wifi_rssi text' if radio else '')+');'
def row(values,time='2026-10-23T12:05Z',radio=None):
 cols=['time']+[f'mdb{n}' for n in values];vals=["'"+time+"'"]+['NULL' if v is None else str(v) for v in values.values()]
 for name,value in (radio or {}).items():cols.append('"'+name+'"');vals.append('NULL' if value is None else "'"+str(value).replace("'","''")+"'")
 return 'INSERT INTO check8610 ('+','.join(cols)+') VALUES ('+','.join(vals)+');'
def electrical(g,b,k):
 return {**{n:None if g is None else 2200*g for n in range(9,15)},**{n:None if b is None else 2200*b for n in range(30,36)},52:k}
def sql_main(keys,overrides=None):
 return 'SELECT row_to_json(q) FROM (SELECT '+','.join('"'+k+'"' for k in keys)+' FROM ('+resolve(main['targets'][0]['rawSql'],overrides)+') x) q;'
def run(parts):
 r=subprocess.run(['docker','exec','-i','logsis-postgres','psql','-U','postgres','-d','logsis','-X','-qAt','-v','ON_ERROR_STOP=1'],input='\n'.join(parts),text=True,capture_output=True,check=True)
 return [json.loads(l) for l in r.stdout.splitlines() if l.startswith('{')]
# Every voltage/breaker combination: measured BUS never depends on the breaker.
parts=['BEGIN;SET LOCAL jit=off;',table()];expected=[]
for g,b,k in itertools.product([0,1,None],repeat=3):
 parts+=['TRUNCATE check8610;',row(electrical(g,b,k)),sql_main(['TENSAO_GMG','TENSAO_BUS','DISJUNTOR_GCB','GCB_POSICAO','GCB_CONTATO_SVG'])]
 expected.append((g,b,k))
parts+=['ROLLBACK;'];rows=run(parts)
for a,(g,b,k) in zip(rows,expected):
 assert (a['TENSAO_GMG'],a['TENSAO_BUS'],a['DISJUNTOR_GCB'])==(g,b,k)
 assert a['GCB_POSICAO']==('SEM DADOS' if k is None else 'FECHADO' if k else 'ABERTO')
 assert 'data-state="'+('indisponivel' if k is None else 'fechado' if k else 'aberto')+'"' in unquote(a['GCB_CONTATO_SVG'])
# Modes and alarm priority.
parts=['BEGIN;SET LOCAL jit=off;',table()];expected_modes=[]
for value,label in [(0,'STOP'),(1,'AUTO'),(2,'MANUAL'),(3,'TESTE C/ CARGA'),(6,'TESTE S/ CARGA'),(7,'OFF'),(4,'INVÁLIDO'),(None,'SEM DADOS')]:
 parts+=['TRUNCATE check8610;',row({40:value}),sql_main(['MODO_LOCAL'])];expected_modes.append(label)
parts+=['TRUNCATE check8610;',row({40:10}),sql_main(['MODO_LOCAL'],{'Codigo_STOP':'10'}),'ROLLBACK;']
assert [r['MODO_LOCAL'] for r in run(parts)]==expected_modes+['STOP']
parts=['BEGIN;SET LOCAL jit=off;',table()];combos=list(itertools.product([0,1,None],repeat=3))
for w,t,s in combos:parts+=['TRUNCATE check8610;',row({41:w,42:t,43:s}),sql_main(['GERADOR_ALARME','GERADOR_ALARME_SVG'])]
parts+=['ROLLBACK;'];rows=run(parts);art={}
for a,(w,t,s) in zip(rows,combos):
 label='GERADOR / SHUTDOWN' if s==1 else 'GERADOR / TRIP' if t==1 else 'GERADOR / WARNING' if w==1 else 'ALARMES / SEM DADOS' if None in [w,t,s] else 'GERADOR MONITORADO'
 assert a['GERADOR_ALARME']==label
 assert '<svg' in unquote(a['GERADOR_ALARME_SVG']);art[label]=a['GERADOR_ALARME_SVG']
assert len({art[k] for k in ['GERADOR / WARNING','GERADOR / TRIP','GERADOR / SHUTDOWN','GERADOR MONITORADO']})==4
# Sparse and invalid reports, radios, sentinels and large valid powers.
keys=['MDB52','GCB_POSICAO','TENSAO_GMG','TENSAO_BUS','MODO_LOCAL','WIFI_LOCAL','GSM_LOCAL','MDB01','MDB03','MDB28','MDB36','MDB39','MDB22','GERADOR_ALARME']
parts=['BEGIN;SET LOCAL jit=off;',table()];cases=[]
def add(name,records,expected,radio=True,overrides=None):
 parts.append('TRUNCATE check8610;')
 for values,time,signals in records:parts.append(row(values,time,signals))
 parts.append(sql_main(keys,overrides));cases.append((name,expected))
base=electrical(0,1,0)|{40:1,41:0,42:0,43:0}
add('other_generators_and_sparse_packet',[(base,'2026-10-23T12:05Z',{'gsm_rssi':-53,'WiFi_rssi':-70}),({},'2026-10-23T12:55Z',None)],{'MDB52':0,'GCB_POSICAO':'ABERTO','TENSAO_GMG':0,'TENSAO_BUS':1,'MODO_LOCAL':'AUTO','GSM_LOCAL':-53,'WIFI_LOCAL':-70})
add('invalid_latest_breaker',[(base,'2026-10-23T12:05Z',None),({52:2},'2026-10-23T12:55Z',None)],{'MDB52':None,'GCB_POSICAO':'INVÁLIDO','TENSAO_BUS':1})
add('conflicting_latest_breaker',[(base,'2026-10-23T12:05Z',None),({52:0},'2026-10-23T12:55Z',None),({52:1},'2026-10-23T12:55Z',None)],{'MDB52':None,'GCB_POSICAO':'SEM DADOS'})
add('historical_window_no_leak',[(base,'2026-10-23T11:59Z',None),(electrical(1,1,1),'2026-10-23T13:01Z',None)],{'MDB52':None,'TENSAO_GMG':None,'TENSAO_BUS':None})
add('sentinels_and_valid_large_power',[({1:65535,3:32767,28:32765,36:2147483647,39:4294967295,22:80000000},'2026-10-23T12:05Z',None)],{'MDB01':None,'MDB03':None,'MDB28':None,'MDB36':None,'MDB39':None,'MDB22':80000})
add('csq_wifi_lowercase',[({},'2026-10-23T12:05Z',{'gsm_rssi':22,'wifi_rssi':-85})],{'GSM_LOCAL':-69,'WIFI_LOCAL':-85},overrides={'Formato_GSM':'csq'})
add('radio_invalid',[({},'2026-10-23T12:05Z',{'gsm_rssi':'bad','WiFi_rssi':65535})],{'GSM_LOCAL':None,'WIFI_LOCAL':None})
add('alarm_not_double_bit_decoded',[({41:1024,42:0,43:0},'2026-10-23T12:05Z',None)],{'GERADOR_ALARME':'ALARMES / SEM DADOS'})
parts+=['ROLLBACK;'];rows=run(parts)
for a,(name,e) in zip(rows,cases):assert all(a[k]==v for k,v in e.items()),(name,a,e)
rows=run(['BEGIN;',table(radio=False),row(base),sql_main(['GSM_LOCAL','WIFI_LOCAL']),'ROLLBACK;'])
assert rows==[{'GSM_LOCAL':None,'WIFI_LOCAL':None}]
# Twelve timezone conversions, including UTC naive storage convention.
parts=['BEGIN;SET LOCAL jit=off;'];tz_expected=[]
for typ in ['timestamptz','timestamp']:
 parts.append(table(typ))
 for zone in ['UTC','America/Sao_Paulo','Asia/Tokyo']:
  parts.append("SET LOCAL TIME ZONE '"+zone+"';")
  for instant,label in [('2026-10-23T12:58','23/10 09:58'),('2026-10-23T01:30','22/10 22:30')]:
   # Replace time filter just for this display conversion test.
   q=sql_main(['ULTIMA_LEITURA']).replace('"time" BETWEEN \'2026-10-23T12:00Z\' AND \'2026-10-23T13:00Z\'','TRUE')
   parts+=['TRUNCATE check8610;',row({},instant+('Z' if typ=='timestamptz' else '')),q];tz_expected.append(label)
 parts+=['DROP TABLE check8610;']
parts+=['ROLLBACK;'];assert [r['ULTIMA_LEITURA'] for r in run(parts)]==tz_expected
# Reuse the literal period-case data, but execute the DSE8610 queries and divisors.
tree=ast.parse((ROOT/'tools/validate_v39.py').read_text());period_cases=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='cases' for t in n.targets)))
parts=['BEGIN;SET LOCAL jit=off;',table()];period_expected=[]
for id,divisor in [(14,3600),(15,10)]:
 query=resolve(next(p for p in d['panels'] if p['id']==id)['targets'][0]['rawSql'])
 for name,values,delta in period_cases:
  parts+=['TRUNCATE check8610;']+[row({36:v,37:v},'2026-10-23T'+t+'Z') for t,v in values]+['SELECT row_to_json(q) FROM ('+query+') q;']
  period_expected.append((id,name,None if delta is None else delta/divisor))
 for div in [0,-10,1]:
  q=resolve(next(p for p in d['panels'] if p['id']==id)['targets'][0]['rawSql'],{'Divisor_Horas' if id==14 else 'Divisor_Energia':str(div)})
  parts+=['TRUNCATE check8610;',row({36:100,37:100},'2026-10-23T11:59Z'),row({36:160,37:160},'2026-10-23T12:30Z'),'SELECT row_to_json(q) FROM ('+q+') q;']
  period_expected.append((id,'divisor_'+str(div),60 if div==1 else None))
parts+=['ROLLBACK;'];rows=run(parts);assert len(rows)==len(period_expected)
for a,(id,name,e) in zip(rows,period_expected):
 v=a['HORAS_PERIODO' if id==14 else 'KWH_PERIODO'];assert (v is None if e is None else abs(v-e)<1e-9),(id,name,v,e)
 if name=='screenshot_shape':assert a['SITUACAO']=='PARCIAL'
 if name in ['minor_internal_drop','reset_internal_recovers']:assert a['SITUACAO']=='VARIAÇÃO LÍQUIDA / HOUVE QUEDA'
# Execute every historical query, including the added hours/energy histories.
history=next(p for p in d['panels'] if p['type']=='row')['panels'];assert len(history)==11
parts=['BEGIN;',table(),row({n:0 for n in range(1,53)})]
for p in history:
 for t in p['targets']:parts+=['SELECT row_to_json(q) FROM ('+resolve(t['rawSql'])+') q;']
 c=p['fieldConfig']['defaults']['custom'];assert c['showPoints']=='always'
 assert c['spanNulls']==(p['id'] not in [117,118])
parts+=['ROLLBACK;'];assert len(run(parts))==11
report={'result':'passed','uid':d['uid'],'channels':52,'sourceBreakerCombinations':27,'modeCases':9,'alarmCombinations':27,'sparseAndRadioCases':len(cases)+1,'timezoneCases':len(tz_expected),'periodCases':len(period_expected),'historyQueries':11,'scope':'Isolated PostgreSQL with synthetic data; no production device access','busRule':'Measured BUS independent of this generator and its breaker'}
(ROOT/'DSE8610_V3_SQL_VALIDACAO.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
