"""Accessible SVG plant view; works without JavaScript or external assets."""
import html
from .telemetry import plant_snapshot


def esc(value):
    return html.escape(str(value if value is not None else ''), quote=True)


def number(value, places=1):
    return f'{value:,.{places}f}'.replace(',', '_').replace('.', ',').replace('_', '.') if isinstance(value, (float, int)) else '—'


def equipment_svg(plugged=False, alarm=False, offline=False):
    tone = '#ef5565' if alarm else '#8293a7' if offline else '#259bf0'
    car = '#73bce9' if plugged else '#c6d3df'
    return f'''<svg class="equipment-art" viewBox="0 0 420 186" role="img" aria-label="Carregador {'em alarme' if alarm else 'offline' if offline else 'online'}; {'veículo conectado' if plugged else 'sem veículo conectado'}">
<ellipse cx="211" cy="167" rx="186" ry="11" fill="#e9eef5"/>
<path d="M51 157V30Q51 17 64 17H119Q132 17 132 30V157Z" fill="#153758"/>
<path d="M58 155V32Q58 24 66 24H116Q125 24 125 32V155Z" fill="{tone}"/>
<path d="M65 34H118V78H65Z" fill="#0c2943"/>
<path d="M72 43H110M72 50H99" stroke="#70e4d3" stroke-width="3" stroke-linecap="round"/>
<path d="M94 54L83 66H92L88 76L102 62H93Z" fill="#ffc627"/>
<circle cx="91" cy="93" r="5" fill="{'#ffe0e4' if alarm else '#e8f6ff'}"/>
<path d="M70 108H112M70 115H112M70 122H112" stroke="#ffffff" stroke-opacity=".35" stroke-width="3"/>
<rect x="44" y="155" width="96" height="9" rx="3" fill="#133450"/>
<path d="M132 59C163 57 160 109 152 129S158 155 177 145{'Q190 136 201 132' if plugged else ''}" fill="none" stroke="{'#2094dc' if plugged else '#75899e'}" stroke-width="6" stroke-linecap="round"/>
<g opacity="{'1' if plugged else '.28'}"><path d="M189 135L198 112L221 104L244 76Q251 69 265 69H309Q321 69 332 82L351 104L380 116Q388 121 388 132V146H188Z" fill="{car}" stroke="#163953" stroke-width="3" stroke-linejoin="round"/>
<path d="M233 103L253 80H277V103ZM284 80H307Q313 80 319 87L332 103H284Z" fill="#153a58"/>
<path d="M190 132H387M278 108V139" stroke="#153a58" stroke-width="2" opacity=".4"/>
<rect x="289" y="110" width="12" height="3" rx="1" fill="#173f5a"/>
<path d="M193 119H208M372 119H384" stroke="#fff7d7" stroke-width="5"/>
<circle cx="229" cy="146" r="19" fill="#15334d"/><circle cx="229" cy="146" r="10" fill="#dce6ef"/><circle cx="229" cy="146" r="4" fill="#7e9bb2"/>
<circle cx="348" cy="146" r="19" fill="#15334d"/><circle cx="348" cy="146" r="10" fill="#dce6ef"/><circle cx="348" cy="146" r="4" fill="#7e9bb2"/></g>
{'<rect x="196" y="124" width="12" height="10" rx="3" fill="#123a57"/><circle cx="202" cy="129" r="3" fill="#5ce0bb"/>' if plugged else ''}
{'<circle cx="135" cy="28" r="15" fill="#ef5565" stroke="white" stroke-width="3"/><path d="M135 20V29M135 35V36" stroke="white" stroke-width="3" stroke-linecap="round"/>' if alarm else ''}
</svg>'''


def meter_svg():
    return '''<svg viewBox="0 0 160 158" role="img" aria-label="Multimedidor de entrada"><rect x="24" y="8" width="112" height="141" rx="15" fill="#153758"/><rect x="34" y="21" width="92" height="78" rx="6" fill="#daf6ed"/><text x="46" y="42" fill="#366357" font-size="10">ENERGY METER</text><path d="M44 73H57L63 53L72 85L80 61L87 73H115" fill="none" stroke="#008b70" stroke-width="3"/><circle cx="49" cy="116" r="6" fill="#ffc627"/><circle cx="80" cy="116" r="6" fill="#54748d"/><circle cx="110" cy="116" r="6" fill="#54748d"/><path d="M48 140V149M64 140V149M80 140V149M96 140V149M112 140V149" stroke="#a3b7c9" stroke-width="4"/></svg>'''


