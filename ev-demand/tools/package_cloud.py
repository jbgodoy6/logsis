"""Distribute cloud setup and public demos with an explicit allowlist; no credentials."""
import hashlib
from pathlib import Path
import zipfile

root=Path(__file__).resolve().parents[1]
repo=root.parent
files={}
for path in (root/'cloud').rglob('*'):
    if not path.is_file() or path.is_symlink() or any(part.startswith('.') for part in path.relative_to(root/'cloud').parts):
        continue
    if path.suffix not in ('.py','.ts','.sql','.toml','.yaml','.json','.svg','.png','.html') and path.name!='Dockerfile':
        continue
    files[str(path.relative_to(root))]=path.read_bytes()
for name in ['app/__init__.py','app/telemetry.py','app/plant_view.py','app/static/plant.css','app/static/d-max-logo.png','tools/plant_demo.py']:
    files[name]=(root/name).read_bytes()
files['CORES-E-VISUAL.md']=(root/'docs/visual-v081.md').read_bytes()
files['LEIA-ME-NUVEM.md']=(root/'docs/nuvem-v080.md').read_bytes()
files['SHA256SUMS.txt']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in sorted(files.items())).encode()
output=repo/'D-Max-v0.8.1-Nuvem-Grafana.zip'
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
    for name,data in sorted(files.items()):
        info=zipfile.ZipInfo('D-Max-Nuvem/'+name);info.create_system=3;info.external_attr=0o100644<<16;info.compress_type=zipfile.ZIP_DEFLATED;archive.writestr(info,data)
with zipfile.ZipFile(output) as archive:
    assert archive.testzip() is None
    assert not any('/.demo/' in n or 'credenciais-dmax' in n or n.endswith('.env') for n in archive.namelist())
output.with_suffix('.zip.sha256').write_text(hashlib.sha256(output.read_bytes()).hexdigest()+'  '+output.name+'\n')
print(output.name, len(files), 'arquivos; sem credenciais geradas')
