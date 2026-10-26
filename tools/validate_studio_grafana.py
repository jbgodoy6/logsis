"""Prove BIN positions and exported Grafana SQL agree, using isolated PostgreSQL."""
import io,json,pathlib,subprocess,sys,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from logsis_studio.core import BinDocument,Project

# Independent address fixture: distinct source voltages expose any mains/BUS swap.
registers={1024:450,1025:82,1026:85,1027:75,1028:278,1029:274,1030:1800,1031:600,
 1032:2201,1034:2206,1036:2198,1038:3810,1040:3820,1042:3802,
 1044:2840,1046:2820,1048:2850,1050:0,1052:62140,1054:62140,1056:62140,
 1536:186420,1544:192186,1552:46780,1554:97,1555:97,1556:97,1557:97,
 1059:600,1060:2403,1062:2404,1064:2405,1066:4162,1068:4163,1070:4164,
 1091:600,1092:2302,1094:2303,1096:2304,1098:3987,1100:3988,1102:3989,
 1798:372600,1800:2180,1808:29,1794:360000,772:2,774:1024|4096,
 43521:1,43523:0,43525:1,43527:0,43529:0,43531:1,43533:0,43535:0,
 48653:1,48654:0,48659:1,1836:720000,1840:90000,1844:0,43553:1,43555:0,43557:65535}
report={'result':'pending','scope':'BIN-to-SQL integration in isolated PostgreSQL; no production access','models':[]}
for model,count in [('DSE7420',59),('DSE8610',58)]:
 project=Project.new(model)
 with zipfile.ZipFile(io.BytesIO(project.bundle_bytes('check_studio','Planta de teste'))) as archive:
  params=BinDocument.from_bytes(archive.read(model+'.bin')).params
  dashboard=json.loads(archive.read(model+'_GRAFANA.json'))
 # Decode the values in actual BIN slot order, including firmware-configured alarm bits.
 values=[]
 for index in range(count):
  address=int(params[f'MDBA_ADDR{index}']);bit=int(params[f'MDBA_BIT{index}'])
  raw=registers[address];values.append((raw>>bit)&1 if bit>=0 else raw)
 parts=['BEGIN;SET LOCAL jit=off;CREATE TEMP TABLE check_studio (time timestamptz,gsm_rssi numeric,"WiFi_rssi" numeric,'+','.join('mdb'+str(n)+' numeric' for n in range(1,count+1))+');']
 for time,hours,kwh in [('2026-10-23T11:59Z',360000,2000),('2026-10-23T12:30Z',372600,2180)]:
  sample=list(values);sample[35]=hours;sample[36]=kwh
  parts.append("INSERT INTO check_studio VALUES ('"+time+"',-53,-67,"+','.join(str(v) for v in sample)+');')
 def resolve(sql):
  for variable in dashboard['templating']['list']:sql=sql.replace('${'+variable['name']+':sqlstring}',"'"+variable['query'].replace("'","''")+"'")
  return sql.replace('$Id_Logsis','check_studio').replace('$__timeFilter("time")','"time" BETWEEN \'2026-10-23T12:00Z\' AND \'2026-10-23T13:00Z\'').replace('$__timeFrom()',"'2026-10-23T12:00Z'::timestamptz").replace('$__timeTo()',"'2026-10-23T13:00Z'::timestamptz")
 keys=['MDB01','MDB09','MDB30','MDB36','MDB37','MDB40','MDB41','MDB42','MDB43','MDB52','MODO_LOCAL','GSM_LOCAL','WIFI_LOCAL']+(['MDB53'] if model=='DSE7420' else ['TENSAO_BUS','GERADOR_ALARME'])
 first=54 if model=='DSE7420' else 53
 keys += [f'MDB{n}' for n in range(first,first+3)]+['MANUTENCAO_1_ESTADO','MANUTENCAO_2_ESTADO','MANUTENCAO_3_ESTADO','MANUTENCAO_RESUMO','MANUTENCAO_ESTADO','GERADOR_STATUS_SVG']
 keys += [f'MDB{n}' for n in range(first+3,first+6)]
 main=dashboard['panels'][0]['targets'][0]['rawSql']
 parts.append('SELECT row_to_json(q) FROM (SELECT '+','.join('"'+k+'"' for k in keys)+' FROM ('+resolve(main)+') data) q;')
 for id in [14,15]:
  query=next(p for p in dashboard['panels'] if p['id']==id)['targets'][0]['rawSql']
  parts.append('SELECT row_to_json(q) FROM ('+resolve(query)+') q;')
 parts.append('ROLLBACK;')
 result=subprocess.run(['docker','exec','-i','logsis-postgres','psql','-U','postgres','-d','logsis','-X','-qAt','-v','ON_ERROR_STOP=1'],input='\n'.join(parts),capture_output=True,text=True,check=True)
 main,hours,energy=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
 expected={'MDB01':4.5,'MDB09':220.1,'MDB30':240.3 if model=='DSE7420' else 230.2,'MDB36':103.5,'MDB37':218,'MDB40':2,'MDB41':1,'MDB42':0,'MDB43':1,'MDB52':1,'MODO_LOCAL':'MANUAL','GSM_LOCAL':-53,'WIFI_LOCAL':-67}
 assert all(main[key]==value for key,value in expected.items()),(model,main,expected)
 if model=='DSE7420':assert main['MDB53']==0
 else:assert main['TENSAO_BUS']==1 and main['GERADOR_ALARME']=='GERADOR / SHUTDOWN'
 assert [main[f'MDB{n}'] for n in range(first,first+3)]==[200,25,0]
 assert [main[f'MANUTENCAO_{n}_ESTADO'] for n in range(1,4)]==['ok','near','due']
 assert main['MANUTENCAO_RESUMO']=='Manutenção 3 / VENCIDA'
 assert [main[f'MDB{n}'] for n in range(first+3,first+6)]==[1,0,None]
 # Active shutdown retains its red picture, despite maintenance due.
 assert '%23' in main.pop('GERADOR_STATUS_SVG')
 assert hours['HORAS_PERIODO']==3.5 and energy['KWH_PERIODO']==18
 report['models'].append({'model':model,'channels':count,'decodedFromBinSlots':True,'grafanaFields':main,'periodHours':hours['HORAS_PERIODO'],'periodKwh':energy['KWH_PERIODO']})
report['result']='passed'
(ROOT/'LOGSIS_STUDIO_GRAFANA_VALIDACAO.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
