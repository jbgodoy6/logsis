"""Independent address fixture -> exported BIN slots -> each generated Grafana SQL."""
import io,json,sys,zipfile,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from logsis_studio.core import Project,BinDocument
registers={1024:450,1025:82,1026:85,1027:75,1028:278,1029:274,1030:1800,1031:600,
 1032:2201,1034:2206,1036:2198,1038:3810,1040:3820,1042:3802,1044:2840,1046:2820,1048:2850,1050:0,
 1052:4294966296,1054:62140,1056:62140,1536:186420,1544:192186,1552:46780,1554:65439,1555:97,1556:97,1557:97,
 1059:600,1060:2403,1062:2404,1064:2405,1066:4162,1068:4163,1070:4164,1076:1200,1078:1300,1080:1400,1082:0,1084:10000,1086:11000,1088:12000,1560:33000,1568:34000,1576:1000,1578:97,1579:97,1580:97,1581:97,
 1091:600,1092:2302,1094:2303,1096:2304,1098:3987,1100:3988,1102:3989,1104:2100,1106:2200,1108:2300,1110:0,1112:14000,1114:15000,1116:16000,1584:45000,1592:46000,1600:2000,1602:98,1603:98,1604:98,1605:98,
 1119:599,1120:2101,1122:2102,1124:2103,1126:3630,1128:3631,1130:3632,1132:3100,1134:3200,1136:3300,1138:0,1140:24000,1142:25000,1144:26000,1622:75000,1630:76000,1638:3000,1640:99,1641:99,1642:99,1621:99,
 1798:372600,1800:2180,1808:29,1794:360000,1836:720000,1840:90000,1844:0,1810:5270,1818:10450,772:4,774:1024|4096,
 43521:1,43523:0,43525:1,43527:0,43529:0,43531:1,43533:1,43535:0,43537:1,43539:0,43553:1,43555:0,43557:65535,
 48653:1,48654:0,48659:1,48660:0,48658:1,48661:0}
