"""Local, deterministic PDF reports; no cloud, subprocesses or runtime PDF package."""
from datetime import datetime
from functools import lru_cache
from pathlib import Path
import time
from zoneinfo import ZoneInfo


def report_data(store, start='', end='', vehicle_id='', charger_id='', report_type='detailed', vehicles='', energy_scope='all'):
    zone = ZoneInfo(store.settings()['timezone'])
    if report_type not in ('detailed', 'vehicles') or energy_scope not in ('all', 'physical', 'simulation'):
        raise ValueError('Tipo de relatório ou origem inválida')
    selected = set(filter(None, vehicles.split(',')))

    def parse(value):
        if not value:
            return None
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=zone)
        return dt.timestamp()

    try:
        after, before = parse(start), parse(end)
    except (ValueError, OverflowError):
        raise ValueError('Informe datas válidas para o relatório') from None
    if after is not None and before is not None and after >= before:
        raise ValueError('O término do filtro deve ser posterior ao início')
    vehicles = {v['id']: v for v in store.entities('vehicle')}
    if selected - vehicles.keys() - {'unassigned'}:
        raise ValueError('Veículo selecionado não encontrado')
    chargers = {c['id']: c for c in store.entities('charger')}
    if vehicle_id and vehicle_id not in vehicles or charger_id and charger_id not in chargers:
        raise ValueError('Veículo ou carregador não encontrado')
    now = time.time()
    sessions = []
    all_selected = []
    for s in sorted(store.entities('session'), key=lambda r: (r['started_at'], r['id'])):
        cid = s['port'].rsplit(':', 1)[0]
        scope = 'simulation' if s.get('mode') in ('simulator', 'simulation') else 'physical' if s.get('mode') == 'ocpp' else 'unknown'
        if (energy_scope != 'all' and scope != energy_scope or selected and (s.get('vehicle_id') or 'unassigned') not in selected
                or vehicle_id and s.get('vehicle_id') != vehicle_id or charger_id and cid != charger_id):
            continue
        all_selected.append(s)
        if (after is not None and s['started_at'] < after or before is not None and s['started_at'] >= before
                or vehicle_id and s.get('vehicle_id') != vehicle_id or charger_id and cid != charger_id):
            continue
        sessions.append(dict(s, vehicle_name=vehicles.get(s.get('vehicle_id'), {}).get('name', 'Não identificado'),
                             plate=vehicles.get(s.get('vehicle_id'), {}).get('plate', ''),
                             charger_name=chargers.get(cid, {}).get('name', cid),
                             duration_s=max(0, (s.get('ended_at') or now) - s['started_at'])))
        if len(sessions) > 20000 and report_type == 'detailed':
            raise ValueError('Mais de 20.000 sessões; reduza o período do relatório')
    groups = {}
    for s in all_selected:
        key = s.get('vehicle_id') or 'unassigned'
        scope = 'simulation' if s.get('mode') in ('simulator', 'simulation') else 'physical' if s.get('mode') == 'ocpp' else 'unknown'
        row = groups.setdefault((key, scope), dict(vehicle_name=vehicles.get(key, {}).get('name', 'Sem veículo associado'),
                scope=scope, total_kwh=0.0, period_kwh=0.0, count=0, last_at=0))
        row['total_kwh'] += s['energy_kwh']
        row['count'] += 1
        row['last_at'] = max(row['last_at'], s['started_at'])
        if (after is None or s['started_at'] >= after) and (before is None or s['started_at'] < before):
            row['period_kwh'] += s['energy_kwh']
    for identifier, vehicle in vehicles.items():
        if selected and identifier not in selected or vehicle_id and identifier != vehicle_id:
            continue
        if not any(key[0] == identifier for key in groups):
            scope = energy_scope if energy_scope != 'all' else 'physical'
            groups[(identifier,scope)] = dict(vehicle_name=vehicle['name'],scope=scope,total_kwh=0,period_kwh=0,count=0,last_at=None)
    return dict(site=store.settings()['site_name'], timezone=str(zone), generated_at=now, sessions=sessions,
                report_type=report_type, vehicle_summary=list(groups.values()), energy_scope=energy_scope,
                real_kwh=sum(s['energy_kwh'] for s in sessions if s.get('mode') == 'ocpp'),
                simulated_kwh=sum(s['energy_kwh'] for s in sessions if s.get('mode') in ('simulator','simulation')),
                unknown_kwh=sum(s['energy_kwh'] for s in sessions if s.get('mode') not in ('ocpp','simulator','simulation')),
                start=after, end=before, vehicle=vehicles.get(vehicle_id, {}).get('name', 'Todos'),
                charger=chargers.get(charger_id, {}).get('name', 'Todos'),
                total_kwh=sum(s['energy_kwh'] for s in sessions),
                total_seconds=sum(s['duration_s'] for s in sessions),
                ongoing=sum(not bool(s.get('ended_at')) for s in sessions))


