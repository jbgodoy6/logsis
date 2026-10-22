"""Unified native one-line diagram, based on the approved V24 revision."""
import copy
import json
import math
import pathlib
import zipfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
source=json.loads((ROOT/'V24_IMPORTAR.json').read_text())
d=copy.deepcopy(source)
panel,instrument,history=d['panels']
old=panel['options']['root']['elements']
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
        'path':'straight','color':{'fixed':color},'size':{'fixed':width,'min':.25,'max':8},'direction':'none',
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

shape('Fundo V25',0,0,1321,1050,BG)
text('Marca',24,17,290,26,'SISTEL / LOGSIS',22,INK)
text('Disciplina',24,48,300,17,'SUPERVISÃO DE ENERGIA',10,CYAN)
text('Título instalação',385,20,620,23,'DSE7420 / UNIFILAR DA INSTALAÇÃO',16,INK)
text('Subtítulo',385,48,640,17,'REDE E GERAÇÃO  →  TRANSFERÊNCIA  →  EDIFÍCIO',10,MUTED)
text('RSSI rótulo',1155,22,68,18,'RSSI',10,MUTED)
text('RSSI valor',1223,19,74,24,'',17,INK,'right','GSM_RSSI')
line(24,78,1297,78,DIM,.7)
shape('Prancha unifilar',20,100,1280,706,SURFACE,'#213448',border=.7)
text('Prancha título',38,115,620,22,'DISTRIBUIÇÃO DE ENERGIA / FONTES ALTERNATIVAS',12,INK)
for x,label,color in [(998,'REDE',CYAN),(1093,'GMG',AMBER),(1186,'CARGA',INK)]:
    line(x,126,x+18,126,color,1.7)
    text('Legenda '+label,x+25,117,70,18,label,9,color)

