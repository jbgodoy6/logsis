"""Shared DSE7420 visual grammar; electrical meaning remains model-specific.

Presentation only: preserve BIN maps, SQL, decoders and period calculations.
Legacy DSE7420/8610 dashboards remain the approved reference artifacts.
"""
from __future__ import annotations
import copy
import math
import re
from pathlib import Path
import json

from . import manual_dashboard as ui


def field(c):return ui.field(c) if c else None


def fixed_text(element,value):
    element['type']='text';element['config']['text']={'fixed':value}
    element['config']['color']={'fixed':ui.MUTED}


def metric(element,name):
    if name:
        element['type']='metric-value';element['config']['text']={'mode':'field','field':name,'fixed':'—'}
        element['config']['color']={'fixed':ui.INK,'field':name}
    else:fixed_text(element,'—')


def img(element,name=None,uri=None):
    element['background']['image']={'mode':'mapping','field':name} if name else {'fixed':uri}


def bus_symbol():
    return ui.svg('''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 110">
    <defs><linearGradient id="bus"><stop stop-color="#526e84"/><stop offset=".5" stop-color="#a9beca"/><stop offset="1" stop-color="#526e84"/></linearGradient></defs>
    <rect x="16" y="16" width="188" height="78" rx="8" fill="#101e2c" stroke="#355267"/>
    <g fill="url(#bus)"><rect x="30" y="32" width="160" height="6" rx="2"/><rect x="30" y="52" width="160" height="6" rx="2"/><rect x="30" y="72" width="160" height="6" rx="2"/></g>
    <g fill="#162b3b" stroke="#7697aa"><rect x="48" y="27" width="8" height="56" rx="2"/><rect x="164" y="27" width="8" height="56" rx="2"/></g></svg>''')


def config(profile):
    if profile.vendor=='DEIF':
        from .deif_dashboard import panel_properties
        result=panel_properties(profile)
    else:result=ui.properties(profile)
    # Large distribution voltages fit the same cards without dropping phases.
    for c in profile.channels:
        if c.unit=='V':
            result['overrides'].append({'matcher':{'id':'byName','options':ui.field(c)},'properties':[{'id':'unit','value':'volt'},{'id':'decimals','value':2}]})
    result['overrides'].append({'matcher':{'id':'byName','options':'MODE'},'properties':[{'id':'color','value':{'mode':'fixed','fixedColor':ui.GOLD}}]})
    return result


def source_rows(rs,prefix,motor=False):
    suffixes=['v_l1n','v_l2n','v_l3n','frequency','rpm','coolant','oil_pressure'] if motor else ['v_l1n','v_l2n','v_l3n','v_l1l2','v_l2l3','v_l3l1','frequency']
    labels=['L1–N','L2–N','L3–N','Freq.','Rotação','T. água','P. óleo'] if motor else ['L1–N','L2–N','L3–N','L1–L2','L2–L3','L3–L1','Freq.']
    return [(label,field(rs.get(s if s in ['rpm','coolant','oil_pressure'] else prefix+'_'+s))) for label,s in zip(labels,suffixes)]


def wire_name(deif,prefix,vertical=True):
    return ('WIRE_'+prefix+('_V' if vertical else '')) if deif else 'WIRE_'+prefix+('_V' if vertical else '_H')


