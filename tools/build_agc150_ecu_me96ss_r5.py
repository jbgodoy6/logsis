"""Standalone paired export: new 59-channel ECU profile + independent ME96SS.

Does not change the Studio catalog or any conventional profile.
The previous BIN supplies only device communication settings and meter FC03
parameters. Every AGC channel comes from AGC150_GEN_ECU, never the old map.
"""
from pathlib import Path
from dataclasses import replace
import copy, csv, hashlib, io, json, re, sys, zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from logsis_studio.core import BinDocument, Project, MDB_FIELDS, DEFAULT_MDB, MDB_KEY
from logsis_studio import electronic_dashboard as ecu, manual_dashboard as ui, standard_layout as layout

STEM = 'AGC150_REDE_GERADOR_ECU_ME96SS_R5'


def build():
    source = BinDocument.from_bytes((ROOT / 'AGC150_ECU_ME96SS_R4.bin').read_bytes())
    project = Project.new('AGC150_GEN_ECU')
    project.change_slave(source.params['MDBA_ID0'])
    base = replace(project.profile, channels=tuple(
        replace(c, params=project.rows[c.index]) for c in project.profile.channels))
    assert base.count == 59
    # Copy the existing, independently addressed Mitsubishi (slave 2).
    meter = []
    captions = ['Corrente R', 'Corrente S', 'Corrente T', 'Corrente total',
                'Tensão R–S', 'Tensão S–T', 'Tensão R–T', 'Fator de potência',
                'Potência ativa', 'Potência reativa', 'Potência aparente',
                'Energia LOWER', 'Energia HIGHER']
    for offset, caption in enumerate(captions):
        row = {f: source.params[f'MDBA_{f}{84+offset}'] for f in MDB_FIELDS}
        row.update(DM='ME96SS · '+caption, DH='ME96SS · '+caption+' ALTO',
                   DL='ME96SS · '+caption+' BAIXO')
        meter.append(row)
    rows = project.rows[:59] + meter + [dict(DEFAULT_MDB) for _ in range(28)]
    data = source.without_mdbs().render({f'MDBA_{f}{i}': row[f]
                                      for i, row in enumerate(rows) for f in MDB_FIELDS})
    result = BinDocument.from_bytes(data)
    assert len(rows) == 100 and not result.duplicates
    for k, v in source.params.items():
        if not MDB_KEY.fullmatch(k):
            assert result.params[k] == v
    for c in base.channels:
        assert all(result.params[f'MDBA_{f}{c.index}'] == c.params[f] for f in MDB_FIELDS)
    assert [int(result.params[f'MDBA_ID{i}']) for i in range(59,72)] == [2]*13

    d = ecu.build_dashboard(base)
    d.update(uid='logsis-agc150-ecu-me96ss-r5', version=5,
             title='LOGSIS / AGC150 ECU + Mitsubishi ME96SS · Rede e gerador')
    vs = d['templating']['list']
    for v in vs:
        if v['name'] == 'Id_Logsis':
            v.update(type='textbox', label='Tabela SQL', hide=0, query='id_79979099838660')
        v['current'] = {'text': v['query'], 'value': v['query']}
    vs.insert(0, {'name':'DS_POSTGRES','label':'PostgreSQL','type':'datasource',
                 'query':'grafana-postgresql-datasource','hide':0,'refresh':1,
                 'current':{'text':'PostgreSQL','value':'zKW_ld27k'}})
    for name, value in [('I','1'),('V','10'),('P','1'),('Q','1'),('S','1'),
                        ('FP','1000'),('kWh','1')]:
        vs.append({'name':'MM_Divisor_'+name,'label':'ME96SS · divisor '+name,
                   'type':'constant','query':value,'current':{'text':value,'value':value},
                   'hide':2,'skipUrlSync':True})
    vs.append({'name':'MM_Base_Energia','label':'ME96SS · multiplicador HIGHER',
               'type':'constant','query':'10000','current':{'text':'10000','value':'10000'},
               'hide':2,'skipUrlSync':True})

    def raw(n): return ui.numeric(f"payload->>'mdb{n}'")
    def word(n):
        r=raw(n)
        return f'CASE WHEN {r}=trunc({r}) AND {r} BETWEEN -32768 AND 65535 THEN mod({r}+65536,65536) END'
    def div(name): return 'NULLIF('+ui.var('MM_Divisor_'+name)+'::numeric,0)'
    specs=[('I1',60,'I','A','Corrente R'),('I2',61,'I','A','Corrente S'),
           ('I3',62,'I','A','Corrente T'),('IT',63,'I','A','Corrente total'),
           ('V12',64,'V','V','Tensão R–S'),('V23',65,'V','V','Tensão S–T'),
           ('V31',66,'V','V','Tensão R–T'),('FP',67,'FP','','Fator de potência'),
           ('P',68,'P','kW','Potência ativa'),('Q',69,'Q','kvar','Potência reativa'),
           ('S',70,'S','kVA','Potência aparente')]
    exprs={name:'('+word(n)+')/'+div(key) for name,n,key,unit,label in specs}
    lo, hi='('+word(71)+')','('+word(72)+')'
    energybase=ui.var('MM_Base_Energia')+'::numeric'
    exprs.update(LOWER=lo,HIGHER=hi,ENERGY=f'CASE WHEN {energybase}>1 AND {lo}<{energybase} THEN ({hi}*{energybase}+{lo})/{div("kWh")} END')
    oldmain=d['panels'][0]['targets'][0]['rawSql']
    # Same timestamp is used for all channels: no last-non-null switch fallback.
    meter_sql='WITH meter_sample AS (SELECT to_jsonb(t) AS payload FROM $Id_Logsis t WHERE $__timeFilter("time") ORDER BY "time" DESC LIMIT 1) SELECT '+','.join(x+f' AS "MM_{k}"' for k,x in exprs.items())+' FROM (SELECT (SELECT payload FROM meter_sample) AS payload) m'
    formats=[]
    for name,n,key,unit,label in specs:
        fmt='FM999999999990.000' if key=='FP' else 'FM999999999990.0' if key=='V' else 'FM999999999990'
        formats.append(f'CASE WHEN "MM_{name}" IS NOT NULL THEN to_char("MM_{name}",{ui.sq(fmt)})||{ui.sq(" "+unit if unit else "")} ELSE \'—\' END AS "MM_{name}_TEXT"')
    formats += ['\'ENERGIA ACUMULADA\' AS "MM_ENERGY_CAPTION"',
                'CASE WHEN "MM_ENERGY" IS NOT NULL THEN to_char("MM_ENERGY",\'FM999999999999990.00\')||\' kWh\' ELSE \'—\' END AS "MM_ENERGY_TEXT"',
                '\'MEDIDOR INDEPENDENTE · SEM VÍNCULO COM A PLANTA\' AS "MM_STATUS"']
    main='WITH controller AS ('+oldmain+'), meter AS ('+meter_sql+') SELECT controller.*,meter.*,'+','.join(formats)+' FROM controller CROSS JOIN meter'

    def upgrade(obj):
        if isinstance(obj,dict):
            if obj.get('type')=='grafana-postgresql-datasource': obj['uid']='${DS_POSTGRES}'
            for k,v in obj.items():
                if k=='rawSql': obj[k]=v.replace(oldmain,main).replace('$Id_Logsis','${Id_Logsis:raw}')
                else: upgrade(v)
        elif isinstance(obj,list):
            for v in obj: upgrade(v)
    upgrade(d)
    # Reuse only the approved drawing of the meter; its SQL is newly generated.
    artwork=json.loads((ROOT/'AGC150_ECU_ME96SS_IMPORTAR_R4.json').read_text(encoding='utf-8'))
    panel=copy.deepcopy(next(p for p in artwork['panels'] if p['id']==2))
    panel.update(id=40, title='02 / Multimedidor independente · Mitsubishi ME96SS',
                 description='ME96SS em Slave 2, FC03. MDB60–72. Sem ligação elétrica com o unifilar do AGC150.')
    panel['targets']=[{'refId':'A','rawQuery':True,'format':'table','editorMode':'code',
                       'rawSql':main.replace('$Id_Logsis','${Id_Logsis:raw}')}]
    panel['datasource']={'type':'grafana-postgresql-datasource','uid':'${DS_POSTGRES}'}
    panel['fieldConfig']={'defaults':{'noValue':'—','color':{'mode':'fixed','fixedColor':'#e4edf6'},
                                      'thresholds':{'mode':'absolute','steps':[{'color':'#e4edf6','value':None}]}},'overrides':[]}
    # Show meter at the top, preserving the tower/contact/generator composition.
    for p in d['panels']:
        if p['id']==2:
            cfg=p['fieldConfig']
            primary=[c for c in base.channels if c.role.startswith('gen_') and
                     ('_v_' in c.role or '_i_' in c.role or c.role=='gen_frequency')]
            compact=layout.group(replace(base,vendor='DEIF',kind='deif'),2,
                '04 / Gerador · instrumentação elétrica',primary,
                {'x':0,'y':30,'w':24,'h':9},300,3)
            compact['fieldConfig']=cfg
            p.clear();p.update(compact)
        elif p['gridPos']['y']>=30:
            p['gridPos']['y']+=9
            for child in p.get('panels',[]): child['gridPos']['y']+=9
    d['panels'].append(panel)
    d['panels'].sort(key=lambda p:(p['gridPos']['y'],p['gridPos']['x']))
    row=next(p for p in d['panels'] if p['type']=='row')
    nexty=max((p['gridPos']['y']+p['gridPos']['h'] for p in row['panels']),default=row['gridPos']['y']+1)
    for pid,title,names,unit in [(140,'ME96SS independente · tensões',['V12','V23','V31'],'volt'),
                                (141,'ME96SS independente · correntes',['I1','I2','I3'],'amp'),
                                (142,'ME96SS independente · energia acumulada',['ENERGY'],'kwatth')]:
        template=copy.deepcopy(row['panels'][0]);template.update(id=pid,title=title,gridPos={'x':0,'y':nexty,'w':24,'h':8})
        template['fieldConfig']['defaults']['unit']=unit
        template['targets']=[{'refId':chr(65+i),'rawQuery':True,'format':'time_series','editorMode':'code',
            'rawSql':'SELECT t."time",('+exprs[name]+') AS '+ui.sq('ME96SS '+name).replace("'",'"')+' FROM ${Id_Logsis:raw} t CROSS JOIN LATERAL (SELECT to_jsonb(t) AS payload) m WHERE $__timeFilter("time") ORDER BY t."time"'} for i,name in enumerate(names)]
        row['panels'].append(template);nexty+=8
    digest=hashlib.sha256(data).hexdigest()
    d['description'] += (' Exportação exclusiva R5: mapa novo AGC150_GEN_ECU, MDB1–59; '
        'Mitsubishi ME96SS independente MDB60–72, Slave 2. Não reutiliza o mapa AGC anterior. '
        'Energia ME96SS: HIGHER MDB72 × 10000 + LOWER MDB71, conforme ajuste anterior '
        'ao visor informado; confirmação simultânea em campo ainda pendente. BIN SHA256 '+digest+'.')
    (ROOT/(STEM+'.bin')).write_bytes(data)
    (ROOT/(STEM+'.json')).write_text(json.dumps(d,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    lines=['MDB;Equipamento;Nome;Slave;FNC;Endereco;Bit;Divisor']
    for c in base.channels:
        lines.append(';'.join(map(str,[c.number,'AGC150 ECU',c.name,c.params['ID'],c.params['FNC'],c.params['ADDR'],c.params['BIT'],c.divisor])))
    for i,r in enumerate(meter,60):
        scale=10 if 64<=i<=66 else 1000 if i==67 else 1
        lines.append(';'.join(map(str,[i,'ME96SS independente',r['DM'],r['ID'],r['FNC'],r['ADDR'],r['BIT'],scale])))
    (ROOT/(STEM+'_MAPA.csv')).write_text('\n'.join(lines)+'\n',encoding='utf-8-sig')
    readme='''AGC150 REDE + GERADOR ECU / MITSUBISHI ME96SS — R5

Mapa novo AGC150_GEN_ECU: MDB1–59. Medidor independente: MDB60–72.
Instale este BIN com este JSON. O histórico gravado no mapa anterior tem
posições diferentes: selecione apenas dados coletados após instalar o R5.
O JSON tem UID próprio. Configure Tabela SQL e datasource no Grafana.
AGC150 Slave 1; Mitsubishi Slave 2. Comunicação geral preservada do BIN
anterior. São dois instrumentos na mesma comunicação; não há ligação do
Mitsubishi ao desenho elétrico do AGC150.

Modos lidos: BLOCK, MANUAL sem regulação, SEMI-AUTO, AUTO e TESTE.
ECU: óleo, temperatura, combustível/alimentação e rail, consumo, níveis,
carga, admissão e escape; valores dependem do suporte da ECU e firmware.
Pressão e temperatura seguem as unidades configuradas no controlador.
Estouro/indisponível = traço. Motor parado exige estado nativo válido.
Warning amarelo, trip laranja, shutdown vermelho; manutenção tem indicação
separada. Horas e energia de geração são calculadas para o período filtrado.

Mitsubishi: tensão /10, FP /1000, corrente e potências /1.
Energia: HIGHER × 10000 + LOWER, mantendo a composição anterior ajustada
à ordem de grandeza do visor. Exemplo 584 e 868 = 5840868 kWh.
A confirmação documental/por leitura simultânea dessa composição permanece
pendente. MM_Base_Energia e divisores são configuráveis no dashboard.
Nenhum comando de manobra ou mudança de modo é enviado pelo Grafana.
Studio e perfis convencionais não foram alterados.
'''
    (ROOT/(STEM+'_LEIA-ME.txt')).write_text(readme,encoding='utf-8')
    with zipfile.ZipFile(ROOT/(STEM+'.zip'),'w',zipfile.ZIP_DEFLATED) as z:
        for suffix in ['.bin','.json','_MAPA.csv','_LEIA-ME.txt']:
            z.write(ROOT/(STEM+suffix),STEM+suffix)
    print(json.dumps({'file':STEM,'agcProfile':base.model,'agcChannels':59,'meterChannels':13,
                      'activeSlots':72,'sha256':digest},indent=2))
    return d,base,exprs

if __name__=='__main__': build()
