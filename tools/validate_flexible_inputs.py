"""Check PDF-derived input states against actual exported SQL in the isolated lab."""
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from logsis_studio.core import Project

report={'result':'pending','source':'DSE_GENCOMM_MAPA_CONFERIDO.json','scope':'Isolated PostgreSQL; processed Q/R/S states only','models':[]}
for model,first in [('DSE7420',57),('DSE8610',56)]:
    project=Project.new(model)
    project.rows[first-1]['DM']="Porta d'água"
    d=project.dashboard('test_flex','Teste','ds')
    sql=d['panels'][0]['targets'][0]['rawSql']
    for variable in d['templating']['list']:
        sql=sql.replace('${'+variable['name']+':sqlstring}',"'"+variable['query'].replace("'","''")+"'")
    sql=sql.replace('$Id_Logsis','test_flex').replace('$__timeFilter("time")',"\"time\" BETWEEN '2026-10-23T12:00Z' AND '2026-10-23T13:00Z'")
    fields=[f'MDB{n}' for n in range(first,first+3)]+['NOME_ENTRADA_Q','NOME_ENTRADA_R','NOME_ENTRADA_S']
    select='SELECT row_to_json(r) FROM (SELECT '+','.join('"'+f+'"' for f in fields)+' FROM ('+sql+') exported) r;'
    columns=','.join(f'mdb{n} numeric' for n in range(1,project.profile.count+1))
    parts=['BEGIN;SET LOCAL jit=off;',f'CREATE TEMP TABLE test_flex(time timestamptz,gsm_rssi numeric,"WiFi_rssi" numeric,{columns});']
    cases=[('active',1,1),('inactive',0,0),('sentinel',65535,None),('invalid',2,None),('null',None,None)]
    for name,raw,expected in cases:
        parts.append('TRUNCATE test_flex;')
        samples=[('2026-10-23T11:59Z',1),('2026-10-23T12:30Z',raw),('2026-10-23T13:01Z',1)]
        if name in ['invalid','sentinel']:samples.insert(1,('2026-10-23T12:10Z',1))
        for timestamp,value in samples:
            values={n:0 for n in range(1,project.profile.count+1)}
            values.update({40:1,first:value,first+1:1,first+2:0})
            parts.append("INSERT INTO test_flex VALUES ('"+timestamp+"',-53,-67,"+','.join('NULL' if values[n] is None else str(values[n]) for n in range(1,project.profile.count+1))+');')
        parts.append(select)
    parts += [f'ALTER TABLE test_flex DROP COLUMN mdb{first};',select,'ROLLBACK;']
    run=subprocess.run(['docker','exec','-i','logsis-postgres','psql','-U','postgres','-d','logsis','-X','-qAt','-v','ON_ERROR_STOP=1'],input='\n'.join(parts),text=True,capture_output=True)
    if run.returncode:raise RuntimeError(run.stderr)
    rows=[json.loads(line) for line in run.stdout.splitlines() if line.startswith('{')]
    for (name,raw,expected),row in zip(cases,rows):
        assert row[f'MDB{first}']==expected,(model,name,row)
        assert row[f'MDB{first+1}']==1 and row[f'MDB{first+2}']==0
        assert row['NOME_ENTRADA_Q']=="Porta d'água"
    assert rows[-1][f'MDB{first}'] is None
    report['models'].append({'model':model,'channels':[first,first+1,first+2],'addresses':[43553,43555,43557],'cases':[c[0] for c in cases]+['missing_column','custom_name_apostrophe','filter_excludes_past_and_future','latest_invalid_does_not_revive_old_valid'],'passed':True})
report['result']='passed'
(ROOT/'LOGSIS_ENTRADAS_FLEXIVEIS_VALIDACAO.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
