# D-Max no Raspberry — validação OCPP 1.6J e Modbus

O Raspberry é o servidor OCPP e o controlador de demanda. O navegador não precisa
ficar aberto; o serviço continua ao desligar ou trocar um computador de acesso.
O protocolo implementado é OCPP 1.6 JSON por WebSocket. OCPP 2.x não está implementado.

## Rede e cadastro

1. Reserve o IP do Raspberry no roteador e confirme que carregadores e multimedidor
   conseguem alcançá-lo. Configure firewall/VLAN conforme a rede da instalação.
2. Entre como root com a palavra-passe do proprietário ou como técnico autorizado.
3. Em Carregadores, cadastre o ID exato do equipamento (exemplo CP-01), nome,
   transporte OCPP, potência total/por conector, mínimo, circuito, unidade W/A,
   número de conectores e senha OCPP. A senha é por carregador, não a senha root.
4. No carregador, configure OCPP 1.6J, ID CP-01 e a senha correspondente. O D-Max
   exige Basic Authentication: usuário igual ao ID e senha igual à cadastrada.

Endereço completo de exemplo:

    ws://IP_DO_PI:8080/ocpp/CP-01

Se o equipamento tiver campos separados para URL base e Charge Point ID e acrescentar
ID automaticamente, use base ws://IP_DO_PI:8080/ocpp e ID CP-01. Não duplique o ID no
caminho. O subprotocolo WebSocket é ocpp1.6. Em uma implantação com TLS confiável,
use wss:// e a porta/certificado configurados. Não desabilite verificação de certificados.
A porta web e OCPP é a mesma; qualquer alteração exige atualizar ambas as URLs.
O sistema não descobre/carrega automaticamente todo equipamento de uma rede por IP:
o carregador inicia a conexão com o servidor e seu cadastro/ID devem existir.

## Multimedidor

TCP: configure IP, porta (normalmente 502), Unit ID, intervalo e timeout.
RTU: conecte adaptador RS485 USB com direção automática e confira:

    ls -l /dev/serial/by-id/

Use o caminho estável do adaptador no cadastro, não COM3/COM4 do Windows. Configure
baud, paridade, stop bits, Unit ID, funções Modbus 03/04 e endereços conforme o manual.
Confira base zero/um, tipos, ordem de bytes/palavras e fatores de escala. O serviço
recebe acesso serial via dialout. Caso o adaptador não tenha ID único, identifique
corretamente o caminho /dev/serial/by-path/ e valide após reinicializações.

Cadastre e teste a potência ativa TOTAL da entrada, com unidade/escala em kW.
Cadastre energia importada em kWh para histórico quando disponível. Compare leituras
com a tela do multimedidor antes de usar como referência de demanda.

## Liberar modo físico e validar

Uma instalação nova e uma importação começam em simulação. Em Configurações, revise
limite técnico, demanda operacional, margem, circuitos e medidor; então selecione
modo físico para aceitar conexões OCPP. O cadastro de carregadores precisa existir.

Esta edição piloto só admite comissionamento físico após validar limite zero e
retomada no equipamento. Marque zero suportado/comissionado apenas depois de testar
essas funções. Um modelo que rejeite zero e só aceite potência mínima exige adaptação
ou homologação específica; não marque suporte inexistente para forçar o cadastro.
Não há teto fixo de 100/1000 kW no controle; informe os valores reais da instalação.

Confirme BootNotification, Heartbeat, StatusNotification e MeterValues. Acompanhe
SetChargingProfile e RemoteStartTransaction. O sistema reduz autorizações existentes
antes de admitir aumentos/novos carregamentos e exige confirmação por medições atuais.
Ausência/atraso de leitura válida do multimedidor mantém a proteção de admissão.

Sequência de homologação, com responsável técnico e proteções independentes:

- Um carregador, sem atingir a demanda máxima: perfil de potência, zero e retomada.
- Dois carregadores: redução confirmada do primeiro antes da entrada do segundo.
- Variação das outras cargas: redução/aumento dentro da demanda e margem.
- Prioridade do veículo, fila, pausa, horários de ponta e emergência individual.
- Perda do multimedidor, perda de comunicação OCPP, queda/reinício do controlador.
- Persistência dos históricos e comportamento após retorno de internet/energia.
- Bloqueio de técnico na planilha: aplicação após sincronização automática bem-sucedida.
  Sem internet continua valendo o cadastro previamente recebido; não há revogação
  remota instantânea de um equipamento sem comunicação.

Quando houver sessão física já existente após reinício, o D-Max exige conciliação com
MeterValues/transactionId e retomada manual; não restaura automaticamente uma autorização
antiga. Watchdog não é proteção elétrica: homologue também o comportamento do carregador
quando perde comunicação/alimentação do controlador e sua política local de contingência.

Dados da etiqueta do veículo/placa ou VIN não são garantidos pelo OCPP 1.6 sem integração
específica. Utilize o vínculo e o cadastro disponíveis; não presuma identificação
universal do veículo por simplesmente conectar o cabo.
