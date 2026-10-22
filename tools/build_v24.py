"""V24: native Canvas engineering illustration; preserve V23 SQL and history."""
import copy
import json
import math
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
baseline = ROOT / 'dist/logsis_dse7420_v23_studio.json'
if not baseline.exists():
    baseline = ROOT / 'LOGSIS_V23.json'
source = json.loads(baseline.read_text())
d = copy.deepcopy(source)
panel = d['panels'][1]
old_elements = panel['options']['root']['elements']
BG, SURFACE = '#080f19', '#0e1a27'
INK, MUTED, CYAN, AMBER = '#e5eef7', '#96aec4', '#67cce4', '#e9bd79'
STEEL, DIM = '#9bb0bf', '#4e6579'
elements = []
anchors = {}
serial = 0

def shape(name, x, y, w, h, fill='transparent', stroke='transparent', kind='rectangle', border=1):
    e = {'name': name, 'type': kind,
         'placement': {'left': x, 'top': y, 'width': w, 'height': h, 'rotation': 0},
         'constraint': {'horizontal': 'left', 'vertical': 'top'},
         'config': {'text': {'fixed': ''}, 'color': {'fixed': INK}, 'size': 12, 'align': 'left', 'valign': 'middle'},
         'background': {'color': {'fixed': fill}},
         'border': {'color': {'fixed': stroke}, 'width': border}, 'links': []}
    elements.append(e)
    return e

def text(name, x, y, w, h, label, size=12, color=MUTED, align='left', field=None):
    e = shape(name, x, y, w, h)
    e['type'] = 'metric-value' if field else 'text'
    e['config'].update(text={'mode': 'field', 'field': field, 'fixed': '###'} if field else {'fixed': label},
                       size=size, color={'fixed': color}, align=align)
    return e

def anchor(x, y):
    key = (round(x, 3), round(y, 3))
    if key not in anchors:
        anchors[key] = shape('Ancoragem técnica %s' % len(anchors), x-5, y-5, 10, 10)
    return anchors[key]

def line(x1, y1, x2, y2, color=STEEL, width=1, dashed=False):
    if x1 == x2 and y1 == y2:
        return
    a, b = anchor(x1, y1), anchor(x2, y2)
    a.setdefault('connections', []).append({
        'source': {'x': 0, 'y': 0}, 'target': {'x': 0, 'y': 0}, 'targetName': b['name'],
        'path': 'straight', 'color': {'fixed': color},
        'size': {'fixed': width, 'min': 0.25, 'max': 8}, 'direction': 'none',
        'lineStyle': {'style': 'dashed' if dashed else 'solid', 'animate': False}})

def poly(points, color=STEEL, width=1, dashed=False):
    for a, b in zip(points, points[1:]):
        line(*a, *b, color, width, dashed)

def ellipse(name, x, y, w, h, fill, stroke=STEEL, width=1):
    return shape(name, x, y, w, h, fill, stroke, 'ellipse', width)

def bolt(x, y):
    ellipse('Fixação %.1f %.1f' % (x, y), x-5, y-5, 10, 10, SURFACE, DIM, .6)
    line(x-2, y, x+2, y, STEEL, .65)

def measure(x1, x2, y, label):
    line(x1,y,x2,y,DIM,.65)
    for x in [x1,x2]:
        line(x,y-4,x,y+4,DIM,.65)
        line(x-2,y+2,x+2,y-2,DIM,.65)
    text('Legenda '+label,x1,y+4,x2-x1,16,label,9,DIM,'center')

