# LOGSIS / DSE8610 — Gerador e BUS

[Baixar o JSON em ZIP](DSE8610_V1_IMPORTAR.zip) · [JSON direto](DSE8610_V1_IMPORTAR.json)

Um único dashboard responsivo no padrão visual da V32: gerador monitorado → disjuntor de acoplamento → BUS comum → carga. Os outros grupos aparecem como referência ligada ao BUS; não são inventados valores ou estados individuais. Não há concessionária nem chave de transferência de rede.

## Importar e configurar a planta

1. Extraia `DSE8610_V1_IMPORTAR.json` do ZIP e importe pelo Grafana em **Dashboards → New → Import → Upload dashboard JSON file**.
2. Em **Dashboard settings → Variables → Id_Logsis**, substitua `id_dse8610` pelo nome real da tabela desta planta. Esse valor é um identificador de exemplo; a consulta precisa da tabela correta antes de retornar dados. A variável é constante e fica oculta no uso normal.
3. O datasource PostgreSQL mantém o UID `zKW_ld27k`, usado no ambiente anterior. Se o seu datasource tiver outro UID, ajuste-o nos painéis que consultam PostgreSQL.

UID da nova planta: **`logsis-dse8610-v1-bus`**. A importação não substitui o dashboard DSE7420. O ZIP contém somente o JSON importável, com os desenhos vetoriais incorporados.

## Mapeamento e funcionamento

- **MDB01–28:** motor e grandezas elétricas do gerador.
- **MDB29–35:** frequência e seis tensões do BUS comum, junto ao desenho.
- **MDB36–39:** horímetro, energia, partidas e horas de manutenção.
- **MDB40:** modo; não usa MDB43 para modo.
- **MDB41–43:** warning, trip elétrico e shutdown.
- **MDB44–51:** entradas A–H.
- **MDB52:** disjuntor de acoplamento, **0 aberto / 1 fechado**, conforme confirmação do usuário. Qualquer outro valor é posição desconhecida.

O BUS é colorido pela sua própria medição, mesmo com o gerador parado ou seu disjuntor aberto. Vermelho significa presença de tensão, não corrente nem direção de potência. A saída para a carga acompanha a tensão do BUS. O desenho não afirma sincronismo ou quantidade de geradores em paralelo sem registros específicos.

Modo e leituras numéricas usam a última leitura válida por campo no período selecionado. Tensões para as cores usam a última amostra disponível de cada grupo de fases; os horários podem diferir. Ausência de dado não vira zero. Todos os 52 canais permanecem acessíveis em grupos de cartões; os quatro resumos reutilizam a consulta principal. Só históricos/alertas ficam recolhidos, com nove painéis próprios do DSE8610.

Wi-Fi usa `WiFi_rssi`, com fallback para `wifi_rssi`. GSM usa `gsm_rssi` em dBm, valor e cinco barras; a constante `Formato_GSM` aceita `csq` quando o equipamento realmente fornecer CSQ 0–31. Os sinais representam rádio, sem teste de acesso à internet.

## Códigos e escalas iniciais

O BIN confirma endereços, rótulos e parâmetros, mas não comprova todas as conversões de engenharia. Esta primeira exportação usa as conversões do padrão anterior nos endereços equivalentes, com constantes para ajuste nas variáveis do dashboard:

| Constante | Valor inicial | Uso |
|---|---:|---|
| Codigo_STOP | 0 | MDB40 / STOP |
| Codigo_AUTO | 1 | MDB40 / AUTO |
| Codigo_MANUAL | 2 | MDB40 / MANUAL |
| Divisor_Tensao | 10 | GMG e BUS |
| Divisor_Corrente | 10 | Correntes do gerador |
| Divisor_Potencia | 1000 | W/VA/VAr para kW/kVA/kVAr |
| Divisor_FP | 100 | Fatores de potência |
| Divisor_Horas | 3600 | Horímetro e manutenção |
| Divisor_Energia | 10 | Energia acumulada |

Pressão usa /100; bateria, alternador DC e frequências usam /10. Temperaturas, rotação, partidas e estados não recebem esses divisores. A enumeração inicial do modo é compatível com os rótulos/limiares do BIN; confira os três modos no controlador e ajuste as constantes se necessário. Os campos de alarme pressupõem que o coletor aplique os BIT 10/11/12 configurados no BIN; a tela não aplica extração duplicada.

Confira escalas com uma leitura real antes de considerar a planta validada em equipamento. O arquivo não altera o controlador nem escreve no banco.

## Evidências

[Desktop](DSE8610_DESKTOP_PREVIEW.png) · [Celular](DSE8610_CELULAR_PREVIEW.png) · [Validação SQL](DSE8610_SQL_VALIDACAO.json) · [Validação Grafana](DSE8610_UI_VALIDACAO.json)

Grafana 11.2.2, Chromium e PostgreSQL isolados com dados simulados. Verificados importação pela interface, 52 canais, larguras de 320 a 1920 px, históricos, BUS energizado por outros grupos com GCB aberto, estados desconhecidos, seleção temporal vazia e modo preservado em telemetria parcial. Não houve acesso ao controlador ou ao banco de produção.

## Gerar novamente

Execute `python tools/build_dse8610_v1.py` na raiz deste repositório. O gerador usa o mapeamento auditado em `DSE8610_ANALISE/` e as definições de desenho da V32, sem executar nem alterar o dashboard DSE7420. A exportação é gravada em `dist/`. Para usar a versão pronta, basta o único JSON.
