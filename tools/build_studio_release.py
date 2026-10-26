"""Package the desktop program and validation records, never user credentials."""
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]
files=[ROOT/name for name in ['LogSis_Studio.py','INICIAR_LOGSIS_STUDIO.bat','requirements-serial.txt']]
files.extend(ROOT/'logsis_studio'/name for name in ['__init__.py','app.py','core.py','transport.py','manual_dashboard.py','resources/profiles.json','resources/template.bin','resources/dse7420.json','resources/dse8610.json'])
files.extend(ROOT/name for name in ['LOGSIS_STUDIO_8_INICIO.png','LOGSIS_STUDIO_8_MAPA.png','LOGSIS_STUDIO_8_EXPORTACAO.png','LOGSIS_STUDIO_8_VALIDACAO.json','LOGSIS_STUDIO_8_VALIDACAO_SQL.json','LOGSIS_STUDIO_8_VALIDACAO_UI.json','LOGSIS_STUDIO_GRAFANA_VALIDACAO.json','DSE_GENCOMM_MAPA_CONFERIDO.json','LOGSIS_STUDIO_8_MAPA_MANUAL.csv'])
output=ROOT/'LOGSIS_STUDIO_8_0.zip'
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
 for path in sorted(files):archive.write(path,'LogSis_Studio_8.0/'+str(path.relative_to(ROOT)).replace('\\','/'))
 readme='\n'.join(line for line in (ROOT/'README_LOGSIS_STUDIO_8.md').read_text().splitlines() if not line.startswith('[Baixar programa completo]'))+'\n'
 archive.writestr('LogSis_Studio_8.0/LEIA-ME.md',readme)
print(output.name,output.stat().st_size,'bytes')
