#!/usr/bin/env bash
# Importação local com serviço parado; não importa .venv nem COM do Windows.
set -euo pipefail
app_dir=/opt/d-max
fail() { echo "D-Max: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || fail 'Execute com sudo.'
[[ $# -eq 1 && -f $1 ]] || fail 'Uso: sudo bash importar-dados-raspberry.sh /caminho/controller.sqlite3'
[[ -f "$app_dir/.dmax-managed" && ! -L "$app_dir" && ! -L /var/lib/d-max ]] || fail 'Instalação gerenciada não identificada.'
[[ ! -L /run/d-max-maintenance ]] || fail 'Diretório de manutenção em link simbólico.'
install -d -o root -g root -m 0700 /run/d-max-maintenance
exec 9>/run/d-max-maintenance/lock
flock -n 9 || fail 'Outra manutenção está em andamento.'
systemctl stop d-max.service
"$app_dir/.venv/bin/python" -I "$app_dir/deploy/manage.py" import-db "$1" /var/lib/d-max/controller.sqlite3 /var/backups/d-max
chown dmax:dmax /var/lib/d-max/controller.sqlite3
chmod 0600 /var/lib/d-max/controller.sqlite3
systemctl start d-max.service
echo 'Dados importados com identidades, senhas, histórico e Google preservados.'
echo 'Modo definido para simulação e comissionamento físico desmarcado. Revise o multimedidor e os carregadores antes de liberar operação física.'
