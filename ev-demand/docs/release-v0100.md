# EnergyCube D-Max 0.10.0

Base: branch `feat/dmax-cloud-visual`, versão 0.9.0, commit `04897f2`.
Atualize sem desinstalar. O instalador preserva `/var/lib/d-max/controller.sqlite3`,
`/etc/d-max`, a porta configurada e o verificador raiz existente. Não copie uma
`.venv` de Windows/x86 para o Raspberry.

## Atualização pelo terminal do Raspberry

Use uma sessão SSH iniciada no Windows. Encerre as sessões de recarga e desconecte
a comunicação dos carregadores antes da manutenção. Extraia fora de `/opt/d-max`:

```sh
mkdir -p "$HOME/dmax-0.10.0"
cd "$HOME/dmax-0.10.0"
curl --fail --location --output D-Max-Raspberry-0.10.0.zip https://raw.githubusercontent.com/jbgodoy6/logsis/feat/dmax-cloud-visual/ev-demand/releases/D-Max-Raspberry-0.10.0.zip
curl --fail --location --output D-Max-Raspberry-0.10.0.zip.sha256 https://raw.githubusercontent.com/jbgodoy6/logsis/feat/dmax-cloud-visual/ev-demand/releases/D-Max-Raspberry-0.10.0.zip.sha256
sha256sum --check D-Max-Raspberry-0.10.0.zip.sha256
unzip D-Max-Raspberry-0.10.0.zip
cd D-Max-Raspberry
sudo bash instalar-raspberry.sh --check
sudo bash instalar-raspberry.sh
sudo systemctl status d-max --no-pager
```

Se o repositório exigir autenticação, use seu mecanismo autorizado de download;
não inclua tokens na URL. O ZIP contém wheels oficiais verificadas pelo lock para
CPython 3.11–3.14/Linux ARM64. O Python e `python3-venv` precisam estar instalados.
Nenhum comando acima apaga a instalação atual. A atualização cria backup em
`/var/backups/d-max/update-*`, incluindo código, ambiente Python, configuração e
banco consistente. Falha de instalação/reinício aciona retorno à versão anterior.
Não interrompa a alimentação durante a manutenção. Confira o journal se houver
falha: `sudo journalctl -u d-max -u d-max-maintenance -n 100 --no-pager`.

## Interface e supervisão

Visão geral reúne a planta, todos os carregadores, veículos, multimedidor,
indicadores e curva. O endereço antigo `/ui/monitor` abre a mesma visão, sem
segunda aba no menu. Valores e SVG são atualizados no lugar; o campo de outras
cargas fica fora da região atualizada para preservar o que está sendo digitado.
Somente técnico/instalador e raiz operam a simulação e suas APIs. No modo físico
os controles de simulação não aparecem. O nome do cliente recebe destaque; o
desenho do multimedidor permanece maior com leituras compactas. O aviso de
alteração some após cinco segundos e é consumido na primeira visita.

Sessões por senha renovam durante requisições autenticadas, incluindo a
supervisão automática: operador, 7 dias de inatividade; administrador, 24 horas;
técnico, 12 horas; raiz, 4 horas. Recuperação raiz por assinatura continua com
15 minutos absolutos. Logout, troca de senha, validade, bloqueios e revogação
continuam encerrando acesso. Mensalidade e prazo de sessão são independentes.
Novas instalações usam porta 80 para web e `/ocpp/IDENTIFICADOR`; atualizações
preservam `/etc/d-max/rede.ini`, inclusive portas diferentes.

Cada carregador mostra limite solicitado, resposta do comando, limite aceito e
potência medida. Aceite OCPP não comprova cumprimento físico. Idade da última
medição distingue leitura válida zero, leitura antiga e leitura nunca recebida.
Motivos de espera incluem horário, orçamento/prioridade, confirmação de redução,
pausa e ausência de medição. A regra de reduzir e medir antes de aumentar continua.

## Relatórios e auditoria

Histórico oferece PDF detalhado e Geral por veículo, com múltipla seleção,
incluindo veículos excluídos e sessões sem veículo. O geral mostra histórico
acumulado, subtotal do período, quantidade e último início de recarga. Energia
real, simulada e de origem desconhecida têm totais separados. O filtro continua
pelo **início da sessão**, e usa toda a energia registrada dessa sessão; não é
medição recortada dentro do intervalo. Sessões abertas são parciais.
Auditoria permite consultar alterações e responsáveis, com filtro por login,
sem exibir verificadores de senha ou chaves. Retenção de eventos segue a política
local já existente; exporte os registros necessários antes da limpeza.

