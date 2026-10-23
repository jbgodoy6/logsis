"""Single responsive dashboard: embedded vectors, fluid paths and native data panels."""
import copy
import html
import json
import pathlib
import zipfile
from urllib.parse import quote as urlquote

ROOT=pathlib.Path(__file__).resolve().parents[1]
source=json.loads((ROOT/'V26_IMPORTAR.json').read_text())
d=copy.deepcopy(source)
base,instrument,history=d['panels']
art=base['options']['root']['elements']
INK,MUTED,CYAN,AMBER,RED,BG,SURFACE='#e5eef7','#96aec4','#67cce4','#e9bd79','#f2495c','#080f19','#0e1a27'

def svg_art(prefix):
    selected=[e for e in art if e['name'].startswith(prefix+' / ')]
    by_name={e['name']:e for e in selected}
    x0=min(e['placement']['left'] for e in selected)-5
    y0=min(e['placement']['top'] for e in selected)-5
    x1=max(e['placement']['left']+e['placement']['width'] for e in selected)+5
    y1=max(e['placement']['top']+e['placement']['height'] for e in selected)+5
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0} {y0} {x1-x0} {y1-y0}" preserveAspectRatio="xMidYMid meet">']
    def esc(s):return html.escape(str(s),quote=True)
    for e in selected:
        p=e['placement'];x,y,w,h=[p[k] for k in ['left','top','width','height']]
        fill=e.get('background',{}).get('color',{}).get('fixed','transparent')
        stroke=e.get('border',{}).get('color',{}).get('fixed','transparent')
        sw=e.get('border',{}).get('width',0)
        if e['type']=='ellipse':
            parts.append(f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" fill="{esc(fill)}" stroke="{esc(stroke)}" stroke-width="{sw}"/>')
        elif e['type']=='rectangle' and (fill!='transparent' or stroke!='transparent'):
            parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{esc(fill)}" stroke="{esc(stroke)}" stroke-width="{sw}"/>')
        elif e['type']=='text':
            label=e['config']['text'].get('fixed','')
            parts.append(f'<text x="{x+w/2}" y="{y+h*.7}" text-anchor="middle" font-family="sans-serif" font-size="{e["config"].get("size",10)}" fill="{esc(e["config"]["color"].get("fixed",INK))}">{esc(label)}</text>')
    for e in selected:
        for c in e.get('connections',[]):
            target=by_name.get(c.get('targetName'))
            if target is None:continue
            p,q=e['placement'],target['placement']
            a,b=c['source'],c['target']
            xx1=p['left']+p['width']/2+a['x']*p['width']/2
            yy1=p['top']+p['height']/2-a['y']*p['height']/2
            xx2=q['left']+q['width']/2+b['x']*q['width']/2
            yy2=q['top']+q['height']/2-b['y']*q['height']/2
            parts.append(f'<line x1="{xx1}" y1="{yy1}" x2="{xx2}" y2="{yy2}" stroke="{esc(c["color"].get("fixed",INK))}" stroke-width="{c["size"].get("fixed",1)}"/>')
    parts.append('</svg>')
    raw=''.join(parts)
    # The readable namespace URI also lets Grafana 11.2 classify this as an absolute resource.
    return 'data:image/svg+xml;charset=utf-8,'+urlquote(raw,safe='/:')

def wire_svg(color,vertical=True,dashed=False):
    view='0 0 10 100' if vertical else '0 0 100 10'
    end='0 100' if vertical else '100 0'
    dash=' stroke-dasharray="4 4"' if dashed else ''
    raw=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" preserveAspectRatio="none"><path d="M0 0 L{end}" fill="none" stroke="{color}" stroke-width="{1.4 if dashed else 4}" vector-effect="non-scaling-stroke"{dash}/></svg>'
    return 'data:image/svg+xml;charset=utf-8,'+urlquote(raw,safe='/:')

elements=[]
def box(name,left,width,top,height,fill='transparent',border='transparent'):
    e={'name':name,'type':'rectangle','placement':{'left':left,'right':100-left-width,'top':top,'height':height,'rotation':0},
       'constraint':{'horizontal':'scale','vertical':'top'},
       'config':{'text':{'fixed':''},'color':{'fixed':INK},'size':12,'align':'center','valign':'middle'},
       'background':{'color':{'fixed':fill}},'border':{'color':{'fixed':border},'width':0 if border=='transparent' else .7},'links':[]}
    elements.append(e);return e
def text(name,left,width,top,height,label='',size=12,color=INK,field=None):
    e=box(name,left,width,top,height)
    e['type']='metric-value' if field else 'text'
    e['config'].update(text={'mode':'field','field':field,'fixed':'###'} if field else {'fixed':label},size=size,color={'fixed':color})
    if field and (field.startswith('TENSAO_') or field in ['QTA_PARALELISMO','QTA_ESTADO']):e['config']['color']['field']=field
    return e
def line(x1,y1,x2,y2,field=None,color=INK,width=2,dashed=False):
    vertical=x1==x2
    e=box('Traço fluido '+str(len(elements)),min(x1,x2),0 if vertical else abs(x2-x1),min(y1,y2),abs(y2-y1) if vertical else 10)
    if field:
        suffix='V' if vertical else 'H'
        e['background'].update(image={'mode':'mapping','field':field+'_'+suffix+'_SVG'},size='fill')
    else:
        e['background'].update(image={'fixed':wire_svg(color,vertical,dashed)},size='fill')

# Mapping observed on the supplied DSE7420 status page: 53 channels.
d['templating']['list']=[{'name':'Id_Logsis','type':'constant','hide':2,'query':'id_269086509881540','skipUrlSync':True},{'name':'Divisor_Energia','type':'constant','hide':2,'query':'10','skipUrlSync':True}]
def valid(n):
    c=f'mdb{n}'
    if n>=41:return c+' IN (0,1)'
    # 32-bit measurements must not inherit a blanket 16-bit ceiling.
    if n in list(range(9,25))+list(range(30,40)):
        return c+' NOT IN (-2147483648,2147483647,4294967295)'
    return c+' BETWEEN -32759 AND 32759'
def scaled(n):
    c=f'mdb{n}::numeric'
    div='100' if n==1 or 25<=n<=28 else '10' if n in [5,6,8,29] or 9<=n<=18 or 30<=n<=35 else '1000' if 19<=n<=24 else '3600' if n in [36,39] else '${Divisor_Energia:sqlstring}' if n==37 else '1'
    return c if div=='1' else '('+c+')/NULLIF(('+div+')::numeric,0)'
relevant=list(range(9,15))+list(range(30,36))+[52,53]
amostra='amostra AS (SELECT '+','.join(f'mdb{n}' for n in relevant)+' FROM $Id_Logsis WHERE $__timeFilter("time") AND ('+' OR '.join(f'mdb{n} IS NOT NULL' for n in relevant)+') ORDER BY "time" DESC LIMIT 1)'
select=[]
for n in range(1,54):
    if n in [52,53]:expr=f'(SELECT CASE WHEN mdb{n} IN (0,1) THEN mdb{n} END FROM amostra)'
    else:expr=f'(SELECT {scaled(n)} FROM $Id_Logsis WHERE $__timeFilter("time") AND mdb{n} IS NOT NULL AND '+valid(n)+' ORDER BY "time" DESC LIMIT 1)'
    select.append(expr+f' AS "MDB{n:02}"')
select+=['(SELECT gsm_rssi FROM $Id_Logsis WHERE $__timeFilter("time") AND gsm_rssi IS NOT NULL ORDER BY "time" DESC LIMIT 1) AS "GSM_RSSI"','(SELECT to_char("time",\'DD/MM HH24:MI\') FROM $Id_Logsis WHERE $__timeFilter("time") ORDER BY "time" DESC LIMIT 1) AS "ULTIMA_LEITURA"']
sources=[]
for ns,alias in [(range(30,36),'rede'),(range(9,15),'gmg')]:
    pos=' OR '.join('('+valid(n)+f' AND mdb{n}>0)' for n in ns)
    zero=' AND '.join(f'mdb{n}=0' for n in ns)
    sources.append(f'CASE WHEN {pos} THEN 1 WHEN {zero} THEN 0 ELSE NULL END AS '+alias)
sources+=['CASE WHEN mdb52 IN (0,1) THEN mdb52 END AS k1','CASE WHEN mdb53 IN (0,1) THEN mdb53 END AS k2']
base['targets'][0]['rawSql']='WITH '+amostra+', leituras AS (SELECT '+',\n'.join(select)+'), fontes AS (SELECT '+','.join(sources)+' FROM amostra), ramos AS (SELECT *, CASE WHEN k1=0 OR rede=0 THEN 0 WHEN k1=1 AND rede=1 THEN 1 END AS ramo_rede, CASE WHEN k2=0 OR gmg=0 THEN 0 WHEN k2=1 AND gmg=1 THEN 1 END AS ramo_gmg FROM fontes) SELECT leituras.*,rede AS "TENSAO_REDE_PRESENTE",gmg AS "TENSAO_GMG_PRESENTE",CASE WHEN ramo_rede=1 OR ramo_gmg=1 THEN 1 WHEN ramo_rede=0 AND ramo_gmg=0 THEN 0 END AS "TENSAO_SAIDA_PRESENTE",CASE WHEN k1=1 AND k2=1 THEN 1 WHEN k1 IS NULL OR k2 IS NULL THEN NULL ELSE 0 END AS "QTA_PARALELISMO",CASE WHEN k1=1 AND k2=1 THEN \'ALERTA / AMBOS NA CARGA\' WHEN k1 IS NULL OR k2 IS NULL THEN \'POSIÇÕES INDISPONÍVEIS\' WHEN k1=1 THEN \'REDE NA CARGA\' WHEN k2=1 THEN \'GERADOR NA CARGA\' ELSE \'AMBOS FORA DA CARGA\' END AS "QTA_ESTADO" FROM leituras LEFT JOIN ramos ON TRUE'
base['fieldConfig']['overrides']=[o for o in base['fieldConfig']['overrides'] if not o['matcher']['options'].startswith('MDB') or int(o['matcher']['options'][3:])<=53]
def set_props(field,props):
    o=next((o for o in base['fieldConfig']['overrides'] if o['matcher']['options']==field),None)
    if o is None:o={'matcher':{'id':'byName','options':field},'properties':[]};base['fieldConfig']['overrides'].append(o)
    p={p['id']:p['value'] for p in o['properties']};p.update(props);o['properties']=[{'id':k,'value':v} for k,v in p.items()]
def values_mapping(opts):return [{'type':'value','options':{str(k):{'text':v,'color':c} for k,v,c in opts}},{'type':'special','options':{'match':'null','result':{'text':'###','color':MUTED}}}]
for n in range(40,54):set_props(f'MDB{n:02}',{'unit':'none','decimals':0,'mappings':[]})
set_props('MDB40',{'mappings':values_mapping([(0,'STOP',MUTED),(1,'AUTO',CYAN),(2,'MANUAL',AMBER),(3,'TESTE C/ CARGA',AMBER),(6,'TESTE S/ CARGA',CYAN),(7,'OFF',MUTED)])})
for n in [41,42,43]:set_props(f'MDB{n}',{'mappings':values_mapping([(0,'INATIVO',MUTED),(1,'ATIVO',AMBER)])})
for n in range(44,52):set_props(f'MDB{n}',{'mappings':values_mapping([(0,'OFF',MUTED),(1,'ON',CYAN)])})
for n in [52,53]:set_props(f'MDB{n}',{'mappings':values_mapping([(0,'ABERTO',MUTED),(1,'FECHADO',AMBER)])})
set_props('QTA_ESTADO',{'unit':'none','mappings':values_mapping([(s,s,c) for s,c in [('REDE NA CARGA',CYAN),('GERADOR NA CARGA',AMBER),('AMBOS FORA DA CARGA',MUTED),('POSIÇÕES INDISPONÍVEIS',MUTED),('ALERTA / AMBOS NA CARGA',RED)]])})
def contact_svg(state):
    colour=AMBER if state is not None else MUTED
    body='<circle cx="30" cy="5" r="2.5"/><circle cx="30" cy="39" r="2.5"/>'
    if state==1:body+='<path d="M30 37V7"/>'
    elif state==0:body+='<path d="M30 37L49 12"/>'
    else:body+='<text x="30" y="27" text-anchor="middle" font-family="sans-serif" font-size="19" fill="'+colour+'" stroke="none">?</text>'
    svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 44" preserveAspectRatio="xMidYMid meet" data-state="'+('fechado' if state==1 else 'aberto' if state==0 else 'indisponivel')+'"><g fill="none" stroke="'+colour+'" stroke-width="2.8" stroke-linecap="round">'+body+'</g></svg>'
    return 'data:image/svg+xml;charset=utf-8,'+urlquote(svg,safe='/:')

box('Fundo responsivo',0,100,0,742,BG)
text('Marca responsivo',4,92,10,25,'LOGSIS / DSE7420',17)
text('Disciplina responsivo',4,92,39,17,'UNIFILAR / TENSÃO POR TRECHO',9,MUTED)
text('Fonte rede',4,42,72,19,'CONCESSIONÁRIA',11,CYAN)
text('Fonte GMG',54,42,72,19,'GRUPO GERADOR',11,AMBER)
for name,left,prefix in [('Torre',4,'Rede'),('Gerador',54,'Gerador')]:
    e=box(name+' vetorial',left,42,99,110)
    e['background'].update(image={'fixed':svg_art(prefix)},size='fill')
text('Tensão rede',3,44,214,19,size=11,color=CYAN,field='TENSAO_REDE_PRESENTE')
text('Tensão GMG',53,44,214,19,size=11,color=AMBER,field='TENSAO_GMG_PRESENTE')
box('QTA responsivo',8,84,258,145,SURFACE,'#345064')
for x,field,title,binding,colour in [(25,'MDB52','K1 / REDE','TENSAO_REDE_PRESENTE',CYAN),(75,'MDB53','K2 / GMG','TENSAO_GMG_PRESENTE',AMBER)]:
    box('Contato '+field,x-10,20,275,70,'#111f2d','#6f8b9e')
    text('Título '+field,x-9,18,281,15,title,8.5,MUTED)
    e=box('Posição '+field,x-9,18,303,32)
    e['background'].update(image={'mode':'mapping','field':field+'_CONTATO_SVG'},size='fill')
    line(x,241,x,275,binding,colour)
    line(x,345,x,385,'TENSAO_SAIDA_PRESENTE',INK)
text('Intertravamento legenda',36,28,302,16,'QTA',10,MUTED)
line(35,332,65,332,color='#4e6579',width=.7,dashed=True)
line(25,385,75,385,'TENSAO_SAIDA_PRESENTE')
line(50,385,50,413,'TENSAO_SAIDA_PRESENTE')
box('QGBT responsivo',36,28,414,24,SURFACE,'#7a95a8')
text('QGBT responsivo título',37,26,418,16,'QGBT',10)
line(50,438,50,451,'TENSAO_SAIDA_PRESENTE')
e=box('Edifício vetorial',27,46,452,112)
e['background'].update(image={'fixed':svg_art('Edifício')},size='fill')
text('Edifício legenda',4,92,567,19,'EDIFÍCIO / CARGA',12)
text('Barramento responsivo',4,92,590,18,'SAÍDA INFERIDA',9,MUTED)
text('Tensão barramento',4,92,610,20,size=12,field='TENSAO_SAIDA_PRESENTE')
text('Diagnóstico QTA',4,92,638,18,size=9,color=MUTED,field='QTA_ESTADO')
text('Último registro rótulo',4,92,668,14,'ÚLTIMO REGISTRO NA JANELA',8,MUTED)
text('Último registro valor',4,92,686,19,size=12,field='ULTIMA_LEITURA')
text('Período rótulo',4,92,716,15,'DADOS DO PERÍODO SELECIONADO',8,AMBER)

# Make room for seven compact measurement rows beneath each source.
for element in elements:
    if element['placement']['top']>=241:
        element['placement']['top']+=176
# Background and root height include the added readings.
elements[0]['placement']['height']=918
# Source readings remain attached to their illustration at every screen width.
box('Leituras locais / rede',3,44,240,168,'#0d1a27','#263c4f')
box('Leituras locais / gerador',53,44,240,168,'#0d1a27','#263c4f')
source_rows=[(3,[(30,'L1–N'),(31,'L2–N'),(32,'L3–N'),(33,'L1–L2'),(34,'L2–L3'),(35,'L3–L1'),(29,'Freq.')]),
             (53,[(9,'L1–N'),(10,'L2–N'),(11,'L3–N'),(8,'Freq.'),(7,'Rotação'),(2,'T. água'),(1,'P. óleo')])]
for left,rows in source_rows:
    for row,(n,label) in enumerate(rows):
        top=249+row*22
        e=text('Fonte rótulo MDB'+f'{n:02}',left+2,13,top,20,label,9,MUTED);e['config']['align']='left'
        e=text('Fonte leitura MDB'+f'{n:02}',left+15,27,top,20,size=12,field=f'MDB{n:02}');e['config']['align']='right'

# Compact equipment badges stay inside the same responsive diagram.
for element in elements:
    if element['placement']['top']>=72:element['placement']['top']+=48
elements[0]['placement']['height']=966

def radio_icon(kind,colour):
    paths='<path d="M3 8 Q12 0 21 8 M6 12 Q12 6 18 12 M9 16 Q12 13 15 16"/><circle cx="12" cy="20" r="1"/>' if kind=='wifi' else '<path d="M12 21 V11 M7 21 H17 M8 11 L12 6 L16 11 M5 5 Q0 10 5 15 M19 5 Q24 10 19 15"/>'
    svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" preserveAspectRatio="xMidYMid meet"><g fill="none" stroke="'+colour+'" stroke-width="1.7" stroke-linecap="round">'+paths+'</g></svg>'
    return 'data:image/svg+xml;charset=utf-8,'+urlquote(svg,safe='/:')
for left,kind,title,field in [(3,'wifi','WI-FI / RSSI','WIFI_LOCAL'),(35,'gsm','GSM / RSSI','GSM_LOCAL')]:
    box('Conexão '+kind,left,30,64,40,'#101e2c','#263c4f')
    text('Conexão título '+kind,left+1,28,67,12,title,8,MUTED)
    e=box('Conexão ícone '+kind,left+(1 if kind=='gsm' else 2),7 if kind=='gsm' else 5,82,17)
    e['background'].update(image={'mode':'mapping','field':field+'_ICONE'},size='fill')
    text('Conexão sinal '+kind,left+8,21,82,18,size=10,field=field)
box('Modo do gerador',67,30,64,40,'#101e2c','#263c4f')
text('Modo rótulo',68,28,67,12,'MODO / GMG',8,MUTED)
e=text('Modo sinalização',69,26,81,20,size=10,field='MODO_LOCAL')
e['config']['color']={'field':'MODO_LOCAL','fixed':MUTED}

overview=copy.deepcopy(base)
overview.update(id=1,title='Unifilar / Rede, transferência e carga',gridPos={'x':0,'y':0,'w':24,'h':27})
overview['options']['root'].update(name='Unifilar único com largura responsiva',elements=elements,connections=[],placement={'left':0,'top':0,'width':360,'height':966})
overview['options'].update(panZoom=False,infinitePan=False,inlineEditing=False)
overview['description']='Ajuste automático de largura. Vermelho indica tensão; saída inferida por tensões das fontes e K1/K2. SEM DADOS não equivale a tensão zero. Consulte os horários e o período selecionado.'
def sqlquote(s):return "'"+s.replace("'","''")+"'"
wire_fields=[]
for field,colour,vertical in [('TENSAO_REDE_PRESENTE',CYAN,True),('TENSAO_GMG_PRESENTE',AMBER,True),('TENSAO_SAIDA_PRESENTE',INK,True),('TENSAO_SAIDA_PRESENTE',INK,False)]:
    alias=field+('_V_SVG' if vertical else '_H_SVG')
    wire_fields.append('CASE WHEN origem."'+field+'"=1 THEN '+sqlquote(wire_svg('#f2495c',vertical))+' ELSE '+sqlquote(wire_svg(colour,vertical))+' END AS "'+alias+'"')
overview['targets'][0]['rawSql']='WITH origem AS (\n'+base['targets'][0]['rawSql'].rstrip().rstrip(';')+'\n) SELECT origem.*,\n'+',\n'.join(wire_fields)+'\nFROM origem'

# Wi-Fi remains optional. Mode and GSM share the existing per-field readings,
# so sparse telemetry rows cannot erase the latest reading inside the period.
d['templating']['list'] += [
    {'name':'Campo_WiFi_RSSI','type':'constant','hide':2,'query':'WiFi_rssi','skipUrlSync':True},
    {'name':'Formato_GSM','type':'constant','hide':2,'query':'dbm','skipUrlSync':True}]
prior=overview['targets'][0]['rawSql']
key='${Campo_WiFi_RSSI:sqlstring}'
wifi='COALESCE(j->>'+key+', j->>lower('+key+'))'
gsm='dados."GSM_RSSI"::text'
parsed=[]
for alias,expr in [('wifi',wifi),('gsm',gsm)]:
    parsed.append("CASE WHEN ("+expr+") ~ '^-?[0-9]+([.][0-9]+)?$' THEN ("+expr+")::numeric ELSE NULL END AS "+alias)
normalizer="CASE WHEN ${Formato_GSM:sqlstring}='csq' THEN CASE WHEN gsm BETWEEN 0 AND 31 AND gsm=trunc(gsm) THEN -113+2*gsm ELSE NULL END WHEN ${Formato_GSM:sqlstring}='dbm' THEN CASE WHEN gsm BETWEEN -140 AND -1 THEN gsm ELSE NULL END ELSE NULL END"

def signal_bars(level):
    colour=AMBER if level<=2 else CYAN
    rects=''.join('<rect x="'+str(1+i*5)+'" y="'+str(23-(5+i*4))+'" width="3" height="'+str(5+i*4)+'" rx="0.7" fill="'+(colour if i<level else '#304354')+'"/>' for i in range(5))
    svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 26 24" preserveAspectRatio="xMidYMid meet">'+rects+'</svg>'
    return 'data:image/svg+xml;charset=utf-8,'+urlquote(svg,safe='/:')
wifi_valid='CASE WHEN wifi>-32760 AND wifi<32760 THEN wifi ELSE NULL END'
bars='CASE WHEN gsm_dbm IS NULL THEN '+sqlquote(radio_icon('gsm',MUTED))
for threshold,level in [(-80,5),(-90,4),(-100,3),(-110,2)]:
    bars+=' WHEN gsm_dbm>='+str(threshold)+' THEN '+sqlquote(signal_bars(level))
bars+=' ELSE '+sqlquote(signal_bars(1))+' END'
extra=[wifi_valid+' AS "WIFI_LOCAL"',
       'CASE WHEN '+wifi_valid+' IS NULL THEN '+sqlquote(radio_icon('wifi',MUTED))+' ELSE '+sqlquote(radio_icon('wifi',CYAN))+' END AS "WIFI_LOCAL_ICONE"',
       'gsm_dbm AS "GSM_LOCAL"','gsm AS "GSM_BRUTO"',bars+' AS "GSM_LOCAL_ICONE"',
       "CASE WHEN dados.\"MDB40\"=0 THEN 'STOP' WHEN dados.\"MDB40\"=1 THEN 'AUTO' WHEN dados.\"MDB40\"=2 THEN 'MANUAL' WHEN dados.\"MDB40\"=3 THEN 'TESTE C/ CARGA' WHEN dados.\"MDB40\"=6 THEN 'TESTE S/ CARGA' WHEN dados.\"MDB40\"=7 THEN 'OFF' WHEN dados.\"MDB40\" IS NULL THEN 'SEM DADOS' ELSE 'INVÁLIDO' END AS \"MODO_LOCAL\""]
for field in ['MDB52','MDB53']:
    extra.append('CASE dados.\"'+field+'\" WHEN 0 THEN '+sqlquote(contact_svg(0))+' WHEN 1 THEN '+sqlquote(contact_svg(1))+' ELSE '+sqlquote(contact_svg(None))+' END AS \"'+field+'_CONTATO_SVG\"')
overview['targets'][0]['rawSql']='WITH dados AS (\n'+prior+'\n), telemetria AS (SELECT to_jsonb(t) AS j FROM $Id_Logsis t WHERE $__timeFilter("time") ORDER BY "time" DESC LIMIT 1), bruto AS (SELECT COALESCE((SELECT j FROM telemetria),\'{}\'::jsonb) AS j), sinais AS (SELECT '+', '.join(parsed)+' FROM bruto CROSS JOIN dados), normalizados AS (SELECT sinais.*, '+normalizer+' AS gsm_dbm FROM sinais) SELECT dados.*, '+', '.join(extra)+' FROM dados CROSS JOIN normalizados'
for field in ['WIFI_LOCAL','GSM_LOCAL']:
    overview['fieldConfig']['overrides'].append({'matcher':{'id':'byName','options':field},'properties':[{'id':'unit','value':'suffix: dBm' if field=='GSM_LOCAL' else 'none'},{'id':'decimals','value':0},{'id':'mappings','value':[{'type':'special','options':{'match':'null','result':{'text':'—','color':MUTED}}}]}]})
overview['fieldConfig']['overrides'].append({'matcher':{'id':'byName','options':'MODO_LOCAL'},'properties':[{'id':'unit','value':'none'},{'id':'mappings','value':[{'type':'value','options':{v:{'text':v,'color':c} for v,c in [('AUTO',CYAN),('MANUAL',AMBER),('TESTE C/ CARGA',AMBER),('TESTE S/ CARGA',CYAN),('OFF',MUTED),('STOP',MUTED),('SEM DADOS',MUTED),('INVÁLIDO',AMBER)]}}]}]})

# One query drives every reading panel; grouping is visual, not another plant.
labels={e['name'].split('MDB')[-1]:e['config']['text']['fixed'] for e in instrument['options']['root']['elements'] if e['name'].startswith('Rótulo MDB')}
labels.update({'23':'Potência aparente','22':'Potência ativa total','24':'Potência reativa','37':'Energia acumulada','38':'Número de partidas','39':'Até manutenção','40':'Modo operação','41':'Warning','42':'Trip elétrico','43':'Shutdown','52':'K1 / Rede','53':'K2 / Gerador'})
short={8:'Frequência',9:'L1–N',10:'L2–N',11:'L3–N',12:'L1–L2',13:'L2–L3',14:'L3–L1',15:'Corrente L1',16:'Corrente L2',17:'Corrente L3',18:'Corrente terra',25:'FP / L1',26:'FP / L2',27:'FP / L3',28:'FP médio',29:'Frequência',30:'L1–N',31:'L2–N',32:'L3–N',33:'L1–L2',34:'L2–L3',35:'L3–L1'}
short.update({15:'I L1',16:'I L2',17:'I L3',18:'I terra',19:'L1',20:'L2',21:'L3',22:'Ativa',23:'Aparente',24:'Reativa'})
for n in range(44,52):labels[f'{n:02}']='Entrada '+chr(65+n-44)
units={o['matcher']['options']:next((p['value'].split('suffix:',1)[1].strip() for p in o['properties'] if p['id']=='unit' and p['value'].startswith('suffix:')),'') for o in base['fieldConfig']['overrides']}
overview['gridPos'].update(w=12)
overview['title']='01 / Unifilar da instalação'
panels=[overview]
registry=[]

def reading_group(id,title,ns,x,y,w,h,accent,cols=2,order=None,note=''):
    global elements
    saved=elements;elements=[]
    height=h*38-44
    box(title+' / fundo',0,100,0,height,BG)
    line(0,3,100,3,color=accent)
    # Every cell has a stable label/value hierarchy and percentage-based columns.
    slots=order or [(n,1) for n in ns]
    cursor=0;positions=[]
    for n,span in slots:
        if cursor%cols+span>cols:cursor+=cols-cursor%cols
        positions.append((n,cursor//cols,cursor%cols,span));cursor+=span
    rows=(cursor+cols-1)//cols
    stride=(height-18-(20 if note else 0))/rows
    for n,row,col,span in positions:
        field=f'MDB{n:02}'
        left=2+col*96/cols;width=span*96/cols-2
        top=12+row*stride;cardh=stride-7
        box('Cartão '+field,left,width,top,cardh,'#101e2c','#263c4f')
        label=short.get(n,labels[f'{n:02}'])
        if cols==3 and units[field]:label+=' · '+units[field]
        e=text('Rótulo '+field,left+2,width-4,top+7,18,label,10,MUTED)
        e['config']['align']='left'
        e=text('Leitura '+field,left+2,width-4,top+30,32,size=18 if cols==3 else (16 if n==37 else 20),color=INK,field=field)
        e['config']['align']='left'
        e=text('Canal '+field,left+2,width-4,top+cardh-16,12,field,8,'#7891a7');e['config']['align']='left'
        registry.append(n)
    if note:text('Nota '+title,2,96,height-18,16,note,8,MUTED)
    cfg=copy.deepcopy(base['fieldConfig'])
    for override in cfg['overrides']:
        f=override['matcher']['options']
        if cols==3 and f in [f'MDB{n:02}' for n in ns]:
            for prop in override['properties']:
                if prop['id']=='unit':prop['value']='none'
        if f in ['MDB52','MDB53']:
            for prop in override['properties']:
                if prop['id']=='mappings':prop['value']=[{'type':'value','options':{'0':{'text':'ABERTO','color':MUTED},'1':{'text':'FECHADO','color':CYAN}}}]
    p={'id':id,'type':'canvas','title':title,'gridPos':{'x':x,'y':y,'w':w,'h':h},'transparent':False,
       'datasource':{'type':'datasource','uid':'-- Dashboard --'},'targets':[{'refId':'A','panelId':1,'withTransforms':False}],
       'fieldConfig':cfg,'options':{'inlineEditing':False,'panZoom':False,'infinitePan':False,
       'root':{'name':title,'type':'frame','placement':{'left':0,'top':0,'width':600,'height':height},'elements':elements,'connections':[]}}}
    panels.append(p);elements=saved

reading_group(21,'02 / Gerador · tensão e corrente',list(range(8,19)),12,0,12,16,AMBER,3,order=[(n,1) for n in [9,10,11,12,13,14,15,16,17]]+[(8,2),(18,1)])
for j,(field,title,colour) in enumerate([('MDB22','POTÊNCIA ATIVA / GERADOR',AMBER),('MDB28','FATOR DE POTÊNCIA / GMG',CYAN),('MDB36','HORÍMETRO / ACUMULADO',INK),('MDB37','ENERGIA / ACUMULADA',INK)]):
    cfg=copy.deepcopy(base['fieldConfig']);cfg['defaults']['color']={'mode':'fixed','fixedColor':colour}
    panels.append({'id':10+j,'type':'stat','title':title,'gridPos':{'x':j*6,'y':27,'w':6,'h':3},'transparent':False,
        'datasource':{'type':'datasource','uid':'-- Dashboard --'},'targets':[{'refId':'A','panelId':1,'withTransforms':False}],
        'transformations':[{'id':'filterFieldsByName','options':{'include':{'names':[field]}}}],
        'fieldConfig':cfg,'options':{'reduceOptions':{'calcs':['lastNotNull'],'fields':'','values':False},'orientation':'auto','textMode':'value','colorMode':'value','graphMode':'none','justifyMode':'center','wideLayout':True,'text':{'valueSize':26,'titleSize':11}}})
reading_group(22,'04 / Gerador · potências e FP',list(range(19,29)),0,30,12,12,AMBER,3,order=[(n,1) for n in [19,20,21,22,23,24,25,26,27]]+[(28,3)])
reading_group(23,'03 / Motor e combustível',list(range(1,8)),12,16,12,11,'#66c9b3',order=[(n,1) for n in range(1,7)]+[(7,2)])
reading_group(24,'05 / Operação e manutenção',list(range(36,40)),12,30,12,12,CYAN,order=[(37,2),(36,1),(39,1),(38,2)])
reading_group(25,'06 / Controle, alarmes e QTA',[40,41,42,43,52,53],0,42,12,12,'#c7a5e8',note='Alarmes: códigos do controlador.')
reading_group(26,'07 / Entradas digitais',list(range(44,52)),12,42,12,12,'#8fa9c2',note='Códigos brutos / polaridade do controlador.')
assert sorted(registry+list(range(29,36)))==list(range(1,54)), 'All 53 channels must belong to exactly one reading group'
# Original history panel identities are retained; alarm and transfer fields are corrected.
import re
for p in history['panels']:
    if p.get('type')!='timeseries':continue
    if p['id']==1012:
        p['title']='CHAVE / REDE E GERADOR NA CARGA'
        p['targets']=[{'refId':'A','format':'time_series','rawQuery':True,'editorMode':'code','rawSql':'SELECT "time",CASE WHEN mdb52 IN (0,1) THEN mdb52 END AS "Rede na carga",CASE WHEN mdb53 IN (0,1) THEN mdb53 END AS "Gerador na carga" FROM $Id_Logsis WHERE $__timeFilter("time") ORDER BY "time"'}]
        p['fieldConfig']['defaults'].setdefault('custom',{}).update(lineInterpolation='stepAfter',spanNulls=False)
        continue
    for t in p.get('targets',[]):
        raw=t.get('rawSql','');match=re.search(r'mdb(\d+)',raw,re.I)
        if not match:continue
        n={1009:41,1010:42,1011:43}.get(p['id'],int(match[1]))
        aliases=re.findall(r'AS\s+"([^"]+)"',raw,re.I);label=aliases[-1] if aliases else p['title']
        label='L3 - L1' if n in [14,35] else label
        t['rawSql']='SELECT "time" AS "time",CASE WHEN '+valid(n)+' THEN '+scaled(n)+' ELSE NULL END AS "'+label.replace('"','""')+'" FROM $Id_Logsis WHERE $__timeFilter("time") ORDER BY "time"'
offset=54-history['gridPos']['y'];history['gridPos']['y']=54
for p in history['panels']:p['gridPos']['y']+=offset
panels.append(history)
d['panels']=sorted(panels,key=lambda p:(p['gridPos']['y'],p['gridPos']['x']))
d.update(title='LOGSIS / DSE7420 — V34 Supervisão',uid=source['uid'],id=None,version=1,
    tags=['LOGSIS','DSE7420','V34','responsivo'],description='Uma planta, um dashboard. Unifilar e instrumentação organizados por subsistema; largura ajustável e reorganização nativa no celular. Saída inferida.')
d['links']=[]
d['refresh']='5s'
d.setdefault('timepicker',{})['refresh_intervals']=['5s','10s','30s','1m','5m']
out=ROOT/'dist/V34_IMPORTAR.json';out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(d,ensure_ascii=True,separators=(',',':'),allow_nan=False)+'\n',encoding='ascii')
with zipfile.ZipFile(ROOT/'dist/V34_IMPORTAR.zip','w',zipfile.ZIP_DEFLATED) as z:z.write(out,out.name)
print('V34: dashboard único, 6 grupos + leituras da rede no unifilar, 53 canais, uma consulta compartilhada')
