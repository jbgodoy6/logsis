"""Generate a Grafana 12 Canvas dashboard using only built-in panels."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = {'type': 'grafana-postgresql-datasource', 'uid': '${DS_DMAX}'}


def target(sql, form='table'):
    return [{'refId': 'A', 'datasource': DS, 'rawSql': sql, 'format': form, 'rawQuery': True, 'editorMode': 'code'}]


def element(name, kind, x, y, w, h, config=None):
    return dict(name=name, type=kind, placement=dict(left=x, top=y, width=w, height=h),
                constraint=dict(horizontal='left', vertical='top'), background={'color': {'fixed': 'transparent'}}, config=config or {})


def text(name, value, x, y, w=350, h=25, size=16, field=False, color='#dce8f4'):
    return element(name, 'metric-value' if field else 'text', x, y, w, h,
        dict(text={'mode': 'field' if field else 'fixed', 'field' if field else 'fixed': value},
             color=color if isinstance(color,dict) else {'fixed': color}, size=size, align='left', valign='middle'))


def icon(name, path, x, y, w, h, field=None):
    result = element(name, 'icon', x, y, w, h, dict(path={'mode': 'fixed', 'fixed': '../img/dmax/' + path},
        fill={'field': field} if field else {'fixed': '#45b2f2'}))
    if path == 'cable.svg':
        result['config']['path'] = {'mode': 'mapping', 'field': 'cable_path'}
        result['config']['stroke'] = {'width': 2, 'color': {'field': 'equipment_state'}}
    if path in ('charger.svg','car.svg'):
        result['config']['stroke'] = {'width': 1.8, 'color': {'field': 'equipment_state'}}
    if path == 'network.svg':
        result['config']['path'] = {'mode':'mapping','field':'network_path'}
        result['config']['stroke'] = {'width': 1.6,'color':{'field':'communication_state'}}
    return result


def canvas(pid, title, elements, sql, grid, repeat=None):
    panel=dict(id=pid,type='canvas',title=title,datasource=DS,gridPos=grid,targets=target(sql),
       fieldConfig={'defaults': {'noValue': '—', 'decimals': 1, 'color': {'mode': 'thresholds'}, 'thresholds': {'mode': 'absolute','steps': [
        {'color': '#8395a8','value': None},{'color': '#25a5ec','value': 1},{'color': '#239b75','value': 2},{'color':'#dc4c58','value':3}]}},'overrides': [{'matcher': {'id':'byName','options':'communication_state'},'properties':[{'id':'thresholds','value':{'mode':'absolute','steps':[{'color':'#c59138','value':None},{'color':'#8296a8','value':1}]}}]}]},
       options=dict(inlineEditing=False,panZoom=True,zoomToContent=True,showAdvancedTypes=False,
        root={'name':'Planta','type':'frame','elements':elements}, tooltip={'mode':'single'}))
    if repeat: panel.update(repeat=repeat,repeatDirection='h',maxPerRow=4)
    return panel


def build():
    title = dict(id=1,type='text',title='',gridPos=dict(x=0,y=0,w=24,h=3),options={'mode':'html','content':
        '<div style="display:flex;align-items:center;gap:24px"><img style="background:white;padding:8px;border-radius:8px" src="/public/img/dmax/d-max-logo.png" alt="D-Max by EnergyCube" width="160"><div><h2 style="margin:0 0 8px">Supervisão de energia · Planta ao vivo</h2><p>Carregando · Cabo conectado · Alarme · Cabo desconectado · Cores ajustáveis no editor | Atualização 5 s · Amostras até 1 minuto · Veículo conforme associação no D-Max</p></div></div>'})
    meter=canvas(2,'Entrada de energia · Multimedidor',[
        icon('Medidor','meter.svg',12,8,110,135),text('Titulo','MEDIÇÃO DA INSTALAÇÃO',150,5,size=12,color='#5fb7e9'),
        text('Potencia','power',150,35,300,50,34,True),text('Unidade','kW · última leitura',150,92,size=13),
        text('Estado','meter_status',150,123,400,30,14,True),
        text('LimiteOperacional','site_limit',360,40,160,36,24,True),text('LimiteLabel','Limite · kW',360,92,160,20,12)],
        "select max(value) filter(where measurement='power_total_kw') as power, (select limit_kw from dmax.v_sites where controller_id=${site:sqlstring}) as site_limit, case when bool_and(fresh) then 'Medição atual' when bool_or(fresh) then 'Medição parcial' else 'Sem medição atual' end as meter_status from dmax.v_meter where controller_id=${site:sqlstring}",dict(x=0,y=3,w=9,h=6))
    meters=dict(id=3,type='table',title='Todas as grandezas recebidas',datasource=DS,gridPos=dict(x=9,y=3,w=15,h=6),
        targets=target('select label as "Grandeza",value as "Valor",unit as "Unidade",case when fresh then \'Atual\' else \'Indisponível\' end as "Qualidade",sampled_at as "Horário da leitura" from dmax.v_meter where controller_id=${site:sqlstring} order by label'),
        options={'showHeader':True,'cellHeight':'sm'},fieldConfig={'defaults':{'decimals':2,'noValue':'—','custom':{'align':'auto'}},'overrides':[]})
    counters=dict(id=4,type='stat',title='Parque da instalação',datasource=DS,gridPos=dict(x=0,y=9,w=24,h=3),targets=target(
        'select count(distinct charger_id) as "Carregadores cadastrados",count(distinct charger_id) filter(where online) as "Carregadores online",count(*) filter(where vehicle_state=1) as "Veículos conectados",count(*) filter(where alarm) as "Conectores em alarme" from dmax.v_ports where controller_id=${site:sqlstring}'),options={'colorMode':'value','graphMode':'none','textMode':'value_and_name','reduceOptions':{'calcs':['lastNotNull'],'fields':'','values':False}},fieldConfig={'defaults':{'color':{'mode':'fixed','fixedColor':'blue'}},'overrides':[]})
    card=canvas(5,'$port',[
       text('Nome','charger_name',8,0,310,24,16,True),
       text('Estado','state_label',8,25,310,20,11,True,color={'field':'equipment_state'}),
       icon('Carregador','charger.svg',8,52,34,56,'equipment_state'),
       icon('Cabo','cable.svg',40,70,20,38,'equipment_state'),
       icon('Veiculo','car.svg',60,74,70,30,'equipment_state'),
       text('P','power_kw',156,52,160,38,31,True),
       text('PLabel','POTÊNCIA · kW',156,91,160,18,9),
       text('VeiculoNome','vehicle_label',8,116,310,22,12,True),
       text('LLabel','LIMITE · kW',8,143,100,17,8),text('Limite','applied_kw',8,161,100,25,17,True),
       text('ELabel','SESSÃO · kWh',118,143,100,17,8),text('Energia','energy_kwh',118,161,100,25,17,True),
       text('MaxLabel','CAPACIDADE · kW',228,143,100,17,8),text('Max','max_kw',228,161,100,25,17,True),
       icon('Rede','network.svg',8,196,13,13,'communication_state'),
       text('Comunicacao','network_note',28,191,300,22,9,True,color={'field':'communication_state'})],
       "select *,case when vehicle_state=1 then '../img/dmax/cable.svg' else '../img/dmax/cable-free.svg' end as cable_path,case when online then '../img/dmax/network.svg' else '../img/dmax/network-off.svg' end as network_path,case when equipment_state=3 then case when online then 'Alarme · ' else 'Último alarme · ' end ||coalesce(error_code,'Faulted') when not online then 'Estado não confirmado' when equipment_state=2 then 'Carregando' when equipment_state=1 then 'Cabo conectado · aguardando' else 'Cabo desconectado' end as state_label,case when last_plugged then case when online then '' else 'Último: ' end || vehicle_name else 'Sem veículo conectado' end as vehicle_label,communication_label||' · '||to_char(observed_at at time zone 'America/Sao_Paulo','HH24:MI:SS') as network_note from dmax.v_ports where controller_id=${site:sqlstring} and port_id=${port:sqlstring}",dict(x=0,y=12,w=6,h=7),'port')
    history=dict(id=6,type='timeseries',title='Demanda da instalação · média e pico por minuto',datasource=DS,
      gridPos=dict(x=0,y=19,w=24,h=7),targets=target('select time,avg_kw as "Média · kW",max_kw as "Pico · kW" from dmax.minutes where controller_id=${site:sqlstring} and source=\'site\' and $__timeFilter(time) order by time','time_series'),fieldConfig={'defaults':{'unit':'kwatt','custom':{'drawStyle':'line','fillOpacity':10,'spanNulls':False}},'overrides':[]},options={'legend':{'displayMode':'list','placement':'bottom'}})
    def var(name,sql,label):
        return dict(name=name,type='query',datasource=DS,query=sql,definition=sql,refresh=2,sort=1,label=label,multi=False,includeAll=False,current={})
    site=var('site','select site_name as __text,controller_id as __value from dmax.v_sites order by site_name','Planta')
    ports=var('port','select charger_name || \' · Conector \' || connector as __text,port_id as __value from dmax.v_ports where controller_id=${site:sqlstring} order by charger_name,connector','Conectores')
    ports.update(multi=True,includeAll=True,current={'text':'All','value':'$__all'},hide=0)
    # Repeat panels get a single selected connector value in their scoped variable.
    return dict(uid='dmax-energycube',title='D-Max · EnergyCube · Planta ao vivo',schemaVersion=41,version=2,
       tags=['D-Max','EnergyCube'],editable=True,timezone='America/Sao_Paulo',refresh='5s',
       time={'from':'now-6h','to':'now'},panels=[title,meter,meters,counters,card,history],
       templating={'list':[{'name':'DS_DMAX','label':'Banco D-Max','type':'datasource','query':'grafana-postgresql-datasource','current':{'text':'D-Max PostgreSQL','value':'dmax-pg'},'hide':2},site,ports]},
       annotations={'list':[]})


if __name__ == '__main__':
    (ROOT/'cloud/grafana/dmax-planta.json').write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n')
