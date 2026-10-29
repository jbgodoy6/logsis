"""Exercise sparse packets, filter limits and historical dependencies in PostgreSQL."""
from pathlib import Path
import copy,json,subprocess,sys,urllib.request
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from logsis_studio.core import load_profile
STEM='AGC150_ECU_MITSUBISHI_R6_ULTIMAS_LEITURAS'
d=json.loads((ROOT/(STEM+'.json')).read_text(encoding='utf-8'))
p=load_profile('AGC150_GEN_ECU');rs={c.role:c for c in p.channels}
TABLE='agc150_async_r6_test'
def run(sql):
    r=subprocess.run(['docker','exec','-i','logsis-postgres','psql','-U','postgres','-d','logsis','-XqAt','-v','ON_ERROR_STOP=1'],input='SET jit=off;'+sql,text=True,capture_output=True)
    assert r.returncode==0,r.stderr[:3000]
    return [json.loads(x) for x in r.stdout.splitlines() if x.startswith('{')]
start,end='2026-10-29T19:00Z','2026-10-29T20:00Z'
def resolve(sql):
    for v in d['templating']['list']:
        val=v.get('current',{}).get('value',v.get('query',''))
        sql=sql.replace('${'+v['name']+':sqlstring}',"'"+str(val).replace("'","''")+"'")
    return sql.replace('${Id_Logsis:raw}',TABLE).replace('$Id_Logsis',TABLE).replace('$__timeFilter("time")',f'"time" BETWEEN \'{start}\' AND \'{end}\'').replace('$__timeFrom()',f"'{start}'::timestamptz").replace('$__timeTo()',f"'{end}'::timestamptz")
run(f'CREATE TABLE IF NOT EXISTS {TABLE}(time timestamptz,gsm_rssi numeric,"WiFi_rssi" numeric,'+','.join(f'mdb{i} numeric' for i in range(1,101))+');TRUNCATE '+TABLE+';')
def insert(when,fields):
    cols=['time']+list(fields)
    vals=["'"+when+"'"]+[('NULL' if v is None else str(v)) for v in fields.values()]
    run(f'INSERT INTO {TABLE}('+','.join('"'+x+'"' for x in cols)+') VALUES ('+','.join(vals)+');')
def packet(when,**roles):insert(when,{'mdb'+str(rs[k].number):v for k,v in roles.items()})
main=d['panels'][0]['targets'][0]['rawSql']
def query(sql):return run('SELECT row_to_json(q) FROM ('+resolve(sql)+') q;')
def snap():return query(main)[0]
# Only period counters may use this previous sample, as a subtraction baseline.
packet('2026-10-29T18:59Z',hour_meter=99,energy_gen=900,battery=120)
# Deliberately separate validity, measurements, meter halves, status and mode.
packet('2026-10-29T19:05Z',ecu_validity_1=65535,ecu_validity_2=65535)
v={}
for c in p.channels:
    role=c.role
    if '_v_' in role:v['mdb'+str(c.number)]=380 if role.endswith(('l1l2','l2l3','l3l1')) else 220
    elif role.endswith('_frequency'):v['mdb'+str(c.number)]=6000
v.update({'mdb43':450,'mdb44':1500,'mdb45':234,'mdb41':82,'mdb42':450,'mdb25':1800,
          'mdb26':100,'mdb27':100,'mdb29':0,'mdb36':0,'mdb37':0,
          'mdb23':100,'mdb15':1000,'gsm_rssi':-53,'WiFi_rssi':-67})
insert('2026-10-29T19:10Z',v)
insert('2026-10-29T19:11Z',dict(zip(['mdb'+str(i) for i in range(60,72)],[902,955,925,919,2202,2225,2229,988,346,54,357,868])))
insert('2026-10-29T19:12Z',{'mdb72':584})
packet('2026-10-29T19:14Z',mode_word=8|64)
packet('2026-10-29T19:15Z',status_word=(1<<1)|(1<<11)|(1<<6))
r=snap()
for k,v in {'MODE':'AUTO','B1_TEXT':'FECHADO','B2_TEXT':'ABERTO','ENGINE_STATE':'MOTOR EM FUNCIONAMENTO','MDB43':4.5,'MDB45':23.4,'MM_V12':220.2,'MM_FP':.988,'MM_P':346,'MM_ENERGY':5840868,'GSM':-53,'LAST_TIME':'29/10 16:15','MDB28':None}.items():assert r[k]==v,(k,r[k],v)
assert r['OBSERVED_AT']['mdb43'].startswith('2026-10-29T19:10:00')
assert r['OBSERVED_AT']['mdb30'].startswith('2026-10-29T19:15:00')
query_count=0
for a in d['panels']:
    for panel in [a]+a.get('panels',[]):
        for t in panel.get('targets',[]):
            if t.get('rawSql'):
                result=query(t['rawSql']);query_count+=1
                if panel['id']==14:assert result[0]['VALUE']==1,result
                if panel['id']==15:assert result[0]['VALUE']==100,result
                if panel['id']==142:assert any(x.get('ME96SS ENERGY')==5840868 for x in result),result
                if panel['type']=='timeseries' and 'consumo' in panel['title'].lower():
                    assert any(x.get('Consumo combustível')==23.4 for x in result),result
