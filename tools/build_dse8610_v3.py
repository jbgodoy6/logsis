"""Generate the single DSE8610 dashboard from the audited BIN mapping and V32 artwork."""
import ast,copy,html,json,pathlib,zipfile
from urllib.parse import quote as urlquote
ROOT=pathlib.Path(__file__).resolve().parents[1]
source=json.loads((ROOT/'V26_IMPORTAR.json').read_text());base,instrument,_=copy.deepcopy(source['panels']);art=base['options']['root']['elements']
INK,MUTED,CYAN,AMBER,RED,BG,SURFACE='#e5eef7','#96aec4','#67cce4','#e9bd79','#f2495c','#080f19','#0e1a27'
elements=[];registry=[]
for element in art:
 if element.get('config',{}).get('text',{}).get('fixed')=='DSE7420':element['config']['text']['fixed']='DSE8610'
# Import definitions only: do not execute or regenerate the DSE7420 dashboard.
tree=ast.parse((ROOT/'tools/build_v32_correcao_modo.py').read_text())
names={'svg_art','wire_svg','box','text','line','radio_icon','signal_bars','reading_group'}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'v32_helpers','exec'))
audit=json.loads((ROOT/'DSE8610_ANALISE/DSE8610_AUDITORIA.json').read_text())
records={int(r['mdb'][3:]):r for r in audit['records'] if r['status']=='configurado'}
assert set(records)==set(range(1,53))
d=copy.deepcopy(source)
d.update(id=None,uid='logsis-dse8610-v1-bus',title='LOGSIS / DSE8610 — V3 Gerador e BUS',version=1,tags=['LOGSIS','DSE8610','BUS','responsivo','V3'],links=[],description='Gerador, disjuntor MDB52, barramento comum medido e carga. Mapeamento auditado do BIN; escalas e códigos de modo configuráveis.')
variables=[{'name':'Id_Logsis','label':'Tabela da planta DSE8610','type':'constant','query':'id_dse8610','hide':2,'skipUrlSync':True}]
def const(name,value):variables.append({'name':name,'type':'constant','hide':2,'query':str(value),'skipUrlSync':True})
for n,v in [('Campo_WiFi_RSSI','WiFi_rssi'),('Formato_GSM','dbm'),('Codigo_STOP',0),('Codigo_AUTO',1),('Codigo_MANUAL',2),('Codigo_TESTE_CARGA',3),('Codigo_TESTE_SEM_CARGA',6),('Codigo_OFF',7),('Divisor_Tensao',10),('Divisor_Corrente',10),('Divisor_Potencia',1000),('Divisor_FP',100),('Divisor_Horas',3600),('Divisor_Energia',10)]:const(n,v)
d['templating']={'list':variables}
def var(n):return '${'+n+':sqlstring}'
def sq(s):return "'"+s.replace("'","''")+"'"
def scaled(n):
 c=f'mdb{n}::numeric'
 divisor=('100' if n==1 else '10' if n in [5,6,8,29] else var('Divisor_Tensao') if 9<=n<=14 or 30<=n<=35  else var('Divisor_Corrente') if 15<=n<=18 else var('Divisor_Potencia') if 19<=n<=24 else var('Divisor_FP') if 25<=n<=28 else var('Divisor_Horas') if n in [36,39] else var('Divisor_Energia') if n==37 else '1')
 return c if divisor=='1' else '('+c+')/NULLIF(('+divisor+')::numeric,0)'
def valid(n):
 c=f'mdb{n}'
 if 41<=n<=52:return c+' IN (0,1)'
 return c+' NOT IN (-2147483648,2147483647,4294967295)'+(' AND '+c+' BETWEEN -32759 AND 32759' if records[n]['FNC']=='3' else '')
