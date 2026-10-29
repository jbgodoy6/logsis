"""Generate separate, documented ECU variants without editing preserved profiles."""
from pathlib import Path
import copy,json
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'logsis_studio/resources'
base=json.loads((R/'profiles.json').read_text(encoding='utf-8'));out={}
roles=['oil_pressure','coolant','oil_temperature','fuel','charge_voltage','battery','rpm','gen_frequency','gen_v_l1n','gen_v_l2n','gen_v_l3n','gen_v_l1l2','gen_v_l2l3','gen_v_l3l1','gen_i_l1','gen_i_l2','gen_i_l3','gen_i_earth','gen_kw_l1','gen_kw_l2','gen_kw_l3','gen_kw','gen_kva','gen_kvar','gen_fp_l1','gen_fp_l2','gen_fp_l3','gen_fp','mains_frequency','mains_v_l1n','mains_v_l2n','mains_v_l3n','mains_v_l1l2','mains_v_l2l3','mains_v_l3l1','hour_meter','energy_gen','starts','maintenance_general','mode','warning','trip','shutdown']
def numbered(rows):
 for n,c in enumerate(rows,1):c.update(number=n,column=f'mdb{n}')
 return rows

def extra(rows,name,addr,role,unit='',div=1,signed=False,fnc='3',bit=-1,validity='',vbit=-1,codec='integer',source='GenComm 2.93, página 5 — Extended Instrumentation'):
 params=dict(DH=name+' ALTO',DM=name,DL=name+' BAIXO',ID='10',FNC=fnc,ADDR=str(addr),BIT=str(bit),H='100',VR='-1',TH='2147483647' if fnc in ['30','40'] else '32767' if signed else '65535',TL='-2147483648' if fnc in ['30','40'] else '-32768',SM='0')
 rows.append(dict(number=0,column='',name=name,group='ECU / CAN',unit=unit,divisor=div,params=params,role=role,signed_value=signed,label_variable='',codec=codec,source_reference=source,validity_role=validity,validity_bit=vbit))

def finish(model,data,rows,base_model,motor):
 data=copy.deepcopy(data);data.update(model=model,base_model=base_model,motor_type=motor,channels=numbered(rows),count=len(rows),version='studio-9.2',dashboard_version='ECU1' if motor else 'TC1')
 assert len(rows)<=100 and len({c['role'] for c in rows})==len(rows),model
 out[model]=data

# The validated sequential map is an additional option; the original remains readable.
p=copy.deepcopy(base['DSE8620']);removed={61,62,63,65,66,71,72,73,74};rows=[copy.deepcopy(c) for c in p['channels'] if c['number'] not in removed]
p['label']='DSE8620 · TC único · sequencial validado'
finish('DSE8620_TC_UNICO',p,rows,'DSE8620','')