# Deliberate editorial hierarchy, with all geometry built from native primitives.
shape('Fundo V24', 0, 0, 1321, 836, BG)
text('Marca V24',24,17,290,26,'SISTEL / LOGSIS',22,INK)
text('Disciplina',24,48,300,17,'SUPERVISÃO DE ENERGIA',10,CYAN)
text('Identificação instalação',385,20,520,23,'DSE7420  /  VISÃO GERAL DA INSTALAÇÃO',15,INK)
text('Subtítulo instalação',385,48,590,17,'REDE  ·  TRANSFERÊNCIA  ·  GRUPO GERADOR',10,MUTED)
text('RSSI título',1155,22,68,18,'RSSI',10,MUTED)
text('RSSI valor',1223,19,74,24,'',17,INK,'right','GSM_RSSI')
line(24,78,1297,78,DIM,.7)
for x,w,num,title,caption in [
    (20,310,'01','CONCESSIONÁRIA','ALIMENTAÇÃO EXTERNA'),
    (342,316,'02','TRANSFERÊNCIA','DIAGRAMA UNIFILAR'),
    (670,630,'03','GRUPO GERADOR','CONJUNTO MOTOR / ALTERNADOR')]:
    shape('Área '+title,x,94,w,474,SURFACE,'#213448',border=.7)
    text('Índice '+num,x+14,107,27,23,num,17,CYAN)
    text('Título '+title,x+50,107,w-66,22,title,14,INK)
    text('Subtítulo '+title,x+50,132,w-66,16,caption,9,MUTED)
    line(x+14,158,x+w-14,158,'#263c50',.6)

# Transmission pylon: steel profiles, cross bracing, crossarms, insulator discs and catenaries.
cx=175
levels=[(183,4),(209,12),(234,21),(257,28),(283,39),(309,49),(342,61),(374,75)]
for side in [-1,1]:
    points=[(cx+side*half,y) for y,half in levels]
    poly(points,STEEL,1.6)
    poly([(x+side*3,y) for x,y in points],'#486073',.7)
line(cx-4,183,cx+4,183,STEEL,1)
for (yt,ht),(yb,hb) in zip(levels[1:],levels[2:]):
    line(cx-ht,yt,cx+hb,yb,STEEL,.8)
    line(cx+ht,yt,cx-hb,yb,STEEL,.8)
    line(cx-hb,yb,cx+hb,yb,STEEL,.8)
    line(cx,yb-2,cx,yb+2,DIM,.6)
for level,span in [(216,61),(245,83),(274,106)]:
    poly([(cx-span,level),(cx+span,level),(cx+span-10,level+9),(cx-span+10,level+9),(cx-span,level)],STEEL,1)
    line(cx-12,level-14,cx-span+12,level,STEEL,.85)
    line(cx+12,level-14,cx+span-12,level,STEEL,.85)
    for side in [-1,1]:
        px=cx+side*(span-7)
        line(px,level+8,px,level+27,DIM,.8)
        for disk in range(5):
            yy=level+11+disk*3
            line(px-4,yy,px+4,yy,STEEL,1)
        # Realistic shallow sag, not heavy horizontal bars.
        endx=43 if side==-1 else 312
        pts=[(px+(endx-px)*k/12,level+28+6*math.sin(math.pi*k/12)) for k in range(13)]
        poly(pts,'#63899f',.85)
for side in [-1,1]:
    footx=cx+side*75
    shape('Sapata torre '+str(side),footx-12,374,24,12,'#24394a',DIM,border=.6)
    line(footx-16,387,footx+16,387,DIM,.8)
line(64,393,290,393,'#263e52',.7)

