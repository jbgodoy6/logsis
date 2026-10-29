"""Integration checks against the local disposable PostgreSQL/Grafana lab."""
from pathlib import Path
import copy, hashlib, json, subprocess, sys, urllib.request, zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from logsis_studio.core import load_profile, BinDocument, MDB_FIELDS
STEM='AGC150_REDE_GERADOR_ECU_ME96SS_R5'
d=json.loads((ROOT/(STEM+'.json')).read_text(encoding='utf-8'))
p=load_profile('AGC150_GEN_ECU');rs={c.role:c for c in p.channels}
b=BinDocument.from_bytes((ROOT/(STEM+'.bin')).read_bytes())
for c in p.channels:
    assert all(b.params[f'MDBA_{f}{c.index}']==c.params[f] for f in ['ADDR','BIT','FNC'])
assert [i+1 for i in range(100) if b.params[f'MDBA_ID{i}']!='-1']==list(range(1,73))
for offset in range(13):
    previous=BinDocument.from_bytes((ROOT/'AGC150_ECU_ME96SS_R4.bin').read_bytes())
    for f in ['ADDR','ID','BIT','FNC']:
        assert b.params[f'MDBA_{f}{59+offset}']==previous.params[f'MDBA_{f}{84+offset}']

TABLE='agc150_new_ecu_me96ss_r5_test'
def run(sql):
    r=subprocess.run(['docker','exec','-i','logsis-postgres','psql','-U','postgres','-d','logsis','-XqAt','-v','ON_ERROR_STOP=1'],input='SET jit=off;'+sql,text=True,capture_output=True)
    assert r.returncode==0,r.stderr[:3000]
    return [json.loads(x) for x in r.stdout.splitlines() if x.startswith('{')]
def resolve(sql):
    for v in d['templating']['list']:
        val=v.get('current',{}).get('value',v.get('query',''))
        sql=sql.replace('${'+v['name']+':sqlstring}',"'"+str(val).replace("'","''")+"'")
    return sql.replace('${Id_Logsis:raw}',TABLE).replace('$Id_Logsis',TABLE).replace('$__timeFilter("time")','"time" BETWEEN \'2026-10-29T12:00Z\' AND \'2026-10-29T13:00Z\'').replace('$__timeFrom()',"'2026-10-29T12:00Z'::timestamptz").replace('$__timeTo()',"'2026-10-29T13:00Z'::timestamptz")
values={i:0 for i in range(1,73)}
for c in p.channels:
    role=c.role;v=0
    if '_v_' in role:v=380 if role.endswith(('l1l2','l2l3','l3l1')) else 220
    elif role.endswith('_frequency'):v=60*c.divisor
    elif '_i_' in role:v=75
    elif role in ['gen_kw','gen_kva','gen_kvar','gen_fp']:v={'gen_kw':45,'gen_kva':47,'gen_kvar':12,'gen_fp':.95}[role]*c.divisor
    elif role=='hour_meter':v=100
    elif role=='energy_gen':v=1000
    elif role=='rpm':v=1800
    elif role=='battery':v=248
    elif role.startswith('maintenance_'):v=100
    elif role=='status_word':v=(1<<1)|(1<<11)|(1<<6)
    elif role=='mode_word':v=8|64
    elif role=='mode_auto':v=1
    elif role.startswith('ecu_validity'):v=65535
    values[c.number]=int(v)
for role,v in [('ecu_fuel_pressure',450),('ecu_rail_pressure',1500),('ecu_fuel_rate',234),('coolant',82),('oil_pressure',450)]:values[rs[role].number]=v
values.update(dict(zip(range(60,73),[902,955,925,919,2202,2225,2229,988,346,54,357,868,584])))
run(f'CREATE TABLE IF NOT EXISTS {TABLE}(time timestamptz,gsm_rssi numeric,"WiFi_rssi" numeric,'+','.join(f'mdb{i} numeric' for i in range(1,101))+');TRUNCATE '+TABLE+';')
for when,prior in [('2026-10-29T11:59Z',True),('2026-10-29T12:30Z',False)]:
    vals=values.copy()
    if prior:vals[rs['hour_meter'].number]=99;vals[rs['energy_gen'].number]=900
    run(f"INSERT INTO {TABLE} VALUES ('{when}',-53,-67,"+','.join(str(vals.get(i,'NULL')) for i in range(1,101))+');')
