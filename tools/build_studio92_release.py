"""Reproducible source-only package; no executables or private installation data."""
from pathlib import Path
import json,zipfile,hashlib
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT))
from logsis_studio import __version__
from logsis_studio.core import available_models
assert __version__=='9.2.0'
reports=['LOGSIS_STUDIO_9_2_0_PRESERVACAO.json','LOGSIS_STUDIO_9_2_0_SQL_VALIDACAO.json','LOGSIS_STUDIO_9_2_0_UI_VALIDACAO.json','LOGSIS_STUDIO_9_2_0_GRAFANA_UI.json']
for n in reports:assert json.loads((ROOT/n).read_text())['result']=='passed',n
files=[ROOT/'LogSis_Studio.py',ROOT/'requirements-serial.txt']+sorted((ROOT/'logsis_studio').glob('*.py'))+sorted(p for p in (ROOT/'logsis_studio/resources').iterdir() if p.is_file())
output=ROOT/'LOGSIS_STUDIO_9_2_0_FONTE.zip';prefix='LogSis_Studio_9.2.0/'
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
 for p in files:z.write(p,prefix+str(p.relative_to(ROOT)))
 z.write(ROOT/'README_LOGSIS_STUDIO_9_2.md',prefix+'LEIA-ME.md')
 for n in reports:z.write(ROOT/n,prefix+'validacao/'+n)
 assert all(Path(n).suffix.lower() not in ['.exe','.bat','.cmd','.ps1','.dll','.pyc','.jks'] for n in z.namelist())
with zipfile.ZipFile(output) as z:assert z.testzip() is None
report={'version':__version__,'profiles':len(available_models()),'sourceOnly':True,'artifacts':[{'file':output.name,'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}]}
(ROOT/'LOGSIS_STUDIO_9_2_0_DOWNLOADS.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
