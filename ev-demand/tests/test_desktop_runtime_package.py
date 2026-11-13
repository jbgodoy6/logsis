import json
from pathlib import Path
import tempfile
import unittest
from tools.package_desktop import REQUIRED, runtime_layout, component_source

class RuntimePackageTests(unittest.TestCase):
    def layout(self, path):
        for name in REQUIRED:(path/name).write_bytes(b'fixture')
        (path/'DMaxAcesso.runtimeconfig.json').write_text(json.dumps({'runtimeOptions':{'includedFrameworks':[{'name':'Microsoft.NETCore.App','version':'10.0.15'},{'name':'Microsoft.WindowsDesktop.App','version':'10.0.15'}]}}))
        (path/'DMaxAcesso.deps.json').write_text(json.dumps({'runtimeTarget':{'name':'.NETCoreApp,Version=v10.0/win-x64'}}))
    def test_external_framework_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.layout(root)
            (root/'DMaxAcesso.runtimeconfig.json').write_text(json.dumps({'runtimeOptions':{'framework':{'name':'Microsoft.WindowsDesktop.App','version':'10.0.15'}}}))
            with self.assertRaisesRegex(ValueError,'runtime externo'):runtime_layout(root)
    def test_missing_native_host_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.layout(root);(root/'coreclr.dll').unlink()
            with self.assertRaisesRegex(ValueError,'Runtime incompleto'):runtime_layout(root)
    def test_nested_runtime_resources_and_components_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);published=root/'published';published.mkdir();self.layout(published)
            (published/'pt-BR').mkdir();(published/'pt-BR'/'example.resources.dll').write_bytes(b'localized runtime fixture')
            project=root/'project';(project/'desktop').mkdir(parents=True);(project/'desktop'/'LEIA-ME.txt').write_text('fixture')
            files,frameworks,ids=component_source(published,project,root/'files.wxs')
            self.assertIn('pt-BR/example.resources.dll',files)
            self.assertEqual(len(ids),len(files))
            self.assertEqual(set(frameworks),{'Microsoft.NETCore.App','Microsoft.WindowsDesktop.App'})
            self.assertIn('pt-BR',(root/'files.wxs').read_text())
