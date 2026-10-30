"""Owner-only offline recovery utility. No private key is distributed with D-Max."""
import argparse
from datetime import datetime, timezone
import getpass
import os
from pathlib import Path
import sys

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

script_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(script_dir if (script_dir / 'app').is_dir() else script_dir.parent))
from app.recovery import DOMAIN, canonical, encode, fingerprint, payload_from


def generate(private_path, public_path, password):
    private_path, public_path = Path(private_path), Path(public_path)
    if private_path.resolve() == public_path.resolve() or private_path.exists() or public_path.exists():
        raise ValueError('Escolha arquivos novos; nenhuma chave existente será sobrescrita')
    if len(password) < 12 or len(password) > 200:
        raise ValueError('Proteja a chave privada com uma senha de 12 a 200 caracteres')
    key = Ed25519PrivateKey.generate()
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                               serialization.BestAvailableEncryption(password.encode()))
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    # Exclusive creation and restrictive mode on POSIX; Windows inherits folder ACLs.
    fd = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(private)
        with public_path.open('xb') as stream:
            stream.write(public)
    except BaseException:
        private_path.unlink(missing_ok=True)
        raise
    return fingerprint(key.public_key())


def authorize(challenge, private_path, password):
    if not challenge.startswith('DMAX-C1.'):
        raise ValueError('Copie o desafio DMAX-C1 completo exibido pelo controlador')
    payload = payload_from(challenge.removeprefix('DMAX-C1.'))
    key = serialization.load_pem_private_key(Path(private_path).read_bytes(), password=password.encode())
    if not isinstance(key, Ed25519PrivateKey) or fingerprint(key.public_key()) != payload['key']:
        raise ValueError('A chave privada não corresponde à chave pública deste equipamento')
    encoded = encode(canonical(payload))
    return 'DMAX-R1.' + encoded + '.' + encode(key.sign(DOMAIN + canonical(payload)))


def main(argv=None):
    parser = argparse.ArgumentParser(description='D-Max — chave única do proprietário e autorizações offline')
    sub = parser.add_subparsers(dest='command', required=True)
    gen = sub.add_parser('gerar-chave', help='Executar uma única vez, no computador do proprietário')
    gen.add_argument('--privada', required=True, type=Path)
    gen.add_argument('--publica', required=True, type=Path)
    sign = sub.add_parser('autorizar', help='Autorizar um desafio de recuperação por 15 minutos')
    sign.add_argument('--privada', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'gerar-chave':
            password = getpass.getpass('Senha para proteger sua chave privada (mínimo 12 caracteres): ')
            if password != getpass.getpass('Confirme a senha: '):
                raise ValueError('As senhas não coincidem')
            identifier = generate(args.privada, args.publica, password)
            print('Chaves criadas. Identificador público: ' + identifier)
            print('Guarde a chave PRIVADA e sua senha com backup seguro, fora das instalações e do repositório.')
            print('Copie somente a chave PÚBLICA como recovery-public.pem para cada D-Max e reinicie.')
        else:
            challenge = input('Cole o desafio exibido no D-Max: ').strip()
            payload = payload_from(challenge.removeprefix('DMAX-C1.')) if challenge.startswith('DMAX-C1.') else None
            if payload is None:
                raise ValueError('Desafio inválido')
            print('Equipamento: ' + payload['controller'])
            print('Válido até: ' + datetime.fromtimestamp(payload['expires'], timezone.utc).astimezone().isoformat())
            print('Autorizar concede acesso RAIZ por 15 minutos, incluindo recuperação de admin e gestão de técnicos.')
            if input('Confirma este equipamento? Digite SIM: ').strip() != 'SIM':
                raise ValueError('Autorização cancelada')
            password = getpass.getpass('Senha da sua chave privada: ')
            print('\nCole esta autorização no mesmo navegador que gerou o desafio:\n')
            print(authorize(challenge, args.privada, password))
    except (ValueError, TypeError, OSError, UnsupportedAlgorithm, EOFError, KeyboardInterrupt):
        print('Operação não concluída. Confira o desafio, a chave, sua senha, o relógio e os caminhos informados.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
