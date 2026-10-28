"""Package the Android preview and service source, excluding private build state."""
from pathlib import Path
import hashlib
import json
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
if len(sys.argv)!=2:raise SystemExit('Use: python tools/build_mobile11_release.py /path/to/signed-preview.apk')
report=json.loads((ROOT/'app/VALIDACAO_ANDROID_1_1.json').read_text(encoding='utf-8'))
assert report['result']=='passed'
assert report['activation']['programmingEnabledInPreview'] is False
source=Path(sys.argv[1])
with zipfile.ZipFile(source) as apk:
    assert apk.testzip() is None and 'classes.dex' in apk.namelist()
    bins=[n for n in apk.namelist() if n.startswith('assets/library/') and n.endswith('.bin')]
    assert len(bins)==17
    assert not any(n.startswith('assets/library/') and n.endswith('.json') for n in apk.namelist())

apk=ROOT/'LOGSIS_ANDROID_1_1_PREVIA.apk';apk.write_bytes(source.read_bytes())
output=ROOT/'LOGSIS_APP_1_1_FONTE_E_SERVICO.zip'
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
    for folder in ['android','backend']:
        for file in sorted((ROOT/'app'/folder).rglob('*')):
            if not file.is_file():continue
            relative=file.relative_to(ROOT/'app'/folder)
            if any(p in ['build','.gradle','.local-signing','.android'] for p in relative.parts):continue
            if file.name in ['local.properties','.DS_Store'] or file.suffix.lower() in ['.jks','.keystore','.key','.p12','.log']:continue
            z.write(file,'LogSis_App_1.1/'+folder+'/'+str(relative))
    z.write(ROOT/'app/README_TECNICO.md','LogSis_App_1.1/LEIA-ME.md')
    z.write(ROOT/'app/VALIDACAO_ANDROID_1_1.json','LogSis_App_1.1/VALIDACAO_ANDROID_1_1.json')
service=ROOT/'LOGSIS_SERVICO_TECNICOS_1_1.zip'
with zipfile.ZipFile(service,'w',zipfile.ZIP_DEFLATED) as z:
    for file in sorted((ROOT/'app/backend').iterdir()):
        if file.is_file():z.write(file,'LogSis_Servico_Tecnicos/'+file.name)
result={'version':'1.1.0','status':'preview; authorization service publication and fixed URL pending','artifacts':[]}
for path in [apk,output,service]:
    if path.suffix=='.zip':
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            assert not any(Path(n).suffix.lower() in ['.jks','.keystore','.key','.p12'] for n in z.namelist())
    result['artifacts'].append({'file':path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(ROOT/'app/ARQUIVOS_ANDROID_1_1.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
