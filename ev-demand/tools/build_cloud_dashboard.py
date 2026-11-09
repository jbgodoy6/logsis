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
        result['config']['stroke'] = {'width': 5, 'color': {'field': 'vehicle_state'}}
    return result


def canvas(pid, title, elements, sql, grid, repeat=None):
    panel=dict(id=pid,type='canvas',title=title,datasource=DS,gridPos=grid,targets=target(sql),
       fieldConfig={'defaults': {'noValue': '—', 'decimals': 1, 'color': {'mode': 'thresholds'}, 'thresholds': {'mode': 'absolute','steps': [
        {'color': '#8395a8','value': None},{'color': '#25a5ec','value': 1},{'color': '#f05264','value': 2}]}},'overrides': []},
       options=dict(inlineEditing=False,panZoom=True,zoomToContent=True,showAdvancedTypes=False,
        root={'name':'Planta','type':'frame','elements':elements}, tooltip={'mode':'single'}))
    if repeat: panel.update(repeat=repeat,repeatDirection='h',maxPerRow=3)
    return panel


def build():
    title = dict(id=1,type='text',title='',gridPos=dict(x=0,y=0,w=24,h=3),options={'mode':'html','content':
        '<div style="display:flex;align-items:center;gap:24px"><img style="background:white;padding:8px;border-radius:8px" src="/public/img/dmax/d-max-logo.png" alt="D-Max by EnergyCube" width="160"><div><h2 style="margin:0 0 8px">Supervisão de energia · Planta ao vivo</h2><p>Azul: online · Vermelho: alarme · Cinza: offline | Atualização 5 s · Amostras até 1 minuto · Veículo conforme associação no D-Max</p></div></div>'})
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
       text('Nome','charger_name',14,5,400,30,21,True),text('Estado','status',14,39,390,25,13,True),
       icon('Carregador','charger.svg',22,76,114,152,'equipment_state'),
       icon('Cabo','cable.svg',128,116,75,95,'vehicle_state'),
       icon('Veiculo','car.svg',186,106,245,126,'vehicle_state'),
       text('VeiculoNome','vehicle_label',14,240,420,30,17,True),
       text('PLabel','POTÊNCIA · kW',14,285,140,25,11),text('P','power_kw',14,310,140,34,26,True),
       text('LLabel','LIMITE · kW',164,285,140,25,11),text('Limite','applied_kw',164,310,140,34,26,True),
       text('ELabel','SESSÃO · kWh',314,285,140,25,11),text('Energia','energy_kwh',314,310,140,34,26,True),
       text('Erro','fault_label',14,360,420,23,12,True,color={'field':'equipment_state'}),
       text('Qualidade','freshness_label',14,390,420,25,11,True,color='#8a9eb4')],
       "select *,case when vehicle_state=1 then '../img/dmax/cable.svg' else '../img/dmax/cable-free.svg' end as cable_path,case when last_plugged then case when online then '' else 'Último estado: ' end || vehicle_name else 'Sem veículo conectado' end as vehicle_label,case when alarm then 'ALARME · '||coalesce(error_code,'Faulted') else 'Sem alarme informado' end as fault_label,'Última atualização: '||to_char(observed_at at time zone 'America/Sao_Paulo','DD/MM HH24:MI:SS') as freshness_label from dmax.v_ports where controller_id=${site:sqlstring} and port_id=${port:sqlstring}",dict(x=0,y=12,w=8,h=12),'port')
    history=dict(id=6,type='timeseries',title='Demanda da instalação · média e pico por minuto',datasource=DS,
      gridPos=dict(x=0,y=24,w=24,h=8),targets=target('select time,avg_kw as "Média · kW",max_kw as "Pico · kW" from dmax.minutes where controller_id=${site:sqlstring} and source=\'site\' and $__timeFilter(time) order by time','time_series'),fieldConfig={'defaults':{'unit':'kwatt','custom':{'drawStyle':'line','fillOpacity':10,'spanNulls':False}},'overrides':[]},options={'legend':{'displayMode':'list','placement':'bottom'}})
    def var(name,sql,label):
        return dict(name=name,type='query',datasource=DS,query=sql,definition=sql,refresh=2,sort=1,label=label,multi=False,includeAll=False,current={})
    site=var('site','select site_name as __text,controller_id as __value from dmax.v_sites order by site_name','Planta')
    ports=var('port','select charger_name || \' · Conector \' || connector as __text,port_id as __value from dmax.v_ports where controller_id=${site:sqlstring} order by charger_name,connector','Conectores')
    ports.update(multi=True,includeAll=True,current={'text':'All','value':'$__all'},hide=0)
    # Repeat panels get a single selected connector value in their scoped variable.
    return dict(uid='dmax-energycube',title='D-Max · EnergyCube · Planta ao vivo',schemaVersion=41,version=1,
       tags=['D-Max','EnergyCube'],editable=True,timezone='America/Sao_Paulo',refresh='5s',
       time={'from':'now-6h','to':'now'},panels=[title,meter,meters,counters,card,history],
       templating={'list':[{'name':'DS_DMAX','label':'Banco D-Max','type':'datasource','query':'grafana-postgresql-datasource','current':{'text':'D-Max PostgreSQL','value':'dmax-pg'},'hide':2},site,ports]},
       annotations={'list':[]})


if __name__ == '__main__':
    (ROOT/'cloud/grafana/dmax-planta.json').write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n')
