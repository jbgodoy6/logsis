"""Build and audit a standard per-user MSI, with no executable custom actions."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess


def table(tool, msi, name, env):
    text=subprocess.check_output([str(tool),'export',str(msi),name],env=env).decode('utf-8')
    lines=text.splitlines()
    return list(csv.DictReader([lines[0]]+lines[3:],delimiter='\t'))


def build(root, wixl, msiinfo, library_path, output):
    env=dict(os.environ)
    if library_path: env['LD_LIBRARY_PATH']=str(library_path)
    published=root/'desktop/bin/Release/net48'
    for name in ['DMaxAcesso.exe','DMaxAcesso.exe.config']:
        if not (published/name).is_file():raise ValueError('Compile primeiro: '+name)
    output.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run([str(wixl),'-a','x64','-D','PublishDir='+str(published),'-D','SourceDir='+str(root/'desktop'),'-o',str(output),str(root/'desktop/Installer.wxs')],env=env,check=True)
    for name in ['CustomAction','ServiceInstall','ServiceControl','Environment','IniFile']:
        if table(msiinfo,output,name,env):raise ValueError('Tabela inesperada: '+name)
    files=table(msiinfo,output,'File',env)
    if {r['FileName'] for r in files}!={'DMaxAcesso.exe','DMaxAcesso.exe.config','LEIA-ME.txt'}:raise ValueError('Payload diferente da lista aprovada')
    registry=table(msiinfo,output,'Registry',env)
    if len(registry)!=2 or any(r['Root']!='1' or r['Key']!='Software\\EnergyCube\\DMaxAcessoDesktop' for r in registry):raise ValueError('Registro inesperado')
    shortcuts=table(msiinfo,output,'Shortcut',env)
    if len(shortcuts)!=2 or any(r['Target']!='[INSTALLFOLDER]DMaxAcesso.exe' or r['Arguments'] for r in shortcuts):raise ValueError('Atalho inesperado')
    properties={r['Property']:r['Value'] for r in table(msiinfo,output,'Property',env)}
    if properties.get('ALLUSERS','') not in ('','0'):raise ValueError('Instalação deve ser por usuário')
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.msi.sha256').write_text(digest+'  '+output.name+'\n')
    report={'product':'D-Max Acesso Desktop 1.0','msi_sha256':digest,'exe_sha256':hashlib.sha256((published/'DMaxAcesso.exe').read_bytes()).hexdigest(),'files':[r['FileName'] for r in files],'custom_actions':0,'services':0,'environment_changes':0,'registry':'two HKCU shortcut markers only','shortcuts':2,'installation_scope':'current user','authenticode_signed':False,'windows_execution_tested':False,'defender_tested':False}
    output.with_suffix('.audit.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wixl',type=Path,required=True);p.add_argument('--msiinfo',type=Path,required=True);p.add_argument('--library-path',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();print(json.dumps(build(Path(__file__).resolve().parents[1],args.wixl,args.msiinfo,args.library_path,args.output),indent=2))
