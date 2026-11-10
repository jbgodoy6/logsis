"""Explicit Raspberry Pi OS ARM64 runtime and offline wheels, without Windows files."""
import argparse
import hashlib
from pathlib import Path
import re
import zipfile

VERSION = '0.11.0'
PYTHON = ('__init__.py', 'access.py', 'control.py', 'directory.py', 'engine.py', 'main.py',
          'meter.py', 'network.py', 'ocpp_server.py', 'recovery.py', 'root_auth.py',
          'security.py', 'server_ui.py', 'services.py', 'store.py', 'live_dom.py', 'licensing.py', 'reports.py', 'maintenance.py', 'remote_gateway.py', 'remote_tunnel.py', 'supervision.py', 'plant_view.py', 'telemetry.py')
STATIC = ('style.css', 'energycube.css', 'server.css', 'plant.css', 'live.css', 'live.js', 'maintenance.js', 'remote.js', 'd-max-logo.png', 'energycube-logo.png', 'd-max-report.jpg', 'energycube-report.jpg')


def package(root, wheels, output, signing_key=None):
    files = {}

    def include(source, target):
        if source.is_symlink() or not source.is_file():
            raise ValueError('Arquivo obrigatório inválido: ' + str(source))
        payload = source.read_bytes()
        if source.suffix == '.sh':
            payload = payload.replace(b'\r\n', b'\n')
        files[target] = payload

    for name in PYTHON:
        include(root / 'app' / name, 'app/' + name)
    for name in STATIC:
        include(root / 'app/static' / name, 'app/static/' + name)
    include(root / 'app/root-credential.json', 'app/root-credential.json')
    for name in ('run.py', 'requirements.lock', 'rede.ini', 'instalar-raspberry.sh',
                 'desinstalar-raspberry.sh', 'importar-dados-raspberry.sh', 'acesso-remoto.sh'):
        include(root / name, name)
    for name in ('d-max.service', 'd-max.env.example', 'manage.py', 'maintenance_worker.py', 'd-max-maintenance.path', 'd-max-maintenance.service', 'update-public.pem', 'remote.py', 'd-max-remote.service', 'd-max-remote-gateway.service'):
        include(root / 'deploy' / name, 'deploy/' + name)
    include(root / 'docs/raspberry.md', 'LEIA-ME.txt')
    include(root / 'docs/nuvem-v080.md', 'NUVEM-E-GRAFANA.md')
    include(root / 'docs/visual-v081.md', 'CORES-E-VISUAL.md')
    include(root / 'docs/navigation-v082.md', 'NAVEGACAO-E-CORES.md')
    include(root / 'docs/layout-v083.md', 'PLANTA-EM-LARGURA-COMPLETA.md')
    include(root / 'docs/live-v084.md', 'ATUALIZACAO-SEM-PISCAR.md')
    include(root / 'docs/release-v085.md', 'NOVIDADES-0.8.5.md')
    include(root / 'docs/release-v090.md', 'NOVIDADES-0.9.0.md')
    include(root / 'docs/release-v0100.md', 'NOVIDADES-0.10.0.md')
    include(root / 'docs/validation-v0100.md', 'VALIDACAO-0.10.0.md')
    include(root / 'docs/release-v0110.md', 'NOVIDADES-0.11.0.md')
    include(root / 'docs/assinaturas-v090.md', 'ASSINATURAS-GOOGLE.md')
    include(root / 'google-apps-script/Code.gs', 'google-apps-script/Code.gs')
    include(root / 'docs/raspberry-acesso.md', 'ACESSO-RAIZ.txt')
    include(root / 'docs/raspberry-ocpp.md', 'OCPP-E-MULTIMEDIDOR.txt')
    lock = (root / 'requirements.lock').read_text()
    hashes = set(re.findall(r'--hash=sha256:([0-9a-f]{64})', lock))
    required = {n.lower().replace('_', '-') for n in re.findall(r'^([A-Za-z0-9_-]+)==', lock, re.M)}
    supplied = sorted(wheels.glob('*.whl'))
    present = {p.name.split('-', 1)[0].lower().replace('_', '-') for p in supplied}
    if required - present:
        raise ValueError('Dependências ausentes: ' + ', '.join(sorted(required - present)))
    for wheel in supplied:
        if not wheel.name.endswith('-any.whl') and not (wheel.name.endswith('_aarch64.whl') and 'manylinux' in wheel.name):
            raise ValueError('Wheel não pertence ao Linux ARM64: ' + wheel.name)
        if hashlib.sha256(wheel.read_bytes()).hexdigest() not in hashes:
            raise ValueError('Hash não aprovado pelo lock: ' + wheel.name)
        include(wheel, 'wheels/' + wheel.name)
    files['SHA256SUMS.txt'] = ''.join(hashlib.sha256(data).hexdigest() + '  ' + name + '\n'
                                    for name, data in sorted(files.items())).encode()
    if signing_key is not None:
        from cryptography.hazmat.primitives import serialization
        key=serialization.load_pem_private_key(Path(signing_key).read_bytes(),password=None)
        files['SHA256SUMS.sig']=key.sign(b'DMAX-UPDATE-1\n'+files['SHA256SUMS.txt'])
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo('D-Max-Raspberry/' + name)
            info.create_system = 3
            info.external_attr = ((0o100755 if name.endswith('.sh') else 0o100644) << 16)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError('Falha na integridade do ZIP')
        for name, data in files.items():
            if archive.read('D-Max-Raspberry/' + name) != data:
                raise ValueError('Conteúdo divergente: ' + name)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(digest + '  ' + output.name + '\n')
    return len(files), digest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--wheels', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--signing-key', type=Path, required=True)
    args = parser.parse_args()
    count, digest = package(Path(__file__).resolve().parents[1], args.wheels, args.output, args.signing_key)
    print(f'{args.output.name}: {count} arquivos; SHA-256 {digest}')