main=d['panels'][0]['targets'][0]['rawSql']
def snap():return run('SELECT row_to_json(q) FROM ('+resolve(main)+') q;')[0]
def update(**kwargs):run(f'UPDATE {TABLE} SET '+','.join('mdb'+str(rs[k].number)+'='+str(v) for k,v in kwargs.items())+';')
r=snap()
expected={'MODE':'AUTO','B1_TEXT':'FECHADO','B2_TEXT':'ABERTO','ENGINE_STATE':'MOTOR EM FUNCIONAMENTO','GSM':-53,'WIFI':-67,'LAST_TIME':'29/10 09:30','HOURS':100,'POWER':45,'MM_FP':.988,'MM_V12':220.2,'MM_I1':902,'MM_ENERGY':5840868,'MDB43':4.5,'MDB44':1500,'MDB45':23.4}
for k,v in expected.items():assert r[k]==v,(k,r[k],v)
query_count=0
for a in d['panels']:
    for panel in [a]+a.get('panels',[]):
        for t in panel.get('targets',[]):
            if t.get('rawSql'):
                result=run('SELECT row_to_json(q) FROM ('+resolve(t['rawSql'])+') q;');query_count+=1
                if panel['id']==14:assert result[0]['VALUE']==1,result
                if panel['id']==15:assert result[0]['VALUE']==100,result
# All modes use the new mode word; no legacy slot aliases are consulted.
for modebit,label in [(0,'BLOCK'),(1,'MANUAL'),(2,'SEMI-AUTO'),(3,'AUTO'),(4,'TESTE')]:
    update(mode_word=1<<modebit);assert snap()['MODE']==label
update(mode_word=12);assert snap()['MODE']=='INCOERENTE'
update(mode_word=8,status_word=(1<<12)|(1<<4)|(1<<6))
r=snap();assert r['B1_TEXT']=='ABERTO' and r['B2_TEXT']=='FECHADO'
# The meter continues measuring regardless of either AGC breaker.
update(status_word=(1<<12)|(1<<11));r=snap();assert r['MM_P']==346 and r['ENGINE_STATE']=='MOTOR PARADO'
update(ecu_fuel_pressure=-1,ecu_rail_pressure=32767,ecu_fuel_rate=65535)
r=snap();assert r['MDB43'] is None and r['MDB44'] is None and r['MDB45'] is None
update(ecu_fuel_pressure=450,ecu_validity_2=0);assert snap()['MDB43'] is None
update(ecu_validity_2=65535,ecu_fuel_pressure=0);assert snap()['MDB43']==0
for word,level in [(2,1),(4,2),(16,3)]:
    update(fail_class_word=word,alarm_count=1);assert snap()['ALARM_LEVEL']==level
update(fail_class_word=2,alarm_count=1,alarm_word_1015=1)
r=snap();assert r['ALARM_LEVEL']==0 and 'VENCIDA' in r['MAINTENANCE']
update(fail_class_word=16);assert snap()['ALARM_LEVEL']==3
update(fail_class_word=0,alarm_count=0,alarm_word_1015=0,ecu_fuel_pressure=450,ecu_rail_pressure=1500,ecu_fuel_rate=234,status_word=(1<<1)|(1<<11)|(1<<6))
# Missing newest switch state must not retain an older closed contact.
run(f'UPDATE {TABLE} SET mdb{rs["status_word"].number}=NULL WHERE time>\'2026-10-29T12:00Z\';')
assert snap()['B1_TEXT']=='SEM DADOS'
update(status_word=(1<<1)|(1<<11)|(1<<6))
preview=copy.deepcopy(d)
for v in preview['templating']['list']:
    if v['name']=='Id_Logsis':v.update(query=TABLE,current={'text':TABLE,'value':TABLE})
req=urllib.request.Request('http://127.0.0.1:3300/api/dashboards/db',data=json.dumps({'dashboard':preview,'overwrite':True}).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req) as f:assert json.loads(f.read())['status']=='success'
with zipfile.ZipFile(ROOT/(STEM+'.zip')) as z:assert z.testzip() is None
report={'result':'passed','agcProfile':'AGC150_GEN_ECU','agcSlots':'1-59','meterSlots':'60-72','queriesExecuted':query_count,'fiveModes':True,'switchesAndCommonOutput':True,'ecuValidityAndSentinels':True,'zeroRemainsZero':True,'independentMeter':True,'periodBaseline':True,'timezone':'America/Sao_Paulo','grafanaLocalImport':True,'hardwareTest':False,'meterEnergyCompositionSimultaneousConfirmation':False,'binSha256':hashlib.sha256((ROOT/(STEM+'.bin')).read_bytes()).hexdigest()}
(ROOT/(STEM+'_VALIDACAO.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
