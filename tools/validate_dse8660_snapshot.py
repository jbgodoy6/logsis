"""Regression checks for coherent DSE8660 snapshots and common switch outputs."""
import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from logsis_studio.core import Project
from logsis_studio.manual_dashboard import wire, RED, MUTED

p=Project.new('DSE8660');rs={c.role:c for c in p.profile.channels}
d=p.dashboard('check_8660','Teste','ds');query=d['panels'][0]['targets'][0]['rawSql']
for v in d['templating']['list']:
    query=query.replace('${'+v['name']+':sqlstring}',"'"+v['query'].replace("'","''")+"'")
query=query.replace('$Id_Logsis','check_8660').replace('$__timeFilter("time")', '"time" BETWEEN \'2026-10-23T12:00Z\' AND \'2026-10-23T13:00Z\'')
source=ast.parse((ROOT/'tools/validate_manual_profiles.py').read_text())
node=next(n for n in source.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='registers' for t in n.targets))
scope={};exec(compile(ast.Module(body=[node],type_ignores=[]),'fixture','exec'),scope)
base=[scope['registers'][int(c.params['ADDR'])] for c in p.profile.channels]
selected=['MDB36','MDB37','MDB38','CONTACT_LED_MAINS_LABEL','CONTACT_LED_BUS_LABEL','WIRE_OUT_MAINS_V','WIRE_OUT_BUS_V','WIRE_OUT_H','WIRE_OUT_V','DIAGNOSTICO_8660','ULTIMA_LEITURA']
select='SELECT row_to_json(q) FROM (SELECT '+','.join('"'+f+'"' for f in selected)+' FROM ('+query+') result) q;'
parts=['BEGIN;SET LOCAL jit=off;','CREATE TEMP TABLE check_8660(time timestamptz,gsm_rssi numeric,"WiFi_rssi" numeric,'+','.join(c.column+' numeric' for c in p.profile.channels)+');']
def insert(stamp,changes):
    values=base.copy()
    for role,value in changes.items():values[rs[role].index]=value
    return f"INSERT INTO check_8660 VALUES ('{stamp}',-53,-58,"+','.join('NULL' if v is None else str(v) for v in values)+');'
cases=[
    ('open_bus_actual_power',{}),
    ('missing_latest_power',{'bus_kw':None,'bus_kva':None,'bus_kvar':None}),
    ('unknown_bus_contact',{'led_bus':None}),
    ('both_open',{'led_mains':0,'led_bus':0}),
    ('bus_only_closed',{'led_mains':0,'led_bus':1}),
    ('both_closed',{'led_mains':1,'led_bus':1}),
    ('no_voltage',dict([('led_mains',1),('led_bus',1)]+[(c.role,0) for c in p.profile.channels if '_v_' in c.role])),
    ('empty_window',None),
]
for name,changes in cases:
    parts+=['TRUNCATE check_8660;',insert('2026-10-23T12:10Z',{'bus_kw':88000,'bus_kva':90000,'led_bus':1}) if changes is not None else '']
    if changes is not None:parts.append(insert('2026-10-23T12:30Z',changes))
    else:parts.append('TRUNCATE check_8660;')
    parts.append(select)
parts.append('ROLLBACK;')
run=subprocess.run(['docker','exec','-i','logsis-postgres','psql','-U','postgres','-d','logsis','-X','-qAt','-v','ON_ERROR_STOP=1'],input='\n'.join(parts),capture_output=True,text=True)
assert run.returncode==0,run.stderr
rows=[json.loads(s) for s in run.stdout.splitlines() if s.startswith('{')]
assert len(rows)==len(cases)
results=dict(zip([c[0] for c in cases],rows))
assert results['open_bus_actual_power']['MDB36']==45 # Never force a received power to zero.
assert results['open_bus_actual_power']['DIAGNOSTICO_8660']=='BUS: POTÊNCIA COM CHAVE ABERTA'
for alias in ['MDB36','MDB37','MDB38']:assert results['missing_latest_power'][alias] is None
assert results['missing_latest_power']['CONTACT_LED_BUS_LABEL']=='ABERTO'
assert results['unknown_bus_contact']['CONTACT_LED_BUS_LABEL']=='SEM DADOS'
for name,mains,bus in [('open_bus_actual_power',True,False),('missing_latest_power',True,False),('both_open',False,False),('bus_only_closed',False,True),('both_closed',True,True),('no_voltage',False,False),('empty_window',False,False)]:
    row=results[name]
    for alias,energized,vertical in [('WIRE_OUT_MAINS_V',mains or bus,True),('WIRE_OUT_BUS_V',mains or bus,True),('WIRE_OUT_H',mains or bus,False),('WIRE_OUT_V',mains or bus,True)]:
        assert row[alias]==wire(RED if energized else MUTED,vertical),(name,alias)
assert results['empty_window']['ULTIMA_LEITURA'] is None
for name,row in results.items():
    for k in [k for k in row if k.startswith('WIRE_')]:row.pop(k)
(ROOT/'DSE8660_VALIDACAO_SNAPSHOT.json').write_text(json.dumps({'result':'passed','scope':'Synthetic PostgreSQL regression cases; no physical controller or production access.','cases':results},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('DSE8660: 8 snapshot/common-output regression cases passed.')
