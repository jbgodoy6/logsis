"""Package Studio 9 and examples, with an explicit credential-free allowlist."""
from pathlib import Path
import hashlib
import io
import json
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from logsis_studio.core import Project,available_models

runtime=['LogSis_Studio.py','INICIAR_LOGSIS_STUDIO.bat','requirements-serial.txt']
runtime+=['logsis_studio/'+n for n in ['__init__.py','app.py','core.py','transport.py','manual_dashboard.py','deif_dashboard.py','codecs.py']]
runtime+=['logsis_studio/resources/'+n for n in ['profiles.json','template.bin','dse7420.json','dse8610.json','logsis_symbol.png','sgc420_alarms.json','agc150_alarms.json']]
reports=['LOGSIS_STUDIO_9_VALIDACAO.json','LOGSIS_STUDIO_9_VALIDACAO_SQL.json','LOGSIS_STUDIO_9_VALIDACAO_DSE_SQL.json','LOGSIS_STUDIO_9_VALIDACAO_UI.json','LOGSIS_STUDIO_GRAFANA_VALIDACAO.json']
screens=['LOGSIS_STUDIO_9_INICIO.png','LOGSIS_STUDIO_9_MAPA.png','LOGSIS_STUDIO_9_EXPORTACAO.png']
output=ROOT/'LOGSIS_STUDIO_9_0.zip'
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
    for name in runtime+reports+screens:z.write(ROOT/name,'LogSis_Studio_9.0/'+name)
    z.write(ROOT/'README_LOGSIS_STUDIO_9.md','LogSis_Studio_9.0/LEIA-ME.md')

# Example packages are separate from the desktop download to keep each purpose clear.
examples=ROOT/'LOGSIS_STUDIO_9_MODELOS.zip'
with zipfile.ZipFile(examples,'w',zipfile.ZIP_DEFLATED) as z:
    for model in available_models():
        p=Project.new(model)
        z.writestr(model+'_PACOTE.zip',p.bundle_bytes('id_planta',model,'zKW_ld27k'))
    z.writestr('LEIA-ME.txt','Exemplos de mapas e dashboards. Não são a configuração da sua planta.\nPrefira exportar pelo Studio com Slave ID, tabela, datasource e UID corretos.\nSGC120/SGC410 fora desta versão. Consulte o README e os relatórios para dependências de firmware.\n')

manifest={'version':'9.0.0','artifacts':[]}
for path in [output,examples]:
    with zipfile.ZipFile(path) as z:assert z.testzip() is None
    data=path.read_bytes();manifest['artifacts'].append({'file':path.name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
(ROOT/'LOGSIS_STUDIO_9_DOWNLOADS.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(manifest,ensure_ascii=False,indent=2))
