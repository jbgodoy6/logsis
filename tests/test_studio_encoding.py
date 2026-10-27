"""Reproduce the Windows CP1252 default without changing the host locale."""
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

from logsis_studio.core import Project, RESOURCES, available_models


def windows_text_open(original):
    def open_file(file, mode='r', buffering=-1, encoding=None, errors=None,
                  newline=None, closefd=True, opener=None):
        if 'b' not in mode and encoding in (None, 'locale'):
            encoding='cp1252'
        return original(file, mode, buffering, encoding, errors, newline, closefd, opener)
    return open_file


class WindowsEncodingTests(unittest.TestCase):
    def test_original_resource_reproduces_reported_byte_and_offset(self):
        # This guards the fixture: the test exercises the exact bytes reported
        # by the user, not an unrelated synthetic accented string.
        with self.assertRaises(UnicodeDecodeError) as caught:
            (RESOURCES/'dse7420.json').read_bytes().decode('cp1252')
        self.assertEqual(caught.exception.start,18005)
        self.assertEqual(caught.exception.object[18005],0x8d)

    def test_all_exports_preserve_unicode_with_windows_default_encoding(self):
        with patch('io.open', windows_text_open(io.open)):
            for model in available_models():
                with self.subTest(model=model):
                    p=Project.new(model)
                    binary=p.bin_bytes()
                    data=p.bundle_bytes('id_194057949800264','São José · Manutenção','zKW_ld27k')
                    with zipfile.ZipFile(io.BytesIO(data)) as archive:
                        self.assertEqual(archive.read(model+'.bin'),binary)
                        dashboard=json.loads(archive.read(model+'_GRAFANA.json').decode('utf-8'))
                        self.assertIn('São José · Manutenção',dashboard['title'])
                        self.assertEqual(dashboard['timezone'],'America/Sao_Paulo')
                        report=json.loads(archive.read('COMPATIBILIDADE.json').decode('utf-8'))
                        self.assertEqual(report['table'],'id_194057949800264')
