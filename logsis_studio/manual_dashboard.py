"""Grafana templates generated from the same role/address map as each new BIN."""
from __future__ import annotations
import copy,json,math,re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote,unquote

INK,MUTED,CYAN,GOLD,RED,BG,SURFACE='#e5eef7','#96aec4','#67cce4','#e9bd79','#f2495c','#080f19','#101e2c'
BOOL_ROLES={'warning','trip','shutdown'}
SENTINELS='(-2147483648,2147483647,2147483648,4294967295)'

def sq(s):return "'"+str(s).replace("'","''")+"'"
def var(s):return '${'+s+':sqlstring}'
def field(c):return f'MDB{c.number:02}'
def ref(c):return '"'+field(c)+'"' if c else 'NULL::numeric'
def svg(raw):return 'data:image/svg+xml;charset=utf-8,'+quote(raw,safe='/:')
def wire(color,vertical=True):
 return svg(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {10 if vertical else 100} {100 if vertical else 10}" preserveAspectRatio="none"><path d="M0 0 L{0 if vertical else 100} {100 if vertical else 0}" stroke="{color}" stroke-width="4" fill="none" vector-effect="non-scaling-stroke"/></svg>')
def led(active):
 color=CYAN if active else MUTED
 return svg(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 40"><circle cx="40" cy="20" r="13" fill="{color if active else BG}" stroke="{color}" stroke-width="2"/><circle cx="36" cy="16" r="3" fill="{INK if active else BG}"/></svg>')
def signal(level):
 return svg('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 26 24">'+''.join(f'<rect x="{1+i*5}" y="{23-(5+i*4)}" width="3" height="{5+i*4}" rx=".7" fill="{CYAN if i<level else "#304354"}"/>' for i in range(5))+'</svg>')
def radio(wifi,color=CYAN):
 path='<path d="M3 9Q13 0 23 9M7 13Q13 7 19 13M10 17Q13 14 16 17"/><circle cx="13" cy="21" r="1"/>' if wifi else '<path d="M8 22V10M13 22V5M18 22V1"/>'
 return svg(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 26 24"><g stroke="{color}" fill="none" stroke-width="2">{path}</g></svg>')

@lru_cache(maxsize=1)
def reference():
 return json.loads((Path(__file__).parent/'resources/dse7420.json').read_text())
@lru_cache(maxsize=1)
def assets():
 d=reference();sql=d['panels'][0]['targets'][0]['rawSql'];p=sql.index('END AS "GERADOR_ALARME_SVG"')
 neutral=re.findall("'(data:image/svg[^']+)'",sql[:p])[-1]
 elements=d['panels'][0]['options']['root']['elements']
 result={'gen':neutral}
 for role,name in [('tower','Torre vetorial'),('load','Edifício vetorial')]:
  result[role]=next(e for e in elements if e['name']==name)['background']['image']['fixed']
 for role,color in [('warning','#f2cc0c'),('trip','#ff9830'),('shutdown',RED)]:
  rgb=[int(color[i:i+2],16)/255 for i in (1,3,5)]
  def tint(m):
   v=[int(m[0][i:i+2],16)/255 for i in (1,3,5)];light=.22+.95*sum(a*b for a,b in zip(v,[.2126,.7152,.0722]))
   return '#'+''.join(f'{round(min(1,c*light)*255):02x}' for c in rgb)
  result[role]=svg(re.sub(r'#[0-9a-fA-F]{6}',tint,unquote(neutral.split(',',1)[1])))
 return result

def numeric(expr):
 return f"(CASE WHEN length({expr})<32 AND {expr} ~ '^-?[0-9]+([.][0-9]+)?$' THEN ({expr})::numeric END)"
def clean(c,value):
 boolean=c.role in BOOL_ROLES or c.role.startswith(('input_','led_'))
 if boolean:return f'CASE WHEN {value} IN (0,1) THEN {value} END'
 bits=32 if c.params['FNC'] in ['30','40'] else 16
 if c.signed:
  maximum=2**bits;half=maximum//2
  signed=f'(CASE WHEN {value}>={half} THEN {value}-{maximum} ELSE {value} END)'
  low,high=(-32759,32759) if bits==16 else (-2147483647,2147483646)
  return f'CASE WHEN {value}=trunc({value}) AND {value} BETWEEN {low} AND {maximum-2} AND {value} NOT IN {SENTINELS} AND {signed} BETWEEN {low} AND {high} THEN {signed} END'
 high=32759 if bits==16 else 4294967294
 return f'CASE WHEN {value}=trunc({value}) AND {value} BETWEEN 0 AND {high} AND {value} NOT IN {SENTINELS} THEN {value} END'
def scaled(c,value):
 raw='('+clean(c,value)+')'
 div=var('Divisor_Energia')+'::numeric' if c.role.startswith('energy_') else str(c.divisor)
 return raw if div=='1' else raw+f'/NULLIF(({div}),0)'
def voltage(roles,prefix):
 cs=[c for role,c in roles.items() if role.startswith(prefix+'_v_')]
 return 'CASE WHEN '+' OR '.join(ref(c)+'>0' for c in cs)+' THEN 1 WHEN '+' AND '.join(ref(c)+'=0' for c in cs)+' THEN 0 END'


def main_sql(profile):
 roles={c.role:c for c in profile.channels}
 raw=[];values=[];labels=[]
 for c in profile.channels:
  last=f"(SELECT payload->>{sq(c.column)} FROM janela WHERE payload->>{sq(c.column)} IS NOT NULL ORDER BY \"time\" DESC LIMIT 1)"
  raw.append(numeric(last)+f' AS r{c.number}')
  values.append(scaled(c,f'r{c.number}')+' AS '+ref(c))
  if c.label_variable:labels.append(var(c.label_variable)+f' AS "NOME_{c.column.upper()}"')
 for alias,expr in [('gsm',"payload->>'gsm_rssi'"),('wifi','payload->>'+var('Campo_WiFi_RSSI'))]:
  raw.append(numeric(f'(SELECT {expr} FROM janela WHERE {expr} IS NOT NULL ORDER BY "time" DESC LIMIT 1)')+' AS '+alias)
 local_time="CASE WHEN pg_typeof(\"time\")='timestamp without time zone'::regtype THEN (\"time\"::timestamp AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo' ELSE \"time\"::timestamptz AT TIME ZONE 'America/Sao_Paulo' END"
 raw.append(f"(SELECT to_char(({local_time}),'DD/MM HH24:MI') FROM janela ORDER BY \"time\" DESC LIMIT 1) AS \"ULTIMA_LEITURA\"")
 values += ['"ULTIMA_LEITURA"',"CASE WHEN wifi BETWEEN -32759 AND -1 THEN wifi END AS \"WIFI_LOCAL\"",f"CASE WHEN {var('Formato_GSM')}='csq' AND gsm BETWEEN 0 AND 31 AND gsm=trunc(gsm) THEN -113+2*gsm WHEN {var('Formato_GSM')}='dbm' AND gsm BETWEEN -140 AND -1 THEN gsm END AS \"GSM_LOCAL\""]
 extra=labels
 codes=[(0,'STOP'),(1,'AUTO'),(2,'MANUAL'),(3,'TESTE C/ CARGA'),(4,'AUTO / RETORNO MANUAL'),(5,'CONFIGURAÇÃO'),(6,'TESTE S/ CARGA'),(7,'OFF')]
 extra.append('CASE '+''.join('WHEN '+ref(roles.get('mode'))+'='+str(n)+' THEN '+sq(text)+' ' for n,text in codes)+"ELSE 'SEM DADOS' END AS \"MODO_LOCAL\"")
 for prefix in ['gen','mains','bus','bus2']:
  if prefix+'_frequency' in roles:extra.append(voltage(roles,prefix)+f' AS "V_{prefix}"')
 for role,c in roles.items():
  if role.startswith('led_'):
   extra.append(f"CASE {ref(c)} WHEN 1 THEN 'LED ATIVO' WHEN 0 THEN 'LED INATIVO' ELSE 'SEM DADOS' END AS \"{role.upper()}_ESTADO\"")
   extra.append(f'CASE WHEN {ref(c)}=1 THEN {sq(led(True))} ELSE {sq(led(False))} END AS "{role.upper()}_SVG"')
 if profile.kind=='engine_transfer':
  alarm='CASE '+''.join('WHEN '+ref(roles[role])+'=1 THEN '+sq(assets()[role])+' ' for role in ['shutdown','trip','warning'])+'ELSE '+sq(assets()['gen'])+' END'
  extra.append(alarm+' AS "GERADOR_ALARME_SVG"')
  missing=' OR '.join(ref(roles[role])+' IS NULL' for role in ['warning','trip','shutdown'])
  extra.append('CASE '+''.join('WHEN '+ref(roles[role])+'=1 THEN '+sq('GERADOR / '+role.upper())+' ' for role in ['shutdown','trip','warning'])+'WHEN '+missing+" THEN 'ALARMES / SEM DADOS' ELSE 'GRUPO GERADOR' END AS \"GERADOR_ALARME\"")
  near=numeric(var('Manutencao_Alerta_h'))
  maintenance='CASE '
  for status,condition in [('VENCIDA','<=0'),('PRÓXIMA','>0')]:
   for i in range(1,4):
    c=roles['maintenance_'+str(i)];cond=ref(c)+condition
    if status=='PRÓXIMA':cond+=' AND '+ref(c)+'<=COALESCE('+near+',50)'
    maintenance+='WHEN '+cond+' THEN '+var(c.label_variable)+' || '+sq(' / '+status)+' '
  maintenance+='WHEN '+' OR '.join(ref(roles['maintenance_'+str(i)])+' IS NULL' for i in range(1,4))+" THEN 'MANUTENÇÃO / SEM DADOS' ELSE 'MANUTENÇÃO EM DIA' END"
  extra.append(maintenance+' AS "MANUTENCAO_RESUMO"')
 extra += [f'CASE WHEN "WIFI_LOCAL" IS NULL THEN {sq(radio(True,MUTED))} ELSE {sq(radio(True))} END AS "WIFI_LOCAL_ICONE"',
  'CASE '+''.join(f'WHEN "GSM_LOCAL">={threshold} THEN {sq(signal(level))} ' for threshold,level in [(-80,5),(-90,4),(-100,3),(-110,2),(-140,1)])+'ELSE '+sq(signal(0))+' END AS "GSM_LOCAL_ICONE"']
 first='WITH janela AS (SELECT "time",to_jsonb(t) AS payload FROM $Id_Logsis t WHERE $__timeFilter("time")), raw AS (SELECT '+','.join(raw)+'), dados AS (SELECT '+','.join(values)+' FROM raw), sinais AS (SELECT dados.*,'+','.join(extra)+' FROM dados) '
 wires=[]
 for prefix in ['gen','mains','bus','bus2']:
  if prefix+'_frequency' in roles:
   for kind,vertical in [('V',True),('H',False)]:wires.append(f'CASE WHEN "V_{prefix}"=1 THEN {sq(wire(RED,vertical))} ELSE {sq(wire(MUTED,vertical))} END AS "WIRE_{prefix}_{kind}"')
 short_mode = '''CASE WHEN "MODO_LOCAL"='AUTO / RETORNO MANUAL' THEN 'AUTO / RET. MAN.' ELSE "MODO_LOCAL" END AS "MODO_CURTO"'''
 return first+'SELECT sinais.*,'+short_mode+','+','.join(wires)+' FROM sinais'


def properties(profile):
 overrides=[]
 for c in profile.channels:
  props={'unit':('suffix: '+c.unit) if c.unit else 'none','decimals':1 if c.divisor in [10,3600] else 2 if c.divisor>10 else 0,'noValue':'—','mappings':[{'type':'special','options':{'match':'null','result':{'text':'—','color':MUTED}}}]}
  if c.role.startswith(('input_','led_')) or c.role in BOOL_ROLES:
   one,zero=('LED ATIVO','LED INATIVO') if c.role.startswith('led_') else ('ON','OFF') if c.role.startswith('input_') else ('ATIVO','INATIVO')
   props.update(unit='none',decimals=0)
   props['mappings'].insert(0,{'type':'value','options':{'0':{'text':zero,'color':MUTED},'1':{'text':one,'color':CYAN if c.role.startswith('input_') else GOLD}}})
  overrides.append({'matcher':{'id':'byName','options':field(c)},'properties':[{'id':k,'value':v} for k,v in props.items()]})
 for c in profile.channels:
  if c.role.startswith('led_'):
   overrides.append({'matcher':{'id':'byName','options':c.role.upper()+'_ESTADO'},'properties':[{'id':'mappings','value':[{'type':'value','options':{'LED ATIVO':{'text':'LED ATIVO','color':CYAN},'LED INATIVO':{'text':'LED INATIVO','color':MUTED},'SEM DADOS':{'text':'SEM DADOS','color':MUTED}}}]}]})
 overrides.append({'matcher':{'id':'byName','options':'GERADOR_ALARME'},'properties':[{'id':'mappings','value':[{'type':'value','options':{'GRUPO GERADOR':{'text':'GRUPO GERADOR','color':GOLD},'ALARMES / SEM DADOS':{'text':'ALARMES / SEM DADOS','color':MUTED},'GERADOR / WARNING':{'text':'GERADOR / WARNING','color':'#f2cc0c'},'GERADOR / TRIP':{'text':'GERADOR / TRIP','color':'#ff9830'},'GERADOR / SHUTDOWN':{'text':'GERADOR / SHUTDOWN','color':RED}}}]}]})
 for alias in ['MODO_LOCAL','MODO_CURTO']:
  overrides.append({'matcher':{'id':'byName','options':alias},'properties':[{'id':'color','value':{'mode':'fixed','fixedColor':GOLD}}]})
 for alias in ['WIFI_LOCAL','GSM_LOCAL']:
  overrides.append({'matcher':{'id':'byName','options':alias},'properties':[{'id':'unit','value':'suffix: dBm'},{'id':'decimals','value':0}]})
 for alias in ['ULTIMA_LEITURA','MODO_LOCAL','MANUTENCAO_RESUMO','GERADOR_ALARME']:
  prop=[{'id':'unit','value':'none'}]
  if alias=='MANUTENCAO_RESUMO':prop.append({'id':'mappings','value':[{'type':'regex','options':{'pattern':pattern,'result':{'color':color}}} for pattern,color in [('.* / VENCIDA$','#ff9830'),('.* / PRÓXIMA$','#f2cc0c')]]})
  overrides.append({'matcher':{'id':'byName','options':alias},'properties':prop})
 return {'defaults':{'unit':'none','noValue':'—','color':{'mode':'fixed','fixedColor':INK}},'overrides':overrides}

def box(name,left,width,top,height,fill='transparent',border='transparent'):
 return {'name':name,'type':'rectangle','placement':{'left':left,'right':100-left-width,'top':top,'height':height,'rotation':0},'constraint':{'horizontal':'scale','vertical':'top'},'config':{'text':{'fixed':''},'color':{'fixed':INK},'size':12,'align':'center','valign':'middle'},'background':{'color':{'fixed':fill}},'border':{'color':{'fixed':border},'width':.7 if border!='transparent' else 0},'links':[]}
def text(name,left,width,top,height,label='',size=12,color=MUTED,field_name=None):
 e=box(name,left,width,top,height);e['type']='metric-value' if field_name else 'text';e['config'].update(text={'mode':'field','field':field_name,'fixed':'—'} if field_name else {'fixed':label},size=size,color={'field':field_name,'fixed':color} if field_name else {'fixed':color});return e
def image(name,left,width,top,height,uri=None,field_name=None):
 e=box(name,left,width,top,height);e['background'].update(image={'mode':'mapping','field':field_name} if field_name else {'fixed':uri},size='fill');return e
def canvas(profile,id,title,pos,elements,height):
 return {'id':id,'type':'canvas','title':title,'gridPos':pos,'transparent':False,'datasource':{'type':'datasource','uid':'-- Dashboard --'},'targets':[{'refId':'A','panelId':1,'withTransforms':False}],'fieldConfig':properties(profile),'options':{'inlineEditing':False,'panZoom':False,'infinitePan':False,'root':{'name':title,'type':'frame','placement':{'left':0,'top':0,'width':600,'height':height},'elements':[box('Fundo',0,100,0,height,BG)]+elements}}}
def group(profile,id,title,cs,pos,height=412,cols=2):
 es=[];rows=max(1,math.ceil(len(cs)/cols));h=(height-24)/rows-6
 for i,c in enumerate(cs):
  left=2+(i%cols)*96/cols;w=96/cols-2;y=12+(i//cols)*(h+6)
  es.append(box('Cartão '+field(c),left,w,y,h,SURFACE,'#263c4f'))
  es.append(text('Nome '+field(c),left+1,w-2,y+6,17,c.name,9,field_name='NOME_'+c.column.upper() if c.label_variable else None))
  es.append(text('Valor '+field(c),left+1,w-2,y+25,26,size=16,color=INK,field_name=field(c)))
  es.append(text('Canal '+field(c),left+1,w-2,y+h-15,12,field(c),8,'#7891a7'))
 return canvas(profile,id,title,pos,es,height)
def stat(profile,id,title,c,pos,period=False):
 p={'id':id,'type':'stat','title':title,'gridPos':pos,'datasource':{'type':'datasource','uid':'-- Dashboard --'},'targets':[{'refId':'A','panelId':1,'withTransforms':False}],'fieldConfig':properties(profile),'transformations':[{'id':'filterFieldsByName','options':{'include':{'names':[field(c)]}}}],'options':{'reduceOptions':{'calcs':['lastNotNull'],'fields':'','values':False},'orientation':'auto','textMode':'value','colorMode':'value','graphMode':'none','justifyMode':'center','text':{'valueSize':26}}}
 if period:
  index=14 if c.role=='hour_meter' else 15
  old=next(x for x in reference()['panels'] if x['id']==index)
  raw=numeric('to_jsonb(t)->>'+sq(c.column));clean_raw=clean(c,raw)
  n=36 if c.role=='hour_meter' else 37
  source=f'(SELECT t."time",({clean_raw}) AS mdb{n} FROM $Id_Logsis t) contador'
  sql=old['targets'][0]['rawSql'].replace('$Id_Logsis',source)
  p['datasource']={'type':'grafana-postgresql-datasource','uid':'zKW_ld27k'}
  p['targets']=[{'refId':'A','rawQuery':True,'format':'table','editorMode':'code','rawSql':sql}]
  p['transformations']=[{'id':'filterFieldsByName','options':{'include':{'names':['EXIBICAO']}}}]
  p['description']='Diferença final − inicial do contador, usando a base válida anterior ao filtro quando compatível. * indica cobertura parcial ou queda; consulte SITUACAO na consulta.'
 return p


def engine_overview(profile):
 p=copy.deepcopy(reference()['panels'][0]);roles={c.role:c for c in profile.channels}
 p['targets'][0]['rawSql']=main_sql(profile);p['fieldConfig']=properties(profile)
 p['title']='01 / Rede → transferência → gerador e carga'
 replacements={'TENSAO_GMG_PRESENTE':'V_gen','TENSAO_REDE_PRESENTE':'V_mains','TENSAO_GMG_PRESENTE_V_SVG':'WIRE_gen_V','TENSAO_REDE_PRESENTE_V_SVG':'WIRE_mains_V','MDB52_CONTATO_SVG':'LED_MAINS_SVG','MDB53_CONTATO_SVG':'LED_GEN_SVG','K1_ESTADO':'LED_MAINS_ESTADO','K2_ESTADO':'LED_GEN_ESTADO'}
 def walk(o):
  if isinstance(o,dict):
   if o.get('field') in replacements:o['field']=replacements[o['field']]
   if isinstance(o.get('fixed'),str):o['fixed']=o['fixed'].replace('DSE7420',profile.label).replace('K1 / REDE','LED / REDE').replace('K2 / GMG','LED / GMG').replace('QTA','LED').replace('SAÍDA INFERIDA','SAÍDA NÃO MEDIDA')
   for value in o.values():walk(value)
  elif isinstance(o,list):
   for value in o:walk(value)
 walk(p['options'])
 for e in p['options']['root']['elements']:
  name=e.get('config',{}).get('text',{}).get('field')
  if name=='QTA_ESTADO':e['config']['text']={'fixed':'INDICADORES DO CONTROLADOR'};e['type']='text';e['config']['color']={'fixed':MUTED}
  if name=='TENSAO_SAIDA_PRESENTE':e['config']['text']={'fixed':'SEM MEDIÇÃO DA SAÍDA'};e['type']='text';e['config']['color']={'fixed':MUTED}
  if name=='MODO_LOCAL':e['config']['text']['field']='MODO_CURTO';e['config']['size']=9
  image_data=e.get('background',{}).get('image',{})
  if image_data.get('field','').startswith('TENSAO_SAIDA_PRESENTE'):
   vertical='_V_' in image_data['field'];e['background']['image']={'fixed':wire(MUTED,vertical)}
 # Voltage text colors are still meaningful after replacing legacy aliases.
 for f in ['V_gen','V_mains']:
  p['fieldConfig']['overrides'].append({'matcher':{'id':'byName','options':f},'properties':[{'id':'mappings','value':[{'type':'value','options':{'0':{'text':'SEM TENSÃO','color':MUTED},'1':{'text':'COM TENSÃO','color':RED}}}]}]})
 return p


def bus_overview(profile):
 roles={c.role:c for c in profile.channels};sources=['mains','bus'] if profile.kind=='mains_bus' else ['bus','bus2']
 labels=['REDE / CONCESSIONÁRIA','BARRAMENTO / BUS'] if profile.kind=='mains_bus' else ['BARRAMENTO / BUS 1','BARRAMENTO / BUS 2']
 es=[text('Marca',3,94,20,30,'LOGSIS / '+profile.label,18,INK)]
 for i,(prefix,label) in enumerate(zip(sources,labels)):
  left=3+i*50
  es.append(text('Fonte '+prefix,left,44,125,20,label,11,CYAN))
  if prefix=='mains':es.append(image('Torre vetorial',left,44,155,100,assets()['tower']))
  else:
   for j in range(3):es.append(image(f'Barra {prefix} {j}',left+5,34,165+j*25,3,field_name='WIRE_'+prefix+'_H'))
  es.append(box('Leituras '+prefix,left,44,270,172,SURFACE,'#263c4f'))
  for j,(suffix,caption) in enumerate([('v_l1n','L1–N'),('v_l2n','L2–N'),('v_l3n','L3–N'),('frequency','Hz'),('i_l1','I L1'),('kw','kW'),('fp','FP')]):
   es += [text('Legenda '+prefix+suffix,left+2,16,278+j*22,19,caption,9),text('Valor '+prefix+suffix,left+18,24,278+j*22,19,size=12,color=INK,field_name=field(roles[prefix+'_'+suffix]))]
  es.append(image('Trecho '+prefix,left+22,1,446,80,field_name='WIRE_'+prefix+'_V'))
 if profile.kind=='bus_tie':
  es += [image('Acoplamento esquerdo',25,22,526,3,wire(MUTED,False)),image('Acoplamento direito',53,22,526,3,wire(MUTED,False)),image('LED acoplador',44,12,509,36,field_name='LED_TIE_SVG'),text('Acoplador título',10,80,556,20,'ACOPLADOR / INDICADOR LED',11,CYAN),text('Acoplador estado',10,80,580,20,field_name='LED_TIE_ESTADO',size=11)]
 else:
  for i,prefix in enumerate(sources):es += [image('Indicador '+prefix,16+i*50,18,508,40,field_name='LED_'+prefix.upper()+'_SVG'),text('LED '+prefix,3+i*50,44,557,20,field_name='LED_'+prefix.upper()+'_ESTADO',size=10)]
 es += [text('Indicação',3,94,618,20,'INDICADORES LED DO CONTROLADOR',9,MUTED),image('Edifício vetorial',55,35,674,124,assets()['load']),text('Carga',53,41,805,20,'CARGA / BUS' if profile.kind=='mains_bus' else 'CARGA / BUS 2',10,INK)]
 es.append(image('BUS medido para carga',75,1,526,166,field_name='WIRE_'+sources[1]+'_V'))
 for i,(caption,field_name) in enumerate([('MODO / CONTROLADOR','MODO_CURTO'),('WI-FI / RSSI','WIFI_LOCAL'),('GSM / RSSI','GSM_LOCAL')]):
  x=3+i*32;es += [box(caption,x,30,70,42,SURFACE,'#263c4f'),text(caption+' label',x+1,28,74,12,caption,8),text(caption+' value',x+1,28,89,19,field_name=field_name,size=9 if field_name=='MODO_CURTO' else 11,color=INK)]
 es += [image('Sinal WiFi',36,4,90,17,field_name='WIFI_LOCAL_ICONE'),image('Sinal GSM',68,4,90,17,field_name='GSM_LOCAL_ICONE'),text('Última leitura título',3,94,850,14,'ÚLTIMO REGISTRO / BRASÍLIA',8),text('Última leitura valor',3,94,869,20,field_name='ULTIMA_LEITURA',size=12,color=INK),text('Período',3,94,909,14,'LEITURAS DO PERÍODO SELECIONADO',8,GOLD)]
 p=canvas(profile,1,'01 / '+('Rede e BUS' if profile.kind=='mains_bus' else 'BUS 1 ↔ acoplador ↔ BUS 2'),{'x':0,'y':0,'w':12,'h':27},es,950)
 p['datasource']={'type':'grafana-postgresql-datasource','uid':'zKW_ld27k'};p['targets']=[{'refId':'A','rawQuery':True,'format':'table','editorMode':'code','rawSql':main_sql(profile)}]
 return p


def history(profile,start_y):
 panels=[];groups={}
 for c in profile.channels:groups.setdefault(c.group,[]).append(c)
 y=start_y+1
 for i,(name,cs) in enumerate(groups.items()):
  columns=['t."time" AS "time"']+[scaled(c,numeric('to_jsonb(t)->>'+sq(c.column)))+' AS '+ref(c) for c in cs]
  config=properties(profile)
  for c in cs:
   if c.label_variable:config['overrides'].append({'matcher':{'id':'byName','options':field(c)},'properties':[{'id':'displayName','value':'${'+c.label_variable+'}'}]})
  config['defaults']['color']={'mode':'palette-classic'}
  config['defaults']['custom']={'drawStyle':'line','lineInterpolation':'linear','lineWidth':1.5,'fillOpacity':0,'showPoints':'always','pointSize':3,'spanNulls':True,'axisBorderShow':False}
  panels.append({'id':1000+i,'type':'timeseries','title':name,'gridPos':{'x':0,'y':y,'w':24,'h':9},'datasource':{'type':'grafana-postgresql-datasource','uid':'zKW_ld27k'},'targets':[{'refId':'A','rawQuery':True,'format':'time_series','editorMode':'code','rawSql':'SELECT '+','.join(columns)+' FROM $Id_Logsis t WHERE $__timeFilter("time") ORDER BY "time"'}],'fieldConfig':config,'options':{'tooltip':{'mode':'multi'},'legend':{'displayMode':'list','placement':'bottom','calcs':['min','max','lastNotNull']}}})
  y+=9
 return {'id':901,'type':'row','title':'HISTÓRICOS E ALERTAS — expandir / recolher','collapsed':True,'gridPos':{'x':0,'y':start_y,'w':24,'h':1},'panels':panels}


def build_dashboard(profile):
 roles={c.role:c for c in profile.channels};variables=[{'name':'Id_Logsis','type':'constant','hide':2,'query':'id_planta','skipUrlSync':True}]
 for name,value in [('Divisor_Energia','10'),('Campo_WiFi_RSSI','WiFi_rssi'),('Formato_GSM','dbm'),('Manutencao_Alerta_h','50')]:variables.append({'name':name,'type':'constant','hide':2,'query':value,'skipUrlSync':True})
 for c in profile.channels:
  if c.label_variable:variables.append({'name':c.label_variable,'label':c.name,'type':'constant','hide':2,'query':c.name,'skipUrlSync':True})
 if profile.kind=='engine_transfer':
  overview=engine_overview(profile);panels=[overview]
  for id in [21,23,22,24]:panels.append(copy.deepcopy(next(p for p in reference()['panels'] if p['id']==id)))
  for i,role in enumerate(['gen_kw','gen_fp','hour_meter','energy_gen','hour_meter','energy_gen']):
   c=roles[role];period=i>=4
   panels.append(stat(profile,10+i,('HORAS / PERÍODO' if role=='hour_meter' else 'ENERGIA / PERÍODO') if period else c.name,c,{'x':i*4,'y':27,'w':4,'h':3},period))
  for i in range(1,4):
   c=roles['maintenance_'+str(i)];panels.append(stat(profile,15+i,'${'+c.label_variable+'} / HORAS RESTANTES',c,{'x':(i-1)*8,'y':42,'w':8,'h':4}))
  control_y=46;end_y=58
 else:
  panels=[bus_overview(profile)];sources=['mains','bus'] if profile.kind=='mains_bus' else ['bus','bus2']
  for i,prefix in enumerate(sources):
   primary=[c for role,c in roles.items() if role.startswith(prefix+'_') and (role[len(prefix)+1:].startswith('v_') or role[len(prefix)+1:] in ['frequency','i_l1','i_l2','i_l3','kw','fp'])]
   panels.append(group(profile,21+i,f'{2+i:02} / '+('Rede' if prefix=='mains' else ('BUS' if profile.kind=='mains_bus' else 'BUS 1') if prefix=='bus' else 'BUS 2'),primary,{'x':12,'y':i*13,'w':12,'h':14 if i else 13},height=450 if i==0 else 488,cols=3))
   detail=[c for role,c in roles.items() if role.startswith(prefix+'_') and c not in primary]
   panels.append(group(profile,23+i,f'{4+i:02} / Potências e correntes · '+prefix.upper(),detail,{'x':i*12,'y':30,'w':12,'h':12}))
  counters=[c for c in profile.channels if c.role.startswith('energy_')]
  stats=[(roles[p+'_kw'],False) for p in sources]+[(c,False) for c in counters]+[(c,True) for c in counters]
  if len(stats)<6:stats += [(roles[p+'_fp'],False) for p in sources][:6-len(stats)]
  for i,(c,period) in enumerate(stats[:6]):panels.append(stat(profile,10+i,c.name+(' / PERÍODO' if period else ''),c,{'x':i*4,'y':27,'w':4,'h':3},period))
  control_y=42;end_y=54
 controls=[c for c in profile.channels if c.role in ['mode','warning','trip','shutdown'] or c.role.startswith('led_')]
 inputs=[c for c in profile.channels if c.input_letter]
 panels += [group(profile,25,'06 / Controle e indicadores LED',controls,{'x':0,'y':control_y,'w':12,'h':12}),group(profile,26,'07 / Entradas digitais e flexíveis',inputs,{'x':12,'y':control_y,'w':12,'h':12}),history(profile,end_y)]
 # Mode is text in controls rather than the numeric code.
 for panel in panels:
  if panel['id']==25:
   for e in panel['options']['root']['elements']:
    if e['name']=='Valor '+field(roles['mode']):e['config']['text']['field']='MODO_LOCAL';e['config']['size']=11
 panels.sort(key=lambda p:(p['gridPos']['y'],p['gridPos']['x']))
 return {'id':None,'uid':'logsis-'+profile.model.lower()+'-manual','title':'LOGSIS / '+profile.label+' — Manual M1','schemaVersion':39,'version':1,'timezone':'America/Sao_Paulo','style':'dark','editable':True,'refresh':'30s','time':{'from':'now-6h','to':'now'},'tags':['LOGSIS',profile.model,'GenComm','M1'],'description':' '.join(profile.manual_notes or []),'templating':{'list':variables},'panels':panels,'annotations':{'list':[]},'links':[]}
