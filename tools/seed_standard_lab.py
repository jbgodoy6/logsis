import sys,ast,json,subprocess,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root));sys.path.insert(0,str(root/'tools'))
from logsis_studio.core import Project,available_models
from validate_deif_integration import fixture
source=ast.parse((root/'tools/validate_manual_profiles.py').read_text(encoding='utf-8'))
node=next(n for n in source.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='registers' for t in n.targets));scope={};exec(compile(ast.Module(body=[node],type_ignores=[]),'fixture','exec'),scope);registers=scope['registers']
for model in available_models():
 p=Project.new(model);table='standard_'+model.lower();rs={c.role:c for c in p.profile.channels}
 schema=','.join(c.column+' numeric' for c in p.profile.channels)
 sql=f'CREATE TABLE IF NOT EXISTS {table}(time timestamptz,gsm_rssi numeric,"WiFi_rssi" numeric,{schema});TRUNCATE {table};'
 for stamp,previous in [('2026-10-23T11:59Z',True),('2026-10-23T12:30Z',False)]:
  if p.profile.vendor=='DEIF':values=fixture(p,previous)
  else:
   values=[]
   for c in p.profile.channels:
    value=registers[int(c.params['ADDR'])];bit=int(c.params['BIT']);values.append((value>>bit)&1 if bit>=0 else value)
   if p.profile.kind=='legacy':
    values[18]=62140
    values[40:43]=[0,0,0]
    if previous:values[35]=360000;values[36]=2000
   else:
    for role in ['warning','trip','shutdown']:values[rs[role].index]=0
    if previous:
     for role,value in [('hour_meter',360000),('energy_gen',2000),('energy_mains',5000),('energy_bus',10000)]:
      if role in rs:values[rs[role].index]=value
  if model=='DSE8660':
   # Reproduce the customer's 3-wire medium-voltage case: phase-neutral
   # unimplemented while all three measured phase-phase values are valid.
   for prefix in ['mains','bus']:
    for suffix in ['v_l1n','v_l2n','v_l3n']:values[rs[prefix+'_'+suffix].index]=4294967295
    for suffix,value in [('v_l1l2',13590 if prefix=='mains' else 0),('v_l2l3',13460 if prefix=='mains' else 0),('v_l3l1',13440 if prefix=='mains' else 0)]:
     values[rs[prefix+'_'+suffix].index]=value*rs[prefix+'_'+suffix].divisor
   for role,value in [('mains_i_l1',30),('mains_i_l2',40),('mains_i_l3',40),('mains_kw',72990),('mains_fp',87),('bus_frequency',0),('bus_i_l1',0),('bus_i_l2',0),('bus_i_l3',0),('bus_kw',0)]:
    values[rs[role].index]=value
  sql+=f"INSERT INTO {table} VALUES ('{stamp}',-53,-58,"+','.join(map(str,values))+');'
 run=subprocess.run(['docker','exec','-i','logsis-postgres','psql','-U','postgres','-d','logsis','-q','-v','ON_ERROR_STOP=1'],input=sql,text=True,capture_output=True);assert not run.returncode,run.stderr
 d=p.dashboard(table,'Padrão '+p.profile.model,'zKW_ld27k','standard-'+model.lower().replace('_','-'))
 req=urllib.request.Request('http://127.0.0.1:3300/api/dashboards/db',data=json.dumps({'dashboard':d,'overwrite':True}).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req) as r:json.load(r)
 print(model,flush=True)
