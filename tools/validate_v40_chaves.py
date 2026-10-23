"""Filtered and sparse switch-state regression in isolated PostgreSQL."""
import itertools,json,pathlib,subprocess
from urllib.parse import unquote
ROOT=pathlib.Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'dist/V40_IMPORTAR.json').read_text())
old=json.loads((ROOT/'V39_IMPORTAR.json').read_text())
assert d['uid']==old['uid'] and d['timezone']==old['timezone']
for id in [14,15]:assert next(p for p in d['panels'] if p['id']==id)==next(p for p in old['panels'] if p['id']==id)
assert next(p for p in d['panels'] if p['type']=='row')==next(p for p in old['panels'] if p['type']=='row')
raw=d['panels'][0]['targets'][0]['rawSql'].replace('$Id_Logsis','switch_check')
for v in d['templating']['list']:raw=raw.replace('${'+v['name']+':sqlstring}',"'"+v['query']+"'")
keys=['MDB52','MDB53','K1_ESTADO','K2_ESTADO','K1_INSTANTE','K2_INSTANTE','TENSAO_REDE_PRESENTE','TENSAO_GMG_PRESENTE','TENSAO_SAIDA_PRESENTE','QTA_ESTADO','MDB52_CONTATO_SVG','MDB53_CONTATO_SVG']
def query(end='13:00'):
 q=raw.replace('$__timeFilter("time")',f'"time" BETWEEN \'2026-10-23T12:00Z\' AND \'2026-10-23T{end}Z\'')
 return 'SELECT row_to_json(q) FROM (SELECT '+','.join('"'+k+'"' for k in keys)+' FROM ('+q+') z) q;'
def row(values,time='12:05'):
 cols=['time']+['mdb'+str(n) for n in values]
 vals=["'2026-10-23T"+time+"Z'"]+['NULL' if v is None else str(v) for v in values.values()]
 return 'INSERT INTO switch_check ('+','.join(cols)+') VALUES ('+','.join(vals)+');'
def electrical(r,g,k1,k2):
 return {**{n:None if r is None else 2200*r for n in range(30,36)},**{n:None if g is None else 2200*g for n in range(9,15)},52:k1,53:k2}
parts=['BEGIN;SET LOCAL jit=off;CREATE TEMP TABLE switch_check (time timestamptz,gsm_rssi numeric,'+','.join('mdb'+str(n)+' numeric' for n in range(1,54))+');'];cases=[]
for r,g,k1,k2 in itertools.product([0,1,None],repeat=4):
 parts+=['TRUNCATE switch_check;',row(electrical(r,g,k1,k2)),query()]
 poss=[([False,True] if v is None else [bool(v)]) for v in [r,g,k1,k2]]
 out={int((a and c) or (b and e)) for a,b,c,e in itertools.product(*poss)}
 cases.append({'name':'truth_table','expected':(k1,k2,r,g,next(iter(out)) if len(out)==1 else None)})
def add(name,records,expected,end='13:00'):
 parts.append('TRUNCATE switch_check;');parts.extend(row(v,t) for t,v in records);parts.append(query(end));cases.append({'name':name,'expected':expected})
initial=electrical(1,1,1,0)
add('voltage_packet_without_contacts',[('12:05',initial),('12:55',electrical(0,1,None,None))],(1,0,0,1,0))
add('contact_only_packet_keeps_voltages',[('12:05',initial),('12:55',{52:0,53:1})],(0,1,1,1,1))
add('different_contact_timestamps',[('12:05',electrical(1,1,0,0)),('12:10',{52:1}),('12:20',{53:1})],(1,1,1,1,1))
add('zero_is_open',[('12:05',electrical(1,1,1,1)),('12:55',{52:0,53:0})],(0,0,1,1,0))
add('invalid_does_not_revive_old_closed',[('12:05',initial),('12:55',{52:2})],(None,0,1,1,None))
add('outside_window_never_used',[('11:59',initial),('13:01',electrical(1,1,1,1))],(None,None,None,None,None))
add('one_contact_without_voltage',[('12:05',{52:1})],(1,None,None,None,None))
add('conflicting_same_instant',[('12:05',initial),('12:55',{52:0}),('12:55',{52:1})],(None,0,1,1,None))
add('duplicate_same_state',[('12:05',initial),('12:55',{52:0}),('12:55',{52:0})],(0,0,1,1,0))
sequence=[('12:05',initial),('12:15',{52:0,53:0}),('12:30',{52:0,53:1}),('12:55',electrical(1,1,None,None))]
add('selected_end_before_transfer',sequence,(0,0,1,1,0),'12:20')
add('selected_end_after_transfer',sequence,(0,1,1,1,1))
add('empty_window',[],(None,None,None,None,None))
parts+=['ROLLBACK;']
r=subprocess.run(['docker','exec','-i','logsis-postgres','psql','-U','postgres','-d','logsis','-X','-qAt','-v','ON_ERROR_STOP=1'],input='\n'.join(parts),capture_output=True,text=True,check=True)
rows=[json.loads(l) for l in r.stdout.splitlines() if l.startswith('{')];assert len(rows)==len(cases)
for result,case in zip(rows,cases):
 a=tuple(result[k] for k in ['MDB52','MDB53','TENSAO_REDE_PRESENTE','TENSAO_GMG_PRESENTE','TENSAO_SAIDA_PRESENTE'])
 assert a==case['expected'],(case,a)
 for i,n in enumerate([52,53],1):
  v=result['MDB'+str(n)];label=result[f'K{i}_ESTADO'];svg=unquote(result[f'MDB{n}_CONTATO_SVG'])
  if v is not None:
   assert label==('FECHADO' if v==1 else 'ABERTO')
   assert 'data-state="'+('fechado' if v==1 else 'aberto')+'"' in svg
  else:assert label in ['SEM DADOS','INVÁLIDO'] and 'data-state="indisponivel"' in svg
 if case['name']=='invalid_does_not_revive_old_closed':assert result['K1_ESTADO']=='INVÁLIDO'
 if case['name']=='different_contact_timestamps':assert result['K1_INSTANTE']!=result['K2_INSTANTE'] and result['QTA_ESTADO']=='ALERTA / AMBOS NA CARGA'
report={'result':'passed','truthTableCases':81,'filteredSparseCases':len(cases)-81,'regression':'Period panels and full historical row identical to V39','cases':[c for c in cases if c['name']!='truth_table']}
(ROOT/'V40_CHAVES_VALIDACAO.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('Passed',len(cases),'switch cases; both period panels and histories unchanged')