## Contato autenticado e assinatura

Contato válido é a resposta assinada por equipamento do fornecedor, com timestamp
mais recente; ping, acesso ao roteador ou sucesso de envio Grafana não contam.
O Apps Script 0.9.0 já produz esse envelope. Configure a plataforma e uma linha
válida na aba Assinaturas, com a chave do equipamento no armazenamento privado
do serviço, nunca em células ou no chat.

Sem contato: aviso aos 15 dias com controle ativo; pendência aos 30 dias com mais
10 dias de prazo; funcionamento nativo solicitado aos 40 dias. A contagem começa
na migração/instalação se ainda não há contato comprovado, sem inventar histórico
anterior. A contagem persiste entre reinícios. Respostas antigas não renovam prazo.
Uma pendência financeira vence em seu próprio prazo de dez dias e prevalece se
for anterior. Reconectar não apaga dívida; somente regularização assinada válida
altera o estado financeiro. O relógio usa marca persistida e avanço monotônico;
um Pi 4 exige RTC com bateria para contar corretamente tempo desligado/offline.
Isso não constitui proteção inviolável contra root ou manipulação de backups.

Ao vencer, o D-Max solicita remover seus próprios perfis OCPP e permite fluxo
nativo de início/fim, sem resetar fábrica ou apagar rede. Offline, rejeição e
timeout ficam como liberação pendente. A instalação elétrica precisa suportar
operação nativa sem a proteção de demanda. Exige homologação de cada modelo.

## Nuvem real e demonstração

Configure `cloud_url` + `EV_CLOUD_TOKEN` para o real; `demo_cloud_url` +
`EV_DEMO_CLOUD_TOKEN` para demonstração. Destinos e tokens devem ser diferentes.
Use projetos/bancos, Edge Functions, credenciais e fontes Grafana separados.
O emissor grava a origem imutável de cada registro e envia somente a fila do
modo correspondente. Registros legados sem origem comprovada ficam preservados
em quarentena, sem envio automático ao ambiente real.

`cloud/supabase/schema.sql` define a instalação do banco como `physical` por
padrão e rejeita lotes de outra origem na ingestão. Banco exclusivo de demonstração
usa `update dmax.deployment set environment='simulation' where id=1;`.
`cloud/prepare_demo.py` e `cloud/compose.yaml` mantêm volumes e fonte de dados de
demonstração separados. Isto não provisiona um Supabase/Grafana de produção.

## Manutenção pelo navegador

Após esta primeira atualização por terminal, Manutenção permite backup ao técnico
e raiz; restauração e atualização somente ao raiz. O serviço web continua sem
privilégios para instalar código. Um worker root, acionado por systemd, revalida o
arquivo antes de parar o serviço. Atualizações exigem Ed25519 e hashes de todos
os arquivos, com chave pública fixada em `/etc/d-max/update-public.pem`; o ZIP não
pode substituir essa confiança. Guarde a chave privada de publicação em local
seguro fora do repositório/pacotes. Neste ambiente ela está em
`/workspace/.dmax-signing/update-private.pem`; preserve-a para assinar versões
futuras. A chave de atualização é independente da credencial raiz existente.

Backups contêm dados privados e chaves locais; armazene com acesso restrito.
Restauração aceita somente banco íntegro da mesma instalação, valida o esquema,
recusa triggers/views, cria backup anterior, invalida sessões e preserva identidade,
assinatura, credencial raiz e vínculo atual da plataforma. A fila antiga restaurada
não é reenviada. O retorno automático é tentado se a nova aplicação falhar no
reinício; confira os registros e restaure manualmente do backup se necessário.

## Limites da validação

Consulte `validation-v0100.md` para os comandos e resultados desta entrega.
Testes locais/simulados não comprovam funcionamento em Pi físico, relógio RTC,
boot, watchdog físico ou carregadores reais. O ambiente anterior e seu checkout
foram preservados. Não houve acesso nem alteração ao Raspberry instalado.