# NULL means not sent. A later zero/invalid word IS a new observation.
packet('2026-10-29T19:16Z',status_word=None)
assert snap()['B1_TEXT']=='FECHADO'
packet('2026-10-29T19:17Z',status_word=(1<<12)|(1<<4))
r=snap();assert r['B1_TEXT']=='ABERTO' and r['B2_TEXT']=='FECHADO' and r['ENGINE_STATE']=='MOTOR PARADO' and r['MDB43']==4.5
packet('2026-10-29T19:18Z',ecu_fuel_pressure=0);assert snap()['MDB43']==0
packet('2026-10-29T19:19Z',ecu_fuel_pressure=65535);assert snap()['MDB43'] is None
packet('2026-10-29T19:20Z',ecu_fuel_pressure=450,ecu_validity_2=0);assert snap()['MDB43'] is None
packet('2026-10-29T19:21Z',ecu_validity_2=65535);assert snap()['MDB43']==4.5
for i,(modebit,label) in enumerate([(0,'BLOCK'),(1,'MANUAL'),(2,'SEMI-AUTO'),(3,'AUTO'),(4,'TESTE')]):
    packet(f'2026-10-29T19:{22+i:02}Z',mode_word=1<<modebit);assert snap()['MODE']==label
for i,(word,level) in enumerate([(2,1),(4,2),(16,3)]):
    packet(f'2026-10-29T19:{28+i:02}Z',fail_class_word=word,alarm_count=1);assert snap()['ALARM_LEVEL']==level
# A future availability bit must not retroactively validate an older point.
packet('2026-10-29T19:32Z',ecu_validity_1=0)
packet('2026-10-29T19:33Z',ecu_fuel_rate=300)
packet('2026-10-29T19:34Z',ecu_validity_1=65535)
assert snap()['MDB45']==30
history=next(t['rawSql'] for a in d['panels'] for panel in a.get('panels',[])
             if panel.get('type')=='timeseries' and 'consumo' in panel['title'].lower()
             for t in panel['targets'])
points=query(history)
assert all(x['Consumo combustível'] is None for x in points if x['time'].startswith('2026-10-29T19:33:00'))
# Changing the filter excludes earlier readings instead of carrying across it.
start='2026-10-29T19:14Z';r=snap();assert r['MM_P'] is None and r['MDB01'] is None
start,end='2026-10-29T20:01Z','2026-10-29T21:00Z'
r=snap();assert r['MM_P'] is None and r['MODE']=='SEM DADOS' and r['GSM'] is None
start,end='2026-10-29T19:00Z','2026-10-29T20:00Z'
# Restore a representative local preview without altering production services.
packet('2026-10-29T19:31Z',mode_word=8|64,fail_class_word=0,alarm_count=0,status_word=(1<<1)|(1<<11)|(1<<6))
preview=copy.deepcopy(d)
for v in preview['templating']['list']:
    if v['name']=='Id_Logsis':v.update(query=TABLE,current={'text':TABLE,'value':TABLE})
req=urllib.request.Request('http://127.0.0.1:3300/api/dashboards/db',data=json.dumps({'dashboard':preview,'overwrite':True}).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req) as f:assert json.loads(f.read())['status']=='success'
report={'result':'passed','queriesExecuted':query_count,'sparsePackets1610And1615':True,'independentFieldTimestamps':True,'missingNullPreserves':True,'zeroUpdates':True,'newInvalidDoesNotResurrectOld':True,'ecuValidityAsynchronous':True,'historicalValidityNoFutureLookahead':True,'meterWordsSeparatePackets':True,'filterBothBoundaries':True,'emptyWindow':True,'periodCounters':True,'fiveModesAndAlarmColors':True,'variablesHidden':all(v['hide']==2 for v in d['templating']['list']),'grafanaLocalImport':True,'hardwareTest':False}
(ROOT/(STEM+'_VALIDACAO.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
