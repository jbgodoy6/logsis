# D-Max 0.8.1 · Visual compacto e cores configuráveis

Os cartões Grafana passam de 12 para 7 unidades de altura (cerca de 42% menos)
e de três para quatro cartões por linha. Desenhos de contorno discretos dão
prioridade à potência, veículo, limite e energia da sessão. A planta local também
recebe os mesmos ícones e disposição compacta. O controle OCPP não foi alterado.

## Escolher suas cores no Grafana

É necessário ter permissão para editar o dashboard.

1. Abra o dashboard D-Max e entre em Editar (Edit).
2. No PRIMEIRO cartão de carregador, abra o menu e escolha Editar (Edit).
   Ele é o modelo que gera os demais cartões por repetição.
3. Na lateral direita, procure Limiares (Thresholds). O modo é Absoluto (Absolute).
4. Clique no círculo colorido de cada faixa e escolha no seletor nativo:

| Faixa | Estado | Padrão inicial |
|---|---|---|
| Base (valor abaixo de 1) | Cabo desconectado ou estado não confirmado | Cinza |
| 1 | Cabo conectado, sem recarga confirmada | Azul |
| 2 | Carregando, com potência atual acima de 0,1 kW | Verde |
| 3 | Alarme informado pelo carregador | Vermelho |

5. Aplique a edição, se o Grafana mostrar Apply/Back to dashboard, e salve o
   dashboard em Save dashboard. As cores são aplicadas a todos os cartões repetidos
   e ficam salvas no Grafana, sem editar Python ou SQL e sem reiniciar o Raspberry.

Não altere os valores das faixas; altere somente suas cores. Os textos continuam
informando os estados, mesmo se você escolher cores parecidas para dois estados.
O painel é nativo do Grafana OSS 12.2; não requer plugin pago.

A demo habilita allowUiUpdates no provisionamento, necessário para salvar as
edições. Em Grafana próprio com dashboard provisionado por arquivo, habilite
`allowUiUpdates: true` no provider. Em dashboard importado pelo navegador, salve
normalmente. Antes de substituir/importar um novo JSON, exporte sua versão
personalizada: uma atualização do arquivo de provisionamento pode sobrescrever
edições que estavam salvas no banco Grafana.

## Comunicação é informação independente

- **Comunicação normal:** conexão OCPP do carregador está estabelecida e há estado
  recente do controlador na nuvem.
- **Sem comunicação OCPP:** o Raspberry está se comunicando com a nuvem, mas a
  conexão do carregador com o D-Max foi perdida. Pode ser rede local, energia,
  configuração ou equipamento; não é prova de falha da internet do carregador.
- **Controlador sem comunicação com a nuvem:** não há estado/contato recente do
  Raspberry (limiar de 150 s). Não se presume que cada carregador tenha desligado.

Ícone de rede cortado e texto em âmbar distinguem perda de comunicação do cabo
fisicamente desconectado. O horário exibido é o da última fotografia da planta.
Nenhum equipamento desaparece por ficar offline. O alarme pode continuar como
último estado informado, mas o aviso de comunicação permanece visível.

A cor de comunicação tem sua própria configuração em Overrides > campo
communication_state > Thresholds: Base = sem comunicação; 1 = comunicação normal.
Ajustar essa configuração não muda a paleta dos quatro estados do carregador.

## Atualizar a partir de 0.8.0

1. Para usar somente o Grafana novo, não precisa atualizar o Raspberry 0.8.0:
   execute novamente cloud/supabase/schema.sql no SQL Editor do projeto existente
   e importe/substitua o novo cloud/grafana/dmax-planta.json. O SQL preserva dados,
   tokens e permissões e acrescenta os campos de comunicação à view. Não execute
   scripts de criação de credenciais novamente.
2. Atualize os arquivos de cloud/grafana/assets no servidor Grafana, preservando
   seu banco de dados e o login existente. Se usar imagem Docker personalizada,
   reconstrua a imagem com o Dockerfile e recrie somente o Grafana, preservando o volume.
3. Para ter o novo visual também no D-Max local, use o pacote Raspberry 0.8.1 e
   o instalador existente, sem desinstalar nem apagar banco, usuários ou rede.ini.
4. Para uma demo Compose já preparada, reinicie Grafana após acrescentar
   `allowUiUpdates: true` ao arquivo cloud/.demo/dashboard.yaml. Não apague a pasta
   .demo nem rode prepare_demo.py novamente sobre uma demo existente.

As cores escolhidas no Grafana não alteram a paleta fixa da página local do D-Max.
