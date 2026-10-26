"""Identical entry point on Windows and Linux."""
import argparse
import uvicorn
from app.main import create_app

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='LOGSIS EV · Controlador de demanda')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--tls-cert')
    parser.add_argument('--tls-key')
    args = parser.parse_args()
    if bool(args.tls_cert) != bool(args.tls_key):
        parser.error('Informe certificado e chave TLS juntos')
    uvicorn.run(create_app(), host=args.host, port=args.port,
                ssl_certfile=args.tls_cert, ssl_keyfile=args.tls_key, log_level='warning')
