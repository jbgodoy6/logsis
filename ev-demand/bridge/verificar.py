"""Verify the complete shipped allowlist before launching the company portal."""
import hashlib
from pathlib import Path
import sys
root = Path(__file__).resolve().parent
try:
    for line in (root / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected, name = line.split('  ', 1)
        path = root / name
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(name)
except (OSError, ValueError) as error:
    print('Pacote incompleto ou alterado. Extraia novamente o ZIP completo. Arquivo:', str(error))
    sys.exit(1)
print('Integridade do pacote conferida.')
