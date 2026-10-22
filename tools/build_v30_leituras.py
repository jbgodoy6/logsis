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
    if field and (field.startswith('TENSAO_') or field=='QTA_PARALELISMO'):e['config']['color']['field']=field
    return e
def line(x1,y1,x2,y2,field=None,color=INK,width=2,dashed=False):
    vertical=x1==x2
    e=box('Traço fluido '+str(len(elements)),min(x1,x2),0 if vertical else abs(x2-x1),min(y1,y2),abs(y2-y1) if vertical else 10)
    if field:
        suffix='V' if vertical else 'H'
        e['background'].update(image={'mode':'mapping','field':field+'_'+suffix+'_SVG'},size='fill')
    else:
        e['background'].update(image={'fixed':wire_svg(color,vertical,dashed)},size='fill')

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
for x,field,title,binding,colour in [(25,'MDB55','K1 / REDE','TENSAO_REDE_PRESENTE',CYAN),(75,'MDB56','K2 / GMG','TENSAO_GMG_PRESENTE',AMBER)]:
    box('Contato '+field,x-10,20,275,70,'#111f2d','#6f8b9e')
    text('Título '+field,x-9,18,281,15,title,8.5,MUTED)
    text('Posição '+field,x-9,18,303,32,size=24,color=AMBER,field=field)
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
text('Diagnóstico QTA',4,92,638,18,size=9,color=MUTED,field='QTA_PARALELISMO')
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

overview=copy.deepcopy(base)
overview.update(id=1,title='Unifilar / Rede, transferência e carga',gridPos={'x':0,'y':0,'w':24,'h':26})
overview['options']['root'].update(name='Unifilar único com largura responsiva',elements=elements,connections=[],placement={'left':0,'top':0,'width':360,'height':918})
overview['options'].update(panZoom=False,infinitePan=False,inlineEditing=False)
overview['description']='Ajuste automático de largura. Vermelho indica tensão; saída inferida por tensões das fontes e K1/K2. SEM DADOS não equivale a tensão zero. Consulte os horários e o período selecionado.'
def sqlquote(s):return "'"+s.replace("'","''")+"'"
wire_fields=[]
for field,colour,vertical in [('TENSAO_REDE_PRESENTE',CYAN,True),('TENSAO_GMG_PRESENTE',AMBER,True),('TENSAO_SAIDA_PRESENTE',INK,True),('TENSAO_SAIDA_PRESENTE',INK,False)]:
    alias=field+('_V_SVG' if vertical else '_H_SVG')
    wire_fields.append('CASE WHEN origem."'+field+'"=1 THEN '+sqlquote(wire_svg('#f2495c',vertical))+' ELSE '+sqlquote(wire_svg(colour,vertical))+' END AS "'+alias+'"')
overview['targets'][0]['rawSql']='WITH origem AS (\n'+base['targets'][0]['rawSql'].rstrip().rstrip(';')+'\n) SELECT origem.*,\n'+',\n'.join(wire_fields)+'\nFROM origem'

# One query drives every reading panel; grouping is visual, not another plant.
labels={e['name'].split('MDB')[-1]:e['config']['text']['fixed'] for e in instrument['options']['root']['elements'] if e['name'].startswith('Rótulo MDB')}
labels.update({'23':'Potência aparente','22':'Potência ativa total','24':'Potência reativa','37':'Energia acumulada','38':'Número de partidas','39':'Até manutenção','40':'Manutenção 1','41':'Manutenção 2','42':'Manutenção 3','55':'K1 / Rede','56':'K2 / Gerador'})
short={8:'Frequência',9:'L1–N',10:'L2–N',11:'L3–N',12:'L1–L2',13:'L2–L3',14:'L3–L1',15:'Corrente L1',16:'Corrente L2',17:'Corrente L3',18:'Corrente terra',25:'FP / L1',26:'FP / L2',27:'FP / L3',28:'FP médio',29:'Frequência',30:'L1–N',31:'L2–N',32:'L3–N',33:'L1–L2',34:'L2–L3',35:'L3–L1'}
short.update({15:'I L1',16:'I L2',17:'I L3',18:'I terra',19:'L1',20:'L2',21:'L3',22:'Ativa',23:'Aparente',24:'Reativa'})
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
        if f in ['MDB55','MDB56']:
            for prop in override['properties']:
                if prop['id']=='mappings':prop['value']=[{'type':'value','options':{'0':{'text':'ABERTO','color':MUTED},'1':{'text':'FECHADO','color':CYAN}}}]
    p={'id':id,'type':'canvas','title':title,'gridPos':{'x':x,'y':y,'w':w,'h':h},'transparent':False,
       'datasource':{'type':'datasource','uid':'-- Dashboard --'},'targets':[{'refId':'A','panelId':1,'withTransforms':False}],
       'fieldConfig':cfg,'options':{'inlineEditing':False,'panZoom':False,'infinitePan':False,
       'root':{'name':title,'type':'frame','placement':{'left':0,'top':0,'width':600,'height':height},'elements':elements,'connections':[]}}}
    panels.append(p);elements=saved

