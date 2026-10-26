"""Create dedicated synthetic fixtures in the local Docker lab for browser checks."""
import ast
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from logsis_studio.core import Project

# This is our own independent test fixture, not uploaded controller software.
tree=ast.parse((ROOT/'tools/validate_studio_grafana.py').read_text())
node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='registers' for t in n.targets))
scope={}
exec(compile(ast.Module(body=[node],type_ignores=[]),'internal_fixture','exec'),scope)
registers=scope['registers']
for model,maintenance in [('DSE7420',54),('DSE8610',53)]:
    p=Project.new(model)
    table='studio_72_'+model.lower()
    columns=','.join(f'mdb{n} numeric' for n in range(1,p.profile.count+1))
    values=[]
    for channel in p.profile.channels:
        raw=registers[int(channel.params['ADDR'])];bit=int(channel.params['BIT'])
        values.append((raw>>bit)&1 if bit>=0 else raw)
    values[40:43]=[0,0,0]
    sql=f'CREATE TABLE IF NOT EXISTS {table} (time timestamptz,gsm_rssi numeric,"WiFi_rssi" numeric,{columns});TRUNCATE {table};'
    for timestamp,hours,energy in [('2026-10-23T11:59Z',360000,2000),('2026-10-23T12:30Z',372600,2180)]:
        sample=list(values);sample[35]=hours;sample[36]=energy
        sql+="INSERT INTO "+table+" VALUES ('"+timestamp+"',-53,-67,"+','.join(str(v) for v in sample)+');'
    subprocess.run(['docker','exec','-i','logsis-postgres','psql','-U','postgres','-d','logsis','-q','-v','ON_ERROR_STOP=1'],input=sql,text=True,check=True)
    for index,name in [(43,'Porta da sala'),(maintenance-1,'Troca de óleo'),(maintenance,'Troca de filtros'),(maintenance+1,'Revisão geral'),(maintenance+2,'Porta de acesso'),(maintenance+3,'Nível do tanque'),(maintenance+4,'Reserva')]:
        p.rows[index]['DM']=name
    d=p.dashboard(table,'Teste '+model,'zKW_ld27k','studio-72-'+model.lower())
    request=urllib.request.Request('http://127.0.0.1:3300/api/dashboards/db',data=json.dumps({'dashboard':d,'overwrite':True}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request) as response:print(json.load(response)['url'])
