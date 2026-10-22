"""Symmetric transfer contacts and data-driven voltage colours."""
import copy
import json
import math
import pathlib
import zipfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
source=json.loads((ROOT/'V25_IMPORTAR.json').read_text())
d=copy.deepcopy(source)
panel,instrument,history=d['panels']
old=json.loads((ROOT/'V24_IMPORTAR.json').read_text())['panels'][0]['options']['root']['elements']
BG,SURFACE='#080f19','#0e1a27'
INK,MUTED,CYAN,AMBER,STEEL,DIM='#e5eef7','#96aec4','#67cce4','#e9bd79','#9bb0bf','#4e6579'
elements=[]
anchors={}

def shape(name,x,y,w,h,fill='transparent',stroke='transparent',kind='rectangle',border=1):
    e={'name':name,'type':kind,'placement':{'left':x,'top':y,'width':w,'height':h,'rotation':0},
       'constraint':{'horizontal':'left','vertical':'top'},
       'config':{'text':{'fixed':''},'color':{'fixed':INK},'size':12,'align':'left','valign':'middle'},
       'background':{'color':{'fixed':fill}},'border':{'color':{'fixed':stroke},'width':border},'links':[]}
    elements.append(e)
    return e

def text(name,x,y,w,h,label='',size=12,color=MUTED,align='left',field=None):
    e=shape(name,x,y,w,h)
    e['type']='metric-value' if field else 'text'
    e['config'].update(text={'mode':'field','field':field,'fixed':'###'} if field else {'fixed':label},
                       size=size,color={'fixed':color},align=align)
    return e

def anchor(x,y):
    key=(round(x,3),round(y,3))
    if key not in anchors: anchors[key]=shape('Nó unifilar '+str(len(anchors)),x-5,y-5,10,10)
    return anchors[key]

def line(x1,y1,x2,y2,color=STEEL,width=1,dashed=False):
    if x1==x2 and y1==y2:return
    a,b=anchor(x1,y1),anchor(x2,y2)
    a.setdefault('connections',[]).append({'source':{'x':0,'y':0},'target':{'x':0,'y':0},'targetName':b['name'],
        'path':'straight','color':copy.deepcopy(color) if isinstance(color,dict) else {'fixed':color},'size':{'fixed':width,'min':.25,'max':8},'direction':'none',
        'lineStyle':{'style':'dashed' if dashed else 'solid','animate':False}})

def poly(points,color=STEEL,width=1,dashed=False):
    for a,b in zip(points,points[1:]):line(*a,*b,color,width,dashed)

def ellipse(name,x,y,w,h,fill='transparent',stroke=STEEL,width=1):
    return shape(name,x,y,w,h,fill,stroke,'ellipse',width)

def chevron(x,y,color=INK,vertical=None):
    if vertical=='up':poly([(x-4,y+5),(x,y),(x+4,y+5)],color,1.3)
    elif vertical=='down':poly([(x-4,y-5),(x,y),(x+4,y-5)],color,1.3)
    else:poly([(x-5,y-4),(x,y),(x-5,y+4)],color,1.3)

def illustration(prefix,box,origin,scale):
    """Reuse only approved vector geometry, including all internal connections."""
    x0,y0,x1,y1=box; ox,oy=origin
    selected=[]
    for e in old:
        p=e['placement'];x,y,w,h=p['left'],p['top'],p['width'],p['height']
        if e['name'].startswith('Ancoragem técnica'):
            include=x0<=x+5<=x1 and y0<=y+5<=y1
        else:
            include=x0<=x and y0<=y and x+w<=x1 and y+h<=y1 and (e['type'] in ['rectangle','ellipse'] or e['name']=='LCD inscrição')
        if include:selected.append(copy.deepcopy(e))
    names={e['name']:prefix+' / '+e['name'] for e in selected}
    for e in selected:
        e['name']=names[e['name']]
        p=e['placement']
        # Anchor boxes remain 10px: native connection locations are their centres.
        if 'Ancoragem técnica' in e['name']:
            p['left']=ox+(p['left']+5-x0)*scale-5
            p['top']=oy+(p['top']+5-y0)*scale-5
        else:
            p['left']=ox+(p['left']-x0)*scale
            p['top']=oy+(p['top']-y0)*scale
            p['width']*=scale;p['height']*=scale
            if e['config'].get('size'):e['config']['size']*=scale
        e['connections']=[c for c in e.get('connections',[]) if c['targetName'] in names]
        for c in e['connections']:
            c['targetName']=names[c['targetName']]
            c.pop('sourceOriginal',None);c.pop('targetOriginal',None)
        elements.append(e)

