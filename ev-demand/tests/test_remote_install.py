"""Activation lifecycle in a private tree; no public tunnel or system changes."""
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]

class RemoteInstallTests(unittest.TestCase):
    def test_repeat_activation_preserves_old_identity_checks_client_and_disables_cleanly(self):
        with tempfile.TemporaryDirectory(prefix='dmax-remote-install-') as temporary:
            base=Path(temporary);tree=base/'root';app=tree/'opt/d-max';config=tree/'etc/d-max';units=tree/'etc/systemd/system'
            for p in (app/'deploy',app/'bin',app/'app',app/'.venv/bin',config,units,base/'bin'):p.mkdir(parents=True,exist_ok=True)
            (app/'.dmax-managed').touch()
            prefixes=('/run/d-max-maintenance','/var/lib/d-max-remote','/etc/systemd/system','/etc/d-max','/opt/d-max')
            def adapt(s):return re.sub('|'.join(map(re.escape,prefixes)),lambda m:str(tree)+m.group(),s)
            for name in ('remote_tunnel.py','remote_gateway.py','network.py','__init__.py'):
                text=(ROOT/'app'/name).read_text()
                (app/'app'/name).write_text(adapt(text))
            for name in ('remote.py','d-max-remote.service','d-max-remote-gateway.service'):
                (app/'deploy'/name).write_text(adapt((ROOT/'deploy'/name).read_text()))
            binary=b'\x7fELF\x02'+bytes(13)+(183).to_bytes(2,'little')+b'fixture client'
            (app/'bin/cloudflared').write_bytes(binary)
            (app/'deploy/cloudflared-release.json').write_text(json.dumps(dict(version='fixture',sha256=hashlib.sha256(binary).hexdigest())))
            home=tree/'var/lib/d-max-remote';home.mkdir(parents=True)
            (home/'.dmax-remote-managed').touch();(home/'id_ed25519').write_bytes(b'old identity preserved')
            script=app/'acesso-remoto.sh';script.write_text(adapt((ROOT/'acesso-remoto.sh').read_text()).replace('[[ $EUID -eq 0 ]]','[[ 1 -eq 1 ]]'))
            python=app/'.venv/bin/python';python.write_text('#!/bin/sh\nexec '+__import__('shlex').quote(sys.executable)+' "$@"\n');python.chmod(0o755)
            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(200);self.end_headers();self.wfile.write(b'{"required":false}')
                def log_message(self,*args):pass
            http=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
            try:
                (config/'rede.ini').write_text('[web]\nhost=127.0.0.1\nporta='+str(http.server_port)+'\n')
                (config/'d-max.env').write_text('# Preserve existing cloud configuration\nEV_CLOUD_TOKEN=fixture-existing-only\n')
                fake=base/'bin/fake-command'
                fake.write_text('#!'+sys.executable+'''\nimport json,os,pathlib,subprocess,sys,time,hashlib
root=pathlib.Path(os.environ['DMAX_REMOTE_FIXTURE']);name=pathlib.Path(sys.argv[0]).name;args=sys.argv[1:]
with open(root/'calls.jsonl','a') as f:f.write(json.dumps([name,*args])+'\\n')
if name=='id':sys.exit(0)
elif name=='getent':print('dmax-remote:x:1001:1001::'+str(root/'root/var/lib/d-max-remote')+':/usr/sbin/nologin')
elif name=='chown':pass
elif name=='install':
 cleaned=[];i=0
 while i<len(args):
  if args[i] in ('-o','-g'):i+=2
  else:cleaned.append(args[i]);i+=1
 sys.exit(subprocess.call(['/usr/bin/install',*cleaned]))
elif name=='systemctl':
 home=root/'root/var/lib/d-max-remote';status=home/'public/status.json'
 if args[0] in ('enable','restart'):
  url='https://fixture-one.trycloudflare.com'
  status.write_text(json.dumps(dict(url=url,connected=True,heartbeat_at=time.time(),message='fixture connected')))
 elif args[0]=='disable' and status.exists():
  data=json.loads(status.read_text());data['connected']=False;status.write_text(json.dumps(data))
''');fake.chmod(0o755)
                for name in ('id','getent','chown','install','systemctl'):(base/'bin'/name).symlink_to(fake)
                env=dict(os.environ,PATH=str(base/'bin')+':'+os.environ['PATH'],DMAX_REMOTE_FIXTURE=str(base))
                def run(action,ok=True):
                    r=subprocess.run(['bash',str(script),action],env=env,text=True,capture_output=True,timeout=30)
                    self.assertEqual(r.returncode==0,ok,r.stdout+r.stderr);return r
                run('ativar');home=tree/'var/lib/d-max-remote';key=(home/'id_ed25519').read_bytes()
                run('ativar');self.assertEqual((home/'id_ed25519').read_bytes(),key)
                self.assertEqual(json.loads((home/'public/status.json').read_text())['url'],'https://fixture-one.trycloudflare.com')
                self.assertIn('fixture-existing-only',(config/'d-max.env').read_text())
                (app/'bin/cloudflared').write_bytes(b'corrupt')
                rejected=run('ativar',ok=False)
                self.assertIn('Integridade',rejected.stdout+rejected.stderr)
                self.assertEqual((home/'id_ed25519').read_bytes(),key)
                run('desativar');self.assertTrue((home/'id_ed25519').exists())
                self.assertFalse(json.loads((home/'public/status.json').read_text())['connected'])
                run('remover');self.assertFalse((units/'d-max-remote.service').exists())
                self.assertFalse((units/'d-max-remote-gateway.service').exists())
                self.assertEqual((home/'id_ed25519').read_bytes(),key)
                calls=[json.loads(line) for line in (base/'calls.jsonl').read_text().splitlines()]
                self.assertIn(['systemctl','enable','--now','d-max-remote-gateway.service','d-max-remote.service'],calls)
            finally:http.shutdown();http.server_close();thread.join(timeout=3)

if __name__=='__main__':unittest.main()