def render_plant(state):
    plant = plant_snapshot(state)
    ports = [(c, port) for c in plant['chargers'] for port in c['connectors']]
    alarms = sum(port['alarm'] for _, port in ports)
    online = sum(c['online'] for c in plant['chargers'])
    connected = sum(port['plugged'] and port['online'] for _, port in ports)
    total = next((r['value'] for r in plant['meter']['readings'] if r['measurement'] == 'power_total_kw'), None)
    utilization = min(100, max(0, (total or 0) / plant['limit_kw'] * 100))
    result = '<section class="plant"><div class="plant-intro"><div><span class="plant-kicker">ENERGYCUBE · ENERGY MANAGEMENT</span><h2>Sua energia. Sob controle.</h2><p>Carregadores, veículos e medição em uma única visão.</p></div><span class="plant-live">' + ('SIMULAÇÃO' if plant['mode'] == 'simulation' else 'OPERAÇÃO LOCAL') + ' · atualização 2 s</span></div>'
    result += '<div class="plant-stats">' + ''.join('<article><span>' + label + '</span><strong>' + value + '</strong><small>' + note + '</small></article>' for label, value, note in [
        ('Demanda da instalação', number(total) + ' <em>kW</em>', 'Medição de entrada' if plant['meter']['fresh'] else 'Sem leitura atual'),
        ('Limite operacional', number(plant['limit_kw']) + ' <em>kW</em>', 'Margem: ' + number(plant['margin_kw']) + ' kW'),
        ('Carregadores online', str(online) + ' <em>/ ' + str(len(plant['chargers'])) + '</em>', str(connected) + ' conectores com veículo confirmado online'),
        ('Alarmes ativos', str(alarms), 'Verifique os equipamentos em vermelho' if alarms else 'Nenhum alarme informado')]) + '</div>'
    result += '<div class="plant-energy"><div class="plant-meter-art">' + meter_svg() + '</div><div class="plant-meter"><span class="plant-kicker">ENTRADA DE ENERGIA · MULTIMEDIDOR</span><h3>Leituras da instalação</h3><span class="plant-badge ' + ('ok' if plant['meter']['fresh'] else 'offline') + '">' + ('Medição atual' if plant['meter']['fresh'] else 'Sem medição atual') + '</span><div class="plant-readings">'
    for reading in plant['meter']['readings']:
        result += '<div><span>' + esc(reading['label']) + '</span><b>' + number(reading['value'], 2) + ' <small>' + esc(reading['unit']) + '</small></b>' + ('<small>Leitura indisponível</small>' if reading['error'] else '') + '</div>'
    result += '</div></div></div><div class="plant-section-title"><div><h3>Parque de carregadores</h3><p>O equipamento permanece na planta mesmo sem comunicação.</p></div><span>Azul · online &nbsp; Vermelho · alarme &nbsp; Cinza · offline</span></div><div class="plant-grid">'
    for charger, port in ports:
        tone = 'alarm' if port['alarm'] else 'offline' if not port['online'] else 'ok'
        vehicle = (port['vehicle_name'] or 'Veículo não identificado') if port['plugged'] else 'Sem veículo conectado'
        if not port['online']:
            vehicle = 'Último estado: ' + vehicle
        result += '<article class="plant-charger ' + tone + '"><div class="plant-card-top"><div><small>' + esc(charger['id']) + ' · CONECTOR ' + str(port['connector']) + '</small><h4>' + esc(charger['name']) + '</h4></div><span class="plant-badge ' + tone + '">' + esc(port['status']) + '</span></div>'
        result += equipment_svg(port['plugged'], port['alarm'], not port['online'])
        result += '<div class="plant-vehicle"><span>' + ('● CABO CONECTADO' if port['plugged'] and port['online'] else 'ESTADO NÃO CONFIRMADO' if not port['online'] else 'PRONTO PARA CONECTAR') + '</span><b>' + esc(vehicle) + '</b></div>'
        result += '<div class="plant-card-data"><div><span>Potência atual</span><b>' + number(port['power_kw']) + ' <small>kW</small></b></div><div><span>Limite aplicado</span><b>' + number(port['limit_kw']) + ' <small>kW</small></b></div><div><span>Energia da sessão</span><b>' + number(port['energy_kwh'], 2) + ' <small>kWh</small></b></div></div>'
        result += '<div class="plant-card-foot"><span>Capacidade ' + number(charger['max_kw'], 0) + ' kW</span><span>' + ('Erro: ' + esc(port['error_code']) if port['alarm'] else 'Leitura atual' if port['telemetry_fresh'] else 'Sem leitura atual') + '</span></div></article>'
    if not ports:
        result += '<article class="plant-empty"><h3>Seu parque começa aqui</h3><p>Cadastre um carregador no D-Max para ele aparecer automaticamente nesta planta.</p></article>'
    return result + '</div><p class="plant-note">Supervisão visual · o controle de demanda permanece no D-Max local. Identificação do veículo depende da associação disponível.</p></section>'
