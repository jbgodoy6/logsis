"""Run deployment shell scripts against a temporary filesystem, never host services.

Set DMAX_PI_PACKAGE to a built ZIP. Only absolute installation prefixes, the root
check and systemd availability check are redirected in the fixture copies. Python
SQL helpers and file operations run for real; UID, systemctl and pip are simulated.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile

from app.store import Store


@unittest.skipUnless(os.getenv('DMAX_PI_PACKAGE'), 'Requires the ARM64 distribution ZIP')
class PiScriptLifecycleTests(unittest.TestCase):
    def test_install_import_preserving_uninstall_reinstall_and_confirmed_purge(self):
        with tempfile.TemporaryDirectory(prefix='dmax-deploy-fixture-') as folder:
            base = Path(folder)
            fixture = base / 'root'
            fixture.mkdir()
            source = base / 'source'
            with zipfile.ZipFile(os.environ['DMAX_PI_PACKAGE']) as archive:
                archive.extractall(source)
            source = source / 'D-Max-Raspberry'
            (fixture / 'run/systemd/system').mkdir(parents=True)
            (fixture / 'etc/systemd/system').mkdir(parents=True)
            unrelated = fixture / 'unrelated.txt'
            unrelated.write_text('preserve')
            for name in ('instalar-raspberry.sh', 'desinstalar-raspberry.sh', 'importar-dados-raspberry.sh'):
                path = source / name
                text = path.read_text().replace('[[ $EUID -eq 0 ]]', '[[ 1 -eq 1 ]]')
                # Longest paths first; replacements are never made in production.
                prefixes = ('/etc/systemd/system.conf.d', '/etc/systemd/system', '/run/systemd/system', '/run/d-max-maintenance',
                            '/var/backups/d-max', '/var/lib/d-max', '/etc/d-max', '/opt/d-max')
                text = re.sub('|'.join(re.escape(p) for p in prefixes), lambda m: str(fixture) + m.group(0), text)
                text = text.replace('-C /opt d-max', '-C ' + str(fixture / 'opt') + ' d-max')
                text = text.replace('-C /etc d-max', '-C ' + str(fixture / 'etc') + ' d-max')
                path.write_text(text)
            # Recompute only fixture script hashes, preserving all distributed data.
            manifest = source / 'SHA256SUMS.txt'
            names = [row.split('  ', 1)[1] for row in manifest.read_text().splitlines()]
            manifest.write_text(''.join(hashlib.sha256((source / name).read_bytes()).hexdigest() + '  ' + name + '\n' for name in names))
            commands = base / 'bin'
            commands.mkdir()
            helper = commands / 'fake-command'
            helper.write_text('''#!''' + sys.executable + '''
import json,os,pathlib,subprocess,sys
name=pathlib.Path(sys.argv[0]).name
args=sys.argv[1:];root=pathlib.Path(os.environ['DMAX_FIXTURE_ROOT'])
with open(root/'calls.jsonl','a') as stream:stream.write(json.dumps([name,*args])+'\\n')
if name=='uname':print('aarch64')
elif name=='systemctl':
 if args[:2]==['is-active','--quiet'] and args[-1]=='watchdog.service':sys.exit(3)
elif name=='id':sys.exit(0 if (root/'user-exists').exists() else 1)
elif name=='useradd':(root/'user-exists').touch()
elif name=='userdel':(root/'user-exists').unlink(missing_ok=True)
elif name=='getent':
 if args[0]=='group':print('dialout:x:20:')
 else:print('dmax:x:1000:1000::'+str(root/'var/lib/d-max')+':/usr/sbin/nologin')
elif name=='chown':pass
elif name=='install':
 cleaned=[];index=0
 while index<len(args):
  if args[index] in ('-o','-g'):index+=2
  else:cleaned.append(args[index]);index+=1
 sys.exit(subprocess.call(['/usr/bin/install',*cleaned]))
elif name=='fake-python' or name=='python':
 if '-m' in args and args[args.index('-m')+1]=='venv':
  target=pathlib.Path(args[-1])/'bin';target.mkdir(parents=True)
  (target/'python').symlink_to(pathlib.Path(sys.argv[0]).resolve())
 elif '-m' in args and args[args.index('-m')+1]=='pip':pass
 else:sys.exit(subprocess.call([os.environ['DMAX_FIXTURE_PYTHON'],*args]))
''')
            helper.chmod(0o755)
            for name in ('uname', 'systemctl', 'id', 'useradd', 'userdel', 'getent', 'chown', 'install', 'fake-python'):
                (commands / name).symlink_to(helper)
            env = dict(os.environ, PATH=str(commands) + ':' + os.environ['PATH'],
                       PYTHON_BIN=str(commands / 'fake-python'), DMAX_FIXTURE_ROOT=str(fixture), DMAX_FIXTURE_PYTHON=sys.executable)

            def run(name, *arguments, input=None, ok=True):
                result = subprocess.run(['bash', str(source / name), *map(str, arguments)], env=env,
                                        input=input, text=True, capture_output=True, timeout=40)
                self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
                return result

            run('instalar-raspberry.sh', '--no-hardware-watchdog')
            app = fixture / 'opt/d-max'
            self.assertTrue((app / '.dmax-managed').is_file())
            self.assertTrue((fixture / 'etc/systemd/system/d-max.service').is_file())
            self.assertTrue((fixture / 'etc/d-max/rede.ini').is_file())
            windows = Store(str(base / 'windows.sqlite3'))
            identity = windows.entities('system')[0]['controller_id']
            windows.db.close()
            run('importar-dados-raspberry.sh', base / 'windows.sqlite3')
            database = fixture / 'var/lib/d-max/controller.sqlite3'
            self.assertTrue(database.is_file())
            run('desinstalar-raspberry.sh')
            self.assertFalse(app.exists())
            self.assertTrue(database.exists())
            self.assertTrue((fixture / 'etc/d-max/rede.ini').exists())
            run('instalar-raspberry.sh', '--no-hardware-watchdog')
            imported = Store(str(database))
            self.assertEqual(imported.entities('system')[0]['controller_id'], identity)
            imported.db.close()
            # Do not remove a service changed by an administrator.
            service = fixture / 'etc/systemd/system/d-max.service'
            original = service.read_text()
            service.write_text(original + '\n# custom fixture change\n')
            run('desinstalar-raspberry.sh', ok=False)
            self.assertTrue(app.exists())
            service.write_text(original)
            run('desinstalar-raspberry.sh', '--purge-data', input='CANCELAR\n', ok=False)
            self.assertTrue(database.exists())
            run('desinstalar-raspberry.sh', '--purge-data', input='APAGAR\n')
            self.assertFalse(app.exists())
            self.assertFalse(database.exists())
            self.assertFalse((fixture / 'etc/d-max').exists())
            self.assertEqual(unrelated.read_text(), 'preserve')
            calls = [json.loads(row) for row in (fixture / 'calls.jsonl').read_text().splitlines()]
            self.assertIn(['systemctl', 'enable', '--now', 'd-max.service'], calls)
            self.assertIn(['systemctl', 'disable', '--now', 'd-max.service'], calls)
