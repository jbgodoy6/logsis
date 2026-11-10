"""Thirty-day measured power history, independent of cloud outbox retention.

Points are recorded every five seconds and when the operating limit changes.
Reduced views select original samples (including extrema), never invented means.
"""
from contextlib import closing,contextmanager
from datetime import datetime
import csv
import html
import math
from pathlib import Path
import sqlite3
import time
from zoneinfo import ZoneInfo

RETENTION=30*86400
FIELDS=('total_kw','ev_kw','other_kw','limit_kw')

def finite(value):
    return float(value) if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) else None

def record(store,at,meter,ev,ev_valid,settings,fault=''):
    last=getattr(store,'_curve_last',{}).get(settings['mode'])
    if last and 0<=at-last[0]<5 and last[1]==settings['limit_kw']:return
    valid=bool(meter.get('at') and 0<=at-meter['at']<=settings['freshness_s'] and not meter.get('error') and not fault)
    total=finite(meter.get('total_kw')) if valid else None
    ev=finite(ev) if ev_valid else None
    valid=valid and total is not None
    ev_valid=ev_valid and ev is not None
    other=max(0,total-ev) if total is not None and ev is not None else None
    quality='valid' if valid and ev_valid else 'meter_missing' if not valid else 'charger_missing'
    if last and at<last[0]:quality='clock_rollback'
    with store.db:
        store.db.execute('INSERT OR REPLACE INTO curve_points VALUES (?,?,?,?,?,?,?,?)',
            (at,settings['mode'],total,ev,other,settings['limit_kw'],meter.get('at') or None,quality))
    if not hasattr(store,'_curve_last'):store._curve_last={}
    store._curve_last[settings['mode']]=(at,settings['limit_kw'])

def parameters(settings,start='',end='',mode='',now=None):
    now=time.time() if now is None else now
    zone=ZoneInfo(settings['timezone'])
    def stamp(value,default):
        if not value:return default
        try:
            dt=datetime.fromisoformat(value.replace('Z','+00:00'))
            return (dt if dt.tzinfo else dt.replace(tzinfo=zone)).timestamp()
        except (ValueError,TypeError,OverflowError):raise ValueError('Informe datas válidas para a curva') from None
    before=stamp(end,now+.001);after=stamp(start,max(before-900,now-RETENTION))
    mode=mode or settings['mode']
    if mode not in ('physical','simulation'):raise ValueError('Selecione origem real ou simulada')
    if after>=before or before-after>RETENTION or after<now-RETENTION-60 or before>now+60:
        raise ValueError('Selecione intervalo válido dentro dos últimos 30 dias')
    return after,before,mode

@contextmanager
def reader(store):
    path=store.db.execute('PRAGMA database_list').fetchone()['file']
    if path:
        with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)) as db:
            db.row_factory=sqlite3.Row
            db.execute('BEGIN')
            yield db
    else:yield store.db