def overview(profile,old):
    deif=profile.vendor=='DEIF';rs={c.role:c for c in profile.channels}
    single=profile.topology in ['gen_bus','engine']
    if single:
        ref=json.loads((Path(__file__).parent/'resources/dse8610.json').read_text(encoding='utf-8'))['panels'][0]
    else:ref=ui.reference()['panels'][0]
    p=copy.deepcopy(ref);p['targets']=copy.deepcopy(old['targets']);p['datasource']=copy.deepcopy(old['datasource']);p['fieldConfig']=config(profile)
    p['title']='01 / Unifilar da instalação';p['gridPos']={'x':0,'y':0,'w':12,'h':27}
    p['description']='Padrão visual DSE7420. Leituras e estados pertencem ao período selecionado. Indicador LED não é retorno físico de contato.' if not deif else 'Padrão visual DSE7420. A topologia e os sinais seguem a aplicação selecionada.'
    mode='MODE' if deif else 'MODO_CURTO'
    mapping={'MODO_LOCAL':mode,'WIFI_LOCAL':'WIFI' if deif else 'WIFI_LOCAL','GSM_LOCAL':'GSM' if deif else 'GSM_LOCAL',
             'WIFI_LOCAL_ICONE':'WIFI_ICON' if deif else 'WIFI_LOCAL_ICONE','GSM_LOCAL_ICONE':'GSM_ICON' if deif else 'GSM_LOCAL_ICONE',
             'ULTIMA_LEITURA':'LAST_TIME' if deif else 'ULTIMA_LEITURA','MANUTENCAO_RESUMO':'MAINTENANCE' if deif else 'MANUTENCAO_RESUMO',
             'GERADOR_ALARME':'ALARM_TEXT' if deif else 'GERADOR_ALARME','GERADOR_ALARME_SVG':'GENERATOR_SVG' if deif else 'GERADOR_ALARME_SVG'}
    mains_bus=profile.kind=='mains_bus' or profile.topology=='mains_bus'
    tie=profile.kind=='bus_tie'
    engine=profile.kind=='engine_transfer' or profile.application in ['GEN','CGC412','CGC413','SGC420','ENG']
    left='gen' if single else 'bus' if tie else 's1' if profile.application=='ATS' else 'mains'
    right='bus' if single or mains_bus else 'bus2' if tie else 's2' if profile.application=='ATS' else 'gen'
    left_rows=source_rows(rs,left,single)
    right_rows=source_rows(rs,right,right=='gen')
    if profile.topology=='engine':
        right_rows=[(label,field(rs.get(role))) for label,role in [('Horímetro','hour_meter'),('Relativo','relative_hours'),('Partidas','starts'),('Serviço 1','maintenance_1'),('Serviço 2','maintenance_2'),('Bateria','battery'),('Alarmes','alarm_count')]]
    # EIC validity affects the same source readings as in the detailed panels.
    if deif:
        def valid_rows(rows):
            return [(label,'VALID_coolant' if name==field(rs.get('coolant')) and 'valid_coolant' in rs else 'VALID_oil_pressure' if name==field(rs.get('oil_pressure')) and 'valid_oil' in rs else name) for label,name in rows]
        left_rows=valid_rows(left_rows);right_rows=valid_rows(right_rows)
    label_left='GERADOR' if single else 'BUS 1' if tie else 'FONTE S1' if profile.application=='ATS' else 'CONCESSIONÁRIA'
    label_right='BARRAMENTO / BUS' if single or mains_bus else 'BUS 2' if tie else 'FONTE S2' if profile.application=='ATS' else 'GRUPO GERADOR'
    if profile.topology=='engine':label_left='MOTOR';label_right='ACIONAMENTO'
    elements=p['options']['root']['elements'];kept=[]
    for e in elements:
        name=e['name'];txt=e.get('config',{}).get('text',{});image=e.get('background',{}).get('image',{})
        previous=txt.get('field');previous_image=image.get('field')
        if previous in mapping:metric(e,mapping[previous])
        if previous_image in mapping:img(e,mapping[previous_image])
        if name in ['Marca responsivo','Marca']:
            fixed_text(e,'LOGSIS / '+('AGC150 EXTENDED' if profile.model.startswith('AGC150') else profile.label or profile.model))
            e['config']['size']=16
        if name in ['Disciplina responsivo','Disciplina']:fixed_text(e,'UNIFILAR / TENSÃO POR TRECHO')
        if name in ['Modo rótulo','Modo título']:fixed_text(e,'MODO / CONTROLADOR');e['config']['size']=8
        if name in ['Modo sinalização','Modo valor']:e['config']['size']=9
        if name in ['Fonte rede','Gerador título']:fixed_text(e,label_left)
        if name in ['Fonte GMG','BUS título']:fixed_text(e,label_right)
        if name=='Torre vetorial':img(e,uri=bus_symbol() if tie else ui.assets()['tower'])
        if name=='Gerador vetorial' and not single and right!='gen':
            img(e,uri=bus_symbol() if right.startswith('bus') else ui.assets()['tower'])
            e['name']='Barramento vetorial' if right.startswith('bus') else 'Fonte S2 vetorial'
        if name=='Símbolo do barramento BUS' and profile.topology=='engine':
            img(e,uri=ui.svg('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 90"><rect x="20" y="20" width="140" height="50" rx="8" fill="#183244" stroke="#7494aa"/><path d="M40 45H140" stroke="#96aec4" stroke-width="5"/></svg>'))
        if name.startswith('Fonte rótulo ') or name.startswith('Fonte leitura '):
            # Source columns are encoded in their placements, not MDB numbers.
            rows=left_rows if e['placement']['left']<50 else right_rows
            start=258 if single else 297
            row=round((e['placement']['top']-start)/22)
            if 0<=row<7:
                caption,value=rows[row]
                if name.startswith('Fonte rótulo '):fixed_text(e,caption)
                else:metric(e,value)
        if name in ['Indicação de manutenção'] and (not engine or profile.application in ['ATS','MAINS']):continue
        if name in ['Tensão rede','Tensão GMG','Tensão gerador','Tensão BUS']:
            prefix=left if name in ['Tensão rede','Tensão gerador'] else right
            fixed_text(e,'TENSÃO / '+('BUS' if prefix.startswith('bus') else 'FONTE'))
        if single:
            binds={'TENSAO_GMG_V_SVG':wire_name(deif,'gen'),'TENSAO_BUS_V_SVG':wire_name(deif,'bus'),'TENSAO_BUS_H_SVG':wire_name(deif,'bus',False),'GCB_CONTATO_SVG':'B2_SVG','GCB_POSICAO':'B2_TEXT','ESTADO_GCB':'B2_TEXT'}
            if previous in binds:metric(e,binds[previous])
            if previous_image in binds:img(e,binds[previous_image])
            if name=='Disjuntor título':fixed_text(e,'GB / GERADOR')
            if name=='BUS nota':fixed_text(e,'BARRAMENTO MEDIDO')
            if profile.topology=='engine' and (name.startswith('Traço') or name.startswith('Disjuntor') or name in ['GCB estado','BUS nota','Tensão BUS','BUS nome','QGBT','QGBT nome']):continue
        else:
            # Approved transfer geometry. In mains/BUS service the two signals
            # are laid out in a series MB -> BUS -> TB path below.
            vbind={'TENSAO_REDE_PRESENTE_V_SVG':wire_name(deif,left),'TENSAO_GMG_PRESENTE_V_SVG':wire_name(deif,right)}
            if previous_image in vbind:img(e,vbind[previous_image])
            if previous_image and previous_image.startswith('TENSAO_SAIDA_PRESENTE'):
                vertical='_V_' in previous_image
                if mains_bus:img(e,uri=ui.wire(ui.MUTED,vertical))
                elif deif:img(e,'WIRE_OUT_V' if vertical else 'WIRE_OUT')
                elif tie:img(e,wire_name(False,'bus2',vertical))
                else:img(e,uri=ui.wire(ui.MUTED,vertical))
            if previous_image in ['MDB52_CONTATO_SVG','MDB53_CONTATO_SVG']:
                side=0 if previous_image=='MDB52_CONTATO_SVG' else 1
                img(e,('B1_SVG' if side==0 else 'B2_SVG') if deif else 'CONTACT_LED_'+('BUS' if tie else 'MAINS' if side==0 else 'BUS' if mains_bus else 'GEN')+'_SVG')
            if previous in ['K1_ESTADO','K2_ESTADO']:
                side=0 if previous=='K1_ESTADO' else 1
                metric(e,('B1_TEXT' if side==0 else 'B2_TEXT') if deif else 'CONTACT_LED_'+('MAINS' if side==0 else 'BUS' if mains_bus else 'GEN')+'_LABEL')
                e['config']['size']=8
                e['placement'].update(left=13 if side==0 else 63,right=63 if side==0 else 13,height=24)
            if name in ['Contato MDB52','Contato MDB53']:e['placement']['height']=84
            if name in ['Traço fluido 15','Traço fluido 21']:e['placement'].update(top=583,height=26)
            if name in ['Título MDB52','Título MDB53']:
                side=0 if name=='Título MDB52' else 1
                fixed_text(e,('MB / REDE' if side==0 else 'TB / BUS') if mains_bus else ('S1' if side==0 else 'S2') if profile.application=='ATS' else ('K1 / REDE' if side==0 else 'K2 / GMG'))
                e['config']['size']=9
            if name=='Intertravamento legenda':fixed_text(e,'BUS' if mains_bus or tie else 'QTA')
            if name=='Barramento responsivo':fixed_text(e,'BARRAMENTO / CARGA' if mains_bus or tie else 'SAÍDA / CARGA')
            if name=='Tensão barramento':fixed_text(e,'TENSÃO MEDIDA NO BUS' if mains_bus or tie else 'LEITURAS DO PERÍODO')
            if name=='Diagnóstico QTA':fixed_text(e,'INDICADORES DO CONTROLADOR' if not deif else 'ESTADO DE ALIMENTAÇÃO' if profile.application=='SGC420' else 'POSIÇÃO DOS DISJUNTORES')
            if name=='Traço fluido 23':continue
            if mains_bus:
                if name in ['Traço fluido 15','Traço fluido 24']:continue
                if name=='Traço fluido 21':img(e,uri=ui.wire(ui.MUTED,True))
            if tie and name in ['QTA responsivo','Contato MDB52','Contato MDB53','Título MDB52','Título MDB53','Posição MDB52','Posição MDB53','Estado MDB52','Estado MDB53','Intertravamento legenda','Traço fluido 15','Traço fluido 21','Traço fluido 24']:
                continue
        kept.append(e)
    if mains_bus:
        # Company -> MB -> measured common BUS -> TB -> load, never two
        # independent power sources feeding a fictitious transfer switch.
        measured=wire_name(deif,'bus');horizontal=wire_name(deif,'bus',False)
        kept += [ui.image('MB até BUS · descida',25,0,583,4,field_name=measured),
                 ui.image('MB até BUS · ponte',25,25,587,2,field_name=horizontal),
                 ui.image('MB até BUS · retorno',50,0,480,107,field_name=measured),
                 ui.image('BUS antes do TB',50,25,480,2,field_name=horizontal),
                 ui.image('TB até carga',50,25,609,2,uri=ui.wire(ui.MUTED,False))]
    if tie:
        kept += [ui.image('BUS1 até acoplador',25,18,526,2,field_name=wire_name(False,'bus',False)),
                 ui.image('Acoplador até BUS2',57,18,526,2,field_name=wire_name(False,'bus2',False)),
                 ui.box('Caixa do acoplador',40,20,493,82,ui.SURFACE,'#294256'),
                 ui.text('Título do acoplador',40,20,497,15,'ACOPLADOR',8),
                 ui.image('Contato do acoplador',43,14,514,30,field_name='CONTACT_LED_TIE_SVG'),
                 ui.text('Estado do acoplador',40,20,549,18,size=8,field_name='CONTACT_LED_TIE_LABEL'),
                 ui.image('BUS2 para carga',75,0,527,82,field_name=wire_name(False,'bus2')),
                 ui.image('BUS2 ponte carga',50,25,609,2,field_name=wire_name(False,'bus2',False))]
    p['options']['root']['elements']=kept
    return p