RED='#f2495c'
PRE_R={'field':'TENSAO_REDE_PRESENTE','fixed':CYAN}
PRE_G={'field':'TENSAO_GMG_PRESENTE','fixed':AMBER}
POST={'field':'TENSAO_SAIDA_PRESENTE','fixed':INK}

shape('Fundo V26',0,0,1321,1140,BG)
text('Marca',24,17,290,26,'SISTEL / LOGSIS',22,INK)
text('Disciplina',24,48,300,17,'SUPERVISÃO DE ENERGIA',10,CYAN)
text('Título',385,20,620,23,'DSE7420 / UNIFILAR DA INSTALAÇÃO',16,INK)
text('Subtítulo',385,48,680,17,'REDE E GERAÇÃO → CONTATOS SIMÉTRICOS → EDIFÍCIO',10,MUTED)
text('RSSI rótulo',1155,22,68,18,'RSSI',10,MUTED)
text('RSSI valor',1223,19,74,24,'',17,INK,'right','GSM_RSSI')
line(24,78,1297,78,DIM,.7)
shape('Prancha',20,100,1280,790,SURFACE,'#213448',border=.7)
text('Prancha título',38,115,740,22,'DISTRIBUIÇÃO / TENSÃO ANTES E DEPOIS DA TRANSFERÊNCIA',12,INK)
line(1020,126,1044,126,RED,2)
text('Legenda tensão',1053,117,225,18,'VERMELHO / TENSÃO PRESENTE',9,INK)

