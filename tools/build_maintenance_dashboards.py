"""Extend approved dashboards without moving existing MDBs or changing their queries.

Source: supplied LOGSIS_DSE7420_MAPEAMENTO_TECNICO.csv, GenComm page 7
(offsets 44/48/52). Reused for the DSE8610 GenComm profile; not a firmware
readback or independent DSE8610 hardware verification.
"""
import copy
import json
from pathlib import Path
import re
from urllib.parse import quote, unquote
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPECS = [('DSE7420', 'V41_IMPORTAR.json', 'V42', 54),
         ('DSE8610', 'DSE8610_V3_IMPORTAR.json', 'V4', 53)]
COLORS = {'ok': '#67cce4', 'near': '#f2cc0c', 'due': '#ff9830', 'unknown': '#96aec4'}


def recolor(uri, color):
    raw = unquote(uri.split(',', 1)[1])
    rgb = [int(color[i:i+2], 16)/255 for i in (1, 3, 5)]
    def replace(match):
        value = [int(match[0][i:i+2], 16)/255 for i in (1, 3, 5)]
        light = .22 + .95 * sum(a*b for a, b in zip(value, [.2126, .7152, .0722]))
        return '#' + ''.join(f'{round(min(1,c*light)*255):02x}' for c in rgb)
    return 'data:image/svg+xml;charset=utf-8,' + quote(re.sub(r'#[0-9a-fA-F]{6}', replace, raw), safe='/:')


def maintenance_value(n):
    # JSON row access also works while SQL columns are not yet provisioned.
    # Read the latest raw sample first; a sentinel must not revive an old value.
    text = f"to_jsonb(t)->>'mdb{n}'"
    raw = f"(SELECT {text} FROM $Id_Logsis t WHERE $__timeFilter(\"time\") AND {text} IS NOT NULL ORDER BY \"time\" DESC LIMIT 1)"
    numeric = f"CASE WHEN length(txt)<32 AND txt ~ '^-?[0-9]+([.][0-9]+)?$' THEN txt::numeric END"
    return f'''(SELECT CASE WHEN value=trunc(value) AND value BETWEEN -2147483647 AND 4294967294 AND value NOT IN (2147483647,2147483648) THEN (CASE WHEN value>2147483648 THEN value-4294967296 ELSE value END)/NULLIF((${{Divisor_Horas:sqlstring}})::numeric,0) END FROM (SELECT {numeric} AS value FROM (SELECT {raw} AS txt) raw) parsed) AS "MDB{n}"'''


