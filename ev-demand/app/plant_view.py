"""Accessible SVG plant view; works without JavaScript or external assets."""
import html
from .telemetry import plant_snapshot, display_colors


def esc(value):
    return html.escape(str(value if value is not None else ''), quote=True)


def number(value, places=1):
    return f'{value:,.{places}f}'.replace(',', '_').replace('.', ',').replace('_', '.') if isinstance(value, (float, int)) else '—'


def equipment_svg(plugged=False, alarm=False, offline=False, charging=False, palette=None):
    colors = display_colors(palette)
    tone = colors['alarm'] if alarm else colors['disconnected'] if offline or not plugged else colors['charging'] if charging else colors['connected']
    car_tone = tone if plugged else '#aeb9c5'
    car_opacity = '1' if plugged else '.4'
    cable_end = 'L75 68' if plugged else 'L65 76'
    return ('<svg class="equipment-art" viewBox="0 0 220 96" role="img" aria-label="Carregador e veículo; estado indicado em texto">'
        + '<g transform="translate(3 4)" fill="' + tone + '" stroke="' + tone + '"><path d="M10 76V10a6 6 0 0 1 6-6h21a6 6 0 0 1 6 6v66" fill="none" stroke="inherit" stroke-width="2.5"/><path d="M6 77h41M17 17h19v19H17Z" fill="none" stroke="inherit" stroke-width="2"/><path d="m28 20-6 9h5l-2 6 8-10h-5Z"/><path d="M18 48h18M18 54h18M18 60h12" fill="none" stroke="inherit" stroke-width="1.5"/></g>'
        + '<path d="M46 35C73 35 58 65 61 75Q65 85 70 75' + cable_end + '" fill="none" stroke="' + car_tone + '" stroke-width="2"/>'
        + '<g transform="translate(75 34)" fill="' + car_tone + '" stroke="' + car_tone + '" opacity="' + car_opacity + '"><g fill="none" stroke="inherit" stroke-width="2" stroke-linejoin="round"><path d="M5 39V28l19-5L39 9h44l18 16 23 5v13h-13M21 43H5m36 0h50M30 24h64M46 11l-9 13m26-13v13m10-13 16 13M61 28v12M72 29h8"/><circle cx="31" cy="42" r="9"/><circle cx="101" cy="42" r="9"/></g></g></svg>')


def meter_svg():
    return '''<svg viewBox="0 0 160 158" role="img" aria-label="Multimedidor de entrada"><rect x="24" y="8" width="112" height="141" rx="15" fill="#153758"/><rect x="34" y="21" width="92" height="78" rx="6" fill="#daf6ed"/><text x="46" y="42" fill="#366357" font-size="10">ENERGY METER</text><path d="M44 73H57L63 53L72 85L80 61L87 73H115" fill="none" stroke="#008b70" stroke-width="3"/><circle cx="49" cy="116" r="6" fill="#ffc627"/><circle cx="80" cy="116" r="6" fill="#54748d"/><circle cx="110" cy="116" r="6" fill="#54748d"/><path d="M48 140V149M64 140V149M80 140V149M96 140V149M112 140V149" stroke="#a3b7c9" stroke-width="4"/></svg>'''


