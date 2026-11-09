# D-Max 0.8.5 · Portas seriais, leituras, cadastro e exclusão

## Alterações

- A porta serial é selecionada numa lista obtida do próprio servidor. Quando
  disponível, usa o identificador estável /dev/serial/by-id. Uma porta configurada
  mas desconectada continua na lista identificada como não detectada; não é trocada
  silenciosamente por outro adaptador. Recarregue Multimedidor após conectar USB.
- Caminhos Linux recebidos como dev/ttyUSB0 são normalizados para /dev/ttyUSB0.
  Endereços COM e caminhos absolutos permanecem compatíveis. O diagnóstico de teste
  conserva o rascunho na tela, sem substituir pelos valores antigos nem salvá-lo
  automaticamente. Salvar multimedidor é uma ação separada.
- Planta ao vivo e Visão geral mostram todas e somente as grandezas habilitadas
  no mapa manual, com unidades. Configurada sem leitura válida aparece com traço;
  não se inventam tensão/corrente. Em simulação, a potência total é simulada; as
  leituras físicas contínuas dependem do modo físico e configuração válida.
- Exclusão em Carregadores exige perfil técnico/raiz e confirmação. O cadastro é
  retirado da operação e o histórico preservado. Um carregador físico precisa estar
  sem recarga/cabo, sem potência/limite pendente e desconectado do OCPP. Simulados
  podem ser removidos, encerrando suas sessões simuladas.
- Ao mudar de simulação para físico, sessões simuladas são encerradas. Os exemplos
  não aparecem na planta física; permanecem acessíveis ao técnico em Carregadores
  de outro modo para exclusão. Voltar ao simulador não reativa antigas sessões.
- Adicionar um carregador durante uma resposta OCPP pendente não altera a lista
  percorrida no ciclo atual; o novo equipamento aguarda o próximo ciclo e as
  confirmações de redução antes de receber potência.
- Novo técnico ou alteração local acorda a sincronização, sem aguardar o intervalo.
  Continua exigindo integração/chave configurada, internet e confirmação do servidor.
  Falhas preservam a fila. Uma confirmação antiga não apaga edição/troca de senha
  feita durante o envio; essa proteção também persiste se falhar a consulta seguinte.
  Outros D-Max recebem alterações no intervalo normal ou ao consultar no login.
- A tabela de usuários informa cadastro local, global ou pendente. Falha de uma
  sincronização solicitada pela página não é mais apresentada como sucesso.
- Mantém atualização de valores/curva sem recarregar e rodapé de versão visível.

## Atualizar no Raspberry

Extraia D-Max-v0.8.5-RaspberryPi-ARM64.zip fora de /opt/d-max. Abra o terminal na
pasta D-Max-Raspberry e execute `sudo bash instalar-raspberry.sh`. Não desinstale
nem apague os dados. Feche a aba antiga e abra novamente o endereço do D-Max.
Confirme **v0.8.5** no rodapé. Não é necessário trocar a chave do Google ou editar
Apps Script por causa desta atualização. Não é necessário atualizar o kit Grafana.

Em Multimedidor, escolha RS485/Modbus RTU, selecione a porta detectada, confira
baud rate, paridade, stop bits, Unit ID e endereços/tipos/escalas do manual.
Use Testar leitura sem salvar; depois Salvar multimedidor. A seleção de porta não
identifica automaticamente o modelo, endereço Modbus ou registradores do medidor.

## Validação

Regressão de controle/OCPP e permissões; testes de caminho serial e conservação de
rascunho, seleção USB, filtragem de leituras, exclusão com histórico, separação de
modos, recriação de exemplos sem sobrescrever históricos e inclusão durante espera
OCPP. Sincronização testada com serviço isolado e planilha simulada, inclusive
edição de senha durante envio, falha no snapshot e recarga da fila persistida.
Browser real: seletor USB, teste e salvamento, leituras V/A nas duas páginas,
exclusão pela página e versão. A USB e o medidor do teste de navegador são fixtures;
não houve teste físico FT232R/RS485 nem publicação na planilha Google do usuário.
Validar o conjunto no Raspberry real antes de liberar operação de produção.
