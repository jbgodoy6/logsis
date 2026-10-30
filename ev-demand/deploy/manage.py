"""Local deployment helpers. Never run imports or configuration from a database."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile

BEGIN = '# BEGIN D-MAX HARDWARE WATCHDOG'
END = '# END D-MAX HARDWARE WATCHDOG'
BLOCK = BEGIN + '\n[all]\ndtparam=watchdog=on\n' + END + '\n'
WATCHDOG_CONF = '# Managed by EnergyCube D-Max installer.\n[Manager]\nRuntimeWatchdogSec=30s\nRebootWatchdogSec=2min\n'


def atomic_write(path, text):
    path = Path(path)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, staging = tempfile.mkstemp(prefix='.dmax-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(staging, mode)
        os.replace(staging, path)
    finally:
        Path(staging).unlink(missing_ok=True)


def watchdog_block(text, enable):
    if BEGIN in text or END in text:
        if text.count(BEGIN) != 1 or text.count(END) != 1 or BLOCK not in text:
            raise ValueError('Bloco watchdog foi alterado; revise manualmente para preservar suas configurações')
        return text if enable else text.replace(BLOCK, '', 1)
    return text.rstrip('\n') + '\n' + BLOCK if enable else text


def configure_watchdog(enable):
    dropin = Path('/etc/systemd/system.conf.d/70-d-max-watchdog.conf')
    boot = next((p for p in (Path('/boot/firmware/config.txt'), Path('/boot/config.txt')) if p.is_file()), None)
    if boot is None:
        raise ValueError('config.txt do Raspberry não encontrado')
    if boot.is_symlink() or dropin.is_symlink():
        raise ValueError('Configuração watchdog em link simbólico; revisão manual necessária')
    if dropin.exists() and dropin.read_text() != WATCHDOG_CONF:
        raise ValueError('Drop-in watchdog personalizado; arquivo preservado')
    original = boot.read_text(encoding='utf-8')
    updated = watchdog_block(original, enable)
    if original != updated:
        backup = Path('/var/backups/d-max')
        backup.mkdir(mode=0o700, parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
        (backup / ('config-' + stamp + '.txt')).write_text(original)
        atomic_write(boot, updated)
    if enable:
        atomic_write(dropin, WATCHDOG_CONF)
    else:
        dropin.unlink(missing_ok=True)


def verify_package(folder):
    folder = Path(folder).resolve()
    manifest = folder / 'SHA256SUMS.txt'
    if not manifest.is_file():
        raise ValueError('Manifesto SHA256SUMS.txt ausente; use o ZIP Raspberry oficial')
    seen = set()
    for row in manifest.read_text().splitlines():
        digest, name = row.split('  ', 1)
        path = folder / name
        if name in seen or Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink() or not path.resolve().is_relative_to(folder):
            raise ValueError('Entrada inválida no manifesto')
        seen.add(name)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Integridade inválida: ' + name)
    for required in ('run.py', 'app/main.py', 'app/root-credential.json', 'requirements.lock', 'deploy/d-max.service'):
        if required not in seen:
            raise ValueError('Manifesto incompleto')
    for path in (folder / 'app').rglob('*'):
        if path.is_symlink():
            raise ValueError('Arquivo extra não verificado em app/')
        if '__pycache__' in path.parts and path.suffix == '.pyc':
            continue  # Installer explicitly excludes bytecode from the copy.
        if path.is_file() and str(path.relative_to(folder)) not in seen:
            raise ValueError('Arquivo extra não verificado em app/')
    return len(seen)


def backup_database(source, destination):
    source, destination = Path(source).resolve(), Path(destination)
    if not source.is_file() or destination.exists() or source == destination.resolve():
        raise ValueError('Origem inválida ou destino já existente')
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as old, closing(sqlite3.connect(destination)) as new:
            if old.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('Banco de origem não passou pela verificação SQLite')
            old.backup(new)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def import_database(source, target, backup_dir):
    target, backup_dir = Path(target), Path(backup_dir)
    if target.is_symlink() or Path(source).resolve() == target.resolve():
        raise ValueError('Destino inválido ou igual à origem')
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    if target.exists():
        backup_database(target, backup_dir / ('before-import-' + stamp + '.sqlite3'))
        with closing(sqlite3.connect(target)) as old:
            if old.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0]:
                raise ValueError('Banco de destino em uso; pare o serviço antes de importar')
    staging = target.with_name('.import-' + stamp + '.sqlite3')
    try:
        backup_database(source, staging)
        with closing(sqlite3.connect(staging)) as new:
            row = new.execute('SELECT payload FROM settings WHERE id=1').fetchone()
            if not row:
                raise ValueError('Configurações do D-Max ausentes')
            settings = json.loads(row[0])
            settings['mode'] = 'simulation'
            if isinstance(settings.get('meter'), dict):
                settings['meter']['serial_port'] = ''
            new.execute('UPDATE settings SET payload=? WHERE id=1', (json.dumps(settings),))
            for identifier, payload in new.execute("SELECT id,payload FROM entities WHERE kind='charger'").fetchall():
                charger = json.loads(payload)
                if charger.get('transport') == 'ocpp':
                    charger['commissioned'] = False
                    new.execute("UPDATE entities SET payload=? WHERE kind='charger' AND id=?", (json.dumps(charger), identifier))
            new.execute('DELETE FROM logins')
            new.commit()
            new.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        # The caller stops the service and holds the installation maintenance lock.
        for suffix in ('-wal', '-shm'):
            Path(str(target) + suffix).unlink(missing_ok=True)
        os.replace(staging, target)
    finally:
        staging.unlink(missing_ok=True)
        for suffix in ('-wal', '-shm'):
            Path(str(staging) + suffix).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('verify', 'backup-db', 'enable-watchdog', 'disable-watchdog', 'import-db'))
    parser.add_argument('paths', nargs='*', type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'verify' and len(args.paths) == 1:
            print('Manifesto conferido:', verify_package(args.paths[0]), 'arquivos')
        elif args.action == 'backup-db' and len(args.paths) == 2:
            backup_database(*args.paths)
        elif args.action == 'import-db' and len(args.paths) == 3:
            import_database(*args.paths)
        elif args.action in ('enable-watchdog', 'disable-watchdog') and not args.paths:
            configure_watchdog(args.action == 'enable-watchdog')
        else:
            parser.error('Argumentos inválidos')
    except ValueError as error:
        parser.exit(1, 'D-Max: ' + str(error) + '\n')
    except (OSError, sqlite3.Error):
        parser.exit(1, 'D-Max: operação não concluída. Confira permissões, integridade, caminhos e a configuração watchdog.\n')


if __name__ == '__main__':
    main()
