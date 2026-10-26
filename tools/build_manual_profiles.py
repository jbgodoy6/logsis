"""Append seven document-based profiles, preserving delivered 7420/8610 definitions."""
from pathlib import Path
import copy,json
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'logsis_studio/resources/profiles.json'
data=json.loads(p.read_text())
roles=['oil_pressure','coolant','oil_temperature','fuel','charge_voltage','battery','rpm','gen_frequency',
 'gen_v_l1n','gen_v_l2n','gen_v_l3n','gen_v_l1l2','gen_v_l2l3','gen_v_l3l1',
 'gen_i_l1','gen_i_l2','gen_i_l3','gen_i_earth','gen_kw_l1','gen_kw_l2','gen_kw_l3',
 'gen_kw','gen_kva','gen_kvar','gen_fp_l1','gen_fp_l2','gen_fp_l3','gen_fp',
 'mains_frequency','mains_v_l1n','mains_v_l2n','mains_v_l3n','mains_v_l1l2','mains_v_l2l3','mains_v_l3l1',
 'hour_meter','energy_gen','starts','maintenance_general','mode','warning','trip','shutdown']

def channel(rows,name,address,role,group,unit='',divisor=1,fn=3,signed=False,bit=-1,variable=''):
 n=len(rows)+1
 params=copy.deepcopy(data['DSE7420']['channels'][43]['params'])
 params.update(ADDR=str(address),FNC=str(fn),BIT=str(bit),DM=name,DH=name+' ATIVO',DL=name+' INATIVO',TH='0',TL='0')
 if role.startswith('maintenance_'):
  params.update(DH=name+' EM DIA',DM=name,DL=name+' VENCIDA',TH='180000',TL='0')
 rows.append(dict(number=n,column=f'mdb{n}',name=name,group=group,unit=unit,divisor=divisor,params=params,
                  role=role,signed_value=signed,label_variable=variable))

def controls(rows):
 channel(rows,'Modo de operação',772,'mode','Controle')
 for name,role,bit in [('Warning','warning',10),('Trip elétrico','trip',11),('Shutdown','shutdown',12)]:
  channel(rows,name,774,role,'Controle',bit=bit)

def inputs(rows,count):
 for i in range(count):
  letter=chr(65+i)
  channel(rows,'Entrada '+letter,43521+2*i,'input_'+letter,'Entradas',variable='Nome_Entrada_'+letter)

def source(rows,prefix,label,freq,volts,currents,watts,total,fp):
 channel(rows,label+' · frequência',freq,prefix+'_frequency',label,'Hz',10)
 for suffix,addr in zip(['l1n','l2n','l3n','l1l2','l2l3','l3l1'],volts):
  channel(rows,label+' · tensão '+{'l1n':'L1–N','l2n':'L2–N','l3n':'L3–N','l1l2':'L1–L2','l2l3':'L2–L3','l3l1':'L3–L1'}[suffix],addr,prefix+'_v_'+suffix,label,'V',10,30)
 for suffix,addr in zip(['l1','l2','l3','earth'],currents):
  channel(rows,label+' · corrente '+('terra' if suffix=='earth' else suffix.upper()),addr,prefix+'_i_'+suffix,label,'A',10,30)
 for suffix,addr in zip(['l1','l2','l3'],watts):
  channel(rows,label+' · potência '+suffix.upper(),addr,prefix+'_kw_'+suffix,label,'kW',1000,30,True)
 for suffix,addr,unit in zip(['kw','kva','kvar'],total,['kW','kVA','kVAr']):
  channel(rows,label+' · total '+unit,addr,prefix+'_'+suffix,label,unit,1000,30,suffix!='kva')
 for suffix,addr in zip(['l1','l2','l3',''],fp):
  channel(rows,label+' · FP '+(suffix.upper() or 'médio'),addr,prefix+'_fp'+('_'+suffix if suffix else ''),label,'',100,3,True)

