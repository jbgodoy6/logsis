"""Create the Windows runtime from an explicit allowlist and verified PyPI wheels.

This is a deployment package, not a source snapshot. Developer tests, old UI,
security samples/reports, databases and credentials stay out of installations.
"""
import argparse
import hashlib
from pathlib import Path
import re
import zipfile


VERSION = '0.6.1'
STATIC = ('style.css', 'energycube.css', 'server.css', 'd-max-logo.png', 'energycube-logo.png')
PYTHON = (
    '__init__.py', 'access.py', 'control.py', 'directory.py', 'engine.py', 'main.py',
    'meter.py', 'network.py', 'ocpp_server.py', 'security.py', 'server_ui.py', 'services.py', 'store.py',
)


def package(root, wheels, output):
    files = {}

    def include(source, target):
        if source.is_symlink() or not source.is_file():
            raise ValueError('Arquivo obrigatório ausente ou inválido: ' + str(source))
        payload = source.read_bytes()
        if source.suffix == '.bat':
            payload = payload.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        files[target] = payload

    for name in PYTHON:
        include(root / 'app' / name, 'app/' + name)
    for name in STATIC:
        include(root / 'app/static' / name, 'app/static/' + name)
    for name in ('run.py', 'iniciar-windows.bat', 'requirements.lock', 'rede.ini'):
        include(root / name, name)
    include(root / 'docs/instalar-windows-v061.md', 'LEIA-ME.txt')
    allowed_hashes = set(re.findall(r'--hash=sha256:([0-9a-f]{64})', (root / 'requirements.lock').read_text()))
    supplied = sorted(wheels.glob('*.whl'))
    if not supplied:
        raise ValueError('Forneça as wheels Windows x64 aprovadas pelo lock.')
    required = {name.lower().replace('_', '-') for name in
                re.findall(r'^([A-Za-z0-9_-]+)==', (root / 'requirements.lock').read_text(), re.M)} - {'uvloop'}
    provided = {wheel.name.split('-', 1)[0].lower().replace('_', '-') for wheel in supplied}
    if required - provided:
        raise ValueError('Dependências ausentes: ' + ', '.join(sorted(required - provided)))
    for wheel in supplied:
        if hashlib.sha256(wheel.read_bytes()).hexdigest() not in allowed_hashes:
            raise ValueError('Wheel não aprovada pelo lock: ' + wheel.name)
        if not wheel.name.endswith(('-win_amd64.whl', '-any.whl')):
            raise ValueError('Artefato não pertence ao Windows x64: ' + wheel.name)
        include(wheel, 'wheels/' + wheel.name)
    manifest = ''.join(hashlib.sha256(data).hexdigest() + '  ' + name + '\n' for name, data in sorted(files.items()))
    files['SHA256SUMS.txt'] = manifest.encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, payload in sorted(files.items()):
            archive.writestr('D-Max/' + name, payload)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError('O ZIP falhou na verificação de integridade')
        for name, payload in files.items():
            if archive.read('D-Max/' + name) != payload:
                raise ValueError('Conteúdo divergente: ' + name)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(digest + '  ' + output.name + '\n')
    return len(files), digest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--wheels', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    count, digest = package(root, args.wheels, args.output)
    print(f'{args.output.name}: {count} arquivos; SHA-256 {digest}')
