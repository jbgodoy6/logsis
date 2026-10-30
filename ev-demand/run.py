"""Identical entry point on Windows and Linux, with explicit LAN configuration."""
import argparse
from dataclasses import replace
import os
from pathlib import Path

import uvicorn
from app.main import create_app
from app.network import LAN, load_config


def main(argv=None):
    parser = argparse.ArgumentParser(description='EnergyCube D-Max · Controlador de demanda')
    parser.add_argument('--config', default=str(Path(__file__).parent / 'rede.ini'))
    parser.add_argument('--host', default=os.getenv('DMAX_HOST'))
    parser.add_argument('--port', type=int, default=os.getenv('DMAX_PORT'))
    parser.add_argument('--name', default=os.getenv('DMAX_NAME'))
    parser.add_argument('--no-discovery', action='store_true')
    parser.add_argument('--tls-cert', default=os.getenv('DMAX_TLS_CERT') or None)
    parser.add_argument('--tls-key', default=os.getenv('DMAX_TLS_KEY') or None)
    args = parser.parse_args(argv)
    if bool(args.tls_cert) != bool(args.tls_key):
        parser.error('Informe certificado e chave TLS juntos')
    try:
        config = load_config(args.config)
        updates = {name: getattr(args, name) for name in ('host', 'port', 'name') if getattr(args, name) is not None}
        if args.no_discovery:
            updates['discovery'] = False
        config = replace(config, **updates).validated()
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    app = create_app()
    print('D-Max · Acesso raiz por palavra-passe ' + ('habilitado' if app.state.root_password_enabled else 'desabilitado'), flush=True)
    if app.state.root_hash_error:
        print('D-Max · Configuração raiz inválida; restaure app/root-credential.json do pacote oficial', flush=True)
    if app.state.root_password_enabled and app.state.recovery.key is None:
        print('D-Max · Recuperação alternativa por assinatura não configurada (opcional)', flush=True)
    else:
        print('D-Max · ' + app.state.recovery.status, flush=True)
    identity = app.state.store.entities('system')[0]['controller_id']
    lan = LAN(config, identity, tls=bool(args.tls_cert))
    app.state.web_network = lan
    print('D-Max · configuração inicial neste computador: ' + lan.scheme + '://127.0.0.1:' + str(config.port), flush=True)
    if config.host not in ('127.0.0.1', '::1', 'localhost'):
        print('Rede local: ' + lan.public()['url'] + ' (depende de mDNS/firewall)', flush=True)
    uvicorn.run(app, host=config.host, port=config.port, ssl_certfile=args.tls_cert,
                ssl_keyfile=args.tls_key, log_level='warning')


if __name__ == '__main__':
    main()