# Six phase voltages in restrained instrumentation beneath the tower.
for j,(label,field) in enumerate(zip(['L1–N','L2–N','L3–N','L1–L2','L2–L3','L3–L1'],['MDB30','MDB31','MDB32','MDB33','MDB34','MDB35'])):
    x=35+(j%3)*96; y=407+(j//3)*59
    text('Rede fase '+field,x,y,88,15,label,10,MUTED)
    text('Rede tensão '+field,x,y+18,90,25,'',19,INK,'left',field)
line(35,526,315,526,'#263e52',.6)
text('Rede Hz legenda',35,535,104,17,'FREQUÊNCIA',9,MUTED)
text('Rede Hz valor',166,531,147,26,'',19,INK,'right','MDB29')

# QTA: drafting-standard line weights, terminal rings and mechanical interlock.
for cx,field,label in [(415,'MDB55','REDE / K1'),(583,'MDB56','GMG / K2')]:
    text('Entrada '+field,cx-47,177,94,18,label,10,INK,'center')
    ellipse('Terminal superior '+field,cx-5,202,10,10,SURFACE,STEEL,1)
    line(cx,213,cx,251,STEEL,1.7)
    shape('Caixa disjuntor '+field,cx-32,252,64,83,'#111f2d','#4e687d',border=.8)
    ellipse('Borne superior '+field,cx-5,258,10,10,SURFACE,STEEL,.8)
    ellipse('Borne inferior '+field,cx-5,318,10,10,SURFACE,STEEL,.8)
    text('Posição contato '+field,cx-28,275,56,36,'',22,AMBER,'center',field)
    line(cx,335,cx,403,STEEL,1.7)
    for yy in [240,348]:
        line(cx-5,yy-3,cx+5,yy+3,DIM,.7)
text('Intertravamento legenda',445,224,108,18,'INTERTRAVAMENTO',8,DIM,'center')
line(443,293,555,293,DIM,.9,True)
line(499,246,499,284,DIM,.7,True)
line(415,403,583,403,STEEL,2)
ellipse('Nó de carga',494,398,10,10,STEEL,STEEL,.6)
line(499,410,499,449,STEEL,1.8)
poly([(493,443),(499,449),(505,443)],STEEL,1)
text('Saída QTA',380,461,239,19,'BARRAMENTO DE CARGA',11,INK,'center')
text('Estado temporal QTA',364,493,274,17,'POSIÇÕES NO PERÍODO SELECIONADO',9,MUTED,'center')
shape('Aviso QTA',357,528,286,26,'#24231f','#645239',border=.6)
text('Aviso QTA legenda',365,532,270,17,'SINAIS DO QTA NÃO HOMOLOGADOS',10,AMBER,'center')

# Generator side elevation, constructed as an illustrative mechanical assembly.
# The dimensions and geometry are generic, not a manufacturer-certified GA drawing.
line(695,382,1275,382,'#263e52',.7)
shape('Sombra skid',716,364,552,10,'#0a131e')
shape('Skid principal',707,344,568,20,'#253a4a','#6e8494',border=.9)
shape('Longarina frontal',713,355,556,14,'#152634','#536e83',border=.7)
for xx in [735,801,1036,1199,1247]:
    bolt(xx,354)
for xx in [755,865,1008,1194]:
    shape('Coxim '+str(xx),xx,332,24,12,'#18232e','#718696',border=.6)

# Cylindrical alternator housing and end bells.
shape('Alternador corpo',729,239,115,87,'#294555','#8098a8',border=.9)
ellipse('Alternador tampa frontal',714,239,30,87,'#1b303e','#8ca3b1',1)
ellipse('Alternador tampa anel',719,246,19,72,'#152937','#607e92',.8)
ellipse('Alternador tampa interna',723,259,11,46,'#233d4e','#4d6c81',.6)
for x in range(749,833,7):
    line(x,250,x,316,'#122a39',2.4)
    line(x+2,250,x+2,316,'#658195',.55)
shape('Alternador caixa conexões',754,220,65,20,'#304c5c','#849aa8',border=.7)
shape('Alternador caixa tampa',750,215,73,10,'#4b6473','#93a8b4',border=.6)
for x in [760,813]: bolt(x,225)
line(833,259,848,259,STEEL,1.4)
line(833,306,848,306,STEEL,1.4)
shape('Acoplamento',838,266,16,37,'#172b39','#829aa9',border=.6)

# Engine block: cast surfaces, rocker covers, injectors and pipework.
shape('Bloco motor',856,253,172,70,'#27414d','#79949f',border=.9)
shape('Cárter óleo',867,319,150,13,'#162a36','#667f8e',border=.7)
shape('Cabeçote motor',852,234,181,23,'#36515b','#8aa2ac',border=.8)
for j in range(6):
    x=860+j*28
    shape('Tampa válvula '+str(j),x,221,24,15,'#617984','#a6b7c0',border=.6)
    bolt(x+12,228)
    line(x+12,237,x+12,254,'#a69a78',.8)
    poly([(x+12,255),(x+15,266),(x+15,282)],'#8e9a9e',.8)
    line(x+8,286,x+8,307,'#41606e',.7)
for x in [866,910,954,1017]:
    bolt(x,312)
line(865,267,1023,267,'#78909b',.6)
poly([(863,274),(893,274),(899,280),(1001,280)],'#b6a887',2.2)
poly([(869,291),(913,291),(924,302),(1004,302)],'#101e29',3)
for x in [889,978]:
    shape('Filtro óleo '+str(x),x,301,14,25,'#7c8d92','#c0cbd0',border=.7)
    line(x+3,306,x+10,306,'#344c5c',.8)
    line(x+3,321,x+10,321,'#344c5c',.8)
ellipse('Turbo carcaça',1006,207,28,28,'#415662','#adc0ca',.9)
ellipse('Turbo centro',1013,214,14,14,'#1b303d','#6d899b',.8)
poly([(884,217),(884,207),(1011,207)],'#8b9da7',4)
poly([(1026,211),(1040,211),(1040,237),(1051,237)],'#6c8796',3.5)

# Exhaust silencer with straps, outlet and thermal section.
poly([(933,207),(933,193),(917,193),(917,183)],'#839aa7',3.3)
shape('Silencioso',908,169,94,17,'#5d7382','#b2c1ca',border=.8)
ellipse('Tampa silencioso',902,169,13,17,'#415c6c','#a0b4c1',.7)
ellipse('Saída silencioso',995,169,13,17,'#344d5d','#96aebb',.7)
for x in [925,978]:
    line(x,169,x,186,'#152b3a',2)
poly([(1008,177),(1021,177),(1021,166)],'#8ca1ad',3)

# Radiator, guarded fan, cooling hoses, feet and shroud.
shape('Radiador estrutura',1060,212,69,119,'#2b404f','#92a8b6',border=.9)
shape('Radiador colmeia',1067,229,55,84,'#142733','#627e91',border=.7)
for x in range(1071,1121,4): line(x,231,x,310,'#476375',.6)
for y in range(235,311,5): line(1069,y,1120,y,'#304b5e',.55)
shape('Radiador reservatório superior',1063,216,63,13,'#657b86','#9eafb9',border=.5)
shape('Radiador reservatório inferior',1064,315,61,12,'#263e4d','#758e9f',border=.5)
ellipse('Radiador tampa',1089,202,14,11,'#849aa5','#c0cdd3',.6)
ellipse('Proteção ventilador',1038,247,48,62,'transparent','#839caa',.8)
ellipse('Ventilador cubo',1056,271,13,13,'#344d5c','#8ca4b2',.8)
for angle in [0,60,120,180,240,300]:
    a=math.radians(angle)
    line(1062,277,1062+18*math.cos(a),277+23*math.sin(a),'#607e91',1.3)
poly([(1029,239),(1040,228),(1059,228)],'#526d7d',4)
poly([(1023,317),(1042,326),(1060,326)],'#526d7d',4)

# Controller enclosure, LCD, membrane keypad and cable tray.
shape('Painel controlador',1162,225,103,103,'#233542','#8fa6b6',border=.9)
shape('Controlador moldura',1170,234,86,74,'#0a141f','#5f7b91',border=.7)
shape('LCD controlador',1178,243,70,27,'#19333e','#5c7c8c',border=.5)
text('LCD inscrição',1181,249,64,14,'DSE7420',10,'#9bb5c2','center')
for j in range(4):
    ellipse('Tecla controlador '+str(j),1178+j*19,284,11,11,'#394e5b','#8098a7',.7)
line(1213,329,1213,342,DIM,1)
poly([(1161,320),(1147,320),(1147,338),(1052,338)],DIM,1.2)
measure(718,843,390,'ALTERNADOR')
measure(851,1035,390,'MOTOR DIESEL')
measure(1045,1132,390,'ARREFECIMENTO')
measure(1158,1268,390,'CONTROLE')

# Main GMG readings below the mechanical assembly, with no overlays.
for j,(label,field) in enumerate([
    ('L1–N','MDB09'),('L2–N','MDB10'),('L3–N','MDB11'),('FREQUÊNCIA','MDB08'),
    ('ROTAÇÃO','MDB07'),('TEMP. MOTOR','MDB02'),('PRESSÃO ÓLEO','MDB01'),('MODO¹','MDB43')]):
    x=687+(j%4)*151; y=427+(j//4)*64
    text('GMG rótulo '+field,x,y,140,16,label,9,MUTED)
    text('GMG valor '+field,x,y+19,140,28,'',20,INK,'left',field)
line(686,484,1284,484,'#263e52',.6)

# Period and key performance indicators: original bindings, larger visual rhythm.
text('Contexto temporal V24',24,582,735,22,'LEITURAS DO PERÍODO SELECIONADO  /  NÃO CONFIRMAM ESTADO AO VIVO',11,AMBER)
text('Último registro título',881,584,195,18,'ÚLTIMO REGISTRO NA JANELA',9,MUTED)
text('Último registro valor',1084,580,213,25,'',15,INK,'right','ULTIMA_LEITURA')
for n,(label,field,note) in enumerate([
    ('POTÊNCIA ATIVA TOTAL','MDB22','GERADOR / TOTAL TRIFÁSICO'),
    ('FATOR DE POTÊNCIA MÉDIO','MDB28','GERADOR / FP MÉDIO'),
    ('HORÍMETRO','MDB36','ACUMULADO / HORAS'),
    ('ENERGIA ACUMULADA','MDB37','GERADOR / kWh')]):
    x=20+n*324
    shape('Indicador '+field,x,628,310,128,SURFACE,'#243a4d',border=.6)
    line(x+14,646,x+36,646,CYAN,1.6)
    text('Indicador título '+field,x+14,659,282,17,label,10,MUTED)
    text('Indicador valor '+field,x+14,681,282,41,'',30,INK,'left',field)
    text('Indicador nota '+field,x+14,733,282,15,note,9,MUTED)
text('Nota modo V24',24,778,1275,17,'¹ Modo conforme mapeamento legado; confirmar no controlador. Instrumentação e históricos nas seções abaixo.',10,MUTED)
line(24,811,1297,811,'#263e52',.6)

panel['options']['root']['elements'] = elements
panel['options']['root']['placement']['height'] = 836
panel['gridPos']['h'] = 24
panel['title'] = 'LOGSIS / Engenharia da instalação'
panel['options']['root']['connections'] = []
for p in d['panels'][2:]: p['gridPos']['y']+=3
d.update(title='LOGSIS / DSE7420 — V24 Engineering',uid='logsis-dse7420-v24-engineering',id=None,version=1,
         tags=['LOGSIS','DSE7420','V24','supervisão'],description='V24 Engineering: ilustração técnica vetorial nativa. Consultas, escalas, instrumentação e históricos preservados da V23. QTA não homologado.')
out=ROOT/'dist/V24_IMPORTAR.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(d,ensure_ascii=True,separators=(',',':'),allow_nan=False)+'\n',encoding='ascii')
with zipfile.ZipFile(ROOT/'dist/V24_IMPORTAR.zip','w',zipfile.ZIP_DEFLATED) as z: z.write(out,out.name)
assert panel['targets']==source['panels'][1]['targets']
assert panel['fieldConfig']==source['panels'][1]['fieldConfig']
assert d['panels'][2]['panels']==source['panels'][2]['panels']
assert d['panels'][3]['panels']==source['panels'][3]['panels']
print('Gerado:',out)
print('Elementos:',len(elements),'Conexões vetoriais:',sum(len(e.get('connections',[])) for e in elements))
print('Consultas, escalas, instrumentação e históricos idênticos à V23.')
