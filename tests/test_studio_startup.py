import builtins
import ctypes
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('studio_launcher', ROOT / 'LogSis_Studio.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class StartupTests(unittest.TestCase):
    def test_incomplete_extraction_shows_missing_files_and_saves_utf8_trace(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(launcher, 'ROOT', Path(folder) / 'pasta incompleta'), patch.dict(os.environ, {'LOCALAPPDATA': folder}), patch.object(launcher, 'show_failure') as popup:
                self.assertEqual(launcher.main(), 1)
            self.assertIn('Extraia TODOS', popup.call_args.args[0])
            logs = list((Path(folder) / 'LogSisStudio/logs').glob('*.txt'))
            self.assertEqual(len(logs), 1)
            text = logs[0].read_text(encoding='utf-8')
            self.assertIn('FileNotFoundError', text)
            self.assertIn('logsis_studio/app.py', text)

    def test_missing_tk_is_caught_before_app_main(self):
        original = builtins.__import__
        def missing_tk(name, *args, **kwargs):
            if name == 'logsis_studio.app':
                raise ModuleNotFoundError("No module named 'tkinter'", name='tkinter')
            return original(name, *args, **kwargs)
        with patch('builtins.__import__', side_effect=missing_tk), patch.object(launcher, 'save_diagnostic', return_value=Path('/tmp/abertura.txt')), patch.object(launcher, 'show_failure') as popup:
            self.assertEqual(launcher.main(), 1)
        self.assertIn('Tcl/Tk', popup.call_args.args[0])
        self.assertIn('abertura.txt', popup.call_args.args[0])

    def test_gui_constructor_failure_reaches_launcher_once(self):
        with patch('logsis_studio.app.main', side_effect=RuntimeError('falha de interface')), patch.object(launcher, 'save_diagnostic', return_value=None) as save, patch.object(launcher, 'show_failure') as popup:
            self.assertEqual(launcher.main(), 1)
        popup.assert_called_once()
        self.assertIn('RuntimeError: falha de interface', popup.call_args.args[0])
        self.assertIn('RuntimeError: falha de interface', save.call_args.args[0])

    def test_unsupported_python_has_readable_message(self):
        with patch.object(launcher.sys, 'version_info', (3, 8)), patch.object(launcher, 'save_diagnostic', return_value=None), patch.object(launcher, 'show_failure') as popup:
            self.assertEqual(launcher.main(), 1)
        self.assertIn('Python 3.10', popup.call_args.args[0])

    def test_windows_dialog_does_not_require_tk(self):
        windll = Mock()
        with patch.object(launcher.sys, 'platform', 'win32'), patch.object(ctypes, 'windll', windll, create=True):
            launcher.show_failure('Erro de abertura')
        windll.user32.MessageBoxW.assert_called_once()
        self.assertEqual(windll.user32.MessageBoxW.call_args.args[1], 'Erro de abertura')

    def test_unwritable_diagnostic_directory_is_nonfatal(self):
        with patch('pathlib.Path.mkdir', side_effect=PermissionError('sem acesso')):
            self.assertIsNone(launcher.save_diagnostic('erro original'))

    def test_success_does_not_write_error_log(self):
        with patch('logsis_studio.app.main') as run, patch.object(launcher, 'save_diagnostic') as save:
            self.assertEqual(launcher.main(), 0)
        run.assert_called_once()
        save.assert_not_called()

    @unittest.skipUnless(os.environ.get('DISPLAY'), 'Tk requer DISPLAY')
    def test_real_entrypoint_opens_and_closes_the_gui(self):
        from logsis_studio.app import Studio
        mainloop = Studio.mainloop
        def close_after_open(window):
            window.after(100, window.destroy)
            mainloop(window)
        with patch.object(Studio, 'mainloop', close_after_open), patch.object(launcher, 'show_failure') as popup:
            self.assertEqual(launcher.main(), 0)
        popup.assert_not_called()
