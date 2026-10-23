"""Package the complete desktop program, never individual user configuration files."""
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
files=[ROOT/'LogSis_Studio.py', ROOT/'INICIAR_LOGSIS_STUDIO.bat', ROOT/'requirements-serial.txt']
files.extend(ROOT/'logsis_studio'/name for name in ['__init__.py','app.py','core.py','transport.py','resources/profiles.json','resources/template.bin','resources/dse7420.json','resources/dse8610.json'])
files.extend(ROOT/name for name in ['LOGSIS_STUDIO_7_INICIO.png','LOGSIS_STUDIO_7_MAPA.png','LOGSIS_STUDIO_7_DSE8610.png','LOGSIS_STUDIO_7_EXPORTACAO.png','LOGSIS_STUDIO_VALIDACAO.json','LOGSIS_STUDIO_GRAFANA_VALIDACAO.json'])
output=ROOT/'LOGSIS_STUDIO_7_0.zip'
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
 for path in sorted(files):archive.write(path,'LogSis_Studio_7.0/'+str(path.relative_to(ROOT)).replace('\\','/'))
 readme=(ROOT/'README_LOGSIS_STUDIO_7.md').read_text()
 readme='\n'.join(line for line in readme.splitlines() if not line.startswith('[Baixar programa completo]'))+'\n'
 archive.writestr('LogSis_Studio_7.0/LEIA-ME.md',readme)
print(output.name,output.stat().st_size,'bytes')