def caption(c):
    role=c.role
    for suffix,label in [('v_l1n','L1–N · V'),('v_l2n','L2–N · V'),('v_l3n','L3–N · V'),('v_l1l2','L1–L2 · V'),('v_l2l3','L2–L3 · V'),('v_l3l1','L3–L1 · V'),('i_l1','L1 · A'),('i_l2','L2 · A'),('i_l3','L3 · A'),('i_earth','Terra · A'),('frequency','Frequência'),('kw_l1','L1 · kW'),('kw_l2','L2 · kW'),('kw_l3','L3 · kW'),('kva_l1','L1 · kVA'),('kva_l2','L2 · kVA'),('kva_l3','L3 · kVA'),('kvar_l1','L1 · kvar'),('kvar_l2','L2 · kvar'),('kvar_l3','L3 · kvar'),('fp_l1','L1 · FP'),('fp_l2','L2 · FP'),('fp_l3','L3 · FP'),('kw','Ativa · kW'),('kva','Aparente · kVA'),('kvar','Reativa · kvar'),('fp','FP médio')]:
        if role.endswith('_'+suffix):return label
    return {'oil_pressure':'Pressão óleo','coolant':'Temp. água','oil_temperature':'Temp. óleo','battery':'Bateria','rpm':'Rotação','fuel':'Nível diesel','charge':'Alternador','charge_voltage':'Alternador','hour_meter':'Horímetro','starts':'Partidas','alarm_count':'Total de alarmes','alarm_unack':'Não reconhecidos','alarm_active_ack':'Ativos reconhecidos'}.get(role,c.name)