reading_group(20,'02 / Rede · tensão e frequência',[30,31,32,33,34,35,29],12,0,12,11,CYAN,3,order=[(n,1) for n in [30,31,32,33,34,35]]+[(29,3)])
reading_group(21,'03 / Gerador · tensão e corrente',list(range(8,19)),12,11,12,15,AMBER,3,order=[(n,1) for n in [9,10,11,12,13,14,15,16,17]]+[(8,2),(18,1)])
for j,(field,title,colour) in enumerate([('MDB22','POTÊNCIA ATIVA / GERADOR',AMBER),('MDB28','FATOR DE POTÊNCIA / GMG',CYAN),('MDB36','HORÍMETRO / ACUMULADO',INK),('MDB37','ENERGIA / ACUMULADA',INK)]):
    cfg=copy.deepcopy(base['fieldConfig']);cfg['defaults']['color']={'mode':'fixed','fixedColor':colour}
    panels.append({'id':10+j,'type':'stat','title':title,'gridPos':{'x':j*6,'y':26,'w':6,'h':3},'transparent':False,
        'datasource':{'type':'datasource','uid':'-- Dashboard --'},'targets':[{'refId':'A','panelId':1,'withTransforms':False}],
        'transformations':[{'id':'filterFieldsByName','options':{'include':{'names':[field]}}}],
        'fieldConfig':cfg,'options':{'reduceOptions':{'calcs':['lastNotNull'],'fields':'','values':False},'orientation':'auto','textMode':'value','colorMode':'value','graphMode':'none','justifyMode':'center','wideLayout':True,'text':{'valueSize':26,'titleSize':11}}})
reading_group(22,'04 / Gerador · potências e FP',list(range(19,29)),0,29,12,12,AMBER,3,order=[(n,1) for n in [19,20,21,22,23,24,25,26,27]]+[(28,3)])
reading_group(23,'05 / Motor e combustível',list(range(1,8)),12,29,12,12,'#66c9b3',order=[(n,1) for n in range(1,7)]+[(7,2)])
reading_group(24,'06 / Operação e manutenção',list(range(36,43)),0,41,8,12,CYAN,order=[(37,2),(36,1),(38,1),(39,1),(40,1),(41,1),(42,1)])
reading_group(25,'07 / Controle, alarmes e QTA',[43,44,45,46,55,56],8,41,8,12,'#c7a5e8',note='Alarmes: códigos do controlador.')
reading_group(26,'08 / Entradas digitais',list(range(47,55)),16,41,8,12,'#8fa9c2',note='Códigos brutos / polaridade do controlador.')
assert sorted(registry)==list(range(1,57)), 'All 56 channels must belong to exactly one reading group'
offset=53-history['gridPos']['y'];history['gridPos']['y']=53
for p in history['panels']:p['gridPos']['y']+=offset
panels.append(history)
d['panels']=panels
d.update(title='LOGSIS / DSE7420 — V30 Supervisão',uid=source['uid'],id=None,version=1,
    tags=['LOGSIS','DSE7420','V30','responsivo'],description='Uma planta, um dashboard. Unifilar e instrumentação organizados por subsistema; largura ajustável e reorganização nativa no celular. Saída inferida.')
d['links']=[]
out=ROOT/'dist/V30_IMPORTAR.json';out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(d,ensure_ascii=True,separators=(',',':'),allow_nan=False)+'\n',encoding='ascii')
with zipfile.ZipFile(ROOT/'dist/V30_IMPORTAR.zip','w',zipfile.ZIP_DEFLATED) as z:z.write(out,out.name)
print('V30: dashboard único, 7 grupos, 56 canais, uma consulta compartilhada')
