"""Auditable source-only company portal; no launchers, binaries or cloud scripts."""
import argparse
import ast
import hashlib
from pathlib import Path
import zipfile

FILES = {'DMaxAcesso.py':'main.py','style.css':'style.css','portal.js':'portal.js','LEIA-ME.md':'LEIA-ME.md'}

def package(root, output):
    files={name:(root/'bridge'/source).read_bytes() for name,source in FILES.items()}
    # Source must be readable UTF-8; no opaque payloads or dynamic execution.
    for data in files.values():
        data.decode('utf-8')
    tree=ast.parse(files['DMaxAcesso.py'])
    forbidden={'subprocess','ctypes','winreg','webbrowser','pickle','marshal'}
    for node in ast.walk(tree):
        if isinstance(node,ast.Import) and any(alias.name.split('.')[0] in forbidden for alias in node.names):
            raise ValueError('Módulo inesperado no pacote básico')
        if isinstance(node,ast.ImportFrom) and (node.module or '').split('.')[0] in forbidden:
            raise ValueError('Módulo inesperado no pacote básico')
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in {'exec','eval','compile','__import__'}:
            raise ValueError('Execução dinâmica não permitida nesta distribuição')
    files['SHA256SUMS.txt']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in sorted(files.items())).encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo('D-Max-Acesso-Windows/'+name,(2026,11,13,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644 << 16
            archive.writestr(info,data)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():raise ValueError('ZIP inválido')
        if len(archive.infolist())!=len(files):raise ValueError('Conteúdo extra no ZIP')
        for name,data in files.items():
            if archive.read('D-Max-Acesso-Windows/'+name)!=data:raise ValueError('Conteúdo divergente')
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(digest+'  '+output.name+'\n')
    return len(files),digest

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(package(Path(__file__).resolve().parents[1],args.output))