# Import reusable vector, tint and counter-difference functions without executing dashboards.
import re as alarm_re
from urllib.parse import unquote
for filename,name in [('build_v40_chaves_periodo.py','contact_svg'),('build_v39_diferenca_contadores.py','alarm_art'),('build_v39_diferenca_contadores.py','period_sql')]:
 parsed_tree=ast.parse((ROOT/'tools'/filename).read_text())
 fn=next(node for node in parsed_tree.body if isinstance(node,ast.FunctionDef) and node.name==name)
 code=ast.get_source_segment((ROOT/'tools'/filename).read_text(),fn)
 if name=='period_sql':code=code.replace("divisor='3600' if n==36 else '${Divisor_Energia:sqlstring}'", "divisor=var('Divisor_Horas') if n==36 else var('Divisor_Energia')")
 exec(compile(code,filename+':'+name,'exec'))
original_generator=unquote(svg_art('Gerador').split(',',1)[1])
mode_codes=[('STOP','Codigo_STOP',0,MUTED),('AUTO','Codigo_AUTO',1,CYAN),('MANUAL','Codigo_MANUAL',2,AMBER),('TESTE C/ CARGA','Codigo_TESTE_CARGA',3,AMBER),('TESTE S/ CARGA','Codigo_TESTE_SEM_CARGA',6,CYAN),('OFF','Codigo_OFF',7,MUTED)]
fields=[]
for n in range(1,53):
 if n==52:
  last=f'(SELECT MAX("time") FROM $Id_Logsis WHERE $__timeFilter("time") AND mdb52 IS NOT NULL)'
  raw=f'(SELECT CASE WHEN COUNT(DISTINCT mdb52)=1 THEN MAX(mdb52) END FROM $Id_Logsis WHERE $__timeFilter("time") AND "time"={last})'
  fields += [f'CASE WHEN {raw} IN (0,1) THEN {raw} END AS "MDB52"',raw+' AS "GCB_BRUTO"',last+' AS "GCB_INSTANTE"']
 else:
  # Discrete invalid latest reports stay unknown instead of reviving an older state.
  expr=f'CASE WHEN {valid(n)} THEN mdb{n} END' if 41<=n<=51 else scaled(n)
  where='' if 41<=n<=51 else ' AND '+valid(n)
  fields.append(f'(SELECT {expr} FROM $Id_Logsis WHERE $__timeFilter("time") AND mdb{n} IS NOT NULL{where} ORDER BY "time" DESC LIMIT 1) AS "MDB{n:02}"')
gsm_expr="COALESCE(to_jsonb(t)->>'gsm_rssi',to_jsonb(t)->>'GSM_RSSI')"
wifi_expr='COALESCE(to_jsonb(t)->>'+var('Campo_WiFi_RSSI')+',to_jsonb(t)->>lower('+var('Campo_WiFi_RSSI')+'))'
fields += [f'(SELECT {gsm_expr} FROM $Id_Logsis t WHERE $__timeFilter("time") AND {gsm_expr} IS NOT NULL ORDER BY "time" DESC LIMIT 1) AS "GSM_RSSI"',f'(SELECT {wifi_expr} FROM $Id_Logsis t WHERE $__timeFilter("time") AND {wifi_expr} IS NOT NULL ORDER BY "time" DESC LIMIT 1) AS wifi_txt']
local_time="CASE WHEN pg_typeof(\"time\")='timestamp without time zone'::regtype THEN (\"time\"::timestamp AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo' ELSE \"time\"::timestamptz AT TIME ZONE 'America/Sao_Paulo' END"
fields.append('(SELECT to_char(('+local_time+"),'DD/MM HH24:MI') FROM $Id_Logsis WHERE $__timeFilter(\"time\") ORDER BY \"time\" DESC LIMIT 1) AS \"ULTIMA_LEITURA\"")
ctes=['leituras AS (SELECT '+',\n'.join(fields)+')']
for group,ns in [('gmg',range(9,15)),('bus',range(30,36))]:
 present=' OR '.join(f'"MDB{n:02}">0' for n in ns);zero=' AND '.join(f'"MDB{n:02}"=0' for n in ns)
 ctes.append(f'{group} AS (SELECT CASE WHEN {present} THEN 1 WHEN {zero} THEN 0 ELSE NULL END AS state FROM leituras)')