for model in ['DSE7420','DSE8610','DSE4520','DSE6120','DSE6320','DSE7320','DSE8620']:
 p=copy.deepcopy(out['DSE8620_TC_UNICO'] if model=='DSE8620' else base[model]);rows=copy.deepcopy(p['channels'])
 if model in ['DSE7420','DSE8610']:
  for c in rows[:43]:
   c['role']=roles[c['number']-1].replace('mains_','bus_') if model=='DSE8610' and 29<=c['number']<=35 else roles[c['number']-1]
   c['signed_value']=c['role'] in ['coolant','oil_temperature','maintenance_general'] or c['role'].startswith(('gen_kw','gen_kvar','gen_fp'))
  for c in rows[43:]:
   n=c['number']
   if n<=51:c['role']='input_'+chr(65+n-44)
   elif model=='DSE7420' and n in [52,53]:c['role']='led_mains' if n==52 else 'led_gen'
   elif model=='DSE8610' and n==52:c['role']='led_gen'
   elif c['group']=='Manutenção':c['role']='maintenance_'+str(n-(53 if model=='DSE7420' else 52))
   else:c['role']='input_'+{43553:'Q',43555:'R',43557:'S'}[int(c['params']['ADDR'])]
  p.update(kind='engine_transfer',vendor='DSE',application='DSE_ECU',topology='gen_bus' if model=='DSE8610' else 'transfer')
 p['label']=(base[model].get('label') or model)+' · Eletrônico / ECU-CAN'
 p.update(application='DSE_ECU',topology='gen_bus' if model=='DSE8610' else 'transfer')
 for c in rows:
  if c['role'].startswith('input_') and not c.get('label_variable'):c['label_variable']='Nome_Entrada_'+c['role'][6:]
  if c['role'].startswith('maintenance_') and c['role']!='maintenance_general' and not c.get('label_variable'):c['label_variable']='Nome_Manutencao_'+c['role'].rsplit('_',1)[1]
 for name,addr,role,unit,div,signed,fn in [
 ('Pressão combustível 1',1282,'ecu_fuel_pressure','bar',100,False,'3'),
 ('Pressão arrefecimento',1280,'ecu_coolant_pressure','bar',100,False,'3'),
 ('Pressão admissão / turbo',1284,'ecu_intake_pressure','bar',100,False,'3'),
 ('Temperatura admissão',1286,'ecu_intake_temperature','°C',1,True,'3'),
 ('Temperatura escape',1288,'ecu_exhaust_temperature','°C',1,True,'3'),
 ('Consumo combustível',1290,'ecu_fuel_rate','L/h',100,False,'30'),
 ('Água no combustível',1292,'ecu_water_in_fuel','',1,False,'3'),
 ('Temperatura combustível',1295,'ecu_fuel_temperature','°C',1,True,'3'),
 ('Carga do motor',1354,'ecu_engine_load','%',1,False,'3'),
 ('Nível óleo',1357,'ecu_oil_level','%',1,False,'3'),
 ('Nível arrefecimento',1359,'ecu_coolant_level','%',1,False,'3'),
 ('Pressão rail 1',1360,'ecu_rail_pressure','MPa',100,False,'3')]:extra(rows,name,addr,role,unit,div,signed,fn)
 p['manual_notes']=(p.get('manual_notes') or [])+['Perfil eletrônico separado; não altera o convencional. Registros de instrumentação estendida GenComm dependem de CAN, hardware e firmware. Não implementado aparece como traço; não equivale a motor parado. Pressões kPa convertidas para bar por /100; rail permanece MPa /100.']
 finish(model+'_ECU',p,rows,model,'ecu')

