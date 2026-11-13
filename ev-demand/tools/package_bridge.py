"""Small standalone Windows company portal: standard-library Python, no controller."""
import argparse
import hashlib
from pathlib import Path
import zipfile

FILES = ('main.py','iniciar-windows.bat','verificar.py','style.css','portal.js','logo.png','LEIA-ME.md')

def package(root, output):
    files={name:(root/'bridge'/name).read_bytes() for name in FILES}
    files['iniciar-windows.bat']=files['iniciar-windows.bat'].replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')
    for name in ('Code.gs','appsscript.json'):
        files['planilha/'+name]=(root/'google-apps-script'/name).read_bytes()
    files['SHA256SUMS.txt']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in sorted(files.items())).encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in sorted(files.items()):archive.writestr('D-Max-Acesso-Windows/'+name,data)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():raise ValueError('ZIP inválido')
        for name,data in files.items():
            if archive.read('D-Max-Acesso-Windows/'+name)!=data:raise ValueError('Conteúdo divergente')
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(digest+'  '+output.name+'\n')
    return len(files),digest

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(package(Path(__file__).resolve().parents[1],args.output))
