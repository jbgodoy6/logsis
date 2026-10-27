"""DEIF dashboards generated from the same channel contract as each exported BIN.

Only PostgreSQL read queries and Grafana native Canvas. A single dashboard
adapts to narrow displays; no external images, SQL functions or mobile copy.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path

from .codecs import sql_value
from .manual_dashboard import (assets,box,text,image,canvas,group,properties,svg,
    sq,var,numeric,wire,radio,signal,reference,INK,MUTED,RED,BG,SURFACE)

BLUE='#0879cc'
YELLOW='#ffbf19'


def roles(profile):return {c.role:c for c in profile.channels}
def f(c):return '"MDB'+f'{c.number:02}'+'"' if c else 'NULL::numeric'
def ident(value):return '"'+value.replace('"','""')+'"'
def bit(expr,n):return f'((({expr})::bigint >> {n}) & 1)'
def raw(c,alias='payload'):return numeric(alias+'->>'+sq(c.column))
def decoded(c,alias='payload'):return sql_value(c,raw(c,alias))
def sgc_alarms():
    return json.loads((Path(__file__).parent/'resources/sgc420_alarms.json').read_text())
def agc_alarms(app):
    return json.loads((Path(__file__).parent/'resources/agc150_alarms.json').read_text())[app]


def fields_sql(profile):
    return ','.join(decoded(c)+' AS '+f(c) for c in profile.channels)


def value_expressions(profile):
    rs=roles(profile)
    def r(name):return f(rs.get(name))
    status=r('status_word');mode=r('mode_word')
    output=[]
    if profile.application=='SGC420':
        code=f'((({status})::bigint >> 11)&7)'
        output.append(f"CASE WHEN {status} IS NULL THEN 'SEM DADOS' WHEN {bit(status,15)}=1 THEN 'CONFIGURAÇÃO' WHEN {code}=4 THEN 'MANUAL' WHEN {code}=5 THEN 'AUTO' WHEN {code}=6 THEN 'AGENDADO' ELSE 'MODO '||({code})::text END AS \"MODE\"")
        # Load flags are explicitly identified as logical feeding state.
        for alias,n in [('B1',10),('B2',9)]:output.append(f'CASE WHEN {status} IS NULL THEN NULL ELSE {bit(status,n)} END AS "{alias}"')
        output.append(f'''CASE WHEN {r('hours_hi')} IS NOT NULL AND {r('hours_lo')} IS NOT NULL
            AND {r('hours_minutes')} BETWEEN 0 AND 59 THEN {r('hours_hi')}*65536+{r('hours_lo')}+{r('hours_minutes')}/60 END AS "HOURS"''')
        for alias,n in [('warning',1),('trip',2),('shutdown',3)]:output.append(f'{bit(status,n)} AS "{alias}"')
        output.append(f'(({r("alarm_word_76")}::bigint >> 8)&15) AS "SERVICE_STATUS"')
        for alarm in sgc_alarms():
            output.append(f'(({r("alarm_word_"+str(alarm["address"]))}::bigint >> {alarm["shift"]})&15) AS "ALARM_{alarm["address"]}_{alarm["shift"]}"')
    else:
        if profile.application=='ATS':
            manual,auto=r('mode_manual'),r('mode_auto')
            modecase=f"CASE WHEN {manual} IS NULL OR {auto} IS NULL THEN 'SEM DADOS' WHEN {manual}+{auto}>1 THEN 'INCOERENTE' WHEN {auto}=1 THEN 'AUTO' WHEN {manual}=1 THEN 'MANUAL' WHEN {bit(mode,0)}=1 THEN 'BLOCK' ELSE 'OUTRO MODO' END"
        else:
            manualbit=1 if profile.application.startswith('CGC') else 2
            bits=[0,manualbit,3,4] if profile.application not in ['ENG'] else [0,manualbit,3]
            terms=[bit(mode,n) for n in bits]
            modecase=f"CASE WHEN {mode} IS NULL THEN 'SEM DADOS' WHEN "+'+'.join(terms)+">1 THEN 'INCOERENTE' "+''.join(f'WHEN {bit(mode,n)}=1 THEN {sq(label)} ' for n,label in [(0,'BLOCK'),(manualbit,'MANUAL'),(3,'AUTO')]+([(4,'TESTE')] if 4 in bits else []))+"ELSE 'OUTRO MODO' END"
        output.append(modecase+' AS "MODE"')
        for alias,on,off in [('B1',1,12),('B2',4,11)]:
            if profile.application in ['ENG','ATS'] or (profile.model=='CGC412' and alias=='B1'):
                expr='NULL::numeric'
            else:
                a,b=bit(status,on),bit(status,off)
                expr=f'CASE WHEN {status} IS NULL THEN NULL WHEN {a}=1 AND {b}=0 THEN 1 WHEN {a}=0 AND {b}=1 THEN 0 WHEN {a}=1 AND {b}=1 THEN 3 ELSE NULL END'
            output.append(expr+f' AS "{alias}"')
        output.append(r('hour_meter')+' AS "HOURS"')
        output += ['NULL::numeric AS "'+name+'"' for name in ['warning','trip','shutdown','SERVICE_STATUS']]
    # SGC values are load measurements; do not relabel as generator measurements.
    output.append(r('load_kw' if profile.application=='SGC420' else 'gen_kw' if profile.application in ['GEN','CGC412','CGC413'] else 'mains_kw' if profile.application=='MAINS' else 's1_kw')+' AS "POWER"')
    return output


def switch(state,vertical=True):
    color=RED if state==1 else MUTED
    if vertical:
        a,b=(50,12),(50,38);end=b if state==1 else (70,32);fixed='M50 0 V12 M50 38 V50'
    else:
        a,b=(26,25),(74,25);end=b if state==1 else (69,8);fixed='M0 25 H26 M74 25 H100'
    blade=f'M{a[0]} {a[1]} L{end[0]} {end[1]}' if state in (0,1) else ''
    unknown=f'<text x="50" y="30" text-anchor="middle" fill="{MUTED}" font-size="15">?</text>' if state not in (0,1) else ''
    return svg(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><rect x="3" y="2" width="94" height="46" rx="8" fill="{SURFACE}" stroke="#2b4c68"/><path d="{fixed} {blade}" stroke="{color}" stroke-width="3" fill="none"/><circle cx="{a[0]}" cy="{a[1]}" r="3" fill="{INK}"/><circle cx="{b[0]}" cy="{b[1]}" r="3" fill="{INK}"/>{unknown}</svg>')


def main_sql(profile):
    rs=roles(profile)
    labels=[var(c.label_variable)+f' AS "NOME_{c.column.upper()}"' for c in profile.channels if c.label_variable]
    # Read a coherent snapshot: never mix switch samples from different rows.
    raw_sql=f'''WITH sample AS (SELECT t."time",to_jsonb(t) AS payload FROM $Id_Logsis t
        WHERE $__timeFilter("time") ORDER BY "time" DESC LIMIT 1), decoded AS MATERIALIZED (
        SELECT {fields_sql(profile)},
        {numeric("payload->>'gsm_rssi'")} AS gsm, {numeric("payload->>"+var('Campo_WiFi_RSSI'))} AS wifi,
        to_char(CASE WHEN pg_typeof("time")='timestamp without time zone'::regtype
          THEN ("time"::timestamp AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo'
          ELSE "time"::timestamptz AT TIME ZONE 'America/Sao_Paulo' END,'DD/MM HH24:MI') AS "LAST_TIME"
        FROM (SELECT (SELECT "time" FROM sample) AS "time",(SELECT payload FROM sample) AS payload) s), states AS MATERIALIZED (
        SELECT decoded.*,{','.join(value_expressions(profile)+labels)} FROM decoded),
        checks AS MATERIALIZED (SELECT states.*,'''
    additions=[]
    for prefix in ['gen','mains','bus','s1','s2']:
        volt=[f(c) for role,c in rs.items() if role.startswith(prefix+'_v_')]
        expr=('CASE WHEN '+' OR '.join(v+'>=30' for v in volt)+' THEN 1 WHEN '+' AND '.join(v+'<30' for v in volt)+' THEN 0 END') if volt else 'NULL::numeric'
        additions.append(expr+' AS "V_'+prefix+'"')
    if profile.application=='SGC420':
        native=[a for a in sgc_alarms() if not a['maintenance'] and not a['reserved']]
        branches=[]
        for code,level in [(3,3),(4,2),(2,1)]:
            branches.append('WHEN '+' OR '.join(f'"ALARM_{a["address"]}_{a["shift"]}"={code}' for a in native)+' THEN '+str(level))
        complete=' AND '.join(f(rs[role])+' IS NOT NULL' for role in rs if role.startswith('alarm_word_'))
        maintenance=' OR '.join(f'"ALARM_{a["address"]}_{a["shift"]}" IN (2,3,4,5)' for a in sgc_alarms() if a['maintenance'])
        additions.append('CASE '+' '.join(branches)+f' WHEN ({complete}) AND ({maintenance}) THEN 0 WHEN "shutdown"=1 THEN 3 WHEN "trip"=1 THEN 2 WHEN "warning"=1 THEN 1 WHEN "warning" IS NULL THEN NULL ELSE 0 END AS "ALARM_LEVEL"')
        additions.append('CASE WHEN "SERVICE_STATUS" IN (2,3,4,5) THEN '+var('Nome_Manutencao_Filtro')+" || ' · ATIVA' WHEN \"SERVICE_STATUS\"=1 THEN "+var('Nome_Manutencao_Filtro')+" || ' · EM DIA' WHEN \"SERVICE_STATUS\"=0 THEN 'MANUTENÇÃO · DESABILITADA' ELSE 'MANUTENÇÃO · SEM DADOS' END AS \"MAINTENANCE\"")
    else:
        alarm=f(rs.get('alarm_count'))
        if 'fail_class_word' in rs:
            fail=f(rs['fail_class_word'])
            native=agc_alarms(profile.application)
            other=' OR '.join(bit(f(rs['alarm_word_'+str(a['address'])]),a['bit'])+'=1' for a in native if not a['maintenance']) or 'false'
            maintenance=' OR '.join(bit(f(rs['alarm_word_'+str(a['address'])]),a['bit'])+'=1' for a in native if a['maintenance']) or 'false'
            complete=' AND '.join(f(rs['alarm_word_'+str(addr)])+' IS NOT NULL' for addr in sorted({a['address'] for a in native})) or 'true'
            red=' OR '.join(bit(fail,n)+'=1' for n in ([4,6] if profile.application=='GEN' else [4] if profile.application=='ENG' else [])) or 'false'
            trip=' OR '.join(bit(fail,n)+'=1' for n in ([2,3,5,7,8] if profile.application=='GEN' else [7] if profile.application=='MAINS' else [])) or 'false'
            additions.append(f'''CASE WHEN {fail} IS NULL THEN NULL
              WHEN ({complete}) AND ({maintenance}) AND NOT ({other}) THEN 0
              WHEN {red} THEN 3 WHEN {trip} THEN 2 WHEN {bit(fail,1)}=1 THEN 1
              WHEN {fail}>0 OR {alarm}>0 THEN 4 ELSE 0 END AS "ALARM_LEVEL"''')
        else:additions.append(f'CASE WHEN {alarm}>0 THEN 4 WHEN {alarm}=0 THEN 0 END AS "ALARM_LEVEL"')
        maint='CASE '
        for i in [1,2]:
            c=rs.get('maintenance_'+str(i))
            if c:
                name=var(c.label_variable)
                active=bit(f(rs.get('service_word')),i-1) if profile.application.startswith('CGC') else f(rs.get('service_alarm_'+str(i)))
                maint+=f"WHEN {active}=1 OR {f(c)}<=0 THEN {name} || ' · VENCIDA' "
        for i in [1,2]:
            c=rs.get('maintenance_'+str(i))
            if c:maint+=f"WHEN {f(c)}>0 AND {f(c)}<={var('Manutencao_Alerta_h')}::numeric THEN {var(c.label_variable)} || ' · PRÓXIMA' "
        if any(role.startswith('maintenance_') for role in rs):
            nulls=' OR '.join(f(rs['maintenance_'+str(i)])+' IS NULL' for i in [1,2])
            maint+=f"WHEN {nulls} THEN 'MANUTENÇÃO · SEM DADOS' ELSE 'MANUTENÇÃO · EM DIA' END"
        else:maint="'MANUTENÇÃO · NÃO APLICÁVEL'"
        additions.append(maint+' AS "MAINTENANCE"')
    raw_sql+=','.join(additions)+' FROM states) SELECT checks.*,'
    extras=[]
    for prefix in ['gen','mains','bus','s1','s2']:
        extras.append(f'CASE WHEN "V_{prefix}"=1 THEN {sq(wire(RED,False))} ELSE {sq(wire(MUTED,False))} END AS "WIRE_{prefix}"')
        extras.append(f'CASE WHEN "V_{prefix}"=1 THEN {sq(wire(RED,True))} ELSE {sq(wire(MUTED,True))} END AS "WIRE_{prefix}_V"')
    if profile.application=='SGC420':
        for i,letter in enumerate('ABCDEFGHIJKLMNOP'):
            extras.append(f'{bit(f(rs["input_word"]),15-i)} AS "INPUT_{letter}"')
    for alias in ['B1','B2']:
        suffix='NA CARGA' if profile.application=='SGC420' else 'FECHADO'
        off='FORA DA CARGA' if profile.application=='SGC420' else 'ABERTO'
        extras.append(f'''CASE "{alias}" WHEN 1 THEN {sq(suffix)} WHEN 0 THEN {sq(off)} WHEN 3 THEN 'INCOERENTE' ELSE 'SEM DADOS' END AS "{alias}_TEXT"''')
        extras.append(f'CASE "{alias}" WHEN 1 THEN {sq(switch(1,profile.topology=="transfer"))} WHEN 0 THEN {sq(switch(0,profile.topology=="transfer"))} ELSE {sq(switch(None,profile.topology=="transfer"))} END AS "{alias}_SVG"')
    extras.append('CASE '+''.join(f'WHEN "ALARM_LEVEL"={n} THEN {sq(assets()[name])} ' for n,name in [(3,'shutdown'),(2,'trip'),(1,'warning')])+'ELSE '+sq(assets()['gen'])+' END AS "GENERATOR_SVG"')
    extras.append('CASE "ALARM_LEVEL" WHEN 0 THEN \'SEM ALARME\' WHEN 1 THEN \'WARNING\' WHEN 2 THEN \'TRIP ELÉTRICO\' WHEN 3 THEN \'SHUTDOWN\' WHEN 4 THEN \'ALARMES REGISTRADOS\' ELSE \'ALARMES · SEM DADOS\' END AS "ALARM_TEXT"')
    extras.append('CASE '+''.join(f'WHEN gsm>={threshold} AND gsm<0 THEN {sq(signal(level))} ' for threshold,level in [(-80,5),(-90,4),(-100,3),(-110,2),(-140,1)])+'ELSE '+sq(signal(0))+' END AS "GSM_ICON"')
    extras.append(f'CASE WHEN wifi BETWEEN -140 AND -1 THEN {sq(radio(True))} ELSE {sq(radio(True,MUTED))} END AS "WIFI_ICON"')
    extras.append("CASE WHEN gsm BETWEEN -140 AND -1 THEN gsm END AS \"GSM\"")
    extras.append("CASE WHEN wifi BETWEEN -140 AND -1 THEN wifi END AS \"WIFI\"")
    # Downstream red requires a measured source and a coherent closed feedback.
    if profile.topology=='transfer':
        p1='s1' if profile.application=='ATS' else 'mains';p2='s2' if profile.application=='ATS' else 'gen'
        condition=f'("B1"=1 AND "V_{p1}"=1) OR ("B2"=1 AND "V_{p2}"=1)'
    else:
        condition='"V_bus"=1' if profile.topology=='mains_bus' else '("B2"=1 AND "V_gen"=1) OR "V_bus"=1'
    extras.append(f'CASE WHEN {condition} THEN {sq(wire(RED,False))} ELSE {sq(wire(MUTED,False))} END AS "WIRE_OUT"')
    extras.append(f'CASE WHEN {condition} THEN {sq(wire(RED,True))} ELSE {sq(wire(MUTED,True))} END AS "WIRE_OUT_V"')
    # Respect validity flags instead of displaying invalid EIC readings.
    for role,flag in [('coolant','valid_coolant'),('oil_pressure','valid_oil')]:
        if flag in rs:extras.append(f'CASE WHEN {f(rs[flag])}=1 THEN {f(rs[role])} END AS "VALID_{role}"')
    return raw_sql+','.join(extras)+' FROM checks'


def period_sql(profile,c=None,hours=False):
    if hours and profile.application=='SGC420':
        rs=roles(profile);h,l,m=[decoded(rs[k]) for k in ['hours_hi','hours_lo','hours_minutes']]
        value=f'CASE WHEN {m} BETWEEN 0 AND 59 THEN {h}*65536+{l}+{m}/60 END'
    else:value=decoded(c)
    unit='h' if hours else c.unit
    return f'''WITH readings AS NOT MATERIALIZED (SELECT t."time",{value} AS v FROM $Id_Logsis t
      CROSS JOIN LATERAL (SELECT to_jsonb(t) AS payload) p WHERE t."time"<=$__timeTo()),
    prior AS (SELECT * FROM readings WHERE "time"<=$__timeFrom() AND v>=0 ORDER BY "time" DESC,v LIMIT 1),
    inside AS (SELECT * FROM readings WHERE $__timeFilter("time") AND v>=0),
    first_inside AS (SELECT * FROM inside ORDER BY "time",v LIMIT 1),
    base AS (SELECT * FROM prior WHERE v<=(SELECT v FROM first_inside)
      UNION ALL SELECT * FROM first_inside WHERE NOT EXISTS(SELECT 1 FROM prior WHERE v<=first_inside.v)),
    points AS (SELECT "time",min(v) AS v,count(DISTINCT v)>1 AS conflict FROM (
      SELECT * FROM inside UNION ALL SELECT * FROM base) p GROUP BY "time"),
    steps AS (SELECT *,lag(v) OVER(ORDER BY "time") AS prev FROM points),
    totals AS (SELECT count(*) AS n,bool_or(conflict) AS conflict,count(*) FILTER(WHERE v<prev) AS drops,
      (SELECT v FROM points ORDER BY "time" DESC LIMIT 1)-(SELECT v FROM base) AS delta FROM steps)
    SELECT CASE WHEN n>=2 AND delta>=0 AND NOT conflict THEN delta END AS "VALUE",
      CASE WHEN n<2 THEN 'SEM AMOSTRAS SUFICIENTES' WHEN conflict THEN 'AMOSTRAS CONFLITANTES'
      WHEN delta<0 THEN 'CONTADOR REINICIOU' WHEN drops>0 THEN 'QUEDA NO CONTADOR · PARCIAL'
      WHEN NOT EXISTS(SELECT 1 FROM prior WHERE v<=(SELECT v FROM first_inside)) THEN 'SEM BASE ANTERIOR · PARCIAL' ELSE 'OK' END AS "STATUS",
      CASE WHEN n>=2 AND delta>=0 AND NOT conflict THEN to_char(delta,'FM999999999990.00') || ' {unit}' ||
        CASE WHEN drops>0 OR NOT EXISTS(SELECT 1 FROM prior WHERE v<=(SELECT v FROM first_inside)) THEN ' *' ELSE '' END ELSE '—' END AS "EXIBICAO" FROM totals'''


def panel_properties(profile):
    config=properties(profile)
    for c in profile.channels:
        if 'configurado' in c.unit or c.unit=='-':
            config['overrides'].append({'matcher':{'id':'byName','options':f(c).strip('"')},'properties':[{'id':'unit','value':'none'}]})
    for name,unit,dec in [('HOURS','suffix: h',2),('POWER','suffix: kW',2),('GSM','suffix: dBm',0),('WIFI','suffix: dBm',0)]:
        config['overrides'].append({'matcher':{'id':'byName','options':name},'properties':[{'id':'unit','value':unit},{'id':'decimals','value':dec}]})
    for name in ['INPUT_'+letter for letter in 'ABCDEFGHIJKLMNOP']+[f(c).strip('"') for c in profile.channels if c.codec=='boolean']:
        config['overrides'].append({'matcher':{'id':'byName','options':name},'properties':[{'id':'mappings','value':[{'type':'value','options':{'0':{'text':'INATIVO','color':MUTED},'1':{'text':'ATIVO','color':BLUE}}}]}]})
    return config


def reading_group(profile,*args,**kwargs):
    p=group(profile,*args,**kwargs)
    p['fieldConfig']=panel_properties(profile)
    # Technical MDB identifiers belong in the Studio/map, not over the values.
    p['options']['root']['elements']=[e for e in p['options']['root']['elements'] if not e['name'].startswith('Canal MDB')]
    starts={e['name'].removeprefix('Cartão '):e['placement']['top'] for e in p['options']['root']['elements'] if e['name'].startswith('Cartão ')}
    for e in p['options']['root']['elements']:
        if e['name'].startswith('Nome MDB'):
            key=e['name'].removeprefix('Nome ');e['placement'].update(top=starts[key]+4,height=28)
            label=e['config']['text'].get('fixed','')
            for prefix in ['Gerador · ','Companhia · ','Barramento · ','Fonte S1 · ','Fonte S2 · ','Carga · ']:label=label.removeprefix(prefix)
            label=label.replace('(TC/transdutor/PMS)','· TC/PMS').replace('Quantidade de alarmes','Total de alarmes').replace('Alarmes ativos reconhecidos','Ativos reconhecidos')
            e['config']['text']['fixed']=label
        elif e['name'].startswith('Valor MDB'):
            key=e['name'].removeprefix('Valor ');e['placement'].update(top=starts[key]+33,height=25);e['config']['size']=14
    return p


def overview(profile):
    rs=roles(profile);es=[]
    es += [box('Cabeçalho',1,98,8,58,SURFACE,'#25415b'),text('Marca',3,44,15,22,'LOGSIS  /  SISTEL',17,INK),text('Modelo',3,50,40,14,profile.label,10),text('Modo',58,17,18,24,size=12,color=YELLOW,field_name='MODE'),image('Wi-Fi',78,5,17,22,field_name='WIFI_ICON'),text('Sinal Wi-Fi',84,13,17,22,size=10,field_name='WIFI'),image('GSM',78,5,40,18,field_name='GSM_ICON'),text('Sinal GSM',84,13,40,18,size=10,field_name='GSM')]
    es[2]['config']['text']['fixed']='AGC150 · '+profile.application if profile.model.startswith('AGC150') else profile.label
    es[2]['config']['size']=9
    es[3]['placement'].update(left=52,right=25)
    es[3]['config']['size']=10
    # Three repeated columns fit even at mobile width: details continue below
    # in full-width responsive cards rather than shrinking an entire image.
    if profile.topology=='transfer':
        p1='s1' if profile.application=='ATS' else 'mains';p2='s2' if profile.application=='ATS' else 'gen'
        left_label='FONTE S1' if profile.application=='ATS' else 'COMPANHIA';right_label='FONTE S2' if profile.application=='ATS' else 'GERADOR'
        es += [text('Nome fonte 1',3,44,79,20,left_label,13,INK),text('Nome fonte 2',53,44,79,20,right_label,13,INK),image('Torre',6,38,107,105,assets()['tower']),image('Gerador',56,38,107,105,field_name='GENERATOR_SVG') if profile.application!='ATS' else image('Fonte S2',56,38,107,105,assets()['tower'])]
        for prefix,left in [(p1,3),(p2,53)]:
            available=[rs.get(prefix+'_v_l1n'),rs.get(prefix+'_v_l2n'),rs.get(prefix+'_v_l3n')]
            for j,c in enumerate(available):
                es.append(text('Fase '+prefix+str(j),left+j*14.5,14,220,13,'L'+str(j+1)+'–N',8))
                es.append(text('Tensão '+prefix+str(j),left+j*14.5,14,235,24,size=12,color=INK,field_name='MDB'+f'{c.number:02}' if c else None,label='—'))
            c=rs.get(prefix+'_frequency')
            es.append(text('Frequência '+prefix,left+8,28,262,21,size=11,field_name='MDB'+f'{c.number:02}' if c else None,label='—'))
            es.append(image('Antes da chave '+prefix,left+22,1,285,30,field_name='WIRE_'+prefix+'_V'))
        es += [image('Contato 1',12,26,315,44,field_name='B1_SVG'),image('Contato 2',62,26,315,44,field_name='B2_SVG'),text('Contato 1 estado',3,44,362,20,size=10,field_name='B1_TEXT'),text('Contato 2 estado',53,44,362,20,size=10,field_name='B2_TEXT'),image('Saída fonte 1',25,25,394,5,field_name='WIRE_OUT'),image('Saída fonte 2',50,25,394,5,field_name='WIRE_OUT'),image('Carga',33,34,416,100,assets()['load']),text('Carga nome',32,36,519,18,'CARGA',11,INK)]
        # The two source contacts are symmetric; each feeds the common output.
        es += [image('Ligação após contato 1',25,1,359,35,field_name='WIRE_OUT_V'),image('Ligação após contato 2',75,1,359,35,field_name='WIRE_OUT_V'),image('Ligação carga',50,1,399,17,field_name='WIRE_OUT_V')]
    else:
        source='mains' if profile.topology=='mains_bus' else 'gen'
        es += [text('Origem',3,45,84,22,'COMPANHIA' if source=='mains' else 'MOTOR' if profile.topology=='engine' else 'GERADOR',14,INK),image('Origem desenho',5,40,120,130,assets()['tower']) if source=='mains' else image('Gerador',5,40,120,130,field_name='GENERATOR_SVG')]
        if profile.topology!='engine':
            alias='B1' if source=='mains' else 'B2'
            es += [image('Antes do disjuntor',44,11,181,5,field_name='WIRE_'+source),image('Acoplamento',55,16,161,45,field_name=alias+'_SVG'),image('Barramento',71,25,181,5,field_name='WIRE_OUT'),image('Carga',57,39,267,127,assets()['load']),text('BUS título',53,44,221,20,'BARRAMENTO  →  CARGA',11,INK),text('Posição',44,52,404,20,size=11,field_name=alias+'_TEXT')]
        es.append(text('Modo operação',3,44,279,24,size=13,field_name='MODE'))
    es += [text('Alarme',2,96,548,22,size=12,color=YELLOW,field_name='ALARM_TEXT'),text('Manutenção',2,96,574,22,size=10,color=YELLOW,field_name='MAINTENANCE'),text('Último registro',2,96,607,17,'ÚLTIMO REGISTRO DO PERÍODO · BRASÍLIA',8),text('Horário',2,96,625,22,size=12,color=INK,field_name='LAST_TIME')]
    p=canvas(profile,1,'01 / Unifilar · '+profile.label,{'x':0,'y':0,'w':12,'h':20},es,660)
    p['datasource']={'type':'grafana-postgresql-datasource','uid':'zKW_ld27k'}
    p['targets']=[{'refId':'A','rawQuery':True,'format':'table','editorMode':'code','rawSql':main_sql(profile)}]
    p['fieldConfig']=panel_properties(profile)
    return p


def build_dashboard(profile):
    rs=roles(profile)
    variables=[{'name':name,'type':'constant','hide':2,'query':value,'skipUrlSync':True} for name,value in [('Id_Logsis','id_planta'),('Divisor_Energia','1'),('Campo_WiFi_RSSI','WiFi_rssi'),('Manutencao_Alerta_h','50')]]
    for c in profile.channels:
        if c.label_variable:variables.append({'name':c.label_variable,'label':c.name,'type':'constant','hide':2,'query':c.name,'skipUrlSync':True})
    if profile.application=='SGC420':variables.append({'name':'Nome_Manutencao_Filtro','label':'Nome manutenção','type':'constant','hide':2,'query':'Filtro / manutenção','skipUrlSync':True})
    panels=[overview(profile)]
    # Compact source cards immediately beside diagram on desktop, beneath it on mobile.
    summaries=[c for c in profile.channels if c.role in ['gen_kw','gen_kva','gen_kvar','gen_fp','load_kw','load_kva','load_kvar','mains_kw','mains_kva','mains_kvar','mains_fp','rpm','battery','coolant','oil_pressure','fuel']]
    panels.append(reading_group(profile,2,'02 / Leituras principais',summaries,{'x':12,'y':0,'w':12,'h':12},height=412,cols=2))
    for e in panels[-1]['options']['root']['elements']:
        if e['name'].startswith('Valor '):
            c=next((c for c in summaries if e['name']=='Valor MDB'+f'{c.number:02}'),None)
            if c and 'valid_'+c.role in rs:e['config']['text']['field']='VALID_'+c.role
    summary=[]
    last=('HORÍMETRO ACUMULADO','HOURS') if 'hour_meter' in rs or profile.application=='SGC420' else ('ALIMENTAÇÃO DC',f(rs['battery']).strip('"'))
    for i,(label,name) in enumerate([('MODO DE OPERAÇÃO','MODE'),('ALARMES','ALARM_TEXT'),('MANUTENÇÃO','MAINTENANCE'),last]):
        summary.extend([text('Título '+name,3,94,10+i*65,16,label,9),text('Resumo '+name,3,94,29+i*65,28,size=14,color=INK,field_name=name)])
    p=canvas(profile,3,'03 / Estado e manutenção',{'x':12,'y':12,'w':12,'h':8},summary,280);p['fieldConfig']=panel_properties(profile);panels.append(p)
    y=20;pid=10
    counters=[c for c in profile.channels if c.role.startswith('energy_')]
    if 'hour_meter' in rs or profile.application=='SGC420':
        counters=[rs.get('hour_meter')]+counters
    for i,c in enumerate(counters):
        hours=c is None or c.role=='hour_meter'
        p={'id':pid,'type':'stat','title':'HORAS / PERÍODO' if hours else c.name+' / PERÍODO','gridPos':{'x':(i%3)*8,'y':y+(i//3)*3,'w':8,'h':3},'datasource':{'type':'grafana-postgresql-datasource','uid':'zKW_ld27k'},'targets':[{'refId':'A','rawQuery':True,'format':'table','editorMode':'code','rawSql':period_sql(profile,c,hours)}],'fieldConfig':{'defaults':{'noValue':'—','color':{'mode':'fixed','fixedColor':BLUE}},'overrides':[]},'transformations':[{'id':'filterFieldsByName','options':{'include':{'names':['EXIBICAO']}}}],'options':{'reduceOptions':{'calcs':['lastNotNull'],'fields':'','values':False},'textMode':'value','colorMode':'value','graphMode':'none','text':{'valueSize':27}},'description':'Diferença cronológica com base válida anterior ao filtro. * indica período parcial ou queda no contador; STATUS detalha a situação.'}
        panels.append(p);pid+=1
        p['options']['reduceOptions']['fields']='/^EXIBICAO$/'
    y+=((len(counters)+2)//3)*3
    details=[(g,[c for c in profile.channels if c.group==g and c.codec!='word']) for g in dict.fromkeys(c.group for c in profile.channels) if g not in ['Controle','Diagnóstico','Alarmes nativos']]
    for i,(name,cs) in enumerate(details):
        if not cs:continue
        height=max(6,((len(cs)+1)//2)*3)
        p=reading_group(profile,pid,f'{pid:02} / '+name,cs,{'x':0,'y':y,'w':24,'h':height},height=height*34,cols=2)
        panels.append(p);pid+=1;y+=height
    # Inputs packed in words use derived fields and editable labels, not opaque binary numbers.
    if profile.application=='SGC420':
        inputs=[]
        for i,letter in enumerate('ABCDEFGHIJKLMNOP'):
            name='Nome_Entrada_'+letter;variables.append({'name':name,'label':'Entrada '+letter,'type':'constant','hide':2,'query':'Entrada '+letter,'skipUrlSync':True})
            inputs.extend([text('Nome entrada '+letter,3+(i%2)*49,45,10+(i//2)*48,16,'${'+name+'}',9),text('Estado entrada '+letter,3+(i%2)*49,45,27+(i//2)*48,22,size=12,field_name='INPUT_'+letter)])
        p=canvas(profile,pid,'Entradas digitais A–P',{'x':0,'y':y,'w':24,'h':12},inputs,410);panels.append(p);pid+=1;y+=12
        selects=[]
        for a in sgc_alarms():
            if a['reserved']:continue
            field=f'"ALARM_{a["address"]}_{a["shift"]}"'
            selects.append(f'SELECT {sq(a["name"])} AS "Alarme",CASE {field} WHEN 0 THEN \'DESABILITADO\' WHEN 1 THEN \'INATIVO\' WHEN 2 THEN \'WARNING\' WHEN 3 THEN \'SHUTDOWN\' WHEN 4 THEN \'TRIP ELÉTRICO\' WHEN 5 THEN \'NOTIFICAÇÃO\' ELSE \'SEM DADOS\' END AS "Estado" FROM snapshot')
        panels.append({'id':pid,'type':'table','title':'Alarmes detalhados · estados nativos','gridPos':{'x':0,'y':y,'w':24,'h':9},'datasource':{'type':'grafana-postgresql-datasource','uid':'zKW_ld27k'},'targets':[{'refId':'A','rawQuery':True,'format':'table','editorMode':'code','rawSql':'WITH snapshot AS ('+main_sql(profile)+') '+ ' UNION ALL '.join(selects)}],'fieldConfig':{'defaults':{'noValue':'—'},'overrides':[]},'options':{'showHeader':True}});pid+=1;y+=9
    if 'fail_class_word' in rs:
        selects=[]
        for a in agc_alarms(profile.application):
            flag=bit(f(rs['alarm_word_'+str(a['address'])]),a['bit'])
            selects.append(f'SELECT {sq(a["name"])} AS "Alarme",CASE {flag} WHEN 1 THEN \'ATIVO\' WHEN 0 THEN \'INATIVO\' ELSE \'SEM DADOS\' END AS "Estado" FROM snapshot')
        panels.append({'id':pid,'type':'table','title':'Alarmes nativos · estado por proteção','gridPos':{'x':0,'y':y,'w':24,'h':9},'datasource':{'type':'grafana-postgresql-datasource','uid':'zKW_ld27k'},'targets':[{'refId':'A','rawQuery':True,'format':'table','editorMode':'code','rawSql':'WITH snapshot AS ('+main_sql(profile)+') SELECT * FROM ('+' UNION ALL '.join(selects)+') alarms ORDER BY ("Estado"=\'ATIVO\') DESC,"Alarme"'}],'fieldConfig':{'defaults':{'noValue':'—'},'overrides':[]},'options':{'showHeader':True}});pid+=1;y+=9
    history=[]
    for prefix,caption in [('gen','Gerador'),('mains','Companhia'),('bus','Barramento'),('s1','Fonte S1'),('s2','Fonte S2'),('load','Carga')]:
        cs=[c for role,c in rs.items() if role.startswith(prefix+'_') and any(t in role for t in ['_v_','_i_','_kw','_fp'])]
        if not cs:continue
        for suffix,group_title in [('_v_','tensões'),('_i_','correntes'),('_kw','potência'),('_fp','FP')]:
            chosen=[c for c in cs if suffix in c.role]
            if not chosen:continue
            targets=[{'refId':chr(65+j),'rawQuery':True,'format':'time_series','editorMode':'code','rawSql':f'SELECT t."time" AS "time",{decoded(c)} AS {ident(c.name)} FROM $Id_Logsis t CROSS JOIN LATERAL (SELECT to_jsonb(t) AS payload) p WHERE $__timeFilter("time") ORDER BY t."time"'} for j,c in enumerate(chosen)]
            history.append({'id':pid,'type':'timeseries','title':caption+' · '+group_title,'gridPos':{'x':0,'y':y,'w':24,'h':8},'datasource':{'type':'grafana-postgresql-datasource','uid':'zKW_ld27k'},'targets':targets,'fieldConfig':{'defaults':{'unit':'suffix: '+chosen[0].unit,'noValue':'—','custom':{'drawStyle':'line','lineInterpolation':'linear','lineWidth':2,'showPoints':'always','pointSize':3,'spanNulls':True,'fillOpacity':5}},'overrides':[]},'options':{'legend':{'displayMode':'table','placement':'bottom','calcs':['lastNotNull','min','max']},'tooltip':{'mode':'multi'}}});pid+=1;y+=8
    panels.append({'id':pid,'type':'row','title':'Históricos do período','collapsed':True,'gridPos':{'x':0,'y':y,'w':24,'h':1},'panels':history})
    panels.sort(key=lambda p:(p['gridPos']['y'],p['gridPos']['x']))
    return {'id':None,'uid':'logsis-'+profile.model.lower().replace('_','-')+'-d1','title':'LOGSIS / '+profile.label,'schemaVersion':39,'version':1,'timezone':'America/Sao_Paulo','style':'dark','editable':True,'refresh':'30s','time':{'from':'now-6h','to':'now'},'tags':['LOGSIS','SISTEL','DEIF',profile.model],'description':' '.join(profile.manual_notes or []),'templating':{'list':variables},'panels':panels,'annotations':{'list':[]},'links':[]}