def group(profile,id,title,cs,pos,height=412,cols=2,entries=None):
    entries=entries or [(caption(c),ui.field(c),'NOME_'+c.column.upper() if c.label_variable else None) for c in cs]
    es=[]
    accent=copy.deepcopy(next(p for p in ui.reference()['panels'] if p['id']==21)['options']['root']['elements'][1])
    es.append(accent);rows=max(1,math.ceil(len(entries)/cols));cell=(height-24)/rows-7
    for i,(label,value,label_field) in enumerate(entries):
        x=2+(i%cols)*96/cols;w=96/cols-2;y=12+(i//cols)*(cell+7)
        es += [ui.box('Cartão '+str(i),x,w,y,cell,ui.SURFACE,'#263c4f'),
               ui.text('Rótulo '+str(i),x+2,w-4,y+7,24,label,9,field_name=label_field),
               ui.text('Leitura '+str(i),x+2,w-4,y+33,28,size=14 if cols>=4 else 16 if cols==3 else 19,color=ui.INK,field_name=value)]
        if value in ['MODE','MODO_CURTO','ALARM_TEXT','MAINTENANCE','B1_TEXT','B2_TEXT']:es[-1]['config']['size']=11
        if value=='MAINTENANCE':
            es[-1]['config']['size']=10;es[-1]['placement']['height']=36
    p=ui.canvas(profile,id,title,pos,es,height);p['fieldConfig']=config(profile)
    return p


def simple_stat(profile,id,title,name):
    return {'id':id,'type':'stat','title':title,'datasource':{'type':'datasource','uid':'-- Dashboard --'},'targets':[{'refId':'A','panelId':1,'withTransforms':False}],
            'gridPos':{},'fieldConfig':config(profile),'transformations':[{'id':'filterFieldsByName','options':{'include':{'names':[name]}}}],
            'options':{'reduceOptions':{'calcs':['lastNotNull'],'fields':'/.*/','values':False},'orientation':'auto','textMode':'value','colorMode':'value','graphMode':'none','justifyMode':'center','text':{'valueSize':24}}}


def apply(profile,dashboard):
    if profile.kind=='legacy':
        if profile.model=='DSE8610':
            for p in dashboard['panels']:
                if p['id']==1:
                    p['gridPos']['h']=27
                    p['options']['root']['placement']['height']=966
                    p['options']['root']['elements'][0]['placement']['height']=966
                elif p['id']==21:p['gridPos']['h']=16
                else:p['gridPos']['y']+=1
                for child in p.get('panels',[]):child['gridPos']['y']+=1
        return dashboard
    deif=profile.vendor=='DEIF';rs={c.role:c for c in profile.channels};old=dashboard['panels'];source=next(p for p in old if p['id']==1)
    main=overview(profile,source)
    first='gen' if 'gen_frequency' in rs else 'mains' if 'mains_frequency' in rs else 's1' if 's1_frequency' in rs else 'bus'
    secondary='bus' if first=='mains' else 'bus2' if first=='bus' else 's2' if first=='s1' else None
    primary=[c for c in profile.channels if c.role.startswith(first+'_') and ('_v_' in c.role or '_i_' in c.role or c.role==first+'_frequency')]
    motor=[c for c in profile.channels if c.role in ['oil_pressure','coolant','oil_temperature','fuel','fuel_litres','charge','charge_voltage','battery','rpm']]
    if not primary:primary=motor
    second=[c for c in profile.channels if secondary and c.role.startswith(secondary+'_') and ('_v_' in c.role or '_i_' in c.role or c.role==secondary+'_frequency')] if secondary else motor
    order=['v_l1n','v_l2n','v_l3n','v_l1l2','v_l2l3','v_l3l1','i_l1','i_l2','i_l3','i_earth','frequency']
    def source_order(c):
        suffix=c.role.split('_',1)[-1]
        return order.index(suffix) if suffix in order else len(order)
    primary.sort(key=source_order)
    if secondary:second.sort(key=source_order)
    if profile.topology=='engine' or not second:second=[c for c in profile.channels if c.role.startswith('maintenance_') or c.role in ['hour_meter','relative_hours','starts']]
    title_primary='Motor · instrumentação' if profile.topology=='engine' else ('Gerador' if first=='gen' else 'Companhia' if first=='mains' else 'Fonte S1' if first=='s1' else 'BUS 1')+' · tensão e corrente'
    panels=[main,group(profile,9701,'02 / '+title_primary,primary,{'x':12,'y':0,'w':12,'h':16},564,3),
            group(profile,9702,'03 / '+('BUS 2' if secondary=='bus2' else 'Barramento / BUS' if secondary=='bus' else 'Fonte S2' if secondary=='s2' else 'Motor e combustível'),second,{'x':12,'y':16,'w':12,'h':11},374,3 if secondary else 2)]
    period=[copy.deepcopy(p) for p in old if p['type']=='stat' and p.get('datasource',{}).get('uid')!='-- Dashboard --']
    if deif:
        power='POWER';fp=rs.get(first+'_fp');energy=next((c for c in profile.channels if c.role=='energy_'+first),None)
        stats=[simple_stat(profile,9800,'POTÊNCIA ATIVA / '+('CARGA' if profile.application=='SGC420' else 'FONTE'),power)]
        if fp:stats.append(simple_stat(profile,9801,'FATOR DE POTÊNCIA',field(fp)))
        if 'hour_meter' in rs or profile.application=='SGC420':stats.append(simple_stat(profile,9802,'HORÍMETRO / ACUMULADO','HOURS'))
        if energy:stats.append(simple_stat(profile,9803,'ENERGIA / ACUMULADA',field(energy)))
        stats+=period
    else:stats=[copy.deepcopy(p) for p in old if p['type']=='stat' and not (16<=p['id']<=18)]
    # Keep the approved compact strip, including period cards; additional
    # counters use another compact row, never a giant full-width stat.
    for i,p in enumerate(stats):
        p['gridPos']={'x':(i%6)*4,'y':27+(i//6)*3,'w':4,'h':3}
        p.setdefault('options',{}).setdefault('text',{})['valueSize']=24
        reference_stat=next(x for x in ui.reference()['panels'] if x['id']==10+i%6)
        p.setdefault('fieldConfig',{}).setdefault('defaults',{})['color']=copy.deepcopy(reference_stat['fieldConfig']['defaults']['color'])
        panels.append(p)
    y=27+max(1,math.ceil(len(stats)/6))*3;pid=9900
    powers=[]
    for prefix in ['gen','mains','bus','bus2','s1','s2','load']:
        cs=[c for c in profile.channels if c.role.startswith(prefix+'_') and any(c.role==prefix+'_'+m or c.role.startswith(prefix+'_'+m+'_') for m in ['kw','kva','kvar','fp'])]
        if cs:powers.append(({'gen':'Gerador','mains':'Companhia','bus':'BUS 1','bus2':'BUS 2','s1':'Fonte S1','s2':'Fonte S2','load':'Carga'}[prefix]+' · potências e FP',cs,3))
    counters=[c for c in profile.channels if c.role in ['hour_meter','relative_hours','starts','maintenance_general','alarm_count','alarm_unack','alarm_active_ack'] or c.role.startswith(('energy_','maintenance_'))]
    if counters:powers.append(('Operação e manutenção' if motor else 'Energia e operação',counters,2))
    powers=[(title+(' · '+str(i//limit+1) if len(cs)>limit else ''),cs[i:i+limit],cols) for title,cs,cols in powers for limit in [12 if cols==3 else 8] for i in range(0,len(cs),limit)]
    for i,(title,cs,cols) in enumerate(powers):
        panels.append(group(profile,pid,title,cs,{'x':(i%2)*12,'y':y+(i//2)*12,'w':12,'h':12},412,cols));pid+=1
    y+=math.ceil(len(powers)/2)*12
    maintenance=[copy.deepcopy(p) for p in old if p['type']=='stat' and 16<=p['id']<=18] if not deif else []
    for i,p in enumerate(maintenance):p['gridPos']={'x':i*8,'y':y,'w':8,'h':4};panels.append(p)
    if maintenance:y+=4
    if deif:
        entries=[('Modo de operação','MODE',None),('Alarmes','ALARM_TEXT',None)]
        if 'maintenance_1' in rs or profile.application=='SGC420':entries.append(('Manutenção','MAINTENANCE',None))
        else:entries.append(('Alimentação DC',field(rs.get('battery')),None))
        entries += [('Fonte 1','B1_TEXT',None),('Fonte 2','B2_TEXT',None)]
        controls=[]
    else:
        controls=[c for c in profile.channels if c.role in ['mode','warning','trip','shutdown'] or c.role.startswith('led_')]
        entries=[(caption(c),'MODO_CURTO' if c.role=='mode' else ui.field(c),None) for c in controls]
    inputs=[c for c in profile.channels if c.input_letter and c.group!='Entradas flexíveis']
    panels.append(group(profile,pid,'Controle e alarmes',controls,{'x':0,'y':y,'w':12,'h':12},412,2,entries));pid+=1
    if profile.application=='SGC420':
        inp_entries=[('Entrada '+letter,'INPUT_'+letter,'NOME_ENTRADA_'+letter) for letter in 'ABCDEFGH']
        panels.append(group(profile,pid,'Entradas digitais',[],{'x':12,'y':y,'w':12,'h':12},412,2,inp_entries))
    else:panels.append(group(profile,pid,'Entradas digitais',inputs[:8],{'x':12,'y':y,'w':12,'h':12},412,2))
    pid+=1;y+=12
    if profile.application=='SGC420':
        remaining=[('Entrada '+letter,'INPUT_'+letter,'NOME_ENTRADA_'+letter) for letter in 'IJKLMNOP']
        panels.append(group(profile,pid,'Entradas digitais I–P',[],{'x':0,'y':y,'w':24,'h':6},220,4,remaining));pid+=1;y+=6
    elif len(inputs)>8:
        panels.append(group(profile,pid,'Entradas digitais · continuação',inputs[8:],{'x':0,'y':y,'w':24,'h':6},220,3));pid+=1;y+=6
    extra=[c for c in profile.channels if c.group=='Entradas flexíveis' or c.role.startswith('analog_')]
    if extra:
        h=max(6,math.ceil(len(extra)/3)*3)
        panels.append(group(profile,pid,'Entradas flexíveis e sensores',extra,{'x':0,'y':y,'w':24,'h':h},h*34,3));pid+=1;y+=h
    for table in [copy.deepcopy(p) for p in old if p['type']=='table']:
        table['gridPos']={'x':0,'y':y,'w':24,'h':9};panels.append(table);y+=9
    histories=[copy.deepcopy(p) for p in old if p['type']=='row']
    for row in histories:
        row['title']='HISTÓRICOS E ALERTAS — expandir / recolher';row['gridPos']={'x':0,'y':y,'w':24,'h':1}
        offset=y+1
        for p in row.get('panels',[]):p['gridPos']['y']=offset;offset+=p['gridPos']['h']
        panels.append(row);y=offset
    dashboard['panels']=sorted(panels,key=lambda p:(p['gridPos']['y'],p['gridPos']['x']))
    dashboard['tags']=[*dashboard.get('tags',[]),'Padrão DSE7420']
    return dashboard