specs=[('DSE4520','DSE4520 MkII','4xxx'),('DSE6120','DSE6120 MkII','61xx MkII'),('DSE6320','DSE6320','6xxx'),('DSE7320','DSE7320 MkII','72xx/73xx'),('DSE8620','DSE8620','8xxx/74xx'),('DSE8660','DSE8660','8x60'),('DSE8680','DSE8680','8680')]
for model,label,family in specs:
 rows=[];kind='engine_transfer'
 notes=['GenComm 2.93, revisão 13/04/2015. Disponibilidade depende do hardware e firmware; registros não implementados exibem traço.', 'LED é indicação do controlador, não confirmação independente do contato físico. O teste de lâmpadas pode afetar o LED.']
 if model not in ['DSE8660','DSE8680']:
  for old,role in zip(data['DSE7420']['channels'][:43],roles):
   c=copy.deepcopy(old);c.update(role=role,signed_value=role in ['coolant','oil_temperature','maintenance_general'] or role.startswith('gen_kw') or role.startswith('gen_kvar') or role.startswith('gen_fp'),label_variable='')
   rows.append(c)
  inputs(rows,6 if model=='DSE6120' else 8 if model=='DSE8620' else 9)
  if model=='DSE6120':
   for letter,addr in zip('ABCD',[43533,43535,43537,43539]):
    channel(rows,'Flexível '+letter+' · digital',addr,'input_flex_'+letter,'Entradas flexíveis',variable='Nome_Entrada_Flex_'+letter)
   notes.append('Flexíveis A–D: página 170, offsets 13/15/17/19. Não usar Q/R/S ou copiar G/H como digitais dedicadas.')
  if model=='DSE8620':
   for letter,addr in zip('QRS',[43553,43555,43557]):
    channel(rows,'Flexível '+letter+' · digital',addr,'input_'+letter,'Entradas flexíveis',variable='Nome_Entrada_'+letter)
  if model in ['DSE4520','DSE7320']:
   notes.append('Versão MkII selecionada; tabela de família do manual fornecido. O PDF não apresenta uma tabela individual dessa revisão; conferir recursos em campo.')
  if model in ['DSE4520','DSE6320','DSE7320']:
   notes.append('A–I são posições documentadas da família; não representam garantia de nove entradas físicas. Q/R/S não são flexíveis locais nesta tabela.')
  leds=(48659,48660) if model=='DSE8620' else (48653,48654)
  channel(rows,'LED · disjuntor da rede',leds[0],'led_mains','Indicadores LED')
  channel(rows,'LED · disjuntor do gerador',leds[1],'led_gen','Indicadores LED')
  for i,addr in enumerate([1836,1840,1844],1):
   channel(rows,'Manutenção '+str(i),addr,'maintenance_'+str(i),'Manutenção','h',3600,30,True,variable='Nome_Manutencao_'+str(i))
 else:
  if model=='DSE8660':
   kind='mains_bus'
   source(rows,'mains','Rede',1059,[1060,1062,1064,1066,1068,1070],[1076,1078,1080,1082],[1084,1086,1088],[1560,1568,1576],[1578,1579,1580,1581])
  else:kind='bus_tie'
  source(rows,'bus','BUS 1' if model=='DSE8680' else 'BUS',1091,[1092,1094,1096,1098,1100,1102],[1104,1106,1108,1110],[1112,1114,1116],[1584,1592,1600],[1602,1603,1604,1605])
  if model=='DSE8680':
   source(rows,'bus2','BUS 2',1119,[1120,1122,1124,1126,1128,1130],[1132,1134,1136,1138],[1140,1142,1144],[1622,1630,1638],[1640,1641,1642,1621])
   notes.append('BUS 2: registros específicos citados para 8680; o manual informa que nem todos foram implementados inicialmente. Não há contador de energia BUS 2 confirmado nesta tabela.')
  if model=='DSE8660':channel(rows,'Energia positiva · rede',1810,'energy_mains','Acumulados','kWh',10,30)
  channel(rows,'Energia positiva · BUS 1' if model=='DSE8680' else 'Energia positiva · BUS',1818,'energy_bus','Acumulados','kWh',10,30)
  controls(rows);inputs(rows,8)
  if model=='DSE8660':
   channel(rows,'LED · disjuntor da rede',48659,'led_mains','Indicadores LED')
   channel(rows,'LED · disjuntor do BUS',48660,'led_bus','Indicadores LED')
  else:
   channel(rows,'LED · acoplador',48659,'led_tie','Indicadores LED')
   channel(rows,'LED · BUS 1 energizado',48658,'led_bus_live','Indicadores LED')
   channel(rows,'LED · BUS 2 energizado',48661,'led_bus2_live','Indicadores LED')
  notes.append('Sem variáveis de motor, horas de funcionamento do motor ou manutenção de motor. Não reutilizar energia do gerador como energia de rede/BUS.')
 data[model]=dict(model=model,version='manual-1.0',count=len(rows),dashboard='manual',dashboard_version='M1',channels=rows,label=label,kind=kind,manual_family=family,manual_notes=notes)
p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
for model,_,_ in specs:print(model,data[model]['count'])
