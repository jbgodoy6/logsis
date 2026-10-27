from pathlib import Path
import shutil
import subprocess
import unittest


class AppsScriptTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'),'Validação do código Apps Script requer Node.js no ambiente de desenvolvimento')
    def test_exact_apps_script_with_google_service_doubles(self):
        root=Path(__file__).resolve().parents[1]
        result=subprocess.run(['node',str(root/'tests/apps_script_contract.cjs'),str(root/'google-apps-script/Code.gs')],
                              capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('contract passed',result.stdout)