ctes += ['sinais AS (SELECT leituras.*, (SELECT state FROM gmg) AS "TENSAO_GMG", (SELECT state FROM bus) AS "TENSAO_BUS" FROM leituras)',
 'parsed AS (SELECT sinais.*,CASE WHEN wifi_txt ~ \'^-?[0-9]+([.][0-9]+)?$\' AND length(wifi_txt)<20 THEN wifi_txt::numeric END AS wifi_raw,CASE WHEN "GSM_RSSI" ~ \'^-?[0-9]+([.][0-9]+)?$\' AND length("GSM_RSSI")<20 THEN "GSM_RSSI"::numeric END AS gsm_raw FROM sinais)',
 'dados AS (SELECT parsed.*,CASE WHEN wifi_raw BETWEEN -32759 AND 32759 THEN wifi_raw END AS "WIFI_LOCAL",CASE WHEN ${Formato_GSM:sqlstring}=\'csq\' AND gsm_raw BETWEEN 0 AND 31 AND gsm_raw=trunc(gsm_raw) THEN -113+2*gsm_raw WHEN ${Formato_GSM:sqlstring}=\'dbm\' AND gsm_raw BETWEEN -140 AND -1 THEN gsm_raw END AS "GSM_LOCAL" FROM parsed)']
mode_sql='CASE '+''.join('WHEN "MDB40"='+var(code)+'::numeric THEN '+sq(label)+' ' for label,code,value,colour in mode_codes)+'WHEN "MDB40" IS NULL THEN \'SEM DADOS\' ELSE \'INVÁLIDO\' END'
extra=[mode_sql+' AS "MODO_LOCAL"','"MDB52" AS "DISJUNTOR_GCB"',
 'CASE "MDB52" WHEN 0 THEN \'DISJUNTOR ABERTO\' WHEN 1 THEN \'DISJUNTOR FECHADO\' ELSE \'POSIÇÃO DESCONHECIDA\' END AS "ESTADO_GCB"',
 'CASE WHEN "MDB52"=0 THEN \'ABERTO\' WHEN "MDB52"=1 THEN \'FECHADO\' WHEN "GCB_BRUTO" IS NOT NULL THEN \'INVÁLIDO\' ELSE \'SEM DADOS\' END AS "GCB_POSICAO"',
 'CASE "MDB52" WHEN 0 THEN '+sq(contact_svg(0))+' WHEN 1 THEN '+sq(contact_svg(1))+' ELSE '+sq(contact_svg(None))+' END AS "GCB_CONTATO_SVG"']
alarm_cases=[('"MDB43"=1','GERADOR / SHUTDOWN',RED),('"MDB42"=1','GERADOR / TRIP','#ff9830'),('"MDB41"=1','GERADOR / WARNING','#f2cc0c'),('"MDB41" IS NULL OR "MDB42" IS NULL OR "MDB43" IS NULL','ALARMES / SEM DADOS',None)]
extra += ['CASE '+''.join('WHEN '+condition+' THEN '+sq(label)+' ' for condition,label,colour in alarm_cases)+'ELSE \'GERADOR MONITORADO\' END AS "GERADOR_ALARME"',
 'CASE '+''.join('WHEN '+condition+' THEN '+sq(alarm_art(colour))+' ' for condition,label,colour in alarm_cases)+'ELSE '+sq(alarm_art(None))+' END AS "GERADOR_ALARME_SVG"']
