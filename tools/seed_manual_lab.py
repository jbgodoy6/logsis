"""Dedicated synthetic fixtures for browser validation of document-based profiles."""
import ast,json,subprocess,sys,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from logsis_studio.core import Project
source=ast.parse((ROOT/'tools/validate_manual_profiles.py').read_text())
node=next(n for n in source.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='registers' for t in n.targets))
scope={};exec(compile(ast.Module(body=[node],type_ignores=[]),'internal_fixture','exec'),scope);registers=scope['registers']
for model in ['DSE4520','DSE6120','DSE6320','DSE7320','DSE8620','DSE8660','DSE8680']:
 p=Project.new(model);roles={c.role:c for c in p.profile.channels};table='studio_manual_'+model.lower()
 columns=','.join(c.column+' numeric' for c in p.profile.channels)
 values=[]
 for c in p.profile.channels:
  value=registers[int(c.params['ADDR'])];bit=int(c.params['BIT']);value=((value>>bit)&1 if bit>=0 else value)
  if c.role in ['warning','trip','shutdown']:value=0
  values.append(value)
 sql=f'CREATE TABLE IF NOT EXISTS {table}(time timestamptz,gsm_rssi numeric,"WiFi_rssi" numeric,{columns});TRUNCATE {table};'
 for time,previous in [('2026-10-23T11:59Z',True),('2026-10-23T12:30Z',False)]:
  sample=list(values)
  if previous:
   for role,value in [('hour_meter',360000),('energy_gen',2000),('energy_mains',5000),('energy_bus',10000)]:
    if role in roles:sample[roles[role].index]=value
  sql+="INSERT INTO "+table+" VALUES ('"+time+"',-53,-67,"+','.join(str(v) for v in sample)+');'
 subprocess.run(['docker','exec','-i','logsis-postgres','psql','-U','postgres','-d','logsis','-q','-v','ON_ERROR_STOP=1'],input=sql,text=True,check=True)
 first_input=next(c for c in p.profile.channels if c.input_letter);p.rows[first_input.index]['DM']='Porta da sala'
 if 'maintenance_3' in roles:p.rows[roles['maintenance_3'].index]['DM']='Troca de óleo'
 d=p.dashboard(table,'Teste '+p.profile.label,'zKW_ld27k','studio-manual-'+model.lower())
 req=urllib.request.Request('http://127.0.0.1:3300/api/dashboards/db',data=json.dumps({'dashboard':d,'overwrite':True}).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req) as response:print(json.load(response)['url'])