def build(model, baseline, version, first):
    dashboard = json.loads((ROOT / baseline).read_text())
    old = 'V41' if model == 'DSE7420' else 'V3'
    dashboard['title'] = dashboard['title'].replace(old, version)
    dashboard['tags'] = [version if tag == old else tag for tag in dashboard.get('tags', [])]
    dashboard['description'] = dashboard.get('description', '') + ' Manutenções 1/2/3: horas restantes, nomes e aviso de proximidade configuráveis.'
    variables = dashboard['templating']['list']
    for variable in variables:
        if variable['name']=='Id_Logsis':
            variable['query']='id_'+model.lower()
            variable.pop('current',None)
    if not any(v['name']=='Divisor_Horas' for v in variables):
        variables.append({'name':'Divisor_Horas','type':'constant','query':'3600','hide':2,'skipUrlSync':True})
    for i in range(1, 4):
        variables.append({'name': f'Nome_Manutencao_{i}', 'label': f'Nome da manutenção {i}', 'type': 'constant', 'query': f'Manutenção {i}', 'hide': 2, 'skipUrlSync': True})
    for letter in 'ABCDEFGH':
        variables.append({'name': f'Nome_Entrada_{letter}', 'label': f'Nome da entrada {letter}', 'type': 'constant', 'query': f'Entrada {letter}', 'hide': 2, 'skipUrlSync': True})
    variables.append({'name': 'Manutencao_Alerta_h', 'label': 'Avisar manutenção a partir de (h)', 'type': 'constant', 'query': '50', 'hide': 2, 'skipUrlSync': True})
    overview = dashboard['panels'][0]
    original = overview['targets'][0]['rawSql']
    # Extract the neutral illustration already approved for this model.
    matches = re.findall(r"ELSE '([^']+)' END AS \"GERADOR_ALARME_SVG\"", original)
    assert len(matches) == 1
    neutral = matches[0]
    additions = ',\n'.join(maintenance_value(n) for n in range(first, first+3))
    near_var = '${Manutencao_Alerta_h:sqlstring}'
    near = f"CASE WHEN {near_var} ~ '^[0-9]+([.][0-9]+)?$' AND length({near_var})<16 THEN ({near_var})::numeric ELSE 50 END"
    states = []
    for i, n in enumerate(range(first, first+3), 1):
        states.append(f'''CASE WHEN "MDB{n}" IS NULL THEN 'unknown' WHEN "MDB{n}"<=0 THEN 'due' WHEN "MDB{n}"<=({near}) THEN 'near' ELSE 'ok' END AS "MANUTENCAO_{i}_ESTADO"''')
    conditions = [(f'"MANUTENCAO_{i}_ESTADO"=\'{state}\'', i, state) for state in ['due','near'] for i in range(1,4)]
    label = 'CASE ' + ''.join(f"WHEN {cond} THEN ${{Nome_Manutencao_{i}:sqlstring}} || ' / {'VENCIDA' if state=='due' else 'PRÓXIMA'}' " for cond,i,state in conditions)
    label += '''WHEN "MANUTENCAO_1_ESTADO"='unknown' OR "MANUTENCAO_2_ESTADO"='unknown' OR "MANUTENCAO_3_ESTADO"='unknown' THEN 'MANUTENÇÃO / SEM DADOS' ELSE 'MANUTENÇÃO EM DIA' END'''
    severity = "CASE " + ''.join(f"WHEN {cond} THEN '{state}' " for cond,i,state in conditions) + "WHEN \"MANUTENCAO_1_ESTADO\"='unknown' OR \"MANUTENCAO_2_ESTADO\"='unknown' OR \"MANUTENCAO_3_ESTADO\"='unknown' THEN 'unknown' ELSE 'ok' END"
    alarm = '"MDB41"=1 OR "MDB42"=1 OR "MDB43"=1'
    colored = {state: recolor(neutral, COLORS[state]) for state in ['near','due']}
    picture = f'''CASE WHEN {alarm} THEN "GERADOR_ALARME_SVG" ''' + ''.join(f'''WHEN "MANUTENCAO_ESTADO"='{state}' THEN '{uri}' ''' for state,uri in colored.items()) + '''ELSE "GERADOR_ALARME_SVG" END AS "GERADOR_STATUS_SVG"'''
    input_names = ', '.join('${Nome_Entrada_'+letter+':sqlstring} AS "NOME_ENTRADA_'+letter+'"' for letter in 'ABCDEFGH')
    overview['targets'][0]['rawSql'] = f'''WITH base_manutencao AS ({original}),
contadores_manutencao AS (SELECT base_manutencao.*, {additions} FROM base_manutencao),
estados_manutencao AS (SELECT contadores_manutencao.*, {', '.join(states)} FROM contadores_manutencao),
resumo_manutencao AS (SELECT estados_manutencao.*, {label} AS "MANUTENCAO_RESUMO", {severity} AS "MANUTENCAO_ESTADO" FROM estados_manutencao)
SELECT resumo_manutencao.*, {input_names}, {picture} FROM resumo_manutencao'''
    elements = overview['options']['root']['elements']
    generator = next(e for e in elements if e['name']=='Gerador vetorial')
    generator['background']['image']['field'] = 'GERADOR_STATUS_SVG'
    position = generator['placement']
    bottom = position['top'] + position['height']
    position['height'] -= 20
    template = next(e for e in elements if e['type']=='metric-value')
    badge = copy.deepcopy(template)
    badge.update(name='Indicação de manutenção', placement={**position, 'top': bottom-18, 'height': 16})
    badge['config'].update(text={'mode':'field','field':'MANUTENCAO_RESUMO','fixed':'—'}, size=9, color={'field':'MANUTENCAO_RESUMO','fixed':COLORS['unknown']})
    badge['background']={'color':{'fixed':'transparent'}}
    badge['border']={'color':{'fixed':'transparent'},'width':0}
    badge.pop('connections',None)
    elements.append(badge)
    mappings = []
    for state, expression in [('due','.* / VENCIDA$'),('near','.* / PRÓXIMA$'),('ok','^MANUTENÇÃO EM DIA$'),('unknown','.*SEM DADOS$')]:
        mappings.append({'type':'regex','options':{'pattern':expression,'result':{'color':COLORS[state]}}})
    overview['fieldConfig']['overrides'].append({'matcher':{'id':'byName','options':'MANUTENCAO_RESUMO'},'properties':[{'id':'mappings','value':mappings}]})
    # Input names are Grafana variables in every visible instrument label.
    def walk(item):
        if isinstance(item,dict):
            name = item.get('name','')
            for n, letter in zip(range(44,52),'ABCDEFGH'):
                if name==f'Rótulo MDB{n}':
                    item['type'] = 'metric-value'
                    item['config']['text'] = {'mode':'field','field':'NOME_ENTRADA_'+letter,'fixed':'—'}
            for value in item.values(): walk(value)
        elif isinstance(item,list):
            for value in item:walk(value)
    walk(dashboard['panels'])
    # Reserve a compact row for the three countdowns; Grafana stacks on mobile.
    insertion = min(p['gridPos']['y'] for p in dashboard['panels'] if p['id'] in [25,26])
    def shift(panels):
        for panel in panels:
            if panel['gridPos']['y']>=insertion: panel['gridPos']['y']+=4
            shift(panel.get('panels',[]))
    shift(dashboard['panels'])
    for i,n in enumerate(range(first,first+3),1):
        card = copy.deepcopy(next(p for p in dashboard['panels'] if p['id']==12))
        card.update(id=15+i, title='${Nome_Manutencao_'+str(i)+'} / HORAS RESTANTES', gridPos={'x':8*(i-1),'y':insertion,'w':8,'h':4},
                    description='Tempo restante até a manutenção. Zero ou negativo: vencida. O desenho fica amarelo dentro do limite Manutencao_Alerta_h e laranja quando vencida. Traço: sem leitura válida no período.')
        card['transformations']=[{'id':'filterFieldsByName','options':{'include':{'names':[f'MDB{n}']}}}]
        card['fieldConfig']={'defaults':{'unit':'suffix: h','decimals':1,'noValue':'—','mappings':[{'type':'special','options':{'match':'null','result':{'text':'—','color':COLORS['unknown']}}}], 'color':{'mode':'fixed','fixedColor':COLORS['ok']}},'overrides':[]}
        dashboard['panels'].append(card)
    dashboard['panels'].sort(key=lambda p:(p['gridPos']['y'],p['gridPos']['x']))
    output_name='V42_IMPORTAR.json' if model=='DSE7420' else 'DSE8610_V4_IMPORTAR.json'
    serialized=json.dumps(dashboard,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n'
    (ROOT/output_name).write_text(serialized)
    (ROOT/'logsis_studio/resources'/f'{model.lower()}.json').write_text(serialized)
    with zipfile.ZipFile((ROOT/output_name).with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as archive:archive.writestr(output_name,serialized)
    return output_name

if __name__=='__main__':
    for spec in SPECS:print(build(*spec))
