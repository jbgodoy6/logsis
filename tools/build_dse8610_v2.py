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
d.update(id=None,uid='logsis-dse8610-v1-bus',title='LOGSIS / DSE8610 — Gerador e BUS',version=1,tags=['LOGSIS','DSE8610','BUS','responsivo','V2'],links=[],description='Gerador, disjuntor MDB52, barramento comum medido e carga. Mapeamento auditado do BIN; escalas e códigos de modo configuráveis.')
variables=[{'name':'Id_Logsis','label':'Tabela da planta DSE8610','type':'constant','query':'id_dse8610','hide':2,'skipUrlSync':True}]
def const(name,value):variables.append({'name':name,'type':'constant','hide':2,'query':str(value),'skipUrlSync':True})
for n,v in [('Campo_WiFi_RSSI','WiFi_rssi'),('Formato_GSM','dbm'),('Codigo_STOP',0),('Codigo_AUTO',1),('Codigo_MANUAL',2),('Divisor_Tensao',10),('Divisor_Corrente',10),('Divisor_Potencia',1000),('Divisor_FP',100),('Divisor_Horas',3600),('Divisor_Energia',10)]:const(n,v)
d['templating']={'list':variables}
def var(n):return '${'+n+':sqlstring}'
def sq(s):return "'"+s.replace("'","''")+"'"
def scaled(n):
 c=f'mdb{n}::numeric'
 divisor=('100' if n==1 else '10' if n in [5,6,8,29] else var('Divisor_Tensao') if 9<=n<=14 or 30<=n<=35  else var('Divisor_Corrente') if 15<=n<=18 else var('Divisor_Potencia') if 19<=n<=24 else var('Divisor_FP') if 25<=n<=28 else var('Divisor_Horas') if n in [36,39] else var('Divisor_Energia') if n==37 else '1')
 return c if divisor=='1' else '('+c+')/NULLIF(('+divisor+')::numeric,0)'
def valid(n):
 c=f'mdb{n}'
 if n==52:return c+' IN (0,1)'
 return c+' NOT IN (-2147483648,2147483647,4294967295)'+(' AND '+c+' BETWEEN -32759 AND 32759' if records[n]['FNC']=='3' else '')
fields=[]
for n in range(1,53):
 # Discrete invalid latest values remain unknown; absent rows may be skipped.
 expr=('CASE WHEN mdb52 IN (0,1) THEN mdb52 ELSE NULL END' if n==52 else scaled(n))
 where='' if n==52 else ' AND '+valid(n)
 fields.append(f'(SELECT {expr} FROM $Id_Logsis WHERE $__timeFilter("time") AND mdb{n} IS NOT NULL{where} ORDER BY "time" DESC LIMIT 1) AS "MDB{n:02}"')
fields += ['(SELECT gsm_rssi FROM $Id_Logsis WHERE $__timeFilter("time") AND gsm_rssi IS NOT NULL ORDER BY "time" DESC LIMIT 1) AS "GSM_RSSI"','(SELECT to_char("time",\'DD/MM HH24:MI\') FROM $Id_Logsis WHERE $__timeFilter("time") ORDER BY "time" DESC LIMIT 1) AS "ULTIMA_LEITURA"']
# Each voltage group takes its own latest sample, independently of the breaker.
ctes=['leituras AS (SELECT '+',\n'.join(fields)+')']
for group,ns in [('gmg',list(range(9,15))),('bus',list(range(30,36)))]:
 cols=','.join(f'mdb{n}' for n in ns);present=' OR '.join(f'({valid(n)} AND ({scaled(n)})>0)' for n in ns);zero=' AND '.join(f'({scaled(n)})=0' for n in ns)
 ctes.append(f'{group} AS (SELECT CASE WHEN {present} THEN 1 WHEN {zero} THEN 0 ELSE NULL END AS state FROM $Id_Logsis WHERE $__timeFilter("time") AND ('+' OR '.join(f'mdb{n} IS NOT NULL' for n in ns)+') ORDER BY "time" DESC LIMIT 1)')
