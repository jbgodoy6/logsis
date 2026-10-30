#!/usr/bin/env bash
# Raspberry Pi OS 64-bit. Execute no equipamento de destino, não no Windows.
set -euo pipefail
umask 022
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
python_bin=${PYTHON_BIN:-python3}
app_dir=/opt/d-max
state_dir=/var/lib/d-max
config_dir=/etc/d-max
service_file=/etc/systemd/system/d-max.service
check_only=false
hardware_watchdog=true
fail() { echo "D-Max: $*" >&2; exit 1; }
for argument in "$@"; do
    case "$argument" in
        --check) check_only=true ;;
        --no-hardware-watchdog) hardware_watchdog=false ;;
        --help) echo 'sudo bash instalar-raspberry.sh [--check] [--no-hardware-watchdog]'; exit 0 ;;
        *) fail "Opção desconhecida: $argument" ;;
    esac
done
command -v "$python_bin" >/dev/null || fail 'Instale Python e python3-venv do Raspberry Pi OS.'
"$python_bin" -I -c 'import sys,struct,venv,ensurepip; assert (3,11)<=sys.version_info[:2]<=(3,14) and struct.calcsize("P")==8, "Use CPython 64 bits 3.11 a 3.14"'
case "$(uname -m)" in aarch64|arm64) ;; *) fail 'Este pacote requer Raspberry Pi OS ARM64. Não use sistema de 32 bits.' ;; esac
for executable in systemctl tar flock install sha256sum getent; do
    command -v "$executable" >/dev/null || fail "Comando necessário ausente: $executable"
done
"$python_bin" -I "$source_dir/deploy/manage.py" verify "$source_dir"
if $check_only; then
    echo 'Python, arquitetura, comandos e integridade conferidos. Nada foi instalado.'
    exit 0
fi
[[ $EUID -eq 0 ]] || fail 'Execute: sudo bash instalar-raspberry.sh'
[[ -d /run/systemd/system ]] || fail 'Execute no Raspberry iniciado com systemd, não em um contêiner.'
[[ $source_dir != "$app_dir" ]] || fail 'Extraia o pacote fora de /opt/d-max.'
[[ ! -L /run/d-max-maintenance ]] || fail 'Diretório de manutenção em link simbólico.'
install -d -o root -g root -m 0700 /run/d-max-maintenance
exec 9>/run/d-max-maintenance/lock
flock -n 9 || fail 'Outra instalação, importação ou remoção está em andamento.'
for path in "$app_dir" "$state_dir" "$config_dir" "$service_file"; do
    [[ ! -L "$path" ]] || fail "Destino em link simbólico; revisão manual necessária: $path"
done
if [[ -e "$app_dir" && ! -f "$app_dir/.dmax-managed" ]]; then
    fail 'Já existe /opt/d-max não gerenciado; arquivos preservados.'
fi
if [[ -f "$service_file" ]] && ! cmp -s "$source_dir/deploy/d-max.service" "$service_file"; then
    old_unit_hash=$(sha256sum "$service_file")
    [[ ${old_unit_hash%% *} == be191077ba07aee4d8cb079a384f98f63cd9712f0625fa9cb68d143201b14e40 ]] || fail 'Unidade systemd personalizada; preserve e revise suas alterações antes de atualizar.'
fi
if [[ -x "$app_dir/.venv/bin/python" ]]; then
    current_python=$("$app_dir/.venv/bin/python" -I -c 'import sys;print("%s.%s" % sys.version_info[:2])')
    requested_python=$("$python_bin" -I -c 'import sys;print("%s.%s" % sys.version_info[:2])')
    [[ $current_python == "$requested_python" ]] || fail 'Python do sistema mudou; preserve os dados e recrie .venv manualmente.'
fi
pi_model=''
if [[ -r /proc/device-tree/model ]]; then pi_model=$(tr -d '\000' < /proc/device-tree/model); fi
if $hardware_watchdog; then
    [[ $pi_model == *'Raspberry Pi'* ]] || fail 'Modelo Raspberry não identificado; para outro ARM64 use --no-hardware-watchdog.'
    [[ -f /boot/firmware/config.txt || -f /boot/config.txt ]] || fail 'Arquivo de boot do Raspberry não encontrado.'
    if systemctl is-active --quiet watchdog.service; then fail 'Existe outro daemon watchdog ativo; revise antes de habilitar o watchdog do systemd.'; fi
