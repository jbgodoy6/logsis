# LOGSIS / DSE7420 — V32 Correções de modo e sinal

## Mudanças

- **Modo corrigido:** a sinalização do unifilar usa agora o mesmo `MDB43` da instrumentação: última leitura válida desse campo dentro do período escolhido. Na V31, ela lia `mdb43` apenas na última linha da tabela; uma linha de telemetria parcial podia deixar o indicador `SEM DADOS`, mesmo com um modo disponível na janela. Preservado o mapeamento legado 0 = STOP, 1 = MANUAL, 2 = AUTO.
- **GSM em dBm com cinco barras:** o valor informado `−53` é mostrado como **−53 dBm**, acompanhado das barras de intensidade. A leitura usa o mesmo `GSM_RSSI` da consulta existente, dentro do período selecionado. Sinal ausente/fora do formato configurado aparece como `—` com ícone discreto.
- **Quadro separado de rede removido:** as seis tensões e a frequência da concessionária permanecem abaixo da torre. Gerador e motor ocupam a coluna direita do computador; no celular, os mesmos painéis se reorganizam em sequência. Os 56 canais continuam acessíveis, com os sete canais da rede no próprio unifilar e os outros 49 em seis grupos.

Os quatro indicadores compactos, as leituras sob os desenhos e os 13 painéis históricos/alertas permanecem. O formato continua sendo uma planta, um dashboard e um JSON, com todos os vetores incorporados.

## GSM e intensidade

A constante oculta `Formato_GSM` vem configurada como **dbm**, conforme o valor negativo informado nesta instalação. O valor bruto fica disponível na consulta como `GSM_BRUTO`; `GSM_LOCAL` é o valor exibido em dBm. Em instalações que comprovadamente usem CSQ de 0 a 31, a constante pode ser alterada para `csq`; nesse formato a conversão é `−113 + 2 × CSQ`. O código 99 é indisponível em CSQ. A exportação não tenta adivinhar o formato a partir de um valor positivo.

As cinco barras representam faixas visuais de RSSI: 1 abaixo de −110 dBm; 2 a partir de −110; 3 a partir de −100; 4 a partir de −90; 5 a partir de −80. São uma referência de intensidade de rádio, sem teste de alcance da internet ou avaliação de velocidade. Wi-Fi continua usando `WiFi_rssi`, com suporte à grafia PostgreSQL `wifi_rssi`.

O modo e o GSM podem ter horários de leitura diferentes, pois seguem a última leitura disponível de cada campo no período. Nenhum deles busca fora da janela. A indicação de período e o horário geral da última amostra permanecem no desenho.

## Importar

Baixe [V32_IMPORTAR.zip](V32_IMPORTAR.zip), extraia **V32_IMPORTAR.json** e use **Dashboards → New → Import → Upload dashboard JSON file → Import (Overwrite)**. O UID permanece `logsis-dse7420-v26-unifilar` para atualizar a planta existente. Para outra planta com UID personalizado, preserve seu UID, datasource e `Id_Logsis` ao atualizar.

## Validação

[Desktop](V32_DESKTOP_PREVIEW.png) · [Celular](V32_CELULAR_PREVIEW.png) · [Layout e estados elétricos](V32_VALIDACAO.json) · [Modo e sinais](V32_SINAIS_VALIDACAO.json)

Grafana 11.2.2, Chromium e PostgreSQL isolados com dados simulados. Casos de regressão incluem última linha com modo vazio e leitura anterior válida, seleção de período histórico, ausência de leitura na janela, GSM −53 dBm, CSQ configurável e ausência do quadro de rede. Conferidos os 56 canais em larguras de 320 a 1920 px, mantendo o SQL elétrico e os históricos anteriores. Os testes não acessam o banco nem o controlador de produção.

## Gerar

`python tools/build_v32_correcao_modo.py` gera o JSON e seu ZIP em `dist/`. O script usa a V26 como fonte de geração; no Grafana basta importar o único JSON da V32.
