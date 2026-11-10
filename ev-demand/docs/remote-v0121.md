# Correção do acesso remoto — D-Max 0.12.1

A 0.12.0 forçava HTTP/2 e deduzia conexão apenas de mensagens do cliente. Na
instalação analisada, o DNS inicialmente expirava e, depois de corrigido,
pré-testes mostraram alcance parcial aos servidores da Cloudflare. Isso não
prova uma regra específica de firewall e não garante o acesso público.

Esta correção:

- Usa o modo oficial `auto`, permitindo QUIC e o fallback nativo para HTTP/2.
  Mantém TLS verificado. Usa IPv4, disponível na instalação analisada.
- Confere `/ready` do próprio cloudflared a cada 5 segundos, por loopback na porta
  20246. Uma linha de log isolada não basta para informar conexão pronta.
  Essa prontidão é do conector: o acesso público ainda deve ser confirmado.
- Reconhece perda da conexão HTTP/2 (`Lost connection with the edge`).
- Recria o cliente se ele ficar 180 segundos sem prontidão. O endereço pode mudar;
  a sincronização existente publica o endereço atual quando conseguir contato.
- Recusa `api.trycloudflare.com` e `www.trycloudflare.com` como endereços de acesso,
  inclusive ao ler status antigo, impedindo o envio desses endereços à planilha.
- Registra falhas de pré-teste por destino e categorias de erro, sem imprimir
  tokens, credenciais ou cabeçalhos. O diagnóstico original não é ecoado inteiro.
- Interrompe o cliente quando o serviço recebe sinal, sem esperar nova linha de
  log; limita a espera e drena a saída para evitar travamento no encerramento.

O protocolo pode ser fixado em um override systemd com a variável
`DMAX_REMOTE_PROTOCOL=http2` ou `quic`, caso o administrador precise homologar um
transporte específico; o padrão é `auto`. Alterar isso não libera uma porta
bloqueada e não substitui a correção de rede. Não modifica DNS, IP, gateway,
firewall, usuários, banco, controle de recarga ou Grafana.

## Instalação completa no Raspberry

Use o procedimento da 0.12.0, substituindo a versão e a pasta por 0.12.1/0121:

```sh
cd ~
mkdir -p atualizar-dmax-0121
cd atualizar-dmax-0121
wget -c https://raw.githubusercontent.com/jbgodoy6/logsis/dmax-v0.12.1/ev-demand/releases/D-Max-Raspberry-0.12.1.zip
wget -c https://raw.githubusercontent.com/jbgodoy6/logsis/dmax-v0.12.1/ev-demand/releases/D-Max-Raspberry-0.12.1.zip.sha256
sha256sum -c D-Max-Raspberry-0.12.1.zip.sha256
```

Só após `OK`, com recargas encerradas:

```sh
unzip -o D-Max-Raspberry-0.12.1.zip
cd D-Max-Raspberry
sudo bash instalar-raspberry.sh --check
sudo bash instalar-raspberry.sh
sudo bash /opt/d-max/acesso-remoto.sh ativar
sudo bash /opt/d-max/acesso-remoto.sh status
```

O cliente e as dependências já vêm no ZIP. Abra somente o endereço atual quando
houver prontidão; confira o login por uma rede externa. Para consultar erros:

```sh
sudo journalctl -u d-max-remote -n 60 --no-pager
```

## Correção pontual em uma instalação 0.12.0

O script `tools/apply_remote_hotfix.sh` aplica somente o supervisor, com cópia
anterior e validação por SHA-256, sem reiniciar o controlador ou Grafana. Use o
script e o `remote_tunnel.py` da mesma referência publicada. O rodapé permanece
0.12.0 porque o restante do aplicativo não muda. A instalação completa 0.12.1 já
inclui a correção. O manifesto da instalação 0.12.0 deixa de corresponder ao
supervisor alterado; use o ZIP íntegro ao reinstalar/atualizar futuramente.

## Validação e limite de acesso

Testes cobrem endereço da API em erro, prontidão 503/200, registro sem prontidão,
perda da borda, protocolo configurável, reciclagem de subprocesso real silencioso,
parada por sinal e ausência de segredos nos registros. O ambiente de desenvolvimento
não possui VPN/rota para os IPs privados do Raspberry. Não foi aplicada correção no
equipamento por este terminal e não foi homologado acesso público na rede do cliente.

Resultado em 10/11/2026: **241 testes Python passaram, zero falhas e zero testes
ignorados**, incluindo pacote ARM64 e PostgreSQL isolado. Chromium validou gateway
HTTPS local, cookies/formulários, bloqueio de OCPP/setup, atualização ao vivo,
curva, exportações e layout móvel. Não foi testado um túnel público neste executor.
O pacote completo mantém assinatura Ed25519 e o cliente ARM64 oficial já validado.

Para aplicar apenas a correção no terminal já conectado ao Raspberry:

```sh
wget -O ~/dmax-corrigir-remoto.sh https://raw.githubusercontent.com/jbgodoy6/logsis/dmax-v0.12.1/ev-demand/tools/apply_remote_hotfix.sh && sudo bash ~/dmax-corrigir-remoto.sh
```

O script baixa o supervisor dessa mesma tag, confere seu hash fixado e recusa
arquivos instalados personalizados. Guarda a cópia anterior em /var/backups/d-max.
Depois de aplicar, aguarda até 60 segundos; se não houver prontidão, mostra o estado
sem declarar o problema resolvido. A recuperação continua por conta do serviço.