for field,color,vertical in [('TENSAO_GMG',AMBER,True),('TENSAO_BUS',INK,True),('TENSAO_BUS',INK,False)]:
 alias=field+('_V_SVG' if vertical else '_H_SVG');extra.append('CASE WHEN "'+field+'"=1 THEN '+sq(wire_svg(RED,vertical))+' ELSE '+sq(wire_svg(color,vertical))+' END AS "'+alias+'"')
extra += ['CASE WHEN "WIFI_LOCAL" IS NULL THEN '+sq(radio_icon('wifi',MUTED))+' ELSE '+sq(radio_icon('wifi',CYAN))+' END AS "WIFI_LOCAL_ICONE"']
bars='CASE WHEN "GSM_LOCAL" IS NULL THEN '+sq(radio_icon('gsm',MUTED))
for threshold,level in [(-80,5),(-90,4),(-100,3),(-110,2)]:bars+=' WHEN "GSM_LOCAL">='+str(threshold)+' THEN '+sq(signal_bars(level))
extra += [bars+' ELSE '+sq(signal_bars(1))+' END AS "GSM_LOCAL_ICONE"']
rawsql='WITH '+',\n'.join(ctes)+' SELECT dados.*,\n'+',\n'.join(extra)+' FROM dados'
# Replace all inherited modes, hours, inputs and transfer contacts after MDB39.
cfg=copy.deepcopy(base['fieldConfig']);cfg['overrides']=[o for o in cfg['overrides'] if not o['matcher']['options'].startswith(('TENSAO_','QTA_')) and (not o['matcher']['options'].startswith('MDB') or int(o['matcher']['options'][3:])<=52)]
def override(field,props):
 o=next((o for o in cfg['overrides'] if o['matcher']['options']==field),None)
 if o is None:o={'matcher':{'id':'byName','options':field},'properties':[]};cfg['overrides'].append(o)
 old={p['id']:p['value'] for p in o['properties']};old.update(props);o['properties']=[{'id':k,'value':v} for k,v in old.items()]
def mapping(values):return [{'type':'value','options':{str(k):{'text':v,'color':c} for k,v,c in values}},{'type':'special','options':{'match':'null','result':{'text':'SEM DADOS','color':MUTED}}}]
for n in range(40,53):override(f'MDB{n:02}',{'unit':'none','decimals':0,'mappings':[]})
for n in [41,42,43]:override(f'MDB{n}',{'mappings':mapping([(0,'INATIVO',MUTED),(1,'ATIVO',AMBER)])})
override('MDB52',{'mappings':mapping([(0,'ABERTO',MUTED),(1,'FECHADO',CYAN)])})
for f in ['TENSAO_GMG','TENSAO_BUS']:override(f,{'unit':'none','mappings':mapping([(0,'SEM TENSÃO',MUTED),(1,'COM TENSÃO',RED)])})
override('DISJUNTOR_GCB',{'unit':'none','mappings':[{'type':'value','options':{'0':{'text':'━','color':AMBER},'1':{'text':'┃','color':AMBER}}},{'type':'special','options':{'match':'null','result':{'text':'?','color':MUTED}}}]})
override('MODO_LOCAL',{'unit':'none','mappings':mapping([(label,label,colour) for label,code,value,colour in mode_codes]+[('SEM DADOS','SEM DADOS',MUTED),('INVÁLIDO','INVÁLIDO',RED)])})
override('MDB40',{'unit':'none','mappings':mapping([(value,label,colour) for label,code,value,colour in mode_codes])})
override('GERADOR_ALARME',{'unit':'none','mappings':mapping([(label,label,colour or MUTED) for condition,label,colour in alarm_cases]+[('GERADOR MONITORADO','GERADOR MONITORADO',AMBER)])})
override('GCB_POSICAO',{'unit':'none','mappings':mapping([(label,label,colour) for label,colour in [('ABERTO',MUTED),('FECHADO',AMBER),('SEM DADOS',MUTED),('INVÁLIDO',RED)]])})
for n in range(44,52):override(f'MDB{n}',{'unit':'none','mappings':mapping([(0,'OFF',MUTED),(1,'ON',CYAN)])})
for f,u in [('WIFI_LOCAL','none'),('GSM_LOCAL','suffix: dBm')]:override(f,{'unit':u,'decimals':0,'mappings':[{'type':'special','options':{'match':'null','result':{'text':'—','color':MUTED}}}]})
base['fieldConfig']=cfg
# Diagram: generator and symbolic other groups connect to one measured common BUS.
box('Fundo',0,100,0,932,BG)
text('Marca',4,92,10,25,'LOGSIS / DSE8610',17)
text('Disciplina',4,92,40,17,'GERADOR / BUS COMUM / CARGA',9,MUTED)
for left,kind,title,field in [(3,'wifi','WI-FI / RSSI','WIFI_LOCAL'),(35,'gsm','GSM / RSSI','GSM_LOCAL')]:
 box('Conexão '+kind,left,30,64,40,SURFACE,'#263c4f');text('Conexão título '+kind,left+1,28,67,12,title,8,MUTED)
 e=box('Conexão ícone '+kind,left+1,7,82,17);e['background'].update(image={'mode':'mapping','field':field+'_ICONE'},size='fill')
 text('Conexão valor '+kind,left+8,21,82,18,size=10,field=field)
