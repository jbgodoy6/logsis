#!/usr/bin/env bash
# Remove o serviço e aplicativo; preserva os dados salvo opção explícita.
set -euo pipefail
app_dir=/opt/d-max
state_dir=/var/lib/d-max
config_dir=/etc/d-max
service_file=/etc/systemd/system/d-max.service
purge=false
fail() { echo "D-Max: $*" >&2; exit 1; }
case ${1:-} in
    '') ;;
    --purge-data) purge=true ;;
    --help) echo 'sudo bash desinstalar-raspberry.sh [--purge-data]'; exit 0 ;;
    *) fail 'Opção inválida.' ;;
esac
[[ $# -le 1 ]] || fail 'Argumentos inválidos.'
[[ $EUID -eq 0 ]] || fail 'Execute com sudo.'
[[ -f "$app_dir/.dmax-managed" && ! -L "$app_dir" && ! -L "$app_dir/.dmax-managed" ]] || fail 'Instalação gerenciada não identificada; nada foi apagado.'
for path in "$state_dir" "$config_dir" "$service_file"; do [[ ! -L "$path" ]] || fail 'Destino em link simbólico; nada foi apagado.'; done
if [[ -f "$service_file" ]]; then
    [[ -f "$app_dir/.dmax-service.sha256" && ! -L "$app_dir/.dmax-service.sha256" ]] || fail 'Verificador do serviço ausente; revise manualmente.'
    expected_hash=$(cut -d ' ' -f 1 "$app_dir/.dmax-service.sha256")
    actual_hash=$(sha256sum "$service_file")
    [[ ${actual_hash%% *} == "$expected_hash" ]] || fail 'Serviço personalizado; revise manualmente antes de remover.'
fi
if compgen -G '/etc/systemd/system/d-max.service.d/*.conf' >/dev/null; then fail 'Há drop-ins personalizados; revise antes de remover.'; fi
if $purge; then
    echo 'Esta opção apaga banco, históricos, usuários e configuração local. Backups anteriores serão preservados.'
    read -r -p 'Para confirmar, digite APAGAR: ' confirmation
    [[ $confirmation == APAGAR ]] || fail 'Remoção cancelada.'
fi
[[ ! -L /run/d-max-maintenance ]] || fail 'Diretório de manutenção em link simbólico.'
install -d -o root -g root -m 0700 /run/d-max-maintenance
exec 9>/run/d-max-maintenance/lock
flock -n 9 || fail 'Outra manutenção está em andamento.'
if [[ -f "$service_file" ]]; then systemctl disable --now d-max.service; fi
if [[ -f /etc/systemd/system.conf.d/70-d-max-watchdog.conf ]]; then
    python3 -I "$app_dir/deploy/manage.py" disable-watchdog || fail 'Watchdog personalizado; revise sem apagar sua configuração.'
fi
rm -f -- "$service_file"
systemctl daemon-reload
systemctl reset-failed d-max.service >/dev/null 2>&1 || true
rm -rf -- "$app_dir"
if $purge; then
    rm -rf -- "$state_dir" "$config_dir"
    if id dmax >/dev/null 2>&1; then userdel dmax || echo 'Conta dmax preservada; confira processos externos que a utilizam.'; fi
    echo 'Aplicativo, serviço, banco e configuração removidos. Backups em /var/backups/d-max preservados.'
else
    echo 'Aplicativo e serviço removidos. Dados, configuração e conta de serviço preservados para reinstalação.'
fi
echo 'Reinicie o Raspberry para aplicar a remoção da configuração watchdog de hardware.'