def decimal(value, digits=2):
    return f'{value:,.{digits}f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def duration(seconds):
    minutes = int(seconds // 60)
    return f'{minutes // 60:02d}h {minutes % 60:02d}min'


def literal(text):
    value = str(text).replace('\n', ' ').replace('\r', ' ').encode('cp1252', 'replace').decode('latin1')
    return '(' + value.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)') + ')'


@lru_cache(maxsize=2)
def logo(name):
    return (Path(__file__).parent / 'static' / (name + '-report.jpg')).read_bytes()


def build_pdf(data, version):
    zone = ZoneInfo(data['timezone'])
    def stamp(value):
        return datetime.fromtimestamp(value, zone).strftime('%d/%m/%Y %H:%M') if value is not None else 'Sem limite'

    def text(x, y, value, size=10, bold=False, color='0.05 0.17 0.29'):
        return f'BT /{"B" if bold else "F"} {size} Tf {color} rg 1 0 0 1 {x} {y} Tm {literal(value)} Tj ET\n'

    pages = []
    general = data.get('report_type') == 'vehicles'
    rows = data['vehicle_summary'] if general else data['sessions']
    groups = [rows[i:i+12] for i in range(0, len(rows), 12)] or [[]]
    for page, group in enumerate(groups, 1):
        stream = 'q 145 0 0 53 30 766 cm /Logo Do Q\nq 56 0 0 56 510 765 cm /Energy Do Q\n'
        stream += text(30, 743, 'RELATÓRIO DE RECARGAS', 17, True)
        stream += text(30, 723, data['site'][:85], 12, True)
        stream += text(30, 704, f'Início das sessões: {stamp(data["start"])} até {stamp(data["end"])}', 9)
        stream += text(30, 690, 'Veículo: ' + data['vehicle'][:75], 9)
        stream += text(30, 676, 'Carregador: ' + data['charger'][:72], 9)
        stream += text(30, 657, f'{len(data["sessions"])} sessões no período | Totais por origem abaixo | {duration(data["total_seconds"])}', 10, True)
        stream += text(30, 642, f'Em andamento: {data["ongoing"]}  |  Fuso: {data["timezone"]}', 8)
        stream += text(30, 632, 'Real: '+decimal(data.get('real_kwh',0),3)+' kWh | Simulação: '+decimal(data.get('simulated_kwh',0),3)+' kWh | Origem desconhecida: '+decimal(data.get('unknown_kwh',0),3), 7)
        if general:
            stream += text(30, 609, 'GERAL POR VEÍCULO · ACUMULADO HISTÓRICO E SUBTOTAL DO PERÍODO', 9, True)
            y=581
            for row in group:
                scope={'physical':'REAL','simulation':'SIMULAÇÃO','unknown':'ORIGEM DESCONHECIDA'}[row['scope']]
                stream += text(30,y,row['vehicle_name'][:65]+' · '+scope,9,True)
                stream += text(30,y-13,'Histórico: '+decimal(row['total_kwh'],3)+' kWh | Período: '+decimal(row['period_kwh'],3)+' kWh | Recargas: '+str(row['count']),8)
                stream += text(30,y-25,'Último início de recarga: '+(stamp(row['last_at']) if row['last_at'] else 'Sem recarga registrada'),8)
                y-=40
        if not general:
            stream += '0.9 0.94 0.97 rg 30 609 535 22 re f\n'
            stream += text(36, 617, 'INÍCIO / FIM', 8, True) + text(208, 617, 'VEÍCULO / CARREGADOR', 8, True)
            stream += text(443, 617, 'DURAÇÃO', 8, True) + text(509, 617, 'kWh', 8, True)
        y = 592
        for row in ([] if general else group):
            stream += text(36, y, stamp(row['started_at']), 8)
            stream += text(36, y-13, stamp(row['ended_at']) if row.get('ended_at') else 'Em andamento · parcial', 8)
            stream += text(208, y, row['vehicle_name'][:40], 8, True)
            stream += text(208, y-13, (row['charger_name'] + ' · ' + row['port'])[:44], 8)
            mode = 'SIMULAÇÃO' if row.get('mode') in ('simulator','simulation') else 'OCPP' if row.get('mode') == 'ocpp' else 'ORIGEM DESCONHECIDA'
            quality = ' · interrompida' if row.get('quality') == 'interrupted' else ''
            stream += text(208, y-25, (mode + quality + (' · ' + row['plate'] if row['plate'] else ''))[:50], 7, color='0.35 0.43 0.5')
            stream += text(443, y, duration(row['duration_s']), 8) + text(509, y, decimal(row['energy_kwh'], 3), 8)
            stream += f'0.87 0.91 0.94 RG 0.5 w 30 {y-32} m 565 {y-32} l S\n'
            y -= 40
        if not group:
            stream += text(36, 579, 'Nenhuma recarga encontrada para os filtros selecionados.', 11)
        notes = ['Filtro pelo início da sessão: início incluso e término exclusivo. Energia total de cada sessão selecionada;',
                 'não é o consumo recortado dentro do intervalo. Sessões abertas têm valores parciais. Simulações são identificadas.',
                 'Energia registrada pelos carregadores; sem custo financeiro estimado. Documento de acompanhamento operacional.']
        for n, note in enumerate(notes):
            stream += text(30, 81-n*11, note, 7, color='0.35 0.43 0.5')
        stream += text(30, 28, f'EnergyCube D-Max v{version} · Emitido em {stamp(data["generated_at"])}', 8)
        stream += text(482, 28, f'Página {page}/{len(groups)}', 8)
        pages.append(stream.encode('latin1'))

    return assemble_pdf(pages)


