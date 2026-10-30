import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from app.access import Access
from app.store import Store
from deploy.manage import BLOCK, backup_database, import_database, verify_package, watchdog_block


class PiDeploymentTests(unittest.TestCase):
    def test_boot_configuration_preserves_existing_options_and_is_idempotent(self):
        original = '[pi4]\narm_boost=1\n[all]\nenable_uart=1\n'
        enabled = watchdog_block(original, True)
        self.assertTrue(enabled.startswith(original))
        self.assertEqual(enabled.count(BLOCK), 1)
        self.assertEqual(watchdog_block(enabled, True), enabled)
        self.assertEqual(watchdog_block(enabled, False), original)
        self.assertEqual(watchdog_block(original, False), original)
        with self.assertRaises(ValueError):
            watchdog_block(enabled.replace('watchdog=on', 'watchdog=off'), False)

    def test_manifest_rejects_modified_or_additional_application_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            files = {'run.py': 'run', 'app/main.py': 'main', 'app/root-credential.json': '{}',
                     'requirements.lock': 'lock', 'deploy/d-max.service': 'service'}
            for name, data in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(data)
            (root / 'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(data.encode()).hexdigest() + '  ' + name + '\n' for name, data in files.items()))
            self.assertEqual(verify_package(root), 5)
            cache = root / 'app/__pycache__'
            cache.mkdir()
            (cache / 'main.cpython-313.pyc').write_bytes(b'fixture-bytecode-not-copied')
            self.assertEqual(verify_package(root), 5)
            (root / 'app/unverified.py').write_text('extra')
            with self.assertRaises(ValueError):
                verify_package(root)
            (root / 'app/unverified.py').unlink()
            (root / 'run.py').write_text('changed')
            with self.assertRaises(ValueError):
                verify_package(root)

    def test_import_preserves_identity_credentials_and_history_but_requires_recommissioning(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = Store(str(root / 'windows.sqlite3'))
            access = Access(source)
            with source.db:
                source.db.execute('INSERT INTO users(name,password,role,id,full_name) VALUES(?,?,?,?,?)', ('admin', 'fixture-verifier', 'admin', 'fixture-admin', 'Admin'))
                source.db.execute('INSERT INTO logins(token,username,expires,epoch) VALUES(?,?,?,?)', ('fixture-token', 'admin', 9999999999, 0))
            access.set_device_token('fixture-google-device-key')
            identity = source.entities('system')[0]['controller_id']
            settings = source.settings()
            settings['mode'] = 'physical'
            settings['meter']['serial_port'] = 'COM3'
            source.save_settings(settings)
            source.put('charger', {'id': 'EV-01', 'transport': 'ocpp', 'commissioned': True, 'password_hash': 'fixture-ocpp-verifier'})
            event = source.record('fixture-history', {'energy_kwh': 42})
            source.db.close()
            target = root / 'controller.sqlite3'
            old = Store(str(target))
            old_identity = old.entities('system')[0]['controller_id']
            old.db.close()
            import_database(root / 'windows.sqlite3', target, root / 'backup')
            imported = Store(str(target))
            try:
                self.assertEqual(imported.entities('system')[0]['controller_id'], identity)
                self.assertEqual(imported.settings()['mode'], 'simulation')
                self.assertEqual(imported.settings()['meter']['serial_port'], '')
                charger = imported.entities('charger')[0]
                self.assertFalse(charger['commissioned'])
                self.assertEqual(charger['password_hash'], 'fixture-ocpp-verifier')
                self.assertEqual(imported.db.execute('SELECT password FROM users').fetchone()[0], 'fixture-verifier')
                self.assertEqual(imported.db.execute('SELECT token FROM directory_secret').fetchone()[0], 'fixture-google-device-key')
                self.assertEqual(imported.db.execute('SELECT COUNT(*) FROM logins').fetchone()[0], 0)
                self.assertEqual(imported.db.execute('SELECT id FROM events WHERE id=?', (event,)).fetchone()[0], event)
            finally:
                imported.db.close()
            backup = next((root / 'backup').glob('before-import-*.sqlite3'))
            restored = Store(str(backup))
            try:
                self.assertEqual(restored.entities('system')[0]['controller_id'], old_identity)
            finally:
                restored.db.close()

    def test_invalid_source_does_not_replace_target_and_backup_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / 'controller.sqlite3'
            old = Store(str(target))
            identity = old.entities('system')[0]['controller_id']
            old.db.close()
            bad = root / 'bad.sqlite3'
            bad.write_text('not a database')
            with self.assertRaises(sqlite3.Error):
                import_database(bad, target, root / 'backup')
            restored = Store(str(target))
            try:
                self.assertEqual(restored.entities('system')[0]['controller_id'], identity)
            finally:
                restored.db.close()
            copy = root / 'copy.sqlite3'
            backup_database(target, copy)
            before = copy.read_bytes()
            with self.assertRaises(ValueError):
                backup_database(target, copy)
            self.assertEqual(copy.read_bytes(), before)
