# D-Max 0.7.2 — Raspberry Pi OS ARM64

A edição Raspberry mantém o servidor OCPP 1.6J, controle de demanda e multimedidor
Modbus TCP/RTU do Windows. Acrescenta implantação Linux, dependências ARM64 locais,
início automático no systemd, supervisão de processo/controle e preparação do watchdog
físico. O cliente acessa pelo navegador e não precisa executar o controlador no PC.

O ZIP tem lista explícita de 95 arquivos, incluindo 60 wheels oficiais manylinux ARM64
ou independentes de plataforma para CPython normal 3.11/3.12/3.13/3.14. Não contém
wheels Windows, BAT, ambientes virtuais, banco, testes ou chaves privadas. O hash raiz
é idêntico ao publicado na edição Windows 0.7.1; não é necessário preparar credencial
por instalação. O cadastro inicial continua somente com a senha de admin.

## Implantação

- instalar-raspberry.sh verifica arquitetura, Python e manifesto SHA-256, instala
  código root-owned em /opt/d-max e cria conta sem login dmax. Dependências são
  instaladas por hashes com --no-index a partir de wheels/. Pacotes base do sistema,
  como python3-venv, precisam ter sido preparados por apt ou imagem do sistema.
- Banco em /var/lib/d-max, configuração em /etc/d-max e acesso serial via dialout.
  O serviço lê /etc/d-max/rede.ini e usa /etc/d-max/d-max.env. A rede é habilitada
  no endereço configurado e o cadastro inicial local pode usar túnel SSH.
- Manutenção serializada por lock em diretório root-owned 0700. Helpers de instalação
  usam Python em modo isolado. Arquivos não verificados em app/ são recusados; caches
  Python podem ser ignorados na verificação, mas nunca são copiados na instalação.
- Antes de atualizar uma instalação gerenciada, o serviço é parado e código anterior,
  configuração e cópia SQLite são preservados em /var/backups/d-max. Unidades e
  drop-ins personalizados desconhecidos não são sobrescritos automaticamente.

## Recuperação automática

A unidade Type=notify envia READY e exige watchdog de 120 segundos. A supervisão
considera progresso monotônico recente do controlador, ausência de falha de controle
e tarefas ainda ativas. Processos congelados ou controle sem progresso deixam de
alimentar o watchdog. O systemd termina o processo e tenta reiniciar após 10 segundos.
TimeoutStopSec limita o encerramento e dumps de memória são desabilitados.

Checkpoints entre fases/por conector acomodam as esperas OCPP limitadas pelo protocolo;
não basta o servidor HTTP responder para considerar o controle saudável. Falha de
internet não provoca reinício por si só: comunicação local continua e o cadastro
mantém a regra offline existente.

No Raspberry, o instalador prepara dtparam=watchdog=on e um drop-in do systemd para
RuntimeWatchdogSec=30s/RebootWatchdogSec=2min. O driver pode ajustar esses prazos.
A ativação depende de reinício e suporte real do hardware/kernel. Essa camada atua
se o sistema deixar de alimentar o dispositivo, independentemente do watchdog do app.
Não se força reboot durante a instalação. Para outras instalações ARM64 pode-se usar
--no-hardware-watchdog, preservando a supervisão do processo.

## Migração e remoção

O importador para o serviço e usa backup SQLite consistente. Preserva identidades,
credenciais, Google e históricos, revoga logins, volta à simulação, remove o caminho
serial Windows e desmarca comissionamento OCPP. A liberação física exige nova revisão.

O desinstalador para/desabilita o serviço, verifica se a unidade foi personalizada e
remove o aplicativo. Mantém banco, configuração e conta dmax por padrão. --purge-data
exige confirmação APAGAR para remover dados/configuração. Backups não são apagados.
Somente o bloco/drop-in de watchdog gerenciado é removido; mudanças de administrador
são preservadas. Uma reinicialização aplica a remoção da configuração watchdog do SO.

## Evidências de validação

- 136 testes aprovados em Linux x86-64, CPython 3.11 e 3.13, com DMAX_PI_PACKAGE.
  Incluem os 126 casos anteriores, cinco de supervisão, quatro de implantação/dados
  e um ciclo de scripts completo em filesystem temporário. Nesse ciclo UID, systemd
  e pip são simulados; cópias, tar, checksums, importação SQLite, preservação na remoção,
  reinstalação, recusa de unidade modificada, cancelamento e purge confirmado são reais.
- Teste OCPP com WebSocket real e dois clientes, também executado usando módulos do
  ZIP extraído: SetChargingProfile, RemoteStartTransaction, MeterValues e confirmação
  das reduções antes de admitir o segundo carregador.
- Pacote extraído executado por Python 3.13 Linux x86-64: navegador sem JavaScript,
  instalação, palavra-passe raiz, perfis, usuários, medidor, horários, carregadores,
  veículos, emergência, histórico, Google simulado e layout móvel. O processo real
  enviou READY/WATCHDOG/STOPPING a um socket Unix de teste, sem systemd real.
- Resolução offline das 36 dependências ARM64 com --require-hashes e sem PyPI nas
  quatro versões alvo. Todas as wheels conferem com hashes aprovados do lock.
- Bash -n nas três rotinas. Pré-verificação --check executada sem mutações com uname
  ARM64 simulado. systemd-analyze verify aceitou a unidade original em uma árvore
  de filesystem de teste, com executável substituto somente para a análise estática.
- Bandit: seis alertas baixos já conhecidos, três B104 médios relacionados à rede LAN
  solicitada e nenhum alto. [Relatório](security/bandit-v072-raspberry.json). Dependências
  fixadas não foram alteradas; o lock apenas documenta o suporte também a Python 3.11.
- CRC do ZIP, manifesto interno, fontes e hash raiz da edição Windows conferidos.

ShellCheck não ficou disponível: a obtenção da ferramenta falhou por acesso de rede;
não se apresenta resultado dessa ferramenta. Os testes acima não equivalem a ela.

## Limites

Não houve execução ARM64 nativa ou emulação ARM neste ambiente, Raspberry físico,
boot real, systemd ativo, watchdog de hardware ou conexão com equipamentos de potência.
Não se afirma homologação física nem compatibilidade OCPP 2.x. A validação real deve
confirmar comunicação, latência, corrente/potência, falhas, retomada e horários.

Nesta edição piloto, comissionamento físico exige limite zero/retomada validados no
carregador. Watchdog não é proteção elétrica nem garante corte de carga quando o
controlador perde energia/comunicação. Configure a contingência do carregador e
proteções independentes. Para horários offline após reboot, utilize relógio confiável
no Pi 4 (por exemplo RTC). Prefira SSD e alimentação protegida.

[Instalar e remover](raspberry.md) · [Configurar OCPP/Modbus](raspberry-ocpp.md) ·
[Acesso raiz](raspberry-acesso.md)