box('Modo',67,30,64,40,SURFACE,'#263c4f');text('Modo título',68,28,67,12,'MODO / GMG',8,MUTED)
e=text('Modo valor',69,26,81,20,size=10,field='MODO_LOCAL');e['config']['color']={'field':'MODO_LOCAL','fixed':MUTED}
e=text('Gerador título',3,44,120,18,size=10,field='GERADOR_ALARME');e['config']['color']={'field':'GERADOR_ALARME','fixed':AMBER}
e=box('Gerador vetorial',3,44,146,100);e['background'].update(image={'mode':'mapping','field':'GERADOR_ALARME_SVG'},size='fill')
text('BUS título',53,44,120,18,'BARRAMENTO / BUS',10,CYAN)
# A neutral three-phase bus symbol replaces the illustrative extra generator.
bus_svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 90" preserveAspectRatio="xMidYMid meet"><g fill="none" stroke="#96aec4" stroke-width="3"><path d="M42 20H218 M42 45H218 M42 70H218"/></g><g fill="#96aec4" font-family="sans-serif" font-size="14"><text x="10" y="25">L1</text><text x="10" y="50">L2</text><text x="10" y="75">L3</text></g><g fill="#96aec4"><circle cx="218" cy="20" r="4"/><circle cx="218" cy="45" r="4"/><circle cx="218" cy="70" r="4"/></g></svg>'
e=box('Símbolo do barramento BUS',55,40,148,88);e['background'].update(image={'fixed':'data:image/svg+xml;charset=utf-8,'+urlquote(bus_svg,safe='/:')},size='fill')
for left,rows in [(3,[(9,'L1–N'),(10,'L2–N'),(11,'L3–N'),(8,'Freq.'),(7,'Rotação'),(2,'T. água'),(1,'P. óleo')]),(53,[(30,'L1–N'),(31,'L2–N'),(32,'L3–N'),(33,'L1–L2'),(34,'L2–L3'),(35,'L3–L1'),(29,'Freq.')])]:
 box('Leituras locais '+str(left),left,44,249,168,SURFACE,'#263c4f')
 for row,(n,label) in enumerate(rows):
  e=text('Fonte rótulo MDB'+f'{n:02}',left+2,13,258+row*22,20,label,9,MUTED);e['config']['align']='left'
  e=text('Fonte leitura MDB'+f'{n:02}',left+15,27,258+row*22,20,size=12,field=f'MDB{n:02}');e['config']['align']='right'