def render_plant(state):
    plant = plant_snapshot(state)
    colors = display_colors(state['settings'].get('display_colors'))
    ports = [(c, port) for c in plant['chargers'] for port in c['connectors']]
    alarms = sum(port['alarm'] for _, port in ports)
    online = sum(c['online'] for c in plant['chargers'])
    connected = sum(port['plugged'] and port['online'] for _, port in ports)
    total = next((r['value'] for r in plant['meter']['readings'] if r['measurement'] == 'power_total_kw'), None)
    utilization = min(100, max(0, (total or 0) / plant['limit_kw'] * 100))
    result = '<section class="plant"><div class="plant-intro"><div><span class="plant-kicker">ENERGYCUBE · ENERGY MANAGEMENT</span><h2>Supervisão da instalação</h2><p>Carregadores, veículos e medição em uma única visão.</p></div><span class="plant-live">' + ('SIMULAÇÃO' if plant['mode'] == 'simulation' else 'OPERAÇÃO LOCAL') + ' · atualização 2 s</span></div>'
    result += '<div class="plant-stats">' + ''.join('<article><span>' + label + '</span><strong>' + value + '</strong><small>' + note + '</small></article>' for label, value, note in [
        ('Demanda da instalação', number(total) + ' <em>kW</em>', 'Medição de entrada' if plant['meter']['fresh'] else 'Sem leitura atual'),
        ('Limite operacional', number(plant['limit_kw']) + ' <em>kW</em>', 'Margem: ' + number(plant['margin_kw']) + ' kW'),
        ('Carregadores online', str(online) + ' <em>/ ' + str(len(plant['chargers'])) + '</em>', str(connected) + ' conectores com veículo confirmado online'),
        ('Alarmes ativos', str(alarms), 'Verifique os equipamentos em vermelho' if alarms else 'Nenhum alarme informado')]) + '</div>'
    result += '<div class="plant-energy"><div class="plant-meter-art">' + meter_svg() + '</div><div class="plant-meter"><span class="plant-kicker">ENTRADA DE ENERGIA · MULTIMEDIDOR</span><h3>Leituras da instalação</h3><span class="plant-badge ' + ('ok' if plant['meter']['fresh'] else 'offline') + '">' + ('Medição atual' if plant['meter']['fresh'] else 'Sem medição atual') + '</span><div class="plant-readings">'
    for reading in plant['meter']['readings']:
        result += '<div><span>' + esc(reading['label']) + '</span><b>' + number(reading['value'], 2) + ' <small>' + esc(reading['unit']) + '</small></b>' + ('<small>Leitura indisponível</small>' if reading['error'] else '') + '</div>'
    result += '</div></div></div><div class="plant-section-title"><div><h3>Parque de carregadores</h3><p>O equipamento permanece na planta mesmo sem comunicação.</p></div><span>Verde · carregando &nbsp; Azul · cabo conectado &nbsp; Vermelho · alarme &nbsp; Cinza · cabo desconectado</span></div><div class="plant-grid">'
    for charger, port in ports:
        tone = ('idle', 'plugged', 'charging', 'alarm')[port['display_state']]
        vehicle = (port['vehicle_name'] or 'Veículo não identificado') if port['plugged'] else 'Sem veículo conectado'
        if not port['online']:
            vehicle = 'Último estado: ' + vehicle
        result += '<article class="plant-charger ' + tone + (' offline' if not port['online'] else '') + '"><div class="plant-card-top"><div><small>' + esc(charger['id']) + ' · CONECTOR ' + str(port['connector']) + '</small><h4>' + esc(charger['name']) + '</h4></div><span class="plant-badge ' + tone + '">' + esc(port['status']) + '</span></div>'
        result += equipment_svg(port['plugged'], port['alarm'], not port['online'], port['charging'], colors)
        result += '<div class="plant-vehicle"><span>' + ('● CABO CONECTADO' if port['plugged'] and port['online'] else 'ESTADO NÃO CONFIRMADO' if not port['online'] else 'PRONTO PARA CONECTAR') + '</span><b>' + esc(vehicle) + '</b></div>'
        result += '<div class="plant-card-data"><div><span>Potência atual</span><b>' + number(port['power_kw']) + ' <small>kW</small></b></div><div><span>Limite aplicado</span><b>' + number(port['limit_kw']) + ' <small>kW</small></b></div><div><span>Energia da sessão</span><b>' + number(port['energy_kwh'], 2) + ' <small>kWh</small></b></div></div>'
        result += '<div class="plant-card-foot"><span class="plant-network ' + ('normal' if port['online'] else 'lost') + '">' + ('● Online · ' if port['online'] else '⊘ Sem comunicação OCPP · ') + 'Capacidade ' + number(charger['max_kw'], 0) + ' kW</span><span>' + ('Erro: ' + esc(port['error_code']) if port['alarm'] else 'Leitura atual' if port['telemetry_fresh'] else 'Sem leitura atual') + '</span></div></article>'
    if not ports:
        result += '<article class="plant-empty"><h3>Seu parque começa aqui</h3><p>Cadastre um carregador no D-Max para ele aparecer automaticamente nesta planta.</p></article>'
    return result + '</div><p class="plant-note">Supervisão visual · o controle de demanda permanece no D-Max local. Identificação do veículo depende da associação disponível.</p></section>'
