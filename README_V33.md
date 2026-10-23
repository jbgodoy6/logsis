# LOGSIS / DSE7420 — V33 Supervisão

Dashboard único e responsivo, com o mapa de 53 variáveis fornecido na imagem. Substitui a V32 para esta configuração DSE7420. Não altera o dashboard DSE8610.

## Importar

Extraia [V33_IMPORTAR.zip](V33_IMPORTAR.zip) e importe **V33_IMPORTAR.json** no Grafana, usando **Import (Overwrite)** para atualizar o dashboard existente. O UID permanece `logsis-dse7420-v26-unifilar`. Confira o datasource PostgreSQL na importação.

A variável constante oculta `Id_Logsis` está configurada como `id_269086509881540`, conforme confirmado pelo usuário. Para outra planta, altere essa variável nas configurações e use um UID próprio.

## Chave de transferência

- **MDB52:** K1, rede na carga; 0 aberto, 1 fechado.
- **MDB53:** K2, gerador na carga; 0 aberto, 1 fechado.
- **MDB40:** modo; 0 STOP, 1 AUTO, 2 MANUAL. A imagem fornecida confirma MANUAL com valor 2.

As lâminas aparecem inclinadas quando abertas, verticais quando fechadas e com indicação de indisponibilidade para valores desconhecidos. Os sinais 52/53 e as tensões usados no desenho vêm da mesma amostra elétrica dentro do período selecionado. Uma linha de telemetria totalmente vazia para esses campos não apaga a amostra anterior dentro do período.

Antes de cada contato, a linha fica vermelha quando há tensão positiva válida nessa fonte. Depois dos contatos, ambos os trechos pertencem ao barramento comum: ficam vermelhos quando qualquer fonte com tensão está conectada. Portanto, um trecho após um contato aberto pode estar energizado pela outra fonte. A saída é **inferida**, pois este mapa não fornece um sensor independente de tensão na carga.

Com ambos os contatos abertos e fontes conhecidas, a saída fica na cor original. Valores ausentes não são tratados como zero. Se ambos os sinais forem 1, o desenho mostra os dois contatos fechados e um alerta; não esconde a condição nem presume um intertravamento.

Atualização automática de 5 segundos, limitada pela chegada da telemetria. Eventos mais curtos que a amostragem podem não aparecer. O dashboard supervisiona os sinais: não comanda a transferência nem comprova a manobra física.

## Mapa e escalas

| MDB | Leitura | Conversão aplicada |
|---|---|---|
| 1 | Pressão do óleo | /100, bar |
| 2–3 | Temperatura da água e do óleo | °C |
| 4 | Combustível | % |
| 5–6 | Alternador de carga e bateria | /10, V |
| 7 | Rotação | rpm |
| 8 | Frequência do gerador | /10, Hz |
| 9–14 | Tensões do gerador: L1–N, L2–N, L3–N, L1–L2, L2–L3, L3–L1 | /10, V |
| 15–18 | Correntes L1, L2, L3 e terra | /10, A |
| 19–22 | Potências ativas L1, L2, L3 e total | /1000, kW |
| 23–24 | Potências aparente e reativa totais | /1000, kVA/kvar |
| 25–28 | Fatores de potência L1, L2, L3 e médio | /100 |
| 29 | Frequência da rede | /10, Hz |
| 30–35 | Tensões da rede, mesma sequência de fases | /10, V |
| 36 | Horímetro acumulado | /3600, h |
| 37 | Energia acumulada | /Divisor_Energia, kWh |
| 38 | Número de partidas | inteiro |
| 39 | Tempo até manutenção | /3600, h |
| 40 | Modo de operação | 0 STOP / 1 AUTO / 2 MANUAL |
| 41–43 | Warning, trip elétrico e shutdown | 0 inativo / 1 ativo |
| 44–51 | Entradas digitais A–H | 0 OFF / 1 ON |
| 52–53 | Rede e gerador na carga | 0 aberto / 1 fechado |

As escalas analógicas preservam a configuração anterior. `Divisor_Energia` é uma constante oculta com valor inicial **10**: MDB37 = 188 aparece como 18,8 kWh. A imagem não comprova essa escala; se o controlador mostrar 188 kWh, configure o divisor como **1**.

Os códigos de indisponibilidade 65535/32767/32765 nos respectivos campos de 16 bits e os sentinelas de 32 bits são descartados, sem limitar indevidamente potências válidas. Na amostra da imagem, óleo, temperatura do óleo, FP médio e manutenção ficam indisponíveis, em vez de exibir valores artificiais.

Os alarmes históricos foram corrigidos para MDB41/42/43. O histórico da chave usa MDB52/53. Mantidos os 13 painéis históricos/alertas, as leituras da rede sob a torre e os indicadores compactos. Não há um quadro de rede redundante.

## Internet

GSM usa `gsm_rssi` em dBm, incluindo −53 dBm e cinco barras de intensidade. Wi-Fi usa `WiFi_rssi`, com suporte à grafia `wifi_rssi`. As barras representam intensidade de rádio, não um teste de acesso à internet. Os campos opcionais de conexão podem estar ausentes sem invalidar a consulta.

## Validação

Grafana 11.2.2, Chromium e PostgreSQL isolados, com dados simulados; nenhum acesso ao controlador ou banco de produção.

- [SQL](V33_SQL_VALIDACAO.json): 81 combinações de tensões/contatos e quatro casos adicionais, incluindo a amostra da imagem, período vazio, posição inválida e telemetria parcial.
- [Interface](V33_UI_VALIDACAO.json): importação real, larguras de 320 a 1920 px, todos os 53 canais e atualização dos contatos/linhas sem recarregar a página. Sequência rede → ambos abertos → gerador e retorno; também ambos fechados e posição inválida.
- [Históricos](V33_HISTORICOS_VALIDACAO.json): execução das 33 consultas dos 13 painéis e conferência das fontes de alarmes/chave.

[Imagem de referência no computador](V33_FOTO_DESKTOP.png) · [Celular](V33_FOTO_CELULAR.png) · [Rede na carga — simulação](V33_ETAPA_REDE.png) · [Gerador na carga — simulação](V33_ETAPA_GERADOR.png) · [Ambos fechados — simulação](V33_ETAPA_ALERTA_AMBOS.png)

Na amostra fornecida, ambos os sinais de carga são 0: o gerador tem tensão, mas o desenho mantém as duas chaves abertas e a saída sem alimentação inferida. Modo MANUAL.

## Gerar

`python tools/build_v33_dse7420.py` gera JSON e ZIP em `dist/`, usando `V26_IMPORTAR.json` como fonte gráfica. Para importar, basta o único JSON V33; vetores e contatos estão incorporados.
