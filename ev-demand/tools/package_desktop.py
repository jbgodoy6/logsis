"""Build/audit the full self-contained Windows MSI; no custom executable actions."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid
import xml.etree.ElementTree as ET

WIX='http://schemas.microsoft.com/wix/2006/wi'
ET.register_namespace('',WIX)
NAMESPACE=uuid.UUID('e67f8748-bfc6-4cda-a80b-e11d403dbd08')
REQUIRED={'DMaxAcesso.exe','DMaxAcesso.dll','DMaxAcesso.deps.json','DMaxAcesso.runtimeconfig.json','coreclr.dll','clrjit.dll','hostfxr.dll','hostpolicy.dll','System.Private.CoreLib.dll','System.Windows.Forms.dll','System.Drawing.Common.dll'}


def table(tool,msi,name,env):
    lines=subprocess.check_output([str(tool),'export',str(msi),name],env=env).decode('utf-8').splitlines()
    return list(csv.DictReader([lines[0]]+lines[3:],delimiter='\t'))


def runtime_layout(published):
    files={p.relative_to(published).as_posix():p for p in published.rglob('*') if p.is_file()}
    if not REQUIRED.issubset(files):raise ValueError('Runtime incompleto: '+', '.join(sorted(REQUIRED-files.keys())))
    if any(p.is_symlink() for p in published.rglob('*')):raise ValueError('Links simbólicos não são permitidos')
    config=json.loads(files['DMaxAcesso.runtimeconfig.json'].read_text())['runtimeOptions']
    if config.get('framework') or config.get('frameworks'):raise ValueError('Publicação ainda exige runtime externo')
    frameworks={r['name']:r['version'] for r in config.get('includedFrameworks',[])}
    if set(frameworks)!={'Microsoft.NETCore.App','Microsoft.WindowsDesktop.App'}:raise ValueError('Runtimes incluídos não confirmados')
    deps=json.loads(files['DMaxAcesso.deps.json'].read_text())
    if not deps['runtimeTarget']['name'].endswith('/win-x64'):raise ValueError('A publicação deve ser win-x64')
    if 'DMaxAcesso.exe.config' in files:raise ValueError('Configuração antiga do .NET Framework presente')
    return files,frameworks


def component_source(published,root,destination):
    files,frameworks=runtime_layout(published)
    files['LEIA-ME.txt']=root/'desktop/LEIA-ME.txt'
    wix=ET.Element('{'+WIX+'}Wix');fragment=ET.SubElement(wix,'{'+WIX+'}Fragment');base=ET.SubElement(fragment,'{'+WIX+'}DirectoryRef',Id='INSTALLFOLDER');group=ET.SubElement(fragment,'{'+WIX+'}ComponentGroup',Id='PublishedRuntime');directories={'':base};ids={}
    def tag(parent,name,**attrs):return ET.SubElement(parent,'{'+WIX+'}'+name,**attrs)
    for name,path in sorted(files.items()):
        parent=''
        for part in name.split('/')[:-1]:
            current=(parent+'/' if parent else '')+part
            if current not in directories:directories[current]=tag(directories[parent],'Directory',Id='dir_'+hashlib.sha256(current.encode()).hexdigest()[:24],Name=part)
            parent=current
        digest=hashlib.sha256(name.lower().encode()).hexdigest()[:24];component_id='cmp_'+digest;file_id='file_'+digest;ids[file_id]=name
        guid='70C7CC08-93C2-4FA9-A91A-9692045BF6E1' if name=='DMaxAcesso.exe' else str(uuid.uuid5(NAMESPACE,name.lower()))
        component=tag(directories[parent],'Component',Id=component_id,Guid=guid,Win64='yes')
        tag(component,'File',Id=file_id,Name=Path(name).name,Source=str(path),KeyPath='yes');tag(group,'ComponentRef',Id=component_id)
    ET.ElementTree(wix).write(destination,encoding='utf-8',xml_declaration=True)
    return files,frameworks,ids


def build(root,wixl,msiinfo,library_path,published,output):
    env=dict(os.environ)
    if library_path:env['LD_LIBRARY_PATH']=str(library_path)
    output.parent.mkdir(parents=True,exist_ok=True)
    generated=published.parent/'PublishedRuntime.wxs'
    files,frameworks,ids=component_source(published,root,generated)
    subprocess.run([str(wixl),'-a','x64','-o',str(output),str(root/'desktop/Installer.wxs'),str(generated)],env=env,check=True)
    for name in ['CustomAction','ServiceInstall','ServiceControl','Environment','IniFile','RegLocator']:
        if table(msiinfo,output,name,env):raise ValueError('Tabela inesperada: '+name)
    conditions=table(msiinfo,output,'LaunchCondition',env)
    if any('NETFRAMEWORK' in row['Condition'].upper() for row in conditions):raise ValueError('Exigência antiga de Framework ainda presente')
    packed=table(msiinfo,output,'File',env)
    if len(packed)!=len(files) or {r['File'] for r in packed}!=set(ids):raise ValueError('Arquivos faltando ou extras no MSI')
    for row in packed:
        path=files[ids[row['File']]]
        if row['FileName'].split('|')[-1]!=path.name or int(row['FileSize'])!=path.stat().st_size:raise ValueError('Arquivo MSI divergente: '+path.name)
    registry=table(msiinfo,output,'Registry',env)
    if len(registry)!=2 or any(r['Root']!='1' or r['Key']!='Software\\EnergyCube\\DMaxAcessoDesktop' for r in registry):raise ValueError('Registro inesperado')
    shortcuts=table(msiinfo,output,'Shortcut',env)
    if len(shortcuts)!=2 or any(r['Target']!='[INSTALLFOLDER]DMaxAcesso.exe' or r['Arguments'] for r in shortcuts):raise ValueError('Atalho inesperado')
    properties={r['Property']:r['Value'] for r in table(msiinfo,output,'Property',env)}
    if properties.get('ALLUSERS','') not in ('','0'):raise ValueError('Instalação deve ser por usuário')
    digest=hashlib.sha256(output.read_bytes()).hexdigest();output.with_suffix('.msi.sha256').write_text(digest+'  '+output.name+'\n')
    manifest={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in sorted(files.items())}
    output.with_suffix('.payload.json').write_text(json.dumps(manifest,indent=2)+'\n')
    report={'product':properties.get('ProductName'),'version':properties.get('ProductVersion'),'self_contained':True,'included_frameworks':frameworks,'framework_installation_required':False,'msi_sha256':digest,'exe_sha256':manifest['DMaxAcesso.exe'],'file_count':len(files),'payload_bytes':sum(p.stat().st_size for p in files.values()),'custom_actions':0,'services':0,'environment_changes':0,'registry':'two HKCU shortcut markers only','shortcuts':2,'installation_scope':'current user','single_file_packing':False,'authenticode_signed':False,'windows_execution_tested':False,'defender_tested':False}
    output.with_suffix('.audit.json').write_text(json.dumps(report,indent=2)+'\n');return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wixl',type=Path,required=True);p.add_argument('--msiinfo',type=Path,required=True);p.add_argument('--library-path',type=Path);p.add_argument('--published-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();print(json.dumps(build(Path(__file__).resolve().parents[1],args.wixl,args.msiinfo,args.library_path,args.published_dir,args.output),indent=2))
