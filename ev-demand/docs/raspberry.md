# D-Max 0.7.2 — Raspberry Pi 4, servidor OCPP e controle de demanda

Use Raspberry Pi OS Lite 64 bits (ARM64). São suportados CPython 3.11 a 3.14;
Bookworm normalmente fornece 3.11 e Trixie 3.13. Não use sistema de 32 bits nem copie
.venv do Windows. Recomendados Ethernet, SSD USB e alimentação protegida por nobreak.
O pacote inclui as dependências Linux ARM64 para instalação local por hashes.

O Raspberry executa o controlador, OCPP 1.6J, leitura Modbus, banco e interface web.
Os computadores usam somente o navegador; não precisam manter Python ou D-Max aberto.
Root e a palavra-passe do proprietário já estão preparados, como na versão Windows.
A primeira instalação pede somente a senha de admin. Nenhuma chave precisa ser gerada.

## 1. Preparar o Raspberry

No Raspberry Pi Imager, escolha Raspberry Pi OS Lite 64 bits, configure seu usuário,
senha do sistema e habilite SSH. Não existe uma conta pi padrão nas versões novas:
use o usuário que você definiu. Ligue na rede e obtenha o IP no roteador.
Reserve esse IP para o Raspberry. O IP do computador Windows não é automaticamente
o IP do Raspberry. Mantenha os relógios corretos; para horários confiáveis após
reinício sem internet, o Pi 4 precisa de RTC externo ou outra fonte confiável de hora.

Na primeira preparação do sistema, conecte à internet e execute por SSH:

    sudo apt update
    sudo apt install -y python3-venv python3-pip unzip
    python3 --version
    uname -m

O resultado da arquitetura deve ser aarch64 (ou arm64). Instale a versão Python do
próprio sistema. As dependências do D-Max serão instaladas do ZIP, sem download PyPI.
A instalação inicial dos pacotes do sistema por apt depende de repositórios acessíveis.
A operação local depois de instalada funciona sem internet.

## 2. Copiar e instalar

Do PowerShell do Windows, ajuste o nome do usuário e o IP:

    scp "$env:USERPROFILE\Downloads\D-Max-v0.7.2-RaspberryPi-ARM64.zip" SEU_USUARIO@IP_DO_PI:~/
    ssh SEU_USUARIO@IP_DO_PI

No terminal SSH do Raspberry:

    unzip D-Max-v0.7.2-RaspberryPi-ARM64.zip
    cd D-Max-Raspberry
    bash instalar-raspberry.sh --check
    sudo bash instalar-raspberry.sh
    sudo reboot

A última instrução reinicia o Raspberry e encerra a conexão SSH. Aguarde o sistema
voltar e conecte novamente. O instalador não reinicia o equipamento sem esse comando.
O ZIP contém SHA256SUMS.txt; o instalador confere o manifesto antes de copiar código.
Instale de uma pasta extraída nova, não de dentro de /opt/d-max. Não misture versões.

O instalador cria o usuário sem login dmax e habilita d-max.service no boot. Código
fica em /opt/d-max, banco em /var/lib/d-max/controller.sqlite3, rede em
/etc/d-max/rede.ini e ambiente em /etc/d-max/d-max.env. O serviço tem acesso serial
pelo grupo dialout. Configuração e banco são separados do código e preservados nas
atualizações. Não rode manualmente outro run.py contra o mesmo banco do serviço.

## 3. Primeiro cadastro de admin

O primeiro cadastro continua restrito ao próprio servidor. Como Raspberry Pi OS Lite
não tem navegador, abra um túnel pelo PowerShell do Windows:

    ssh -N -L 18080:127.0.0.1:8080 SEU_USUARIO@IP_DO_PI

Mantenha esse terminal aberto e visite http://127.0.0.1:18080 no navegador Windows.
Defina somente a senha de admin. Se você importou o banco do Windows, esse cadastro
não aparece e as contas existentes são mantidas. A porta local 18080 evita conflito
com o D-Max Windows antigo na porta 8080. Não exponha o cadastro inicial pela internet.

Após configurar, qualquer computador da mesma rede pode acessar:

    http://IP_DO_PI:8080

