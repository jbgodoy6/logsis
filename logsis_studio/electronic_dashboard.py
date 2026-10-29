"""Matched dashboards for the new ECU profiles. Preserved templates are untouched."""
from __future__ import annotations
import copy,math
from . import manual_dashboard as ui,standard_layout as layout,deif_dashboard as deif


def field(c):return '"MDB'+f'{c.number:02}'+'"' if c else 'NULL::numeric'
def bit(expr,n):return f'((({expr})::bigint >> {n}) & 1)'
def raw(c):return ui.numeric("payload->>"+ui.sq(c.column))

def decode_sql(c,expr=None):
    expr=expr or raw(c);width=32 if c.params['FNC'] in ['30','40'] else 16;wrap=1<<width
    bits=f'mod(({expr})::numeric+{wrap},{wrap})'
    value=f'CASE WHEN {bits}>={wrap//2} THEN {bits}-{wrap} ELSE {bits} END' if c.signed else bits
    valid=f'{expr}=trunc({expr}) AND {expr} BETWEEN {-wrap//2} AND {wrap-1}'
    if c.codec=='boolean' or int(c.params['BIT'])>=0:value=expr;valid+=f' AND {expr} IN (0,1)'
    elif c.codec!='word':
        if c.source_reference.startswith('GenComm') or c.params['FNC'] in ['3','30']:
            # GenComm signed/unsigned sentinels depend on the declared type.
            valid+=f' AND ({value})<{wrap//2-8 if c.signed else wrap-8}'
        else:
            # ECU availability is checked separately; reserved invalid values
            # must never become an engineering sensor reading.
            invalid=[wrap//2-1,wrap//2-2,wrap//2-3] if c.signed else [wrap-1]
            valid+=' AND '+bits+' NOT IN ('+','.join(map(str,invalid))+')'
    result=f'CASE WHEN {valid} THEN ({value}) END'
    if c.role.endswith('water_in_fuel'):result=f'CASE WHEN ({result}) IN (0,1) THEN ({result}) END'
    divisor=('NULLIF('+ui.var('Divisor_Energia')+'::numeric,0)') if c.role.startswith('energy_') and c.params['FNC']=='30' else str(c.divisor)
    return f'({result})/{divisor}'


def history_value(c,rs):
    expr=decode_sql(c)
    if c.validity_role:
        valid=decode_sql(rs[c.validity_role]);expr=f'CASE WHEN {bit(valid,c.validity_bit)}=1 THEN {expr} END'
    return expr


def main_sql(profile):
    rs={c.role:c for c in profile.channels};dse=profile.vendor=='DSE'
    def r(role):return field(rs.get(role))
    u=lambda c:'"U_MDB'+f'{c.number:02}'+'"'
    unvalidated=','.join(decode_sql(c)+' AS '+u(c) for c in profile.channels)
    values=[]
    for c in profile.channels:
        v=u(c)
        if c.validity_role:v=f'CASE WHEN {bit(u(rs[c.validity_role]),c.validity_bit)}=1 THEN {v} END'
        values.append(v+' AS '+field(c))
    labels=[ui.var(c.label_variable)+' AS "NOME_'+c.column.upper()+'"' for c in profile.channels if c.label_variable]
    states=labels[:]
    if dse:
        states.append('CASE '+''.join(f'WHEN {r("mode")}={code} THEN {ui.sq(label)} ' for code,label in [(0,'STOP'),(1,'AUTO'),(2,'MANUAL'),(3,'TESTE C/ CARGA'),(4,'AUTO / RET. MAN.'),(5,'CONFIGURAÇÃO'),(6,'TESTE S/ CARGA'),(7,'OFF')])+"ELSE 'SEM DADOS' END AS \"MODE\"")
        for name,role in [('B1','led_mains'),('B2','led_gen')]:states.append(f'CASE WHEN {r(role)} IN (0,1) THEN {r(role)} END AS "{name}"')
        states.append(f"CASE WHEN {r('rpm')}=0 THEN 'MOTOR PARADO' WHEN {r('rpm')}>0 THEN 'MOTOR EM FUNCIONAMENTO' ELSE 'ESTADO DO MOTOR · SEM DADOS' END AS \"ENGINE_STATE\"")
        states.append('CASE '+''.join(f'WHEN {r(role)}=1 THEN {level} ' for role,level in [('shutdown',3),('trip',2),('warning',1)])+'WHEN '+' OR '.join(r(role)+' IS NULL' for role in ['warning','trip','shutdown'])+' THEN NULL ELSE 0 END AS "ALARM_LEVEL"')
        states.append("'CONTROLE DSE' AS \"OPERATION_FUNCTION\"")
    else:
        mode=r('mode_word');status=r('status_word');modebits=[(0,'BLOCK'),(1,'MANUAL'),(2,'SEMI-AUTO'),(3,'AUTO')]+([] if profile.application=='ENG' else [(4,'TESTE')])
        states.append('CASE WHEN '+mode+" IS NULL THEN 'SEM DADOS' WHEN "+'+'.join(bit(mode,n) for n,_ in modebits)+">1 THEN 'INCOERENTE' "+''.join(f'WHEN {bit(mode,n)}=1 THEN {ui.sq(label)} ' for n,label in modebits)+"ELSE 'OUTRO MODO' END AS \"MODE\"")
        for name,on,off in [('B1',1,12),('B2',4,11)]:
            value='NULL::numeric' if profile.application=='ENG' or (name=='B1' and profile.topology=='gen_bus') else f'CASE WHEN {bit(status,on)}=1 AND {bit(status,off)}=0 THEN 1 WHEN {bit(status,on)}=0 AND {bit(status,off)}=1 THEN 0 WHEN {bit(status,on)}=1 AND {bit(status,off)}=1 THEN 3 END'
            states.append(value+' AS "'+name+'"')
        states.append(f"CASE WHEN {bit(status,6)}=0 THEN 'MOTOR PARADO' WHEN {bit(status,6)}=1 THEN 'MOTOR EM FUNCIONAMENTO' ELSE 'ESTADO DO MOTOR · SEM DADOS' END AS \"ENGINE_STATE\"")
        fail=r('fail_class_word');service=r('alarm_word_1015');count=r('alarm_count');sc=f'({bit(service,0)}+{bit(service,1)})'
        only_service=f'({fail}=2 AND {count}={sc} AND {sc}>0 AND ({service}::bigint & 65532)=0)'
        states.append(f'CASE WHEN {fail} IS NULL THEN NULL WHEN {bit(fail,4)}=1 OR {bit(fail,6)}=1 THEN 3 WHEN '+ ' OR '.join(bit(fail,n)+'=1' for n in [2,3,5,7,8])+f' THEN 2 WHEN {only_service} THEN 0 WHEN {bit(fail,1)}=1 THEN 1 WHEN {fail}>0 OR {count}>0 THEN 4 ELSE 0 END AS "ALARM_LEVEL"')
        parts=','.join(f'CASE WHEN {bit(mode,n)}=1 THEN {ui.sq(label)} END' for n,label in [(5,'ILHA'),(6,'AMF'),(7,'CONTROLE DE PICO'),(8,'POTÊNCIA FIXA'),(9,'EXPORTAÇÃO'),(10,'TRANSFERÊNCIA DE CARGA'),(11,'GERENCIAMENTO')])
        states.append(f"CASE WHEN {mode} IS NULL THEN 'SEM DADOS' ELSE coalesce(nullif(concat_ws(' / ',{parts}),''),'NÃO INDICADA') END AS \"OPERATION_FUNCTION\"")
    maint='CASE '
    for label,comparison in [('VENCIDA','<=0'),('PRÓXIMA','>0')]:
        for i in range(1,4):
            c=rs.get('maintenance_'+str(i))
            if not c:continue
            cond=field(c)+comparison
            if label=='VENCIDA' and not dse:cond='('+cond+' OR '+bit(r('alarm_word_1015'),i-1)+'=1)'
            if label=='PRÓXIMA':cond+=' AND '+field(c)+'<='+ui.var('Manutencao_Alerta_h')+'::numeric'
            name=ui.var(c.label_variable) if c.label_variable else ui.sq(c.name)
            maint+=f'WHEN {cond} THEN {name} || {ui.sq(" / "+label)} '
    maintenance=[c for role,c in rs.items() if role.startswith('maintenance_') and role!='maintenance_general']
    maint+=('WHEN '+' OR '.join(field(c)+' IS NULL' for c in maintenance)+" THEN 'MANUTENÇÃO / SEM DADOS' ELSE 'MANUTENÇÃO EM DIA' END") if maintenance else "ELSE 'MANUTENÇÃO · NÃO DISPONÍVEL' END"
    states += [maint+' AS "MAINTENANCE"',r('hour_meter')+' AS "HOURS"',r('gen_kw')+' AS "POWER"']
    flags=[]
    for prefix in ['gen','mains','bus']:
        vs=[field(c) for role,c in rs.items() if role.startswith(prefix+'_v_')]
        v='CASE WHEN '+' OR '.join(x+'>=30' for x in vs)+' THEN 1 WHEN '+' AND '.join(x+'<30' for x in vs)+' THEN 0 END' if vs else 'NULL::numeric'
        flags.append(v+' AS "V_'+prefix+'"')
    if 'input_word' in rs:
        for terminal,n in [(t,t-39) for t in range(39,47)]+[(t,t-36) for t in range(47,51)]:flags.extend([bit(r('input_word'),n)+f' AS "INPUT_{terminal}"',ui.var('Nome_Entrada_'+str(terminal))+f' AS "INPUT_NAME_{terminal}"'])
    condition='("B1"=1 AND "V_mains"=1) OR ("B2"=1 AND "V_gen"=1)'
    if profile.topology=='gen_bus':condition='("B2"=1 AND "V_gen"=1) OR "V_bus"=1'
    extras=[]
    for prefix in ['gen','mains','bus']:
        for vertical,suffix in [(False,''),(True,'_V')]:extras.append(f'CASE WHEN "V_{prefix}"=1 THEN {ui.sq(ui.wire(ui.RED,vertical))} ELSE {ui.sq(ui.wire(ui.MUTED,vertical))} END AS "WIRE_{prefix}{suffix}"')
    for vertical,suffix in [(False,''),(True,'_V')]:extras.append(f'CASE WHEN {condition} THEN {ui.sq(ui.wire(ui.RED,vertical))} ELSE {ui.sq(ui.wire(ui.MUTED,vertical))} END AS "WIRE_OUT{suffix}"')
    for alias in ['B1','B2']:
        extras.append(f'''CASE "{alias}" WHEN 1 THEN 'FECHADO' WHEN 0 THEN 'ABERTO' WHEN 3 THEN 'INCOERENTE' ELSE 'SEM DADOS' END AS "{alias}_TEXT"''')
        extras.append(f'CASE "{alias}" WHEN 1 THEN {ui.sq(deif.switch(1))} WHEN 0 THEN {ui.sq(deif.switch(0))} ELSE {ui.sq(deif.switch(None))} END AS "{alias}_SVG"')
    extras += ['CASE '+''.join(f'WHEN "ALARM_LEVEL"={n} THEN {ui.sq(ui.assets()[key])} ' for n,key in [(3,'shutdown'),(2,'trip'),(1,'warning')])+'ELSE '+ui.sq(ui.assets()['gen'])+' END AS "GENERATOR_SVG"', '''CASE "ALARM_LEVEL" WHEN 0 THEN 'SEM ALARME' WHEN 1 THEN 'WARNING' WHEN 2 THEN 'TRIP ELÉTRICO' WHEN 3 THEN 'SHUTDOWN' WHEN 4 THEN 'ALARMES REGISTRADOS' ELSE 'ALARMES · SEM DADOS' END AS "ALARM_TEXT"''']
    extras+=['CASE '+''.join(f'WHEN gsm>={threshold} AND gsm<0 THEN {ui.sq(ui.signal(level))} ' for threshold,level in [(-80,5),(-90,4),(-100,3),(-110,2),(-140,1)])+'ELSE '+ui.sq(ui.signal(0))+' END AS "GSM_ICON"',f'CASE WHEN wifi BETWEEN -140 AND -1 THEN {ui.sq(ui.radio(True))} ELSE {ui.sq(ui.radio(True,ui.MUTED))} END AS "WIFI_ICON"','CASE WHEN gsm BETWEEN -140 AND -1 THEN gsm END AS "GSM"','CASE WHEN wifi BETWEEN -140 AND -1 THEN wifi END AS "WIFI"']
    timeexpr='''CASE WHEN pg_typeof("time")='timestamp without time zone'::regtype THEN ("time"::timestamp AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo' ELSE "time"::timestamptz AT TIME ZONE 'America/Sao_Paulo' END'''
    return f'''WITH sample AS (SELECT "time",to_jsonb(t) AS payload FROM $Id_Logsis t WHERE $__timeFilter("time") ORDER BY "time" DESC LIMIT 1), decoded AS MATERIALIZED (SELECT {unvalidated}, {ui.numeric("payload->>'gsm_rssi'")} AS gsm,{ui.numeric("payload->>"+ui.var('Campo_WiFi_RSSI'))} AS wifi,to_char({timeexpr},'DD/MM HH24:MI') AS "LAST_TIME" FROM (SELECT (SELECT payload FROM sample) AS payload,(SELECT "time" FROM sample) AS "time") q), validated AS MATERIALIZED (SELECT {','.join(values)},gsm,wifi,"LAST_TIME" FROM decoded), states AS MATERIALIZED (SELECT validated.*,{','.join(states)} FROM validated), flags AS MATERIALIZED (SELECT states.*,{','.join(flags)} FROM states) SELECT flags.*,{','.join(extras)} FROM flags'''


def build_dashboard(profile):
    rs={c.role:c for c in profile.channels};main=main_sql(profile)
    variables=[{'name':n,'type':'constant','query':v,'hide':2,'skipUrlSync':True} for n,v in [('Id_Logsis','id_planta'),('Campo_WiFi_RSSI','WiFi_rssi'),('Manutencao_Alerta_h','50'),('Divisor_Energia','10' if profile.vendor=='DSE' else '1')]]
    for c in profile.channels:
        if c.label_variable:variables.append({'name':c.label_variable,'type':'constant','query':c.name,'hide':2,'skipUrlSync':True})
    if 'input_word' in rs:
        for t in range(39,51):variables.append({'name':'Nome_Entrada_'+str(t),'type':'constant','query':'Entrada '+str(t),'hide':2,'skipUrlSync':True})
    # This changes only visual aliases. Source vendor, decoder and profile remain intact.
    from dataclasses import replace
    visual=replace(profile,vendor='DEIF',kind='deif')
    cfg=deif.panel_properties(profile)
    for c in profile.channels:
        if c.role.endswith('water_in_fuel'):cfg['overrides'].append({'matcher':{'id':'byName','options':ui.field(c)},'properties':[{'id':'mappings','value':[{'type':'value','options':{'0':{'text':'NÃO DETECTADA','color':ui.MUTED},'1':{'text':'DETECTADA','color':ui.RED}}}]}]})
    source={'targets':[{'refId':'A','rawQuery':True,'format':'table','editorMode':'code','rawSql':main}],'datasource':{'type':'grafana-postgresql-datasource','uid':'zKW_ld27k'}}
    overview=layout.overview(visual,source);overview['fieldConfig']=copy.deepcopy(cfg)
    for e in overview['options']['root']['elements']:
        if e['name'] in ['Marca','Marca responsivo']:e['config']['text']={'fixed':'LOGSIS / '+profile.base_model.replace('_GEN_BUS','').replace('_GEN','').replace('_ENG','')+' · ECU'}
        if e['name']=='Diagnóstico QTA':e['type']='metric-value';e['config']['text']={'mode':'field','field':'ENGINE_STATE','fixed':'—'}
        if profile.base_model == 'DSE8620' and e['name'] == 'Fonte rótulo 0 9':
            e['config']['text']={'fixed':'FP TC'}
        if profile.base_model == 'DSE8620' and e['name'] == 'Fonte leitura 0 9':
            e['type']='metric-value';e['config']['text']={'mode':'field','field':ui.field(rs['mains_fp_l1']),'fixed':'—'}
    # Do not advertise BUS currents/power where this application has no such
    # instruments. An unavailable installed sensor still retains its own card.
    missing={e['name'].removeprefix('Fonte leitura ') for e in overview['options']['root']['elements']
             if e['name'].startswith('Fonte leitura ') and not e.get('config',{}).get('text',{}).get('field')}
    overview['options']['root']['elements']=[e for e in overview['options']['root']['elements']
        if not any(e['name'] in ['Fonte leitura '+key,'Fonte rótulo '+key] for key in missing)]
    def group(pid,title,cs,pos,height=412,cols=3,entries=None):
        p=layout.group(visual,pid,title,cs,pos,height,cols,entries);p['fieldConfig']=copy.deepcopy(cfg);return p
    primary=[c for c in profile.channels if c.role.startswith('gen_') and ('_v_' in c.role or '_i_' in c.role or c.role=='gen_frequency')]
    if not primary:primary=[c for c in profile.channels if c.role in ['rpm','battery','hour_meter','starts']]
    motor=[c for c in profile.channels if c.role in ['oil_pressure','coolant','oil_temperature','fuel','battery','rpm','charge_voltage']]
    panels=[overview,group(2,'02 / Gerador · instrumentação' if profile.application!='ENG' else '02 / Motor · instrumentação',primary,{'x':12,'y':0,'w':12,'h':16},564,3),group(3,'03 / Motor e sensores',motor,{'x':12,'y':16,'w':12,'h':11},374,2)]
    stats=[('POTÊNCIA ATIVA','POWER'),('FATOR DE POTÊNCIA',ui.field(rs['gen_fp']) if 'gen_fp' in rs else 'MODE'),('HORÍMETRO ACUMULADO','HOURS'),('ENERGIA GERADOR',ui.field(rs['energy_gen']) if 'energy_gen' in rs else 'ENGINE_STATE')]
    if profile.application=='ENG':stats=[('HORÍMETRO ACUMULADO','HOURS'),('MODO','MODE')]
    for i,(title,name) in enumerate(stats):
        p=layout.simple_stat(visual,10+i,title,name);p['gridPos']={'x':i*4,'y':27,'w':4,'h':3};p['fieldConfig']=copy.deepcopy(cfg);panels.append(p)
    for i,role in enumerate(['hour_meter','energy_gen']):
        c=rs.get(role)
        if not c:continue
        sql=deif.period_sql(profile,c,role=='hour_meter').replace(deif.decoded(c),decode_sql(c))
        p={'id':14+i,'type':'stat','title':'HORAS / PERÍODO' if role=='hour_meter' else 'GERAÇÃO / PERÍODO','gridPos':{'x':16+i*4,'y':27,'w':4,'h':3},'datasource':source['datasource'],'targets':[{'refId':'A','rawQuery':True,'format':'table','editorMode':'code','rawSql':sql}],'fieldConfig':{'defaults':{'noValue':'—'},'overrides':[]},'transformations':[{'id':'filterFieldsByName','options':{'include':{'names':['EXIBICAO']}}}],'options':{'reduceOptions':{'calcs':['lastNotNull'],'fields':'/^EXIBICAO$/','values':False},'textMode':'value','colorMode':'value','graphMode':'none','text':{'valueSize':24}}};panels.append(p)
    y=30;ecu=[c for c in profile.channels if c.role.startswith('ecu_') and c.codec!='word'];h=max(6,math.ceil(len(ecu)/3)*3)
    panels.append(group(20,'04 / ECU-CAN · motor e combustível',ecu,{'x':0,'y':y,'w':24,'h':h},h*34,3));y+=h
    entries=[('Estado motor','ENGINE_STATE',None),('Modo','MODE',None),('Função da aplicação','OPERATION_FUNCTION',None),('Alarmes','ALARM_TEXT',None),('Manutenção','MAINTENANCE',None)]
    entries += [(c.name,ui.field(c),'NOME_'+c.column.upper() if c.label_variable else None) for c in profile.channels if c.role.startswith('maintenance_') and c.role!='maintenance_general']
    panels.append(group(21,'05 / Operação e manutenção',[],{'x':0,'y':y,'w':24,'h':9},310,3,entries));y+=9
    inputs=[c for c in profile.channels if c.role.startswith('input_') and c.role!='input_word']
    if 'input_word' in rs:entries=[('Entrada '+str(t),'INPUT_'+str(t),'INPUT_NAME_'+str(t)) for t in range(39,51)]
    else:entries=None
    n=12 if entries else len(inputs)
    if n:
        h=max(6,math.ceil(n/3)*3);panels.append(group(22,'06 / Entradas digitais',inputs,{'x':0,'y':y,'w':24,'h':h},h*34,3,entries));y+=h
    analogues=[c for c in profile.channels if c.role.startswith('analog_')]
    if analogues:
        h=max(6,math.ceil(len(analogues)/3)*3)
        panels.append(group(23,'07 / Entradas multifunção · unidade configurada',analogues,{'x':0,'y':y,'w':24,'h':h},h*34,3));y+=h
    histories=[];pid=100
    groups=[('Gerador · tensões',[c for c in profile.channels if c.role.startswith('gen_v_')]),('Gerador · corrente',[c for c in profile.channels if c.role.startswith('gen_i_')]),('Fontes · tensões',[c for c in profile.channels if c.role.startswith(('mains_v_','bus_v_'))]),('Gerador · potência',[rs['gen_kw']] if 'gen_kw' in rs else []),('ECU · consumo',[c for c in ecu if c.role.endswith('fuel_rate')]),('ECU · temperaturas',[c for c in ecu if 'temperature' in c.role]),('ECU · pressões',[c for c in ecu if 'pressure' in c.role])]
    separated=[]
    for title,cs in groups:
        units=list(dict.fromkeys(c.unit for c in cs))
        for unit in units:separated.append((title+(' · '+unit if len(units)>1 else ''),[c for c in cs if c.unit==unit]))
    for title,cs in separated:
        if not cs:continue
        histories.append({'id':pid,'type':'timeseries','title':title,'gridPos':{'x':0,'y':y+1,'w':24,'h':8},'datasource':source['datasource'],'targets':[{'refId':chr(65+j),'rawQuery':True,'format':'time_series','editorMode':'code','rawSql':f'SELECT t."time",{history_value(c,rs)} AS {deif.ident(c.name)} FROM $Id_Logsis t CROSS JOIN LATERAL (SELECT to_jsonb(t) AS payload) q WHERE $__timeFilter("time") ORDER BY t."time"'} for j,c in enumerate(cs)],'fieldConfig':{'defaults':{'noValue':'—','unit':'none' if len({c.unit for c in cs})>1 else 'suffix: '+cs[0].unit,'custom':{'drawStyle':'line','lineInterpolation':'linear','lineWidth':2,'showPoints':'always','pointSize':3,'spanNulls':True,'fillOpacity':5}},'overrides':[]},'options':{'tooltip':{'mode':'multi'},'legend':{'displayMode':'table','placement':'bottom','calcs':['lastNotNull','min','max']}}});pid+=1;y+=8
    start=min((p['gridPos']['y'] for p in histories),default=y)-1
    panels.append({'id':90,'type':'row','title':'HISTÓRICOS E ALERTAS — expandir / recolher','collapsed':True,'gridPos':{'x':0,'y':start,'w':24,'h':1},'panels':histories})
    return {'id':None,'uid':'logsis-'+profile.model.lower().replace('_','-'),'title':'LOGSIS / '+profile.label,'schemaVersion':39,'version':1,'timezone':'America/Sao_Paulo','editable':True,'style':'dark','refresh':'30s','time':{'from':'now-6h','to':'now'},'tags':['LOGSIS','SISTEL','ECU/CAN',profile.base_model],'templating':{'list':variables},'panels':panels,'annotations':{'list':[]},'links':[],'description':'Perfil eletrônico separado do convencional. Leituras dependem da ECU, hardware e firmware. Sentinelas/validade resultam em traço; motor parado exige RPM válido ou estado nativo. BIN e JSON seguem o mesmo mapa. '+ ' '.join(profile.manual_notes or [])}
