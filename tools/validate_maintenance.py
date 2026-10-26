"""Maintenance edge cases against isolated PostgreSQL, no equipment commands."""
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from logsis_studio.core import Project

def execute(sql):
    result=subprocess.run(['docker','exec','-i','logsis-postgres','psql','-U','postgres','-d','logsis','-X','-qAt','-v','ON_ERROR_STOP=1'],input=sql,text=True,capture_output=True)
    if result.returncode:raise RuntimeError(result.stderr)
    return [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]

report={'result':'pending','scope':'Isolated PostgreSQL fixtures; no physical controller validation','models':[]}
for model,first,count in [('DSE7420',54,56),('DSE8610',53,55)]:
    project=Project.new(model)
    project.rows[first-1]['DM']="Troca de óleo d'água"
    project.maintenance_alert_hours='20'
    dashboard=project.dashboard('check_maintenance','Teste','ds')
    sql=dashboard['panels'][0]['targets'][0]['rawSql']
    for variable in dashboard['templating']['list']:
        sql=sql.replace('${'+variable['name']+':sqlstring}',"'"+variable['query'].replace("'","''")+"'")
    sql=sql.replace('$Id_Logsis','check_maintenance').replace('$__timeFilter("time")',"\"time\" BETWEEN '2026-10-23T12:00Z' AND '2026-10-23T13:00Z'")
    fields=[f'MDB{first}', 'MANUTENCAO_1_ESTADO','MANUTENCAO_ESTADO','MANUTENCAO_RESUMO','GERADOR_STATUS_SVG','GERADOR_ALARME_SVG']
    select='SELECT row_to_json(q) FROM (SELECT '+','.join('"'+f+'"' for f in fields)+' FROM ('+sql+') all_fields) q;'
    columns=','.join(f'mdb{n} numeric' for n in range(1,count+1))
    parts=['BEGIN;SET LOCAL jit=off;',f'CREATE TEMP TABLE check_maintenance (time timestamptz,gsm_rssi numeric,"WiFi_rssi" numeric,{columns});']
    scenarios=[('normal',21*3600,0,'ok'),('limit',20*3600,0,'near'),('near',3600,0,'near'),('zero',0,0,'due'),('negative',-3600,0,'due'),('unsigned_negative',4294963696,0,'due'),('sentinel',2147483647,0,'unknown'),('sentinel_high',2147483648,0,'unknown'),('sentinel_all',4294967295,0,'unknown'),('absent',None,0,'unknown'),('shutdown',3600,1,'near')]
    for name,raw,shutdown,expected in scenarios:
        parts.append('TRUNCATE check_maintenance;')
        # Valid old value precedes selected range and must not mask a sentinel.
        for timestamp,value in [('2026-10-23T11:59Z',720000),('2026-10-23T12:30Z',raw)]:
            values={n:0 for n in range(1,count+1)}
            values.update({40:1,41:0,42:0,43:shutdown,first:value,first+1:720000,first+2:720000})
            parts.append("INSERT INTO check_maintenance VALUES ('"+timestamp+"',-53,-67,"+','.join('NULL' if values[n] is None else str(values[n]) for n in range(1,count+1))+');')
        parts.append(select)
    # Missing SQL columns must give unknown instead of breaking the old dashboard.
    parts += [f'ALTER TABLE check_maintenance DROP COLUMN mdb{first};',select,'ROLLBACK;']
    results=execute('\n'.join(parts))
    for (name,raw,shutdown,expected),result in zip(scenarios,results):
        assert result['MANUTENCAO_1_ESTADO']==expected,(model,name,result)
        if name in ['negative','unsigned_negative']:assert result[f'MDB{first}']==-1
        if name in ['normal','limit']:assert result[f'MDB{first}']==raw/3600
        if expected=='unknown':assert result[f'MDB{first}'] is None
        if expected in ['near','due']:
            assert "Troca de óleo d'água" in result['MANUTENCAO_RESUMO']
            assert (result['GERADOR_STATUS_SVG']==result['GERADOR_ALARME_SVG'])==bool(shutdown)
        else:assert result['GERADOR_STATUS_SVG']==result['GERADOR_ALARME_SVG']
    assert results[-1]['MANUTENCAO_1_ESTADO']=='unknown'
    report['models'].append({'model':model,'cases':[s[0] for s in scenarios]+['missing_sql_column'],'passed':True})
report['result']='passed'
(ROOT/'LOGSIS_MANUTENCAO_VALIDACAO.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