fi
if compgen -G '/etc/systemd/system/d-max.service.d/*.conf' >/dev/null; then fail 'Há drop-ins personalizados de d-max.service; revise antes de instalar.'; fi
getent group dialout >/dev/null || fail 'Grupo dialout não encontrado.'
if id dmax >/dev/null 2>&1; then
    [[ $(getent passwd dmax | cut -d: -f6) == "$state_dir" ]] || fail 'Usuário dmax já existe para outra finalidade.'
else
    useradd --system --user-group --home-dir "$state_dir" --shell /usr/sbin/nologin dmax
fi
install -d -m 0755 "$app_dir"
install -d -o dmax -g dmax -m 0750 "$state_dir"
install -d -o root -g dmax -m 0750 "$config_dir"
if [[ -f "$app_dir/.dmax-managed" ]]; then
    if [[ -f "$service_file" ]]; then systemctl stop d-max.service; fi
    backup_dir=/var/backups/d-max/update-$(date -u +%Y%m%dT%H%M%S)-$$
    install -d -m 0700 "$backup_dir"
    tar --exclude=d-max/.venv -czf "$backup_dir/app.tar.gz" -C /opt d-max
    tar -czf "$backup_dir/config.tar.gz" -C /etc d-max
    if [[ -f "$state_dir/controller.sqlite3" ]]; then
        "$python_bin" -I "$source_dir/deploy/manage.py" backup-db "$state_dir/controller.sqlite3" "$backup_dir/controller.sqlite3"
    fi
    echo "Backup da versão anterior: $backup_dir"
fi
# A lista do manifesto já foi verificada; não misture módulos da versão antiga.
rm -rf -- "$app_dir/app"
tar --exclude='__pycache__' --exclude='*.pyc' -C "$source_dir" -cf - app | tar -C "$app_dir" -xf -
chown -R root:root "$app_dir/app"
chmod -R a+rX "$app_dir/app"
install -d -m 0755 "$app_dir/deploy"
install -m 0644 "$source_dir/deploy/manage.py" "$app_dir/deploy/manage.py"
install -m 0644 "$source_dir/run.py" "$source_dir/requirements.lock" "$app_dir/"
install -m 0644 "$source_dir/desinstalar-raspberry.sh" "$source_dir/importar-dados-raspberry.sh" "$app_dir/"
install -m 0644 /dev/null "$app_dir/.dmax-managed"
if [[ ! -x "$app_dir/.venv/bin/python" ]]; then "$python_bin" -I -m venv "$app_dir/.venv"; fi
if compgen -G "$source_dir/wheels/*.whl" >/dev/null; then
    "$app_dir/.venv/bin/python" -I -m pip install --disable-pip-version-check --no-index --find-links "$source_dir/wheels" --only-binary=:all: --require-hashes -r "$app_dir/requirements.lock"
else
    fail 'Pasta wheels ausente. Extraia o ZIP Raspberry completo.'
fi
if [[ ! -f "$config_dir/d-max.env" ]]; then
    install -o root -g dmax -m 0640 "$source_dir/deploy/d-max.env.example" "$config_dir/d-max.env"
fi
if [[ ! -f "$config_dir/rede.ini" ]]; then
    install -o root -g dmax -m 0640 "$source_dir/rede.ini" "$config_dir/rede.ini"
fi
if $hardware_watchdog; then
    "$python_bin" -I "$source_dir/deploy/manage.py" enable-watchdog
    echo 'Watchdog de hardware preparado. Reinicie o Raspberry após concluir a instalação e confira a ativação.'
fi
install -o root -g root -m 0644 "$source_dir/deploy/d-max.service" "$service_file"
sha256sum "$service_file" > "$app_dir/.dmax-service.sha256"
systemctl daemon-reload
systemctl enable --now d-max.service
sleep 2
systemctl is-active --quiet d-max.service || fail 'Serviço não iniciou. Consulte: sudo journalctl -u d-max -n 60'
echo 'D-Max instalado e habilitado no boot. Processo monitorado pelo systemd.'
echo 'Primeira configuração: use o túnel SSH descrito no LEIA-ME.txt.'
echo 'Rede: /etc/d-max/rede.ini. Estado: sudo systemctl status d-max --no-pager'
echo 'Logs: sudo journalctl -u d-max -f'
