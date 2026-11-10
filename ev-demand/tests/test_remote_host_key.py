"""Public provider key fixtures; no private keys or network access."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
PUBLIC='proxy.tunnl.gg ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIN3HFkIcqgWI6Sa1E31KiUbcfcrX/5MZl4LnaQnUYL8K'

@unittest.skipUnless(shutil.which('ssh-keygen'),'OpenSSH client required')
class HostKeyTests(unittest.TestCase):
    def verify(self,text):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'known_hosts';path.write_text(text)
            return subprocess.run([sys.executable,'-I',str(ROOT/'deploy/remote.py'),'verify-host',str(path)],capture_output=True,text=True)
    def test_exact_published_key_with_banner_and_blank_lines(self):
        for text in (PUBLIC+'\n','# proxy.tunnl.gg:22 SSH-2.0-Go\n\n'+PUBLIC+'\n',' \n  # banner\r\n  '+PUBLIC+'  \r\n'):
            result=self.verify(text)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('conferida',result.stdout)
    def test_comments_without_key_and_other_host_rejected(self):
        for text in ('','# banner\n\n',PUBLIC.replace('proxy.tunnl.gg','other.example')):
            self.assertNotEqual(self.verify(text).returncode,0)
    def test_another_valid_ed25519_key_still_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'key'
            subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(path)],check=True)
            other='proxy.tunnl.gg '+' '.join(path.with_suffix('.pub').read_text().split()[:2])
            result=self.verify('# banner\n'+other+'\n')
            self.assertNotEqual(result.returncode,0)
            self.assertIn('mudou',result.stderr)

if __name__=='__main__':unittest.main()
