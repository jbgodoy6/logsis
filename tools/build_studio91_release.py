"""Source-only distribution and a separate data-only Grafana download."""
from pathlib import Path
import hashlib
import json
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from logsis_studio.core import Project,available_models
from logsis_studio import __version__
tag=__version__.replace('.','_')

runtime=['LogSis_Studio.py','requirements-serial.txt']
runtime+=['logsis_studio/'+n for n in ['__init__.py','app.py','core.py','transport.py','manual_dashboard.py','deif_dashboard.py','standard_layout.py','codecs.py']]
runtime+=['logsis_studio/resources/'+n for n in ['profiles.json','template.bin','dse7420.json','dse8610.json','logsis_symbol.png','sgc420_alarms.json','agc150_alarms.json']]
reports=[f'LOGSIS_STUDIO_{tag}_VALIDACAO.json','LOGSIS_STUDIO_9_1_VALIDACAO_UI.json']
if __version__=='9.1.3':
    reports+=['DSE8660_CONFERENCIA_MODBUS.json','DSE8660_VALIDACAO_SNAPSHOT.json','LOGSIS_STUDIO_9_1_3_DSE8660_UI.json']
    runtime+=['DSE8660_CONFERENCIA_MODBUS.csv']
for name in reports:
    assert json.loads((ROOT/name).read_text(encoding='utf-8'))['result']=='passed',name+' ainda não aprovado'
output=ROOT/f'LOGSIS_STUDIO_{tag}_FONTE.zip'
prefix=f'LogSis_Studio_{__version__}/'
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
    for name in runtime+reports:z.write(ROOT/name,prefix+name)
    z.write(ROOT/'README_LOGSIS_STUDIO_9.md',prefix+'LEIA-ME.md')
    assert all(Path(name).suffix.lower() not in ['.exe','.bat','.cmd','.ps1','.vbs','.dll','.msi','.pyc'] for name in z.namelist())

out=ROOT/f'DASHBOARDS_PADRAO_{tag}_JSON.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for model in available_models():
        p=Project.new(model)
        z.writestr(model+'.json',json.dumps(p.dashboard('id_planta',model,'zKW_ld27k'),ensure_ascii=False,indent=2)+'\n')
    z.writestr('LEIA-ME.txt','Arquivos JSON para importar no Grafana. Configure Id_Logsis e datasource conforme a planta.\nPara gerar o BIN e o JSON já configurados juntos, use o Studio.\nEste pacote contém somente dados JSON e esta orientação em texto.\n')
    assert all(Path(name).suffix.lower() in ['.json','.txt'] for name in z.namelist())

# Exact plant/table entered in the user's DSE8660 screenshot; no DB access.
p=Project.new('DSE8660')
specific=ROOT/f'DSE8660_PADRAO_DSE7420_{tag}.json'
specific.write_text(json.dumps(p.dashboard('id_194057949800264','logsis','zKW_ld27k'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

manifest={'version':__version__,'artifacts':[]}
for path in [output,out,specific]:
    if path.suffix=='.zip':
        with zipfile.ZipFile(path) as z:assert z.testzip() is None
    data=path.read_bytes();manifest['artifacts'].append({'file':path.name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
(ROOT/f'LOGSIS_STUDIO_{tag}_DOWNLOADS.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False,indent=2))
