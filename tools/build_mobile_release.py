"""Package the Android evaluation APK and clean source tree; never signing keys."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'app/android'
if len(sys.argv)!=2:
    raise SystemExit('Use: python tools/build_mobile_release.py /path/to/signed-evaluation.apk')
source_apk=Path(sys.argv[1])
with zipfile.ZipFile(source_apk) as apk:
    assert apk.testzip() is None
    assert 'classes.dex' in apk.namelist()
    assert any(name.startswith('META-INF/') for name in apk.namelist())
apk=ROOT/'LOGSIS_ANDROID_1_0_TESTE.apk'
apk.write_bytes(source_apk.read_bytes())
output=ROOT/'LOGSIS_APP_ANDROID_FONTE_1_0.zip'
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
    for file in sorted(SOURCE.rglob('*')):
        if not file.is_file():continue
        relative=file.relative_to(SOURCE)
        if any(part in ['build','.gradle','.local-signing'] for part in relative.parts):continue
        if file.name=='local.properties' or file.suffix in ['.jks','.keystore']:continue
        archive.write(file,'Logsis_App_1.0/android/'+str(relative))
    readme='\n'.join(line for line in (ROOT/'app/README.md').read_text().splitlines() if not line.startswith('[Baixar APK de teste]'))+'\n'
    archive.writestr('Logsis_App_1.0/LEIA-ME.md',readme)
    archive.write(ROOT/'app/VALIDACAO_ANDROID_1_0.json','Logsis_App_1.0/VALIDACAO_ANDROID_1_0.json')
report={file.name:{'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()} for file in [apk,output]}
(ROOT/'app/ARQUIVOS_ANDROID_1_0.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