text('Tensão gerador',3,44,423,18,size=10,field='TENSAO_GMG')
text('Tensão BUS',53,44,423,18,size=10,field='TENSAO_BUS')
line(25,447,25,466,'TENSAO_GMG',AMBER)
box('Disjuntor caixa',15,20,466,68,SURFACE,'#6f8b9e');text('Disjuntor título',16,18,472,14,'52 / GCB',8,MUTED)
e=box('Disjuntor posição',16,18,486,30);e['background'].update(image={'mode':'mapping','field':'GCB_CONTATO_SVG'},size='fill')
e=text('Disjuntor estado curto',16,18,519,12,size=8,field='GCB_POSICAO');e['config']['color']={'field':'GCB_POSICAO','fixed':MUTED}
line(25,534,25,574,'TENSAO_BUS')
line(75,447,75,574,'TENSAO_BUS',INK)
text('BUS nome',37,26,547,17,'BUS COMUM',10,CYAN)
line(15,574,85,574,'TENSAO_BUS')
line(50,574,50,607,'TENSAO_BUS')
box('QGBT',37,26,607,25,SURFACE,'#6f8b9e');text('QGBT nome',38,24,611,16,'QGBT / CARGA',9)
line(50,632,50,647,'TENSAO_BUS')
e=box('Edifício vetorial',30,40,648,116);e['background'].update(image={'fixed':svg_art('Edifício')},size='fill')
text('Carga nome',3,94,769,18,'CARGA DA INSTALAÇÃO',11)
text('GCB estado',3,94,798,18,size=11,field='ESTADO_GCB')
text('BUS nota',3,94,824,16,'TENSÃO DO BUS MEDIDA / INDEPENDENTE DO GCB',8,MUTED)
text('Última leitura título',3,94,854,14,'ÚLTIMO REGISTRO / BRASÍLIA',8,MUTED)
text('Última leitura valor',3,94,871,20,size=12,field='ULTIMA_LEITURA')
text('Período',3,94,908,15,'LEITURAS DO PERÍODO SELECIONADO',8,AMBER)
overview=copy.deepcopy(base);overview.update(id=1,title='01 / Gerador → BUS comum → carga',gridPos={'x':0,'y':0,'w':12,'h':26})
overview['options']['root'].update(name='Unifilar DSE8610',elements=elements,connections=[],placement={'left':0,'top':0,'width':360,'height':932})
overview['options'].update(panZoom=False,infinitePan=False,inlineEditing=False)
overview['targets']=[copy.deepcopy(base['targets'][0])];overview['targets'][0]['rawSql']=rawsql
overview['description']='BUS medido independentemente do estado deste gerador. MDB52: 0 aberto, 1 fechado. Cor vermelha indica tensão, sem afirmar fluxo de potência ou sincronismo.'
labels={f'{n:02}':r['DM'].title() for n,r in records.items()};labels.update({'01':'Pressão óleo','02':'Temp. água','03':'Temp. óleo','04':'Nível diesel','05':'Alternador DC','06':'Tensão bateria','07':'RPM motor','36':'Horímetro','37':'Energia acumulada','38':'Número de partidas','39':'Até manutenção','40':'Modo operação','41':'Warning','42':'Trip elétrico','43':'Shutdown','52':'Disjuntor / GCB','22':'Potência ativa total','23':'Potência aparente','24':'Potência reativa'})
for i in range(44,52):labels[f'{i:02}']='Entrada '+chr(65+i-44)
short={9:'L1–N',10:'L2–N',11:'L3–N',12:'L1–L2',13:'L2–L3',14:'L3–L1',15:'I L1',16:'I L2',17:'I L3',18:'I terra',8:'Frequência',19:'L1',20:'L2',21:'L3',22:'Ativa',23:'Aparente',24:'Reativa',25:'FP / L1',26:'FP / L2',27:'FP / L3',28:'FP médio'}
units={o['matcher']['options']:next((p['value'].split('suffix:',1)[1].strip() for p in o['properties'] if p['id']=='unit' and p['value'].startswith('suffix:')),'') for o in cfg['overrides']}
panels=[overview]
reading_group(21,'02 / Gerador · tensão e corrente',list(range(8,19)),12,0,12,15,AMBER,3,order=[(n,1) for n in [9,10,11,12,13,14,15,16,17]]+[(8,2),(18,1)])
reading_group(23,'03 / Motor e combustível',list(range(1,8)),12,15,12,11,'#66c9b3',order=[(n,1) for n in range(1,7)]+[(7,2)])
for j,(f,title,color) in enumerate([('MDB22','POTÊNCIA ATIVA / GMG',AMBER),('MDB28','FATOR DE POTÊNCIA / GMG',CYAN),('MDB36','HORÍMETRO / ACUMULADO',INK),('MDB37','ENERGIA / GERADOR',INK)]):
 fc=copy.deepcopy(cfg);fc['defaults']['color']={'mode':'fixed','fixedColor':color}
 panels.append({'id':10+j,'type':'stat','title':title,'gridPos':{'x':j*6,'y':26,'w':6,'h':3},'datasource':{'type':'datasource','uid':'-- Dashboard --'},'targets':[{'refId':'A','panelId':1,'withTransforms':False}],'transformations':[{'id':'filterFieldsByName','options':{'include':{'names':[f]}}}],'fieldConfig':fc,'options':{'reduceOptions':{'calcs':['lastNotNull'],'fields':'','values':False},'textMode':'value','colorMode':'value','graphMode':'none','justifyMode':'center','text':{'valueSize':26}}})