for model in ['AGC150_GEN','AGC150_GEN_BUS','AGC150_ENG']:
 p=copy.deepcopy(base[model]);rows=[]
 keep={'hour_meter','starts','rpm','battery','alarm_count','status_word','mode_word','fail_class_word','maintenance_1','maintenance_2'}
 for c in p['channels']:
  role=c['role']
  electric=role.startswith(('gen_v_','gen_i_','mains_v_','bus_v_')) or role in ['gen_frequency','mains_frequency','bus_frequency','gen_kw','gen_kva','gen_kvar','gen_fp','energy_gen']
  if role in keep or electric or role.startswith('analog_') or role=='alarm_word_1015':rows.append(copy.deepcopy(c))
 # Whole input/validity words avoid dozens of duplicate transactions.
 extra(rows,'Entradas digitais - bits',1142,'input_word',fnc='4',codec='word',source='DEIF 4189341212 revisão Y, FC04 1142')
 extra(rows,'Validade ECU grupo 1',26900,'ecu_validity_1',fnc='4',codec='word',source='DEIF 4189341212 revisão Y, FC04 26900')
 extra(rows,'Validade ECU grupo 2',26901,'ecu_validity_2',fnc='4',codec='word',source='DEIF 4189341212 revisão Y, FC04 26901')
 for name,addr,role,unit,div,signed,vr,vbit in [
 ('Temperatura motor',26001,'coolant','°C/°F configurado',1,False,'ecu_validity_1',14),
 ('Pressão óleo',26002,'oil_pressure','bar/psi configurado',100,False,'ecu_validity_1',13),
 ('Pressão alimentação combustível',26022,'ecu_fuel_pressure','bar/psi configurado',100,False,'ecu_validity_2',9),
 ('Pressão rail combustível',620,'ecu_rail_pressure','bar/psi configurado',1,True,'',-1),
 ('Consumo combustível',26009,'ecu_fuel_rate','L/h',10,False,'ecu_validity_1',6),
 ('Temperatura combustível',26005,'ecu_fuel_temperature','°C/°F configurado',1,False,'ecu_validity_1',10),
 ('Temperatura óleo',26004,'ecu_oil_temperature','°C/°F configurado',10,False,'ecu_validity_1',11),
 ('Nível arrefecimento',26008,'ecu_coolant_level','%',10,False,'ecu_validity_1',7),
 ('Carga motor',26015,'ecu_engine_load','%',1,False,'ecu_validity_1',0),
 ('Temperatura escape',26017,'ecu_exhaust_temperature','°C/°F configurado',10,False,'ecu_validity_2',14),
 ('Pressão admissão',26006,'ecu_intake_pressure','bar/psi configurado',100,False,'ecu_validity_1',9),
 ('Temperatura admissão',26007,'ecu_intake_temperature','°C/°F configurado',1,False,'ecu_validity_1',8),
 ('Nível óleo',26023,'ecu_oil_level','%',10,False,'ecu_validity_2',8),
 ('Água no combustível',26026,'ecu_water_in_fuel','',1,False,'ecu_validity_2',5)]:extra(rows,name,addr,role,unit,div,signed,'4',validity=vr,vbit=vbit,source='DEIF 4189341212 revisão Y, FC04 '+str(addr))
 for bit,role,name in [(0,'mode_block','BLOCK'),(1,'mode_no_regulation','MANUAL - sem regulação'),(2,'mode_semi_auto','SEMI-AUTO - MANUAL no protocolo'),(3,'mode_auto','AUTO')]+([] if model.endswith('ENG') else [(4,'mode_test','TESTE')]):extra(rows,'Modo '+name,1019,role,fnc='4',bit=bit,codec='boolean',source='DEIF 4189341212 revisão Y, FC04 1019 bit '+str(bit))
 p['label']+=' · Eletrônico / ECU-CAN';p['manual_notes']=['Perfil ECU separado. Validade EIC obrigatória; sinais ausentes são traços. Bits 1019: 1 No Regulation (MANUAL sem regulação), 2 MANUAL no protocolo apresentado como SEMI-AUTO conforme padrão acordado; conferir rótulos no firmware instalado.','Pressão/temperatura seguem unidades configuradas na ECU/controlador. Rail genérico 620 não é substituído por mapa específico de fabricante. Manutenção permanece independente. Alarmes resumidos por classe nativa; não há lista completa de proteções neste perfil.']
 finish(model+'_ECU',p,rows,model,'ecu')
(R/'profiles_ecu.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
# Validated artifact kept as an internal reusable template; table is set at export time.
d=json.loads((ROOT/'DSE8620_SEQUENCIAL_IMPORTAR_R3.json').read_text());d['uid']='logsis-dse8620-tc-unico';d['templating']['list']=[v for v in d['templating']['list'] if v['name']!='DS_POSTGRES']
def restore(o):
 if isinstance(o,dict):
  if o.get('uid')=='${DS_POSTGRES}':o['uid']='zKW_ld27k'
  for k,v in o.items():
   if k=='rawSql' and isinstance(v,str):o[k]=v.replace('${Id_Logsis:raw}','$Id_Logsis')
   else:restore(v)
 elif isinstance(o,list):
  for v in o:restore(v)
restore(d);(R/'dse8620_sequencial.json').write_text(json.dumps(d,ensure_ascii=False,separators=(',',':'))+'\n')
print('New separate profiles:',{k:v['count'] for k,v in out.items()})
