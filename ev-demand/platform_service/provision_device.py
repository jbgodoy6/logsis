"""Provision a device token into private files, never print its value."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets


def main():
    parser=argparse.ArgumentParser(description='Provisionar equipamento D-Max na plataforma')
    parser.add_argument('--controller-id',required=True)
    parser.add_argument('--registry',required=True,help='JSON privado de hashes no servidor central')
    parser.add_argument('--device-env',required=True,help='Arquivo privado para copiar ao equipamento')
    args=parser.parse_args()
    if not re.fullmatch('[A-Za-z0-9_-]{1,100}',args.controller_id):
        parser.error('Identificador inválido')
    registry,device=Path(args.registry),Path(args.device_env)
    data=json.loads(registry.read_text()) if registry.exists() else {}
    if args.controller_id in data or device.exists():
        parser.error('Equipamento ou arquivo já existe; preservado para evitar rotação acidental')
    token=secrets.token_urlsafe(48)
    registry.parent.mkdir(parents=True,exist_ok=True)
    device.parent.mkdir(parents=True,exist_ok=True)
    with device.open('x') as f:
        os.chmod(device,0o600)
        f.write('DMAX_DIRECTORY_TOKEN='+token+'\n')
    data[args.controller_id]=hashlib.sha256(token.encode()).hexdigest()
    temporary=registry.with_suffix('.tmp')
    with temporary.open('x') as f:
        os.chmod(temporary,0o600)
        json.dump(data,f)
    temporary.replace(registry)
    print('Equipamento provisionado. Copie o arquivo privado ao destino por canal seguro; o token não é exibido.')


if __name__=='__main__': main()
