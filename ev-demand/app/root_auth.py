"""Load the owner's packaged PBKDF2 verifier; never contains a plaintext secret."""
import json
from pathlib import Path

from .access import valid_hash


def load_root_hash(path=None):
    path = Path(path) if path is not None else Path(__file__).with_name('root-credential.json')
    if not path.is_file():
        return ''
    if path.stat().st_size > 4096:
        raise ValueError('Configuração raiz inválida')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError('Configuração raiz inválida') from None
    if (not isinstance(data, dict) or set(data) != {'version', 'password_hash'}
            or type(data['version']) is not int or data['version'] != 1
            or not valid_hash(data['password_hash'])):
        raise ValueError('Configuração raiz inválida')
    return data['password_hash']
