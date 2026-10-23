"""Replace the overflow/unavailable placeholder, preserving V40 behavior."""
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
source = json.loads((ROOT / 'V40_IMPORTAR.json').read_text())

def clean(value):
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean(item) for item in value]
    return value.replace('###', '—') if isinstance(value, str) else value

dashboard = clean(source)
dashboard['title'] = source['title'].replace('V40', 'V41')
dashboard['tags'] = ['V41' if tag == 'V40' else tag for tag in source['tags']]
output = ROOT / 'dist' / 'V41_IMPORTAR.json'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(dashboard, ensure_ascii=True, separators=(',', ':'), allow_nan=False) + '\n', encoding='ascii')
with zipfile.ZipFile(output.with_suffix('.zip'), 'w', zipfile.ZIP_DEFLATED) as archive:
    archive.write(output, output.name)
print('V41: indicador de estouro/indisponibilidade substituído por —')
