"""Pinned repair in a private tree, including preservation and rollback."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class RemoteHotfixTests(unittest.TestCase):
    def test_apply_repeat_tamper_and_restart_rollback(self):
        original=subprocess.check_output(['git','show','dmax-v0.12.0:ev-demand/app/remote_tunnel.py'],cwd=ROOT)
        fixed=(ROOT/'app/remote_tunnel.py').read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);tree=base/'root';app=tree/'opt/d-max';commands=base/'commands';commands.mkdir()
            for path in (app/'app',app/'.venv/bin',app/'deploy'):path.mkdir(parents=True,exist_ok=True)
            for name in ('.dmax-managed','.dmax-remote-managed'):(app/name).touch()
            target=app/'app/remote_tunnel.py';target.write_bytes(original)
            candidate=base/'candidate.py';candidate.write_bytes(fixed)
            script=base/'apply.sh';text=(ROOT/'tools/apply_remote_hotfix.sh').read_text()
            prefixes=('/opt/d-max','/var/backups/d-max','/run/d-max-maintenance')
            text=re.sub('|'.join(map(re.escape,prefixes)),lambda m:str(tree)+m.group(),text).replace('[[ $EUID -eq 0 ]]','[[ 1 -eq 1 ]]')
            script.write_text(text)
            fake=commands/'systemctl';fake.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$FIXTURE_CALLS"\nif [ "$1" = restart ] && [ "${FIXTURE_FAIL:-0}" = 1 ]; then exit 1; fi\n');fake.chmod(0o755)
            python=app/'.venv/bin/python';python.write_text('#!'+sys.executable+'\nimport os,sys\nif len(sys.argv)>3 and sys.argv[2]=="-c" and "py_compile" in sys.argv[3]:os.execv(sys.executable,[sys.executable,*sys.argv[1:]])\nsys.exit(0)\n');python.chmod(0o755)
            env=dict(os.environ,PATH=str(commands)+':'+os.environ['PATH'],FIXTURE_CALLS=str(base/'calls'))
            def run(ok=True):
                result=subprocess.run(['bash',str(script),str(candidate)],env=env,capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode==0,ok,result.stdout+result.stderr);return result
            run();self.assertEqual(target.read_bytes(),fixed)
            backups=list((tree/'var/backups/d-max').glob('*.py'));self.assertEqual(len(backups),1);self.assertEqual(backups[0].read_bytes(),original)
            run();self.assertEqual(len(list((tree/'var/backups/d-max').glob('*.py'))),1)
            self.assertEqual((base/'calls').read_text().count('restart d-max-remote.service'),1)
            candidate.write_bytes(b'bad');run(False);self.assertEqual(target.read_bytes(),fixed)
            candidate.write_bytes(fixed);target.write_bytes(b'custom');run(False);self.assertEqual(target.read_bytes(),b'custom')
            target.write_bytes(original);env['FIXTURE_FAIL']='1';run(False);self.assertEqual(target.read_bytes(),original)