def query(store,settings,start='',end='',mode='',now=None,max_points=1200):
    after,before,mode=parameters(settings,start,end,mode,now)
    buckets=max(1,min(1200,max_points)//16);width=(before-after)/buckets
    selected={};group=[];bucket=None;previous=None;segments={f:0 for f in FIELDS}
    count=0;valid_count=0;extrema={f:{'min':None,'max':None,'sum':0.0,'count':0} for f in FIELDS}
    def flush():
        if not group:return
        keep={0,len(group)-1}
        for field in FIELDS:
            available=[i for i,p in enumerate(group) if p[field] is not None]
            if available:
                keep.add(min(available,key=lambda i:group[i][field]));keep.add(max(available,key=lambda i:group[i][field]))
            invalid=next((i for i,p in enumerate(group) if p[field] is None),None)
            if invalid is not None:keep.add(invalid)
        for i in keep:selected[group[i]['ts']]=group[i]
    with reader(store) as db:
        for row in db.execute('SELECT * FROM curve_points WHERE mode=? AND ts>=? AND ts<? ORDER BY ts',(mode,after,before)):
            p=dict(row);count+=1;valid_count+=p['quality']=='valid'
            for field in FIELDS:
                value=p[field]
                if previous is None or p['ts']-previous>15 or value is None:segments[field]+=1
                p[field+'_segment']=segments[field]
                if value is not None:
                    x=extrema[field];x['min']=value if x['min'] is None else min(x['min'],value);x['max']=value if x['max'] is None else max(x['max'],value);x['sum']+=value;x['count']+=1
            previous=p['ts']
            b=min(buckets-1,int((p['ts']-after)/width))
            if bucket is not None and b!=bucket:flush();group=[]
            bucket=b;group.append(p)
        flush()
    for data in extrema.values():data['mean_kw']=data.pop('sum')/data['count'] if data['count'] else None
    return dict(start=after,end=before,mode=mode,timezone=settings['timezone'],site=settings['site_name'],
        sample_interval_s=5,total_samples=count,valid_samples=valid_count,missing_samples=count-valid_count,
        reduced=len(selected)<count,points=[selected[k] for k in sorted(selected)],statistics=extrema)

def export_csv(store,settings,path,start='',end='',mode=''):
    after,before,mode=parameters(settings,start,end,mode)
    zone=ZoneInfo(settings['timezone'])
    with reader(store) as db,open(path,'w',encoding='utf-8-sig',newline='') as output:
        writer=csv.writer(output,delimiter=';')
        writer.writerow(['instante','origem','total_kw','carregadores_kw','outras_cargas_kw','limite_kw','ultima_leitura_medidor','qualidade'])
        count=0
        for p in db.execute('SELECT * FROM curve_points WHERE mode=? AND ts>=? AND ts<? ORDER BY ts',(mode,after,before)):
            writer.writerow([datetime.fromtimestamp(p['ts'],zone).isoformat(),mode,
                *['' if p[f] is None else format(p[f],'.6f').replace('.',',') for f in FIELDS],
                datetime.fromtimestamp(p['meter_at'],zone).isoformat() if p['meter_at'] else '',p['quality']]);count+=1
    return count

COLORS={'total_kw':'#075fc4','ev_kw':'#d66a05','other_kw':'#108567','limit_kw':'#c63949'}
QUALITIES={'valid':'Leituras completas','meter_missing':'Sem leitura válida do multimedidor','charger_missing':'Leitura incompleta dos carregadores','clock_rollback':'Alteração no relógio'}
LABELS={'total_kw':'Total','ev_kw':'Carregadores','other_kw':'Outras cargas','limit_kw':'Limite'}

def geometry(data):
    peak=max([1]+[p[f] for p in data['points'] for f in FIELDS if p[f] is not None])*1.05
    target=peak/5;scale=10**math.floor(math.log10(target))
    step=next(v*scale for v in (1,2,2.5,5,10) if v*scale>=target)
    maximum=math.ceil(peak/step)*step
    return maximum,lambda ts:55+(ts-data['start'])/max(1,data['end']-data['start'])*820,lambda value:225-value/maximum*205

def render(data):
    esc=lambda value:html.escape(str(value),quote=True)
    zone=ZoneInfo(data['timezone']);maximum,x,y=geometry(data)
    if not data['points']:return '<p class="hint">Sem leituras registradas neste período e nesta origem. O histórico começa após instalar esta versão.</p>'
    latest=data['points'][-1]
    result='<div class="curve-legend">'
    for field in FIELDS:
        value='sem leitura' if latest[field] is None else f'{latest[field]:.1f} kW'.replace('.',',')
        result+='<span class="curve-legend-item"><i class="curve-dot curve-'+field+'"></i><span>'+LABELS[field]+'<b>'+value+'</b></span></span>'
    result+='</div><p class="hint">'+str(data['total_samples'])+' registros · '+('REAL' if data['mode']=='physical' else 'SIMULAÇÃO')+' · amostragem e atualização visual a cada 5 s'+(' · visualização reduzida, com extremos preservados' if data['reduced'] else '')+'. Consulte os instantes com mouse ou toque.</p>'
    if data['missing_samples']:result+='<p class="curve-quality">'+str(data['missing_samples'])+' registros com leituras incompletas. As lacunas são preservadas; valores ausentes não são zero.</p>'
    result+='<svg class="server-chart curve-chart" viewBox="0 0 900 275" role="img" aria-label="Curva histórica de demanda">'
    for i in range(6):
        value=maximum*i/5;result+=f'<line x1="55" x2="875" y1="{y(value):.2f}" y2="{y(value):.2f}" stroke="#d6e3f0"/><text x="45" y="{y(value)+4:.2f}" text-anchor="end">{value:g}</text>'
    result+='<text x="10" y="12">kW</text>'
    for field in ('total_kw','other_kw','ev_kw','limit_kw'):
        group=[];segment=None
        def series():
            if not group:return ''
            points=' '.join(f'{a:.2f},{b:.2f}' for a,b in group)
            shade=''
            if field=='total_kw' and len(group)>1:
                shade=f'<path d="M {group[0][0]:.2f},225 L '+ ' L '.join(f'{a:.2f},{b:.2f}' for a,b in group)+f' L {group[-1][0]:.2f},225 Z" fill="{COLORS[field]}" fill-opacity="0.09"/>'
            return shade+'<polyline class="curve-line" points="'+points+'" fill="none" stroke="'+COLORS[field]+'" stroke-width="'+('3.4' if field=='total_kw' else '2.6')+'" stroke-linejoin="round" stroke-linecap="round"'+(' stroke-dasharray="8 6"' if field=='limit_kw' else '')+'/>'
        for p in data['points']:
            if p[field] is None or segment is not None and p[field+'_segment']!=segment:
                result+=series();group=[]
            if p[field] is not None:group.append((x(p['ts']),y(p[field])))
            segment=p[field+'_segment']
        result+=series()
        last=next((p for p in reversed(data['points']) if p[field] is not None),None)
        if last:result+=f'<circle cx="{x(last["ts"]):.2f}" cy="{y(last[field]):.2f}" r="4" fill="{COLORS[field]}" stroke="#fff" stroke-width="1.5"/>'
    for p in data['points']:
        text=datetime.fromtimestamp(p['ts'],zone).strftime('%d/%m/%Y %H:%M:%S')+' · '+('REAL' if data['mode']=='physical' else 'SIMULAÇÃO')
        text+=' | '+' | '.join(LABELS[f]+': '+('sem leitura' if p[f] is None else f'{p[f]:.2f} kW'.replace('.',',')) for f in FIELDS)+' | '+QUALITIES.get(p['quality'],p['quality'])
        value=next((p[f] for f in FIELDS if p[f] is not None),0)
        result+=f'<circle class="curve-sample" cx="{x(p["ts"]):.2f}" cy="{y(value):.2f}" r="5" fill="{COLORS["total_kw"]}" fill-opacity="0" tabindex="0" data-curve-value="{esc(text)}"><title>{esc(text)}</title></circle>'
    for i in range(6):
        ts=data['start']+(data['end']-data['start'])*i/5;anchor='start' if i==0 else 'end' if i==5 else 'middle'
        label=datetime.fromtimestamp(ts,zone).strftime('%d/%m %H:%M' if i in (0,5) else '%H:%M')
        result+=f'<text x="{x(ts):.2f}" y="255" text-anchor="{anchor}">{esc(label)}</text>'
    return result+'</svg><p class="hint">As linhas ligam amostras registradas; degraus podem representar mudanças reais de carga. O limite tracejado usa o valor vigente em cada instante.</p>'


def pdf(data,version):
    from .reports import assemble_pdf,literal,decimal
    zone=ZoneInfo(data['timezone']);maximum,x,y=geometry(data)
    def text(a,b,value,size=10):return f'BT /F {size} Tf 0.05 0.17 0.29 rg 1 0 0 1 {a} {b} Tm {literal(value)} Tj ET\n'
    page='q 145 0 0 53 30 766 cm /Logo Do Q\nq 56 0 0 56 510 765 cm /Energy Do Q\n'
    page+=text(30,735,'CURVA DE DEMANDA · '+('REAL' if data['mode']=='physical' else 'SIMULAÇÃO'),16)
    page+=text(30,713,data['site'][:85],12)
    for n,(label,ts) in enumerate((('Início incluso',data['start']),('Término exclusivo',data['end']))):
        page+=text(30,690-n*16,label+': '+datetime.fromtimestamp(ts,zone).strftime('%d/%m/%Y %H:%M:%S')+' · '+data['timezone'],9)
    page+=text(30,640,f'{data["total_samples"]} amostras | {data["missing_samples"]} com qualidade incompleta | resolução nominal 5 s',9)
    page+='q 0.60 0 0 -1.15 0 610 cm\n'
    for field in FIELDS:
        rgb=[int(COLORS[field][i:i+2],16)/255 for i in (1,3,5)];page+=' '.join(f'{v:.4f}' for v in rgb)+' RG 1.5 w\n'+('[5 5] 0 d\n' if field=='limit_kw' else '[] 0 d\n')
        previous=None
        for p in data['points']:
            if p[field] is None:previous=None;continue
            if previous and previous[field+'_segment']==p[field+'_segment']:
                page+=f'{x(previous["ts"]):.2f} {y(previous[field]):.2f} m {x(p["ts"]):.2f} {y(p[field]):.2f} l S\n'
            previous=p
    page+='Q\n'
    for i,f in enumerate(FIELDS):
        stats=data['statistics'][f]
        page+=text(30,300-i*22,LABELS[f]+': mínimo '+('—' if stats['min'] is None else decimal(stats['min']))+' kW; máximo '+('—' if stats['max'] is None else decimal(stats['max']))+' kW',10)
    page+=text(30,180,'Azul: total; laranja: carregadores; verde: outras cargas; vermelho tracejado: limite.',8)
    page+=text(30,163,'Visualização reduzida seleciona amostras originais e extremos. CSV contém todos os pontos.',8)
    page+=text(30,146,'Lacunas representam ausência de leituras. Média amostral não é consumo de energia em kWh.',8)
    page+=text(30,28,'EnergyCube D-Max v'+version+' · Relatório local da curva',8)
    return assemble_pdf([page.encode('latin1','replace')])