O nome anunciado é dmax-<identificador>.local. Para personalizar:

    sudo nano /etc/d-max/rede.ini

Exemplo:

    [web]
    host = 0.0.0.0
    porta = 8080
    nome = dmax-garagem
    anunciar = true

Salve e aplique:

    sudo systemctl restart d-max

O endereço será http://dmax-garagem.local:8080 em clientes/redes compatíveis com mDNS.
Caso o nome não resolva, use o IP ou um registro no DNS do roteador. Não é necessário
instalar nada nos computadores de acesso. Ao trocar a porta, atualize também os
carregadores: painel e OCPP compartilham a mesma porta. Variáveis DMAX_HOST/DMAX_PORT
equivalentes no arquivo de ambiente têm precedência; não mantenha valores conflitantes.
Configure TLS com certificado confiável em d-max.env para HTTPS/WSS com credenciais reais;
os arquivos devem ser legíveis por root:dmax, modo 0640, dentro de /etc/d-max.
O programa não modifica firewall ou roteador automaticamente.

## 4. Validar OCPP e multimedidor

O sistema novo começa em SIMULAÇÃO. Ele é servidor OCPP real, mas não presume que
os equipamentos estejam homologados. Consulte OCPP-E-MULTIMEDIDOR.txt para configurar
ID/senha, endereço WebSocket, mapa Modbus TCP/RTU, limites, zero e retomada.
Este pacote implementa OCPP 1.6J; não afirma compatibilidade OCPP 2.x.
O Raspberry deve conseguir alcançar o multimedidor e receber conexões dos carregadores.
Não confunda trocar a plataforma Linux com validar comportamento elétrico do hardware.

## 5. Início automático e recuperação de travamentos

- Boot: d-max.service é habilitado automaticamente, sem login e sem terminal aberto.
- Processo encerrado: systemd tenta iniciar novamente após 10 segundos, inclusive
  após falha/saída inesperada. Uma parada explícita por systemctl stop é respeitada.
- Processo/controle travado: WatchdogSec=120 exige notificações do próprio D-Max.
  Só há heartbeat enquanto as tarefas estão vivas, sem falha de controle e com
  progresso recente do controlador. Se o processo ou o controle travar, o systemd
  encerra e reinicia o processo. A detecção e a finalização podem levar alguns minutos;
  não são uma atuação elétrica instantânea. OCPP lento dentro dos timeouts normais
  possui checkpoints para não confundir uma rodada longa com travamento.
- Linux/PID1 travado: por padrão no Raspberry, o instalador prepara
  dtparam=watchdog=on e um drop-in do systemd com RuntimeWatchdogSec=30s. O watchdog
  de hardware pode reiniciar o Raspberry se o sistema parar de alimentá-lo. O driver
  pode ajustar o prazo ao limite do hardware. A ativação é conferida DEPOIS de reiniciar.

O watchdog de hardware depende do kernel/driver do Raspberry e só pode ser validado
no equipamento real. O instalador preserva config.txt e acrescenta um bloco identificado,
com backup em /var/backups/d-max. Ele não toma controle de outro daemon watchdog ativo.
Para uma instalação deliberadamente sem hardware watchdog, use
sudo bash instalar-raspberry.sh --no-hardware-watchdog; o watchdog do processo permanece.
Não desative o watchdog do processo como solução para defeitos sem analisar os logs.

Depois do boot:

    sudo systemctl is-enabled d-max
    sudo systemctl status d-max --no-pager
    sudo systemctl show d-max -p WatchdogUSec -p Restart -p NRestarts
    sudo systemctl show -p RuntimeWatchdogUSec
    ls -l /dev/watchdog*
    cat /sys/class/watchdog/watchdog0/identity
    cat /sys/class/watchdog/watchdog0/state
    cat /sys/class/watchdog/watchdog0/timeout
    sudo journalctl -u d-max -n 60 --no-pager

Serviço ativo não comprova controle físico. Teste a API, recarga e medidor em conjunto.
Não provoque congelamento do kernel ou falhas de watchdog durante recarga real. Reboot
ou queda de energia não garantem que um carregador vá a zero: valide a contingência
do firmware e mantenha proteções elétricas independentes do controlador.