report={'result':'pending','scope':'Document-based profiles, synthetic Modbus register fixture and isolated PostgreSQL. No physical controller or production access.','models':[]}
for model in ['DSE4520','DSE6120','DSE6320','DSE7320','DSE8620','DSE8660','DSE8680']:
 project=Project.new(model);roles={c.role:c for c in project.profile.channels}
 for c in project.profile.channels:
  if c.role.startswith('input_'):project.rows[c.index]['DM']="Contato d'água";break
 with zipfile.ZipFile(io.BytesIO(project.bundle_bytes('check_manual','Planta de teste'))) as archive:
  binary=BinDocument.from_bytes(archive.read(model+'.bin')).params
  dashboard=json.loads(archive.read(model+'_GRAFANA.json'))
 values=[]
 for i in range(project.profile.count):
  address=int(binary[f'MDBA_ADDR{i}']);bit=int(binary[f'MDBA_BIT{i}']);value=registers[address]
  values.append((value>>bit)&1 if bit>=0 else value)
 parts=['BEGIN;SET LOCAL jit=off;', 'CREATE TEMP TABLE check_manual (time timestamptz,gsm_rssi numeric,"WiFi_rssi" numeric,'+','.join('mdb'+str(n)+' numeric' for n in range(1,project.profile.count+1))+');']
 for time,previous in [('2026-10-23T11:59Z',True),('2026-10-23T12:30Z',False)]:
  sample=list(values)
  if previous:
   for role,value in [('hour_meter',360000),('energy_gen',2000),('energy_mains',5000),('energy_bus',10000)]:
    if role in roles:sample[roles[role].index]=value
  parts.append("INSERT INTO check_manual VALUES ('"+time+"',-53,-67,"+','.join(str(v) for v in sample)+');')
 def resolve(sql):
  for variable in dashboard['templating']['list']:sql=sql.replace('${'+variable['name']+':sqlstring}',"'"+variable['query'].replace("'","''")+"'")
  return sql.replace('$Id_Logsis','check_manual').replace('$__timeFilter("time")','"time" BETWEEN \'2026-10-23T12:00Z\' AND \'2026-10-23T13:00Z\'').replace('$__timeFrom()',"'2026-10-23T12:00Z'::timestamptz").replace('$__timeTo()',"'2026-10-23T13:00Z'::timestamptz")
 selected=['MODO_LOCAL','ULTIMA_LEITURA','GSM_LOCAL','WIFI_LOCAL']+[f'MDB{c.number:02}' for c in project.profile.channels]
 if project.profile.kind=='engine_transfer':selected+=['MANUTENCAO_RESUMO']
 first_input=next(c for c in project.profile.channels if c.role.startswith('input_'));selected+=['NOME_'+first_input.column.upper()]
 main=dashboard['panels'][0]['targets'][0]['rawSql']
 parts.append('SELECT row_to_json(q) FROM (SELECT '+','.join('"'+f+'"' for f in selected)+' FROM ('+resolve(main)+') result) q;')
 period_panels=[p for p in dashboard['panels'] if p['type']=='stat' and p['datasource']['uid']!='-- Dashboard --']
 for panel in period_panels:parts.append('SELECT row_to_json(q) FROM ('+resolve(panel['targets'][0]['rawSql'])+') q;')
 # Execute every history target too; empty/in-range data must still parse and scale.
 for row in dashboard['panels']:
  for panel in row.get('panels',[]):parts.append('SELECT count(*) FROM ('+resolve(panel['targets'][0]['rawSql'])+') q;')
 if project.profile.kind=='engine_transfer':
  unset=[roles[r].column+'=NULL' for r in ['warning','trip','shutdown','maintenance_1','maintenance_2','maintenance_3']]
  parts.append('UPDATE check_manual SET '+','.join(unset)+';')
  parts.append('SELECT row_to_json(q) FROM (SELECT "GERADOR_ALARME" AS "EDGE_ALARM","MANUTENCAO_RESUMO" AS "EDGE_MAINTENANCE" FROM ('+resolve(main)+') result) q;')
 else:
  parts.append('ALTER TABLE check_manual DROP COLUMN '+first_input.column+';')
  parts.append('SELECT row_to_json(q) FROM (SELECT "MDB'+f'{first_input.number:02}'+'" AS "EDGE_OPTIONAL" FROM ('+resolve(main)+') result) q;')
 parts.append('ROLLBACK;')
 run=subprocess.run(['docker','exec','-i','logsis-postgres','psql','-U','postgres','-d','logsis','-X','-qAt','-v','ON_ERROR_STOP=1'],input='\n'.join(parts),text=True,capture_output=True)
 if run.returncode:raise RuntimeError(model+'\n'+run.stderr)
 rows=[json.loads(line) for line in run.stdout.splitlines() if line.startswith('{')];result=rows[0]
 assert result['MODO_LOCAL']=='AUTO / RETORNO MANUAL',model
 assert result['ULTIMA_LEITURA']=='23/10 09:30'
 assert result['GSM_LOCAL']==-53 and result['WIFI_LOCAL']==-67
 assert result['NOME_'+first_input.column.upper()]=="Contato d'água"
 for role,value in [('warning',1),('trip',0),('shutdown',1),('gen_kw_l1',-1),('gen_fp_l1',-.97),('mains_v_l1n',240.3),('bus_v_l1n',230.2),('bus2_v_l1n',210.1),('bus2_fp',.99)]:
  if role in roles:assert result[f'MDB{roles[role].number:02}']==value,(model,role,result)
 if project.profile.kind=='engine_transfer':assert result['MANUTENCAO_RESUMO']=='Manutenção 3 / VENCIDA'
 if project.profile.kind=='engine_transfer':
  assert rows[-1]['EDGE_ALARM']=='ALARMES / SEM DADOS'
  assert rows[-1]['EDGE_MAINTENANCE']=='MANUTENÇÃO / SEM DADOS'
 else:assert rows[-1]['EDGE_OPTIONAL'] is None
 periods=[]
 for panel,values in zip(period_panels,rows[1:]):
  expected=3.5 if 'HORAS' in panel['title'] else 18 if model not in ['DSE8660','DSE8680'] else 27 if 'rede' in panel['title'] else 45
  actual=values.get('HORAS_PERIODO',values.get('KWH_PERIODO'));assert actual==expected,(model,panel['title'],values)
  periods.append({'title':panel['title'],'value':actual})
 report['models'].append({'model':model,'label':project.profile.label,'channels':project.profile.count,'kind':project.profile.kind,'sourceFamily':project.profile.manual_family,'periods':periods,'passed':True})
report['result']='passed'
(ROOT/'LOGSIS_STUDIO_8_VALIDACAO_SQL.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
