"""Mobile view: fluid native Canvas paths, embedded vector artwork and native data panels."""
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
    e=box('Traço móvel '+str(len(elements)),min(x1,x2),0 if vertical else abs(x2-x1),min(y1,y2),abs(y2-y1) if vertical else 10)
    if field:
        suffix='V' if vertical else 'H'
        e['background'].update(image={'mode':'mapping','field':field+'_'+suffix+'_SVG'},size='fill')
    else:
        e['background'].update(image={'fixed':wire_svg(color,vertical,dashed)},size='fill')

box('Fundo mobile',0,100,0,742,BG)
text('Marca mobile',4,92,10,25,'LOGSIS / DSE7420',17)
text('Disciplina mobile',4,92,39,17,'UNIFILAR / TENSÃO POR TRECHO',9,MUTED)
text('Fonte rede',4,42,72,19,'CONCESSIONÁRIA',11,CYAN)
text('Fonte GMG',54,42,72,19,'GRUPO GERADOR',11,AMBER)
for name,left,prefix in [('Torre',4,'Rede'),('Gerador',54,'Gerador')]:
    e=box(name+' vetorial',left,42,99,110)
    e['background'].update(image={'fixed':svg_art(prefix)},size='fill')
text('Tensão rede',3,44,214,19,size=11,color=CYAN,field='TENSAO_REDE_PRESENTE')
text('Tensão GMG',53,44,214,19,size=11,color=AMBER,field='TENSAO_GMG_PRESENTE')
box('QTA mobile',8,84,258,145,SURFACE,'#345064')
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
box('QGBT mobile',36,28,414,24,SURFACE,'#7a95a8')
text('QGBT mobile título',37,26,418,16,'QGBT',10)
line(50,438,50,451,'TENSAO_SAIDA_PRESENTE')
e=box('Edifício vetorial',27,46,452,112)
e['background'].update(image={'fixed':svg_art('Edifício')},size='fill')
text('Edifício legenda',4,92,567,19,'EDIFÍCIO / CARGA',12)
text('Barramento mobile',4,92,590,18,'SAÍDA INFERIDA',9,MUTED)
text('Tensão barramento',4,92,610,20,size=12,field='TENSAO_SAIDA_PRESENTE')
text('Diagnóstico QTA',4,92,638,18,size=9,color=MUTED,field='QTA_PARALELISMO')
text('Último registro rótulo',4,92,668,14,'ÚLTIMO REGISTRO NA JANELA',8,MUTED)
text('Último registro valor',4,92,686,19,size=12,field='ULTIMA_LEITURA')
text('Período rótulo',4,92,716,15,'DADOS DO PERÍODO SELECIONADO',8,AMBER)

overview=copy.deepcopy(base)
overview.update(id=1,title='Unifilar / Mobile',gridPos={'x':0,'y':0,'w':24,'h':21})
overview['options']['root'].update(name='Unifilar fluido para celular',elements=elements,connections=[],placement={'left':0,'top':0,'width':360,'height':742})
overview['options'].update(panZoom=False,infinitePan=False,inlineEditing=False)
overview['description']='Ajuste automático de largura. Vermelho indica tensão; saída inferida por tensões das fontes e K1/K2. SEM DADOS não equivale a tensão zero. Consulte os horários e o período selecionado.'
def sqlquote(s):return "'"+s.replace("'","''")+"'"
wire_fields=[]
for field,colour,vertical in [('TENSAO_REDE_PRESENTE',CYAN,True),('TENSAO_GMG_PRESENTE',AMBER,True),('TENSAO_SAIDA_PRESENTE',INK,True),('TENSAO_SAIDA_PRESENTE',INK,False)]:
    alias=field+('_V_SVG' if vertical else '_H_SVG')
    wire_fields.append('CASE WHEN origem."'+field+'"=1 THEN '+sqlquote(wire_svg('#f2495c',vertical))+' ELSE '+sqlquote(wire_svg(colour,vertical))+' END AS "'+alias+'"')
overview['targets'][0]['rawSql']='WITH origem AS (\n'+base['targets'][0]['rawSql'].rstrip().rstrip(';')+'\n) SELECT origem.*,\n'+',\n'.join(wire_fields)+'\nFROM origem'

# Native Stat panels handle mobile typography and Grafana's responsive panel layout.
panels=[overview]
for j,(field,title) in enumerate([('MDB22','Potência total do gerador'),('MDB28','Fator de potência médio'),('MDB36','Horímetro'),('MDB37','Energia acumulada')]):
    panels.append({'id':10+j,'type':'stat','title':title,'gridPos':{'x':j*6,'y':21,'w':6,'h':4},'transparent':True,
        'datasource':{'type':'datasource','uid':'-- Dashboard --'},'targets':[{'refId':'A','panelId':1,'withTransforms':False}],
        'transformations':[{'id':'filterFieldsByName','options':{'include':{'names':[field]}}}],
        'fieldConfig':copy.deepcopy(base['fieldConfig']),
        'options':{'reduceOptions':{'calcs':['lastNotNull'],'fields':'','values':False},'orientation':'auto','textMode':'value','colorMode':'none','graphMode':'none','justifyMode':'center','wideLayout':True}})