# Two sources above identical, side-by-side contacts. No electrical path crossings.
text('Rede título',40,158,350,22,'01 / CONCESSIONÁRIA',12,CYAN)
illustration('Rede',(43,183,312,393),(55,188),.95)
text('Gerador título',730,158,430,22,'02 / GRUPO GERADOR',12,AMBER)
illustration('Gerador',(695,166,1275,382),(730,192),.9)
for j,(label,field) in enumerate(zip(['L1–N','L2–N','L3–N','L1–L2','L2–L3','L3–L1'],['MDB30','MDB31','MDB32','MDB33','MDB34','MDB35'])):
    x=40+(j%3)*112;y=415+(j//3)*47
    text('Rede fase '+field,x,y,105,14,label,9,MUTED)
    text('Rede leitura '+field,x,y+15,105,25,'',18,INK,'left',field)
text('Rede frequência rótulo',40,514,129,15,'FREQUÊNCIA',9,MUTED)
text('Rede frequência valor',173,509,188,27,'',19,INK,'right','MDB29')
for j,(label,field) in enumerate([
    ('L1–N','MDB09'),('L2–N','MDB10'),('L3–N','MDB11'),('FREQUÊNCIA','MDB08'),
    ('ROTAÇÃO','MDB07'),('TEMP. MOTOR','MDB02'),('PRESSÃO ÓLEO','MDB01'),('MODO¹','MDB43')]):
    x=900+(j%3)*128;y=415+(j//3)*46
    text('GMG rótulo '+field,x,y,119,14,label,9,MUTED)
    text('GMG leitura '+field,x,y+15,119,25,'',18,INK,'left',field)

shape('Envoltória QTA',390,551,470,254,'transparent','#345064',border=.8)
text('QTA título',405,560,440,22,'03 / CHAVE DE TRANSFERÊNCIA',13,INK,'center')
poly([(310.55,301.05),(450,301.05),(450,608)],PRE_R,2.0)
chevron(407,301.05,PRE_R)
chevron(450,514,PRE_R,'down')
ellipse('Porta de saída GMG',795,388,10,10,SURFACE,STEEL,.7)
line(800,399,800,608,PRE_G,2.0)
chevron(800,514,PRE_G,'down')
text('Estado rede',477,442,226,20,'',12,CYAN,'left','TENSAO_REDE_PRESENTE')
text('Estado GMG',572,480,208,20,'',12,AMBER,'right','TENSAO_GMG_PRESENTE')

for cx,field,label in [(450,'MDB55','K1 / REDE'),(800,'MDB56','K2 / GMG')]:
    shape('Contato caixa '+field,cx-32,609,64,82,'#111f2d','#6f8b9e',border=.8)
    ellipse('Contato entrada '+field,cx-5,605,10,10,SURFACE,STEEL,.7)
    ellipse('Contato saída '+field,cx-5,683,10,10,SURFACE,STEEL,.7)
    text('Contato título '+field,cx-30,618,60,14,label,8.5,INK,'center')
    text('Contato posição '+field,cx-27,633,54,35,'',22,AMBER,'center',field)
    line(cx,693,cx,747,POST,2.0)
    chevron(cx,722,POST,'down')
line(484,650,766,650,DIM,.7,True)
text('Intertravamento',524,621,210,17,'INTERTRAVAMENTO MECÂNICO',9,MUTED,'center')
line(450,747,930,747,POST,2.3)
ellipse('Junção barramento',795,742,10,10,INK,INK,.5)['background']['color']=POST.copy()
poly([(930,747),(930,758),(1002,758)],POST,2.3)
chevron(978,758,POST)
text('Saída título',505,758,252,17,'BARRAMENTO DE SAÍDA (INFERIDO)',9,MUTED,'center')
text('Estado saída',886,786,170,22,'',12,INK,'center','TENSAO_SAIDA_PRESENTE')
text('QTA diagnóstico',403,815,450,22,'',11,AMBER,'center','QTA_PARALELISMO')

# Architectural load retained from V25, moved below the generator and beside the output bus.
original_art=old
old=source['panels'][0]['options']['root']['elements']
illustration('Edifício',(1010,210,1290,585),(1000,582),.8)
old=original_art
text('Prédio título',1020,551,265,23,'04 / EDIFÍCIO',13,INK,'center')
text('Prédio legenda',1020,577,265,15,'CARGA DA INSTALAÇÃO',9,MUTED,'center')
text('QGBT inscrição',1004,751,35,14,'QGBT',9,INK,'center')
line(1041,759,1048,759,POST,1.5)

text('Período',24,906,735,22,'LEITURAS DO PERÍODO SELECIONADO / NÃO CONFIRMAM ESTADO AO VIVO',10,AMBER)
text('Último registro rótulo',879,908,200,18,'ÚLTIMO REGISTRO NA JANELA',9,MUTED)
text('Último registro',1084,903,213,25,'',15,INK,'right','ULTIMA_LEITURA')
for n,(label,field,note) in enumerate([
    ('POTÊNCIA ATIVA TOTAL','MDB22','GERADOR / TOTAL TRIFÁSICO'),
    ('FATOR DE POTÊNCIA MÉDIO','MDB28','GERADOR / FP MÉDIO'),
    ('HORÍMETRO','MDB36','ACUMULADO / HORAS'),
    ('ENERGIA ACUMULADA','MDB37','GERADOR / kWh')]):
    x=20+n*324
    shape('Indicador '+field,x,952,310,124,SURFACE,'#243a4d',border=.6)
    line(x+14,969,x+36,969,CYAN,1.6)
    text('Indicador título '+field,x+14,983,282,17,label,10,MUTED)
    text('Indicador valor '+field,x+14,1005,282,40,'',30,INK,'left',field)
    text('Indicador nota '+field,x+14,1055,282,15,note,9,MUTED)
text('Nota modo',24,1097,1275,18,'¹ Modo conforme mapeamento legado; confirmar no controlador. Instrumentação completa logo abaixo.',10,MUTED)

# Drive colours from one coherent, latest row inside the selected interval.
# Existing MDB readings remain untouched; auxiliary flags never forward-fill older rows.
base_sql=panel['targets'][0]['rawSql'].rstrip().rstrip(';')
cols=[9,10,11,12,13,14,30,31,32,33,34,35,55,56]
def presence_sql(numbers):
    present=' OR '.join(f'(mdb{n}>0 AND mdb{n}<32760)' for n in numbers)
    zero=' AND '.join(f'mdb{n}=0' for n in numbers)
    return f'CASE WHEN {present} THEN 1 WHEN {zero} THEN 0 ELSE NULL END'
panel['targets'][0]['rawSql']=f'''WITH leituras AS (
{base_sql}
), amostra AS (
 SELECT {', '.join('mdb'+str(n) for n in cols)}
 FROM $Id_Logsis WHERE $__timeFilter("time") ORDER BY "time" DESC LIMIT 1
), fontes AS (
 SELECT {presence_sql(range(30,36))} AS rede,
        {presence_sql(range(9,15))} AS gmg,
        CASE WHEN mdb55 IN (0,1) THEN mdb55 ELSE NULL END AS k1,
        CASE WHEN mdb56 IN (0,1) THEN mdb56 ELSE NULL END AS k2
 FROM amostra
), ramos AS (
 SELECT *, CASE WHEN k1=0 OR rede=0 THEN 0 WHEN k1=1 AND rede=1 THEN 1 ELSE NULL END AS ramo_rede,
           CASE WHEN k2=0 OR gmg=0 THEN 0 WHEN k2=1 AND gmg=1 THEN 1 ELSE NULL END AS ramo_gmg
 FROM fontes
)
SELECT leituras.*, ramos.rede AS "TENSAO_REDE_PRESENTE", ramos.gmg AS "TENSAO_GMG_PRESENTE",
 CASE WHEN ramo_rede=1 OR ramo_gmg=1 THEN 1
      WHEN ramo_rede=0 AND ramo_gmg=0 THEN 0 ELSE NULL END AS "TENSAO_SAIDA_PRESENTE",
 CASE WHEN k1=1 AND k2=1 THEN 1 WHEN k1 IS NULL OR k2 IS NULL THEN NULL ELSE 0 END AS "QTA_PARALELISMO"
FROM leituras LEFT JOIN ramos ON TRUE'''

for name,base in [('TENSAO_REDE_PRESENTE',CYAN),('TENSAO_GMG_PRESENTE',AMBER),('TENSAO_SAIDA_PRESENTE',INK)]:
    panel['fieldConfig']['overrides'].append({'matcher':{'id':'byName','options':name},'properties':[
        {'id':'unit','value':'none'}, {'id':'decimals','value':0},
        {'id':'color','value':{'mode':'thresholds'}},
        {'id':'thresholds','value':{'mode':'absolute','steps':[{'color':base,'value':None},{'color':RED,'value':1}]}},
        {'id':'mappings','value':[
            {'type':'value','options':{'0':{'text':'SEM TENSÃO','color':base},'1':{'text':'COM TENSÃO','color':RED}}},
            {'type':'special','options':{'match':'null','result':{'text':'SEM DADOS','color':base}}}]}]})
panel['fieldConfig']['overrides'].append({'matcher':{'id':'byName','options':'QTA_PARALELISMO'},'properties':[
    {'id':'mappings','value':[{'type':'value','options':{'0':{'text':'CONTATOS NÃO SIMULTÂNEOS','color':MUTED},'1':{'text':'K1 + K2 FECHADOS / VERIFICAR PARALELISMO','color':RED}}},
                            {'type':'special','options':{'match':'null','result':{'text':'POSIÇÕES INDISPONÍVEIS','color':MUTED}}}]}]})
for e in elements:
    if e['type']=='metric-value' and (e['config']['text']['field'].startswith('TENSAO_') or e['config']['text']['field']=='QTA_PARALELISMO'):
        e['config']['color']={'field':e['config']['text']['field'],'fixed':e['config']['color']['fixed']}

panel['options']['root']['elements']=elements
panel['options']['root']['placement']['height']=1140
panel['gridPos']['h']=33
panel['description']='Vermelho: presença de tensão maior que zero na amostra mais recente do período. Antes dos contatos: tensões medidas das fontes. Após os contatos: estado inferido das fontes e posições K1/K2; não há sensor direto do barramento neste mapeamento. Dados ausentes não são tratados como tensão zero.'
instrument['gridPos']['y']=33
offset=33+instrument['gridPos']['h']-history['gridPos']['y']
history['gridPos']['y']+=offset
for p in history['panels']:p['gridPos']['y']+=offset
d.update(title='LOGSIS / DSE7420 — V26 Unifilar',uid='logsis-dse7420-v26-unifilar',id=None,version=1,
         tags=['LOGSIS','DSE7420','V26','unifilar'],description='Contatos simétricos K1/K2 e percursos vermelhos com tensão. Saída inferida a partir das fontes e contatos, com estados desconhecidos preservados.')
out=ROOT/'dist/V26_IMPORTAR.json';out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(d,ensure_ascii=True,separators=(',',':'),allow_nan=False)+'\n',encoding='ascii')
with zipfile.ZipFile(ROOT/'dist/V26_IMPORTAR.zip','w',zipfile.ZIP_DEFLATED) as z:z.write(out,out.name)
print(out)
print('Elementos',len(elements),'Conexões',sum(len(e.get('connections',[])) for e in elements))