def assemble_pdf(pages):
    objects = []
    def obj(value):
        objects.append(value if isinstance(value, bytes) else value.encode('ascii'))
        return len(objects)
    def stream_obj(header, payload):
        return obj(f'<< {header} /Length {len(payload)} >>\nstream\n'.encode() + payload + b'\nendstream')
    catalog = obj('')
    page_tree = obj('')
    normal = obj('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>')
    bold = obj('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>')
    # Fixed branding assets derived from the supplied PNGs; JPEG dimensions are
    # read from their SOF marker, avoiding an imaging dependency on the Raspberry.
    images = []
    for name in ('d-max', 'energycube'):
        payload = logo(name)
        at = 2
        while at < len(payload):
            marker = payload[at+1]
            length = int.from_bytes(payload[at+2:at+4], 'big')
            if marker in (0xC0, 0xC2):
                h = int.from_bytes(payload[at+5:at+7], 'big')
                w = int.from_bytes(payload[at+7:at+9], 'big')
                break
            at += length + 2
        else:
            raise ValueError('Logo JPEG inválido')
        images.append(stream_obj(f'/Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode', payload))
    ids = []
    for content in pages:
        content_id = stream_obj('', content)
        ids.append(obj(f'<< /Type /Page /Parent {page_tree} 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F {normal} 0 R /B {bold} 0 R >> /XObject << /Logo {images[0]} 0 R /Energy {images[1]} 0 R >> >> /Contents {content_id} 0 R >>'))
    objects[catalog-1] = f'<< /Type /Catalog /Pages {page_tree} 0 R >>'.encode()
    objects[page_tree-1] = ('<< /Type /Pages /Count ' + str(len(ids)) + ' /Kids [' + ' '.join(f'{i} 0 R' for i in ids) + '] >>').encode()
    result = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = [0]
    for i, value in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(f'{i} 0 obj\n'.encode() + value + b'\nendobj\n')
    xref = len(result)
    result.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:
        result.extend(f'{offset:010d} 00000 n \n'.encode())
    result.extend(f'trailer\n<< /Size {len(offsets)} /Root {catalog} 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    return bytes(result)