reading_group(22,'04 / Gerador · potências e FP',list(range(19,29)),0,29,12,12,AMBER,3,order=[(n,1) for n in [19,20,21,22,23,24,25,26,27]]+[(28,3)])
reading_group(24,'05 / Operação e manutenção',list(range(36,40)),12,29,12,12,CYAN,order=[(37,2),(36,1),(39,1),(38,2)])
reading_group(25,'06 / Modo, alarmes e disjuntor',[40,41,42,43,52],0,41,12,12,'#c7a5e8',order=[(40,2),(41,1),(42,1),(43,1),(52,1)],note='Últimos estados no período selecionado.')
reading_group(26,'07 / Entradas digitais',list(range(44,52)),12,41,12,12,'#8fa9c2',note='Entradas digitais / estados informados.')
for p in panels:
 if p['id']==25:
  next(e for e in p['options']['root']['elements'] if e['name']=='Leitura MDB40')['config']['text']['field']='MODO_LOCAL'
assert sorted(registry+list(range(29,36)))==list(range(1,53))
# Six compact summaries, including the same audited period-difference rules as DSE7420 V39.
for panel in panels:
 if panel['id'] in [10,11,12,13]:panel['gridPos'].update(x=(panel['id']-10)*4,w=4)
for id,n,field,title,colour in [(14,36,'HORAS_PERIODO','HORAS / PERÍODO',CYAN),(15,37,'KWH_PERIODO','ENERGIA / PERÍODO',AMBER)]:
 panels.append({'id':id,'type':'stat','title':title,'description':'Último contador menos contador inicial. Prefere base anterior compatível ao filtro; caso contrário usa a primeira leitura interna. * = cobertura parcial ou queda intermediária; não representa total comprovado após reset. A resposta da consulta informa contadores, horários e motivo. Divisor_Horas/Divisor_Energia ajustam as escalas.',
 'gridPos':{'x':(id-10)*4,'y':26,'w':4,'h':3},'datasource':copy.deepcopy(base['datasource']),
 'targets':[{'refId':'A','format':'table','rawQuery':True,'editorMode':'code','rawSql':period_sql(n,field)}],
 'transformations':[{'id':'filterFieldsByName','options':{'include':{'names':['EXIBICAO']}}}],
 'fieldConfig':{'defaults':{'unit':'none','noValue':'SEM LEITURAS','color':{'mode':'fixed','fixedColor':colour}},'overrides':[]},
 'options':{'reduceOptions':{'calcs':['lastNotNull'],'fields':'/^EXIBICAO$/','values':False},'textMode':'value','colorMode':'value','graphMode':'none','justifyMode':'center','text':{'valueSize':24}}})
