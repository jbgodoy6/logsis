"""Generate only a platform verifier; never save or echo the entered password."""
import getpass
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import password_hash

def main():
    password=getpass.getpass('Senha individual (mínimo 12 caracteres): ')
    confirm=getpass.getpass('Confirme: ')
    if password!=confirm or len(password)<12 or len(password)>200:
        raise SystemExit('Senhas divergentes ou tamanho inválido')
    print(password_hash(password))

if __name__=='__main__':main()
