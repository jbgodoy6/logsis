"""Fixed deployment entrypoints, kept outside mutable local data."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

if __name__=='__main__':
    action=sys.argv.pop(1) if len(sys.argv)>1 else ''
    if action=='gateway':
        from app.remote_gateway import main
        main()
    elif action=='tunnel':
        from app.remote_tunnel import main
        main()
    elif action=='status':
        from app.remote_tunnel import public_status
        data=public_status()
        print(data['message'])
        if data.get('url'):print('Endereço: '+data['url'])
    elif action=='verify-client':
        import hashlib,json
        root=Path(__file__).resolve().parents[1]
        info=json.loads((root/'deploy/cloudflared-release.json').read_text())
        path=root/'bin/cloudflared'
        if path.is_symlink() or not path.is_file():raise SystemExit('Cliente Cloudflare ausente ou inválido')
        with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        with path.open('rb') as stream:header=stream.read(20)
        if digest!=info['sha256'] or header[:5]!=b'\x7fELF\x02' or int.from_bytes(header[18:20],'little')!=183:
            raise SystemExit('Integridade ou arquitetura do cliente Cloudflare inválida; use o pacote ARM64 oficial')
        print('Cliente Cloudflare ARM64 conferido: '+info['version'])
    elif action=='verify-host' and len(sys.argv)==2:
        import subprocess
        from app.remote_tunnel import HOST_FINGERPRINT
        path=Path(sys.argv[1])
        # ssh-keyscan versions can include banner comments and empty lines on
        # stdout. They are valid known_hosts syntax, not host-key records.
        lines=[row.strip() for row in path.read_text().splitlines()
               if row.strip() and not row.lstrip().startswith('#')]
        if not lines or any(len(r.split())!=3 or r.split()[:2]!=['proxy.tunnl.gg','ssh-ed25519'] for r in lines):
            raise SystemExit('Chave de servidor inválida')
        result=subprocess.run(['ssh-keygen','-lf',str(path),'-E','sha256'],capture_output=True,text=True,check=True)
        fingerprints=[row.split()[1] for row in result.stdout.splitlines() if len(row.split())>=2]
        if len(fingerprints)!=len(lines) or any(value!=HOST_FINGERPRINT for value in fingerprints):
            raise SystemExit('Chave do provedor mudou. Não será aceita automaticamente; revise com o fornecedor.')
        print('Identidade SSH do provedor conferida')
    elif action=='preflight':
        import json,os,shlex,urllib.request
        from app.remote_gateway import backend
        env=dict(os.environ)
        path=Path('/etc/d-max/d-max.env')
        if path.exists():
            for line in path.read_text().splitlines():
                if '=' not in line or line.lstrip().startswith('#'):continue
                key,value=line.split('=',1)
                if key in ('DMAX_HOST','DMAX_PORT','DMAX_TLS_CERT','DMAX_REMOTE_CA_FILE'):
                    values=shlex.split(value,comments=True)
                    env[key]=values[0] if len(values)==1 else ''
        target,trust=backend(environment=env)
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=trust))
        with opener.open(target+'/api/setup',timeout=10) as response:data=json.loads(response.read(8192))
        if data.get('required') is not False:raise SystemExit('Configure o administrador local antes de ativar o acesso remoto')
        print('D-Max local configurado e acessível')
    else:raise SystemExit('Operação remota inválida')