Para testar apenas o watchdog do PROCESSO, use uma instalação vazia em simulação,
sem carregadores físicos conectados. Consulte PID/contador, suspenda o processo e
aguarde alguns minutos; o systemd deverá encerrá-lo e iniciar outro:

    sudo systemctl show d-max -p MainPID -p NRestarts
    sudo systemctl kill --kill-whom=main --signal=SIGSTOP d-max
    sudo systemctl show d-max -p MainPID -p NRestarts
    sudo journalctl -u d-max -n 40 --no-pager

O PID deve mudar e NRestarts aumentar após o tempo de detecção/finalização. Faça a
última consulta depois de aguardar. Este procedimento não testa o watchdog físico
do Linux e não deve ser usado em instalação com recargas ativas.

## 6. Migrar os dados do Windows

1. Pause/encerre as recargas antes da manutenção. Pare o D-Max Windows com Ctrl+C.
   Faça backup da pasta data inteira depois de parar. Não copie somente o SQLite
   principal enquanto ele estiver sendo gravado; arquivos WAL podem conter dados.
2. Copie a pasta data para o Raspberry, por exemplo pelo PowerShell:

       scp -r "C:\CAMINHO\D-Max\data" SEU_USUARIO@IP_DO_PI:~/dmax-windows-data

3. No Raspberry, depois de instalar o pacote:

       sudo bash /opt/d-max/importar-dados-raspberry.sh "$HOME/dmax-windows-data/controller.sqlite3"

O importador para o serviço, salva o banco atual em /var/backups/d-max e importa por
backup SQLite consistente. Mantém contas, senhas, ID do controlador, chave Google,
carregadores, veículos, históricos e dados pendentes. Encerra sessões de login,
volta para simulação, limpa a porta serial Windows e desmarca comissionamento OCPP.
Revise o Linux/RS485 e homologue novamente antes de liberar o modo físico.
Não execute simultaneamente o Windows antigo e o Raspberry como controlador físico
para os mesmos carregadores. Ao preservar ID/chave Google salva pela tela, não é preciso autorizar
outro equipamento, desde que a chave não tenha sido revogada na plataforma. Tokens
e certificados definidos no ambiente/arquivos do Windows não estão no banco: configure-os
separadamente em /etc/d-max/d-max.env e nos caminhos protegidos correspondentes.

## 7. Atualizar

Extraia outro pacote em pasta nova e execute seu instalador. O banco e a configuração
local são preservados. O app, configuração e uma cópia SQLite anterior ficam em
/var/backups/d-max/update-<data>. A instalação não sobrescreve unidade systemd
personalizada desconhecida. Se a versão principal do Python do sistema mudou, é
necessário planejar/recriar o ambiente virtual; a rotina não apaga .venv sozinha.
Em caso de falha, mantenha o serviço parado, consulte journalctl e restaure código,
configuração e banco do backup correspondente. Não misture código e banco antigos.

## 8. Desinstalar

Pare as recargas e execute:

    sudo bash /opt/d-max/desinstalar-raspberry.sh

Remove o serviço e /opt/d-max; preserva banco, configuração, conta dmax e backups.
Permite reinstalar sem perder cadastros. Remove somente o bloco/drop-in de hardware
watchdog criado pelo instalador; configuração personalizada é preservada para revisão.
Reinicie depois para aplicar essa remoção da configuração do sistema.

Para APAGAR também banco, históricos, usuários e configuração local:

    sudo bash /opt/d-max/desinstalar-raspberry.sh --purge-data

Será necessário digitar APAGAR para confirmar. Os backups em /var/backups/d-max
permanecem até você decidir removê-los. O desinstalador não remove Python, SSH nem
pacotes do sistema que possam ser usados por outros programas.

## Limites desta entrega

Código, fluxo OCPP, supervisão e migração são testados em Linux x86-64. A resolução
ARM64 das wheels foi validada para as quatro versões Python; não é execução ARM64.
Não foram executados aqui um Raspberry físico, boot real, watchdog de hardware,
USB/RS485 ou carregadores reais. Essa homologação deve ser feita no seu equipamento.