ctes += ['telemetria AS (SELECT to_jsonb(t) AS j FROM $Id_Logsis t WHERE $__timeFilter("time") ORDER BY "time" DESC LIMIT 1)', 'sinais AS (SELECT leituras.*, (SELECT state FROM gmg) AS "TENSAO_GMG", (SELECT state FROM bus) AS "TENSAO_BUS", (SELECT COALESCE(j->>${Campo_WiFi_RSSI:sqlstring},j->>lower(${Campo_WiFi_RSSI:sqlstring})) FROM telemetria) AS wifi_txt FROM leituras)', 'parsed AS (SELECT sinais.*,CASE WHEN wifi_txt ~ \'^-?[0-9]+([.][0-9]+)?$\' THEN wifi_txt::numeric END AS "WIFI_LOCAL",CASE WHEN "GSM_RSSI"::text ~ \'^-?[0-9]+([.][0-9]+)?$\' THEN "GSM_RSSI"::numeric END AS gsm_raw FROM sinais)', 'dados AS (SELECT parsed.*,CASE WHEN ${Formato_GSM:sqlstring}=\'csq\' AND gsm_raw BETWEEN 0 AND 31 AND gsm_raw=trunc(gsm_raw) THEN -113+2*gsm_raw WHEN ${Formato_GSM:sqlstring}=\'dbm\' AND gsm_raw BETWEEN -140 AND -1 THEN gsm_raw END AS "GSM_LOCAL" FROM parsed)']
extra=['CASE WHEN "MDB40"=${Codigo_STOP:sqlstring}::numeric THEN \'STOP\' WHEN "MDB40"=${Codigo_AUTO:sqlstring}::numeric THEN \'AUTO\' WHEN "MDB40"=${Codigo_MANUAL:sqlstring}::numeric THEN \'MANUAL\' WHEN "MDB40" IS NULL THEN \'SEM DADOS\' ELSE \'OUTRO\' END AS "MODO_LOCAL"','"MDB52" AS "DISJUNTOR_GCB"','CASE "MDB52" WHEN 0 THEN \'DISJUNTOR ABERTO\' WHEN 1 THEN \'DISJUNTOR FECHADO\' ELSE \'POSIÇÃO DESCONHECIDA\' END AS "ESTADO_GCB"']
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
override('MODO_LOCAL',{'unit':'none','mappings':mapping([(v,v,c) for v,c in [('AUTO',CYAN),('MANUAL',AMBER),('STOP',MUTED),('SEM DADOS',MUTED)]])})
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
text('Gerador título',3,44,120,18,'GERADOR MONITORADO',10,AMBER)
e=box('Gerador vetorial',3,44,146,100);e['background'].update(image={'fixed':svg_art('Gerador')},size='fill')
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
text('Disjuntor posição',16,18,491,32,size=24,color=AMBER,field='DISJUNTOR_GCB')
line(25,534,25,574,'TENSAO_BUS')
line(75,447,75,574,color='#6d8194',dashed=True)
text('BUS nome',37,26,547,17,'BUS COMUM',10,CYAN)
line(15,574,85,574,'TENSAO_BUS')
line(50,574,50,607,'TENSAO_BUS')
box('QGBT',37,26,607,25,SURFACE,'#6f8b9e');text('QGBT nome',38,24,611,16,'QGBT / CARGA',9)
line(50,632,50,647,'TENSAO_BUS')
e=box('Edifício vetorial',30,40,648,116);e['background'].update(image={'fixed':svg_art('Edifício')},size='fill')
text('Carga nome',3,94,769,18,'CARGA DA INSTALAÇÃO',11)
text('GCB estado',3,94,798,18,size=11,field='ESTADO_GCB')
text('BUS nota',3,94,824,16,'TENSÃO DO BUS MEDIDA / INDEPENDENTE DO GCB',8,MUTED)
text('Última leitura título',3,94,854,14,'ÚLTIMO REGISTRO NA JANELA',8,MUTED)
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
reading_group(25,'06 / Modo, alarmes e disjuntor',[40,41,42,43,52],0,41,12,12,'#c7a5e8',order=[(40,2),(41,1),(42,1),(43,1),(52,1)],note='Alarmes: conferir extração de bits no coletor.')
reading_group(26,'07 / Entradas digitais',list(range(44,52)),12,41,12,12,'#8fa9c2',note='Estados do coletor / polaridade a conferir.')
for p in panels:
 if p['id']==25:
  next(e for e in p['options']['root']['elements'] if e['name']=='Leitura MDB40')['config']['text']['field']='MODO_LOCAL'
assert sorted(registry+list(range(29,36)))==list(range(1,53))
# Fresh history queries use DSE8610 positions, never inherited DSE7420 mode/alarms.
hp=[]
for i,(title,ns) in enumerate([('Tensões do gerador',list(range(9,15))),('Tensões do BUS',list(range(30,36))),('Frequências / GMG e BUS',[8,29]),('Correntes do gerador',[15,16,17,18]),('Potências do gerador',[19,20,21,22,23,24]),('Fatores de potência',[25,26,27,28]),('Motor e combustível',[1,2,3,4,5,6,7]),('Modo e GCB',[40,52]),('Alarmes / controlador',[41,42,43])]):
 # Column aliases are SQL identifiers.
 select=['"time" AS "time"']+['CASE WHEN '+valid(n)+' THEN '+scaled(n)+' ELSE NULL END AS "'+labels[f'{n:02}'].replace('"','""')+'"' for n in ns]
 hp.append({'id':110+i,'type':'timeseries','title':title,'gridPos':{'x':0,'y':54+i*9,'w':24,'h':9},'datasource':copy.deepcopy(base['datasource']),'targets':[{'refId':'A','format':'time_series','rawQuery':True,'editorMode':'code','rawSql':'SELECT '+','.join(select)+' FROM $Id_Logsis WHERE $__timeFilter("time") ORDER BY "time"'}],'fieldConfig':{'defaults':{'noValue':'—','custom':{'drawStyle':'line','lineWidth':1,'fillOpacity':4,'spanNulls':False}},'overrides':[]},'options':{'legend':{'displayMode':'list','placement':'bottom'},'tooltip':{'mode':'multi'}}})
panels.append({'id':100,'type':'row','title':'HISTÓRICOS E ALERTAS / DSE8610','collapsed':True,'gridPos':{'x':0,'y':53,'w':24,'h':1},'panels':hp})
d['panels']=sorted(panels,key=lambda p:(p['gridPos']['y'],p['gridPos']['x']))
out=ROOT/'dist/DSE8610_V2_IMPORTAR.json';out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(d,ensure_ascii=True,separators=(',',':'),allow_nan=False)+'\n',encoding='ascii')
with zipfile.ZipFile(ROOT/'dist/DSE8610_V2_IMPORTAR.zip','w',zipfile.ZIP_DEFLATED) as z:z.write(out,out.name)
print('DSE8610 V2: um gerador, símbolo BUS, UID e consultas preservados')
