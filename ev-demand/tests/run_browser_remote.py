"""Create and pin an ephemeral local TLS certificate; no global TLS bypass."""
import base64
from datetime import datetime,timedelta,timezone
import hashlib
import ipaddress
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.request
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization,hashes

root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='dmax-remote-browser-') as folder:
    folder=Path(folder);key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'127.0.0.1')]);now=datetime.now(timezone.utc)
    cert=(x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=1))
          .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False).sign(key,hashes.SHA256()))
    (folder/'cert.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (folder/'key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    (folder/'key.pem').chmod(0o600)
    pin=base64.b64encode(hashlib.sha256(key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)).digest()).decode()
    env=dict(os.environ,DMAX_TEST_REMOTE_ROOT=secrets.token_urlsafe(32),DMAX_TEST_REMOTE_DB=str(folder/'controller.sqlite3'),
             DMAX_TEST_REMOTE_CERT=str(folder/'cert.pem'),DMAX_TEST_REMOTE_KEY=str(folder/'key.pem'),DMAX_TEST_REMOTE_PIN=pin)
    with open('/tmp/dmax-remote-browser-server.log','w') as log:
        server=subprocess.Popen([sys.executable,str(root/'tests/server_remote.py')],env=env,stdout=log,stderr=log)
        try:
            for attempt in range(60):
                try:urllib.request.urlopen('http://127.0.0.1:8123/api/setup',timeout=1);break
                except Exception:time.sleep(.2)
            else:raise RuntimeError('Remote browser fixture did not start')
            subprocess.run(['node','tests/browser_remote.cjs'],cwd=root,env=env,check=True)
        finally:
            server.terminate();server.wait(timeout=20)
