#!/usr/bin/env bash
# Pinned repair for managed D-Max 0.12.0 remote supervisor only.
set -euo pipefail
umask 077
app_dir=/opt/d-max
backup_root=/var/backups/d-max
expected=72949d78c8b9e16cd0788ff5ca8413c1e9e735c7ad409338c2e577cac5ec4ccb
original=42da99623eac7682b6b9f0c1951b06b61339af5a3b135519f7e2c5e495888097
fail() { echo "Correção D-Max: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || fail 'Execute com sudo bash.'
[[ $# -le 1 ]] || fail 'Use: sudo bash apply_remote_hotfix.sh [arquivo-local]'
[[ -f "$app_dir/.dmax-managed" && -f "$app_dir/.dmax-remote-managed" ]] || fail 'D-Max e acesso remoto gerenciados precisam estar instalados.'
for path in "$app_dir" "$app_dir/app" "$app_dir/app/remote_tunnel.py" "$backup_root" /run/d-max-maintenance; do
    [[ ! -L "$path" ]] || fail "Destino em link simbólico: $path"
done
install -d -m 0700 /run/d-max-maintenance
exec 9>/run/d-max-maintenance/lock
flock -n 9 || fail 'Outra manutenção está em andamento.'
python_bin="$app_dir/.venv/bin/python"
[[ -x "$python_bin" ]] || fail 'Python instalado não encontrado.'
current=$(sha256sum "$app_dir/app/remote_tunnel.py" | cut -d' ' -f1)
[[ $current == "$original" || $current == "$expected" ]] || fail 'Supervisor personalizado ou de outra versão; arquivo preservado.'
folder=$(mktemp -d)
stage=''
trap 'rm -rf -- "$folder"; [[ -z $stage ]] || rm -f -- "$stage"' EXIT
candidate="$folder/remote_tunnel.py"
if [[ $# == 1 ]]; then
    [[ -f $1 && ! -L $1 ]] || fail 'Arquivo de origem inválido.'
    cp -- "$1" "$candidate"
else
    wget --timeout=30 --tries=2 -O "$candidate" https://raw.githubusercontent.com/jbgodoy6/logsis/dmax-v0.12.1/ev-demand/app/remote_tunnel.py
fi
printf '%s  %s\n' "$expected" "$candidate" | sha256sum --check --status || fail 'SHA-256 divergente. Nada foi aplicado.'
"$python_bin" -I -c 'import py_compile,sys; py_compile.compile(sys.argv[1],doraise=True)' "$candidate"
install_supervisor() {
    stage=$(mktemp "$app_dir/app/.remote_tunnel.XXXXXXXX")
    install -m 0644 "$1" "$stage"
    mv -fT -- "$stage" "$app_dir/app/remote_tunnel.py"
    stage=''
}
if [[ $current != "$expected" ]]; then
    install -d -m 0700 "$backup_root"
    backup="$backup_root/remote_tunnel-$(date -u +%Y%m%dT%H%M%S)-$$.py"
    cp -p -- "$app_dir/app/remote_tunnel.py" "$backup"
    install_supervisor "$candidate"
    if ! systemctl restart d-max-remote.service; then
        install_supervisor "$backup"
        systemctl restart d-max-remote.service || true
        fail 'Falha ao reiniciar; supervisor anterior restaurado.'
    fi
    echo "Correção aplicada. Cópia anterior: $backup"
else
    echo 'Correção já instalada; não foi criado outro túnel.'
fi
echo 'D-Max local e Grafana preservados. Aguardando prontidão do conector...'
for attempt in {1..12}; do
    if "$python_bin" -I -c 'import sys; sys.path.insert(0,"/opt/d-max"); from app.remote_tunnel import public_status; sys.exit(0 if public_status().get("connected") else 1)'; then
        "$python_bin" -I "$app_dir/deploy/remote.py" status
        echo 'Abra o endereço atual por outra rede e confirme o login.'
        exit 0
    fi
    sleep 5
done
"$python_bin" -I "$app_dir/deploy/remote.py" status
echo 'Correção instalada, mas o conector ainda não está pronto. Não foi confirmado acesso público.'
echo 'Consulte: sudo journalctl -u d-max-remote -n 60 --no-pager'
