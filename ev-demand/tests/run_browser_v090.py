"""Run isolated browser checks; no retained user credentials or database."""
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.request

root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='dmax-v090-browser-') as folder:
    env=dict(os.environ,DMAX_TEST_URL='http://127.0.0.1:8111',DMAX_TEST_ROOT=secrets.token_urlsafe(28),DMAX_TEST_DBPATH=folder+'/controller.sqlite3')
    with open('/tmp/dmax-v090-browser-server.log','w') as log:
        server=subprocess.Popen([sys.executable,str(root/'tests/server_v090.py')],env=env,stdout=log,stderr=log)
        try:
            for attempt in range(60):
                try:urllib.request.urlopen('http://127.0.0.1:8111/api/setup',timeout=1);break
                except Exception:time.sleep(.2)
            else:raise RuntimeError('Servidor de testes não iniciou; consulte log local')
            subprocess.run(['node',sys.argv[1] if len(sys.argv)>1 else 'tests/browser_v090.cjs'],cwd=root,env=env,check=True)
        finally:
            server.terminate();server.wait(timeout=15)