# Histories keep the DSE8610 mapping, with per-series units and measured points.
hp=[]
groups=[('Tensões do gerador',list(range(9,15))),('Tensões do BUS',list(range(30,36))),('Frequências / GMG e BUS',[8,29]),('Correntes do gerador',[15,16,17,18]),('Potências do gerador',[19,20,21,22,23,24]),('Fatores de potência',[25,26,27,28]),('Motor e combustível',[1,2,3,4,5,6,7]),('Modo e GCB',[40,52]),('Alarmes / controlador',[41,42,43]),('Controle de horas',[36]),('Energia acumulada / kWh',[37])]
for i,(title,ns) in enumerate(groups):
 select=['"time" AS "time"'];field_overrides=[]
 for n in ns:
  label=labels[f'{n:02}'];expr=scaled(n)
  if n==40:expr='CASE '+''.join('WHEN mdb40='+var(code)+'::numeric THEN '+str(value)+' ' for text,code,value,colour in mode_codes)+'ELSE NULL END'
  select.append('CASE WHEN '+valid(n)+' THEN '+expr+' ELSE NULL END AS "'+label.replace('"','""')+'"')
  props=copy.deepcopy(next((o['properties'] for o in cfg['overrides'] if o['matcher']['options']==f'MDB{n:02}'),[]))
  field_overrides.append({'matcher':{'id':'byName','options':label},'properties':props})
 discrete=i in [7,8]
 hp.append({'id':110+i,'type':'timeseries','title':title,'gridPos':{'x':0,'y':54+i*9,'w':24,'h':9},'datasource':copy.deepcopy(base['datasource']),
 'targets':[{'refId':'A','format':'time_series','rawQuery':True,'editorMode':'code','rawSql':'SELECT '+','.join(select)+' FROM $Id_Logsis WHERE $__timeFilter("time") ORDER BY "time"'}],
 'fieldConfig':{'defaults':{'noValue':'—','custom':{'drawStyle':'line','lineWidth':2,'fillOpacity':0,'lineInterpolation':'stepAfter' if discrete else 'smooth','spanNulls':not discrete,'showPoints':'always','pointSize':3}},'overrides':field_overrides},
 'options':{'legend':{'displayMode':'list','placement':'bottom','calcs':[] if discrete else ['lastNotNull','min','max']},'tooltip':{'mode':'multi'}}})
panels.append({'id':100,'type':'row','title':'HISTÓRICOS E ALERTAS / DSE8610','collapsed':True,'gridPos':{'x':0,'y':53,'w':24,'h':1},'panels':hp})
d['panels']=sorted(panels,key=lambda p:(p['gridPos']['y'],p['gridPos']['x']))
d['timezone']='America/Sao_Paulo'
d['refresh']='5s'
d.setdefault('timepicker',{})['refresh_intervals']=['5s','10s','30s','1m','5m']
def clean(value):
 if isinstance(value,dict):return {key:clean(item) for key,item in value.items()}
 if isinstance(value,list):return [clean(item) for item in value]
 return value.replace('###','—') if isinstance(value,str) else value
d=clean(d)
out=ROOT/'dist/DSE8610_V3_IMPORTAR.json';out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(d,ensure_ascii=True,separators=(',',':'),allow_nan=False)+'\n',encoding='ascii')
with zipfile.ZipFile(ROOT/'dist/DSE8610_V3_IMPORTAR.zip','w',zipfile.ZIP_DEFLATED) as z:z.write(out,out.name)
print('DSE8610 V3: 52 canais, BUS medido, disjuntor, alarmes, modos completos e totais do período')