# Pylon and genset share one drawing surface and actual source-to-load routes.
illustration('Concessionária',(43,183,312,393),(55,160),.9)
text('Rede título',35,151,123,20,'01 / REDE',12,CYAN)
text('Rede subtítulo',350,203,185,17,'CONCESSIONÁRIA',10,MUTED)
for j,(label,field) in enumerate(zip(['L1–N','L2–N','L3–N','L1–L2','L2–L3','L3–L1'],['MDB30','MDB31','MDB32','MDB33','MDB34','MDB35'])):
    x=40+(j%3)*99;y=365+(j//3)*51
    text('Rede fase '+field,x,y,94,15,label,9,MUTED)
    text('Rede leitura '+field,x,y+16,94,25,'',18,INK,'left',field)
text('Rede frequência rótulo',352,365,154,16,'FREQUÊNCIA DA REDE',9,MUTED)
text('Rede frequência valor',352,385,154,28,'',20,INK,'left','MDB29')

text('Gerador título',40,467,390,22,'02 / GRUPO GERADOR',12,AMBER)
illustration('Grupo gerador',(695,166,1275,382),(40,510),.83)
# Electrical lead originates at the alternator terminal box, outside the engine silhouette.
poly([(140,555),(140,503),(550,503),(550,680),(800,680),(800,588)],AMBER,1.8)
text('Saída alternador legenda',334,483,205,17,'SAÍDA DO ALTERNADOR',9,MUTED,'right')
for x in [600,700]:chevron(x,680,AMBER)
chevron(800,620,AMBER,'up')

# QTA top input is the utility; bottom input is the genset. Only the post-contact bus is common.
text('QTA título',597,178,318,23,'03 / TRANSFERÊNCIA',14,INK)
shape('Envoltória QTA',592,214,326,498,'transparent','#345064',border=.8)
poly([(297,267.1),(405,267.1),(405,260),(650,260),(650,306)],CYAN,1.8)
chevron(492,260,CYAN);chevron(650,287,CYAN,'down')
text('K1 título',691,326,115,17,'K1 / REDE',10,CYAN)
shape('Disjuntor rede',618,307,64,77,'#111f2d','#6f8b9e',border=.8)
text('Posição K1',623,328,54,35,'',22,AMBER,'center','MDB55')
ellipse('Borne K1 entrada',645,303,10,10,SURFACE,STEEL,.7)
ellipse('Borne K1 saída',645,376,10,10,SURFACE,STEEL,.7)
line(650,386,650,430,STEEL,1.8)
chevron(650,409,STEEL,'down')

shape('Disjuntor gerador',768,508,64,77,'#111f2d','#6f8b9e',border=.8)
text('Posição K2',773,529,54,35,'',22,AMBER,'center','MDB56')
ellipse('Borne K2 entrada',795,577,10,10,SURFACE,STEEL,.7)
ellipse('Borne K2 saída',795,504,10,10,SURFACE,STEEL,.7)
text('K2 título',840,538,70,17,'K2 / GMG',10,AMBER)
line(800,506,800,430,STEEL,1.8)
chevron(800,469,STEEL,'up')
line(650,430,1012,430,INK,2.1)
ellipse('Junção fontes',795,425,10,10,INK,INK,.5)
chevron(967,430,INK)
text('Barramento título',680,394,228,20,'BARRAMENTO DE SAÍDA',10,INK,'center')
text('Saída rótulo',922,459,130,16,'PARA A CARGA',9,INK,'center')
# Dashed mechanical relationship is separate from the electrical paths.
poly([(684,344),(731,344),(731,548),(766,548)],DIM,.7,True)
text('Vínculo mecânico',608,645,166,16,'INTERTRAVAMENTO',9,MUTED)
text('Nota posição temporal',609,688,294,16,'POSIÇÕES NO PERÍODO SELECIONADO',9,MUTED)

# Architectural load: front elevation, perspective side, glass curtain wall and service podium.
text('Carga título',1015,166,266,22,'04 / EDIFÍCIO',14,INK)
text('Carga subtítulo',1015,190,266,17,'CARGA DA INSTALAÇÃO',9,MUTED)
shape('Fachada principal',1060,250,155,304,'#142b3b','#8da4b4',border=.85)
poly([(1060,250),(1115,225),(1270,225),(1215,250)],'#8da4b4',.9)
poly([(1215,250),(1270,225),(1270,529),(1215,554)],'#8da4b4',1)
poly([(1060,554),(1085,570),(1241,570),(1270,553),(1270,529)],DIM,.8)
for x in range(1221,1270,5):
    dy=(x-1215)*25/55
    line(x,250-dy,x,554-dy,'#294656',2.5)
for floor in range(10):
    yy=258+floor*27
    line(1060,yy+23,1215,yy+23,'#5b788c',.6)
    line(1215,yy+23,1270,yy-2,'#5b788c',.6)
    for col in range(6):
        x=1069+col*23
        # Static architectural shading, never a measured on/off indication.
        fill=['#213e51','#1b3547','#29485a'][(floor+col)%3]
        shape('Vidro %s %s'%(floor,col),x,yy,14,18,fill,'#456276',border=.45)
for x in [1065,1210]:line(x,251,x,553,'#8ca3b3',1)
shape('Cobertura técnica',1112,230,57,19,'#273f4f','#7a93a5',border=.6)
poly([(1112,230),(1126,223),(1183,223),(1169,230)],DIM,.7)
line(1145,223,1145,211,DIM,.8)
shape('Portaria podium',1029,531,122,37,'#20394a','#7793a7',border=.7)
shape('Entrada fachada',1120,519,41,35,'#122633','#65849b',border=.6)
line(1140,520,1140,554,'#7f9bad',.7)
shape('Marquise',1105,509,72,10,'#3e5a6e','#8ea5b5',border=.6)
line(1010,579,1290,579,DIM,.8)
line(1030,585,1280,585,'#243d50',.6)
shape('Quadro geral',1012,407,48,47,'#182e3e','#a7bdcb',border=.85)
text('Quadro geral inscrição',1015,421,42,17,'QGBT',10,INK,'center')
line(1060,430,1069,430,INK,1.4)
text('Carga legenda',1015,603,266,20,'QUADRO GERAL / DISTRIBUIÇÃO',10,INK,'center')
text('Carga legenda inferior',1015,627,266,18,'ALIMENTAÇÃO DO EDIFÍCIO',9,MUTED,'center')

# Genset data stays next to its source; no invented building demand measurement.
for j,(label,field) in enumerate([
    ('L1–N','MDB09'),('L2–N','MDB10'),('L3–N','MDB11'),('FREQUÊNCIA','MDB08'),
    ('ROTAÇÃO','MDB07'),('TEMP. MOTOR','MDB02'),('PRESSÃO ÓLEO','MDB01'),('MODO¹','MDB43')]):
    x=40+(j%4)*132;y=711+(j//4)*45
    text('GMG rótulo '+field,x,y,125,14,label,9,MUTED)
    text('GMG leitura '+field,x,y+15,125,26,'',18,INK,'left',field)

text('Período rótulo',24,822,730,21,'LEITURAS DO PERÍODO SELECIONADO / NÃO CONFIRMAM ESTADO AO VIVO',10,AMBER)
text('Último registro rótulo',885,823,195,18,'ÚLTIMO REGISTRO NA JANELA',9,MUTED)
text('Último registro valor',1086,820,211,24,'',15,INK,'right','ULTIMA_LEITURA')
for n,(label,field,note) in enumerate([
    ('POTÊNCIA ATIVA TOTAL','MDB22','GERADOR / TOTAL TRIFÁSICO'),
    ('FATOR DE POTÊNCIA MÉDIO','MDB28','GERADOR / FP MÉDIO'),
    ('HORÍMETRO','MDB36','ACUMULADO / HORAS'),
    ('ENERGIA ACUMULADA','MDB37','GERADOR / kWh')]):
    x=20+n*324
    shape('Indicador '+field,x,865,310,124,SURFACE,'#243a4d',border=.6)
    line(x+14,881,x+36,881,CYAN,1.6)
    text('Indicador título '+field,x+14,895,282,17,label,10,MUTED)
    text('Indicador valor '+field,x+14,917,282,40,'',30,INK,'left',field)
    text('Indicador nota '+field,x+14,968,282,15,note,9,MUTED)
text('Nota modo',24,1010,1275,17,'¹ Modo conforme mapeamento legado; confirmar no controlador. Instrumentação completa logo abaixo.',10,MUTED)

panel['options']['root']['elements']=elements
panel['options']['root']['placement']['height']=1050
panel['options']['root']['name']='LOGSIS / Unifilar integrado da instalação'
panel['title']='LOGSIS / Caminhos da energia'
panel['description']='Diagrama topológico: rede e gerador entram por contatos distintos e convergem no barramento que alimenta o edifício. Traços e setas indicam percursos previstos, sem inferir energização. Leituras conforme o período selecionado.'
panel['gridPos']['h']=30
instrument['gridPos']['y']=30
old_history_y=history['gridPos']['y']
history['gridPos']['y']=30+instrument['gridPos']['h']
for p in history['panels']:p['gridPos']['y']+=history['gridPos']['y']-old_history_y
d.update(title='LOGSIS / DSE7420 — V25 Unifilar',uid='logsis-dse7420-v25-unifilar',id=None,version=1,
         tags=['LOGSIS','DSE7420','V25','unifilar'],description='Unifilar vetorial integrado: concessionária e grupo gerador, transferência e edifício. Instrumentação aberta e históricos recolhíveis. Sem alterações nas consultas ou escalas da V24.')
assert panel['targets']==source['panels'][0]['targets']
assert panel['fieldConfig']==source['panels'][0]['fieldConfig']
assert instrument['targets']==source['panels'][1]['targets']
assert len(history['panels'])==13
out=ROOT/'dist/V25_IMPORTAR.json';out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(d,ensure_ascii=True,separators=(',',':'),allow_nan=False)+'\n',encoding='ascii')
with zipfile.ZipFile(ROOT/'dist/V25_IMPORTAR.zip','w',zipfile.ZIP_DEFLATED) as z:z.write(out,out.name)
print(out)
print('Elementos',len(elements),'Conexões',sum(len(e.get('connections',[])) for e in elements))
