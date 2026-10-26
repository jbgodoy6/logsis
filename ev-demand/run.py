"""Identical entry point on Windows and Linux."""
import argparse
import os
import uvicorn
from app.main import create_app

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='EnergyCube D-Max · Controlador de demanda')
    parser.add_argument('--host', default=os.getenv('DMAX_HOST', '127.0.0.1'))
    parser.add_argument('--port', type=int, default=int(os.getenv('DMAX_PORT', '8080')))
    parser.add_argument('--tls-cert', default=os.getenv('DMAX_TLS_CERT') or None)
    parser.add_argument('--tls-key', default=os.getenv('DMAX_TLS_KEY') or None)
    args = parser.parse_args()
    if bool(args.tls_cert) != bool(args.tls_key):
        parser.error('Informe certificado e chave TLS juntos')
    uvicorn.run(create_app(), host=args.host, port=args.port,
                ssl_certfile=args.tls_cert, ssl_keyfile=args.tls_key, log_level='warning')
