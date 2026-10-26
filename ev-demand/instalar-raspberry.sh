#!/usr/bin/env bash
# Raspberry Pi OS 64-bit / Linux com systemd. Execute no equipamento de destino.
set -euo pipefail
umask 022
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
python_bin=${PYTHON_BIN:-python3}
app_dir=/opt/d-max
state_dir=/var/lib/d-max
config_dir=/etc/d-max
service_file=/etc/systemd/system/d-max.service

fail() { echo "D-Max: $*" >&2; exit 1; }
command -v "$python_bin" >/dev/null || fail 'Python não encontrado.'
"$python_bin" -c 'import sys; assert sys.version_info[:2] in ((3,12),(3,13),(3,14)), "Use Python 3.12, 3.13 ou 3.14"'
case "$(uname -m)" in aarch64|arm64|x86_64) ;; *) fail 'Use um sistema operacional de 64 bits.' ;; esac
command -v systemctl >/dev/null || fail 'Este instalador requer systemd.'
command -v tar >/dev/null || fail 'Comando tar não encontrado.'
if [[ ${1:-} == --check ]]; then
    echo 'Pré-requisitos básicos encontrados. Nenhum arquivo ou serviço foi alterado.'
    exit 0
fi
[[ $EUID -eq 0 ]] || fail 'Execute: sudo bash instalar-raspberry.sh'
[[ -d /run/systemd/system ]] || fail 'Execute no Raspberry/Linux iniciado com systemd, não em um contêiner.'
for path in "$app_dir" "$state_dir" "$config_dir" "$service_file"; do
    [[ ! -L "$path" ]] || fail "O destino é um link simbólico; revisão manual necessária: $path"
done
if [[ -d "$app_dir" ]] && [[ ! -f "$app_dir/.dmax-managed" ]]; then
    fail 'Já existe /opt/d-max não gerenciado por este instalador; arquivos preservados.'
fi
if [[ -f "$service_file" ]] && ! cmp -s "$source_dir/deploy/d-max.service" "$service_file"; then
    fail 'Existe uma unidade systemd diferente. Preserve suas alterações e revise a atualização manualmente.'
fi
if id dmax >/dev/null 2>&1; then
    [[ $(getent passwd dmax | cut -d: -f6) == "$state_dir" ]] || fail 'O usuário dmax já existe com outra finalidade.'
else
    useradd --system --user-group --home-dir "$state_dir" --shell /usr/sbin/nologin dmax
fi
getent group dialout >/dev/null || fail 'Grupo dialout não encontrado; configure a permissão serial deste sistema.'
install -d -m 0755 "$app_dir"
install -d -o dmax -g dmax -m 0750 "$state_dir"
install -d -o root -g dmax -m 0750 "$config_dir"

# Para uma atualização, interrompa o serviço e preserve o aplicativo anterior.
# O banco em /var/lib/d-max permanece separado e nunca é substituído.
if [[ -f "$app_dir/.dmax-managed" ]]; then
    if systemctl cat d-max.service >/dev/null 2>&1; then
        systemctl stop d-max.service
    fi
    install -d -m 0700 /var/backups/d-max
    backup=/var/backups/d-max/app-$(date -u +%Y%m%dT%H%M%S)-$$.tar.gz
    tar -czf "$backup" -C /opt d-max
    echo "Aplicativo anterior preservado: $backup"
fi
install -m 0644 /dev/null "$app_dir/.dmax-managed"
cp -a "$source_dir/app" "$app_dir/"
chown -R root:root "$app_dir/app"
install -m 0644 "$source_dir/run.py" "$source_dir/requirements.lock" "$app_dir/"
chmod -R a+rX "$app_dir/app"
if [[ ! -x "$app_dir/.venv/bin/python" ]]; then
    "$python_bin" -m venv "$app_dir/.venv"
fi
"$app_dir/.venv/bin/python" -c 'import sys; assert sys.version_info[:2] in ((3,12),(3,13),(3,14)), "Versão do ambiente existente não suportada"'
"$app_dir/.venv/bin/python" -m pip install --requirement "$app_dir/requirements.lock"
if [[ ! -f "$config_dir/d-max.env" ]]; then
    install -o root -g dmax -m 0640 "$source_dir/deploy/d-max.env.example" "$config_dir/d-max.env"
fi
install -o root -g root -m 0644 "$source_dir/deploy/d-max.service" "$service_file"
systemctl daemon-reload
systemctl enable --now d-max.service

# Confirme que o serviço não saiu durante a inicialização. A documentação inclui
# a verificação HTTP, necessária após configurar host, porta e certificado.
sleep 2
systemctl is-active --quiet d-max.service || fail 'Serviço não iniciou. Consulte: sudo journalctl -u d-max -n 60'
echo 'D-Max instalado. Inicialização automática habilitada.'
echo 'Confira a API local: curl --fail http://127.0.0.1:8080/api/setup'
echo 'Estado: sudo systemctl status d-max --no-pager'
echo 'Logs: sudo journalctl -u d-max -f'
