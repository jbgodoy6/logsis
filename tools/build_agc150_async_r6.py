"""Fix asynchronous telemetry in the exported dashboard without changing BIN/Studio."""
from pathlib import Path
import copy, json, zipfile
import sys

ROOT=Path(__file__).resolve().parents[1]
STEM='AGC150_ECU_MITSUBISHI_R6_ULTIMAS_LEITURAS'
sys.path.insert(0,str(ROOT))
from logsis_studio.core import load_profile


def build():
    original=json.loads((ROOT/'AGC150_REDE_GERADOR_ECU_ME96SS_R5_SEM_CAMPOS.json').read_text(encoding='utf-8'))
    d=copy.deepcopy(original)
    keys=','.join("('mdb"+str(i)+"')" for i in range(1,73))
    keys+=",('gsm_rssi'),(${Campo_WiFi_RSSI:sqlstring})"
    # Resolve each raw field separately, bounded by BOTH ends of the filter.
    # A received zero, overflow or malformed value is a new observation and
    # must not be replaced by an older apparently good measurement.
    # Only absent/SQL NULL/JSON null/empty fields mean 'not transmitted'.
    latest=f'''WITH wanted(field) AS (VALUES {keys}), latest AS (
      SELECT wanted.field,r."time",r.value FROM wanted LEFT JOIN LATERAL (
        SELECT t."time",to_jsonb(t)->wanted.field AS value
        FROM ${{Id_Logsis:raw}} t WHERE $__timeFilter("time")
          AND nullif(btrim(to_jsonb(t)->>wanted.field),'') IS NOT NULL
        ORDER BY t."time" DESC,(to_jsonb(t)->wanted.field)::text DESC LIMIT 1
      ) r ON true)
      SELECT max("time") AS "time",
        coalesce(jsonb_object_agg(field,value) FILTER(WHERE "time" IS NOT NULL),'{{}}'::jsonb) AS payload,
        coalesce(jsonb_object_agg(field,to_jsonb("time")) FILTER(WHERE "time" IS NOT NULL),'{{}}'::jsonb) AS observed_at
      FROM latest'''
    main=original['panels'][0]['targets'][0]['rawSql']
    controller_sample='SELECT "time",to_jsonb(t) AS payload FROM ${Id_Logsis:raw} t WHERE $__timeFilter("time") ORDER BY "time" DESC LIMIT 1'
    meter_sample='SELECT to_jsonb(t) AS payload FROM ${Id_Logsis:raw} t WHERE $__timeFilter("time") ORDER BY "time" DESC LIMIT 1'
    assert main.count(controller_sample)==1 and main.count(meter_sample)==1
    updated=main.replace(controller_sample,'SELECT "time",payload FROM latest_values').replace(meter_sample,'SELECT payload FROM latest_values')
    assert updated.startswith('WITH controller AS (')
    updated='WITH latest_values AS MATERIALIZED ('+latest+'), '+updated[len('WITH '):]
    # Expose field-specific timestamps as query metadata; the footer shows
    # only the most recent update among the selected channels, not simultaneity.
    updated=updated.replace('SELECT controller.*,meter.*,','SELECT controller.*,meter.*,(SELECT observed_at FROM latest_values) AS "OBSERVED_AT",',1)
    def visit(obj):
        if isinstance(obj,dict):
            for k,v in obj.items():
                if k=='rawSql' and isinstance(v,str):obj[k]=v.replace(main,updated)
                elif k=='fixed' and v=='ÚLTIMO REGISTRO / BRASÍLIA':obj[k]='ÚLTIMA ATUALIZAÇÃO / BRASÍLIA'
                else:visit(v)
        elif isinstance(obj,list):
            for v in obj:visit(v)
    visit(d)
    # Histories still use the sensor's real sample time. Availability flags
    # and the two meter words can have arrived in earlier packets; resolve
    # those dependencies at/before each point, never from the future.
    def asof_payload(fields):
        pairs=[]
        for field in fields:
            observed=f'''(SELECT to_jsonb(v)->'{field}' FROM ${{Id_Logsis:raw}} v
              WHERE $__timeFilter("time") AND v."time"<=t."time"
              AND nullif(btrim(to_jsonb(v)->>'{field}'),'') IS NOT NULL
              ORDER BY v."time" DESC LIMIT 1)'''
            pairs.extend(["'"+field+"'",observed])
        return 'SELECT to_jsonb(t)||jsonb_build_object('+','.join(pairs)+') AS payload'
    flags={'mdb'+str(c.number) for c in load_profile('AGC150_GEN_ECU').channels if c.role.startswith('ecu_validity_')}
    def history_fix(panel):
        if panel.get('type')=='timeseries':
            for target in panel.get('targets',[]):
                sql=target.get('rawSql','')
                needed=sorted(field for field in flags if "payload->>'"+field+"'" in sql)
                if panel['id']==142:needed=['mdb71','mdb72']
                if needed:
                    assert 'SELECT to_jsonb(t) AS payload' in sql
                    target['rawSql']=sql.replace('SELECT to_jsonb(t) AS payload',asof_payload(needed))
        for child in panel.get('panels',[]):history_fix(child)
    for panel in d['panels']:history_fix(panel)
    d['version']=7
    for v in d['templating']['list']:v['hide']=2
    note=(' R6: cada variável usa a última observação recebida dentro do período, '
          'mesmo com envios em horários diferentes. Campos ausentes/nulos/vazios não apagam '
          'a observação anterior dentro do filtro. Zero atualiza normalmente; estouro ou '
          'dado inválido recebido mostra traço, sem recuperar um valor antigo. '
          'OBSERVED_AT guarda os horários individuais; o rodapé mostra a atualização mais recente. '
          'O conjunto exibido pode reunir horários diferentes. Contadores do período continuam '
          'usando a base anterior ao filtro exclusivamente para calcular horas/kWh.')
    d['description']+=note
    for p in d['panels']:
        if p['type']=='canvas':p['description']=p.get('description','')+note
    assert d['uid']==original['uid']
    assert all(v['hide']==2 for v in d['templating']['list'])
    path=ROOT/(STEM+'.json')
    path.write_text(json.dumps(d,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    with zipfile.ZipFile(ROOT/(STEM+'.zip'),'w',zipfile.ZIP_DEFLATED) as z:z.write(path,path.name)
    with zipfile.ZipFile(ROOT/(STEM+'.zip')) as z:
        assert z.testzip() is None and z.read(path.name)==path.read_bytes()
    print('Created',STEM+'.zip','— latest observation per variable; same R5 BIN and UID.')
    return d

if __name__=='__main__':build()
