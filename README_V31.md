# LOGSIS / DSE7420 — V31 Sinal e modo

A V31 acrescenta três indicadores compactos dentro do próprio unifilar, acima da torre e do gerador:

- **Wi-Fi / RSSI:** usa o campo `WiFi_rssi` informado para esta instalação. Reconhece também `wifi_rssi`, a grafia que o PostgreSQL produz quando o identificador é criado sem aspas.
- **GSM / RSSI:** usa `gsm_rssi`, já existente nas versões anteriores.
- **Modo / GMG:** mostra `STOP`, `MANUAL` ou `AUTO`, com o mapeamento legado `MDB43`: 0, 1 e 2, respectivamente. Código diferente aparece como `INVÁLIDO`; modo ausente aparece como `SEM DADOS`.

Os dois rádios têm ícones próprios e podem aparecer ao mesmo tempo. RSSI é mostrado como recebido, sem conversão presumida para porcentagem, dBm ou qualidade. O painel não determina qual rádio encaminha o tráfego nem testa acesso à internet. Um traço `—` indica sinal ausente ou inválido; o ícone correspondente fica discreto. Dados disponíveis usam ciano, que identifica a presença da leitura.

Os três indicadores usam **a última amostra dentro do período selecionado**. Um sinal ou modo ausente nessa amostra não é preenchido com uma leitura antiga. A consulta acessa a coluna Wi-Fi por JSON: instalações sem essa coluna continuam funcionando e mostram `—`. O nome pode ser ajustado na constante oculta `Campo_WiFi_RSSI`, cujo valor padrão é `WiFi_rssi`.

## Importar

Baixe [V31_IMPORTAR.zip](V31_IMPORTAR.zip), extraia **V31_IMPORTAR.json** e importe em **Dashboards → New → Import → Upload dashboard JSON file**. Use **Import (Overwrite)** para atualizar a planta existente. O UID continua `logsis-dse7420-v26-unifilar`.

O ZIP tem um único JSON com os vetores incorporados. A mesma planta atende celular, tablet e computador. As leituras sob a torre/gerador, os quatro indicadores compactos, os sete grupos com 56 canais e os 13 painéis históricos/alertas da V30 permanecem disponíveis. Para outra planta com UID personalizado, mantenha seu UID, datasource e `Id_Logsis` ao aplicar a atualização.

As leituras elétricas e conversões anteriores foram preservadas. A saída continua inferida pelas tensões das fontes e posições dos contatos. Os grupos completos e os resumos compartilham a consulta principal; não há consultas independentes para cada sinal ou modo.

## Evidências

[Desktop](V31_DESKTOP_PREVIEW.png) · [Celular](V31_CELULAR_PREVIEW.png) · [Validação visual](V31_VALIDACAO.json) · [Validação dos sinais/modo](V31_SINAIS_VALIDACAO.json)

Grafana 11.2.2, Chromium e PostgreSQL de laboratório com dados simulados. Testados importação pela interface, largura de 320 a 1920 px, 56 canais, texto dos cartões, estados elétricos, modos de operação, campos Wi-Fi com as duas grafias, GSM sem coluna Wi-Fi, sinais ausentes, entradas malformadas e ausência de preenchimento com amostras anteriores. As capturas usam dados simulados, não leituras de equipamento real.

## Gerar

Execute `python tools/build_v31_sinal_modo.py`. O gerador lê a V26 como fonte e grava o JSON universal e seu ZIP em `dist/`. Para importar a versão pronta, basta o JSON da V31.
