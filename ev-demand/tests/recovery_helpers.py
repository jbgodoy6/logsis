"""Ephemeral owner key for isolated tests only; never included in deployment."""
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from app.main import create_app
from app.recovery import DOMAIN, canonical, encode, payload_from

PRIVATE = Ed25519PrivateKey.generate()
PUBLIC = PRIVATE.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)


def create_test_app(*args, **kwargs):
    kwargs.setdefault('root_password_hash', '')
    return create_app(*args, **kwargs, recovery_public_key=PUBLIC)


def sign(challenge, private=PRIVATE):
    payload = payload_from(challenge.removeprefix('DMAX-C1.'))
    return 'DMAX-R1.' + encode(canonical(payload)) + '.' + encode(private.sign(DOMAIN + canonical(payload)))


def recover_root(client):
    challenge = client.post('/api/recovery/challenge', json={})
    assert challenge.status_code == 200, challenge.text
    return client.post('/api/recovery/authorize', json={'authorization': sign(challenge.json()['challenge'])})
