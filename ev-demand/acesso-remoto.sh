#!/usr/bin/env bash
# Optional remote pilot. Does not change OCPP, database, Grafana or local networking.
set -euo pipefail
umask 077
app_dir=/opt/d-max
remote_home=/var/lib/d-max-remote
config_dir=/etc/d-max
remote_config=/etc/d-max-remote
units_dir=/etc/systemd/system
python_bin="$app_dir/.venv/bin/python"
fail() { echo "D-Max remoto: $*" >&2; exit 1; }
action=${1:-status}
[[ $# -le 1 ]] || fail 'Use: sudo bash acesso-remoto.sh ativar|desativar|status|remover'
[[ -x "$python_bin" && -f "$app_dir/.dmax-managed" ]] || fail 'Atualize o D-Max antes de ativar o acesso remoto.'
if [[ $action == status ]]; then
    "$python_bin" -I "$app_dir/deploy/remote.py" status
    exit 0
fi
[[ $EUID -eq 0 ]] || fail 'Execute com sudo.'
for path in "$remote_home" "$remote_home/public" "$remote_home/.dmax-remote-managed" "$config_dir" "$remote_config" "$remote_config/known_hosts" "$units_dir/d-max-remote.service" "$units_dir/d-max-remote-gateway.service"; do
    [[ ! -L "$path" ]] || fail "Link simbólico não permitido: $path"
done
case "$action" in
 desativar|remover)
    if [[ -f "$app_dir/.dmax-remote-managed" ]]; then
        systemctl disable --now d-max-remote.service d-max-remote-gateway.service
        if [[ $action == remover ]]; then
            sha256sum --check --status "$app_dir/.dmax-remote-units.sha256" || fail 'Unidades personalizadas; arquivos preservados.'
            rm -f -- "$units_dir/d-max-remote.service" "$units_dir/d-max-remote-gateway.service"
            rm -f -- "$app_dir/.dmax-remote-managed" "$app_dir/.dmax-remote-units.sha256"
            systemctl daemon-reload
        fi
    fi
    echo 'Acesso remoto parado. D-Max local e Grafana continuam funcionando. Chave preservada para reativação.'
    exit 0 ;;
 ativar) ;;
 *) fail 'Use: sudo bash acesso-remoto.sh ativar|desativar|status|remover' ;;
esac
for executable in ssh ssh-keygen ssh-keyscan systemctl install getent flock; do
    command -v "$executable" >/dev/null || fail "Comando ausente: $executable. Instale openssh-client se necessário."
done
[[ ! -L /run/d-max-maintenance ]] || fail 'Diretório de manutenção em link simbólico.'
install -d -o root -g root -m 0700 /run/d-max-maintenance
exec 9>/run/d-max-maintenance/lock
flock -n 9 || fail 'Outra manutenção está em andamento.'
if [[ -e "$remote_home" && ! -f "$remote_home/.dmax-remote-managed" ]]; then
    fail 'Diretório remoto preexistente não gerenciado; arquivos preservados.'
fi
for unit in d-max-remote.service d-max-remote-gateway.service; do
    if [[ -f "$units_dir/$unit" && ! -f "$app_dir/.dmax-remote-managed" ]]; then
        fail "Serviço preexistente não gerenciado: $unit"
    fi
done
if [[ -f "$app_dir/.dmax-remote-managed" ]]; then
    sha256sum --check --status "$app_dir/.dmax-remote-units.sha256" || fail 'Unidades personalizadas; revise antes de ativar.'
fi
"$python_bin" -I "$app_dir/deploy/remote.py" preflight
temporary=$(mktemp -d)
trap 'rm -rf -- "$temporary"' EXIT
echo 'Conferindo a identidade SSH do provedor; exige saída para proxy.tunnl.gg na porta 22...'
ssh-keyscan -T 15 -t ed25519 proxy.tunnl.gg > "$temporary/known_hosts" 2>/dev/null || fail 'Provedor inacessível. Acesso local preservado; confira internet e saída TCP 22.'
"$python_bin" -I "$app_dir/deploy/remote.py" verify-host "$temporary/known_hosts"
if id dmax-remote >/dev/null 2>&1; then
    [[ $(getent passwd dmax-remote | cut -d: -f6) == "$remote_home" ]] || fail 'Usuário dmax-remote pertence a outra finalidade.'
else
    useradd --system --user-group --home-dir "$remote_home" --shell /usr/sbin/nologin dmax-remote
fi
install -d -o dmax-remote -g dmax -m 0750 "$remote_home"
install -d -o dmax-remote -g dmax -m 2750 "$remote_home/public"
install -o root -g root -m 0644 /dev/null "$remote_home/.dmax-remote-managed"
[[ ! -L "$remote_home/id_ed25519" && ! -L "$remote_home/id_ed25519.pub" ]] || fail 'Chave em link simbólico; preservada para revisão.'
if [[ ! -f "$remote_home/id_ed25519" ]]; then
    ssh-keygen -q -t ed25519 -N '' -C 'D-Max remote access' -f "$remote_home/id_ed25519"
fi
if [[ ! -f "$remote_home/id_ed25519.pub" ]]; then
    ssh-keygen -y -P '' -f "$remote_home/id_ed25519" > "$remote_home/id_ed25519.pub"
fi
chown dmax-remote:dmax-remote "$remote_home/id_ed25519" "$remote_home/id_ed25519.pub"
chmod 0600 "$remote_home/id_ed25519"
install -o root -g root -m 0755 -d "$remote_config"
install -o root -g root -m 0644 "$temporary/known_hosts" "$remote_config/known_hosts"
for unit in d-max-remote.service d-max-remote-gateway.service; do
    install -o root -g root -m 0644 "$app_dir/deploy/$unit" "$units_dir/$unit"
done
sha256sum "$units_dir/d-max-remote.service" "$units_dir/d-max-remote-gateway.service" > "$app_dir/.dmax-remote-units.sha256"
install -o root -g root -m 0644 /dev/null "$app_dir/.dmax-remote-managed"
systemctl daemon-reload
systemctl enable --now d-max-remote-gateway.service d-max-remote.service
systemctl restart d-max-remote-gateway.service d-max-remote.service
echo 'Serviços habilitados no boot. Aguardando endereço remoto...'
for attempt in {1..20}; do
    if "$python_bin" -I -c 'import json,pathlib,sys,time; p=pathlib.Path("/var/lib/d-max-remote/public/status.json"); d=json.loads(p.read_text()) if p.exists() else {}; sys.exit(0 if d.get("connected") and time.time()-d.get("heartbeat_at",0)<90 else 1)'; then
        "$python_bin" -I "$app_dir/deploy/remote.py" status
        echo 'Confira o endereço por uma rede externa e faça login no D-Max.'
        exit 0
    fi
    sleep 2
done
echo 'Serviços instalados, mas o túnel ainda não confirmou conexão.' >&2
echo 'Consulte: sudo journalctl -u d-max-remote -u d-max-remote-gateway -n 60 --no-pager' >&2
exit 1