# Compact two-column table: same measured fields and scales, with literal units.
labels={e['name'].split('MDB')[-1]:e['config']['text']['fixed'] for e in instrument['options']['root']['elements'] if e['name'].startswith('Rótulo MDB')}
props={o['matcher']['options']:{p['id']:p['value'] for p in o['properties']} for o in base['fieldConfig']['overrides']}
def quote(s):return "'"+s.replace("'","''")+"'"
rows=[]
short_labels={9:'GMG L1–N',10:'GMG L2–N',11:'GMG L3–N',12:'GMG L1–L2',13:'GMG L2–L3',14:'GMG L3–L1',
              18:'Corrente terra',25:'FP GMG L1',26:'FP GMG L2',27:'FP GMG L3',28:'FP médio GMG',
              30:'Rede L1–N',31:'Rede L2–N',32:'Rede L3–N',33:'Rede L1–L2',34:'Rede L2–L3',35:'Rede L3–L1',
              39:'Até manutenção',40:'Manutenção 1',41:'Manutenção 2',42:'Manutenção 3'}
for n in range(1,57):
    field=f'MDB{n:02}';cfg=props[field];dec=cfg.get('decimals',0)
    unit=cfg.get('unit','none');unit=unit.split('suffix:',1)[1].strip() if unit.startswith('suffix:') else ''
    display=f'ROUND(dados."{field}"::numeric,{dec})::text'+(' || '+quote(' '+unit) if unit else '')
    if n==43:display=f'CASE dados."{field}" WHEN 0 THEN \'STOP\' WHEN 1 THEN \'MANUAL\' WHEN 2 THEN \'AUTO\' ELSE dados."{field}"::text END'
    if n in [55,56]:display=f'CASE dados."{field}" WHEN 0 THEN \'ABERTO\' WHEN 1 THEN \'FECHADO\' ELSE NULL END'
    label=f'{n:02} · '+short_labels.get(n,labels[f'{n:02}'])
    rows.append(f'({n}, {quote(label)}, COALESCE({display}, \'###\'))')
raw=base['targets'][0]['rawSql'].rstrip().rstrip(';')
target=copy.deepcopy(base['targets'][0]);target['rawSql']='WITH dados AS (\n'+raw+'\n) SELECT lista.medicao AS "Medição", lista.leitura AS "Leitura" FROM dados CROSS JOIN LATERAL (VALUES\n'+',\n'.join(rows)+'\n) lista(ordem, medicao, leitura) ORDER BY lista.ordem'
table={'id':2,'type':'table','title':'Instrumentação completa / 56 canais','gridPos':{'x':0,'y':25,'w':24,'h':58},
       'transparent':True,'datasource':copy.deepcopy(base['datasource']),'targets':[target],
       'fieldConfig':{'defaults':{'custom':{'align':'left','cellOptions':{'type':'auto'},'inspect':False},'noValue':'###'},
                      'overrides':[{'matcher':{'id':'byName','options':'Leitura'},'properties':[{'id':'custom.width','value':110},{'id':'custom.align','value':'right'}]}]},
       'options':{'showHeader':True,'cellHeight':'sm','footer':{'show':False},'sortBy':[]}}
panels.append(table)
offset=83-history['gridPos']['y'];history['gridPos']['y']=83
for p in history['panels']:p['gridPos']['y']+=offset
panels.append(history)
d['panels']=panels
d.update(title='LOGSIS / DSE7420 — V27 Mobile',uid='logsis-dse7420-v27-mobile',id=None,version=1,
         tags=['LOGSIS','DSE7420','V27','mobile'],description='Visão para smartphone com ajuste de largura, unifilar compacto, indicadores nativos e 56 leituras. Mesma lógica de tensão da V26; saída inferida.')
d['links']=[{'title':'Visão desktop','type':'link','url':'/d/logsis-dse7420-v26-unifilar/','icon':'dashboard','includeVars':True,'keepTime':True,'targetBlank':False}]
out=ROOT/'dist/V27_MOBILE_IMPORTAR.json';out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(d,ensure_ascii=True,separators=(',',':'),allow_nan=False)+'\n',encoding='ascii')
with zipfile.ZipFile(ROOT/'dist/V27_MOBILE_IMPORTAR.zip','w',zipfile.ZIP_DEFLATED) as z:z.write(out,out.name)
shortcut=copy.deepcopy(source)
shortcut.setdefault('links',[]).append({'title':'Visão Mobile','type':'link','url':'/d/logsis-dse7420-v27-mobile/','icon':'mobile-android','includeVars':True,'keepTime':True,'targetBlank':False})
shortcut['id']=None
shortcut_path=ROOT/'dist/V26_DESKTOP_COM_ATALHO_MOBILE.json'
shortcut_path.write_text(json.dumps(shortcut,ensure_ascii=True,separators=(',',':'),allow_nan=False)+'\n',encoding='ascii')
with zipfile.ZipFile(ROOT/'dist/V26_ATALHO_MOBILE.zip','w',zipfile.ZIP_DEFLATED) as z:z.write(shortcut_path,shortcut_path.name)
print(out)
print('Elementos fluidos:',len(elements),'Indicadores nativos:',4,'Leituras:',56)
