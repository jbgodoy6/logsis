# LOGSIS / DSE8610 — V3 Gerador e BUS

Atualiza o DSE8610 V2 com as melhorias aprovadas no DSE7420 V41, preservando o mapa auditado de 52 canais do BIN e a topologia própria do DSE8610. **Um único JSON responsivo**, com vetores incorporados, para computador e celular.

## Desenho preservado

**Gerador monitorado → disjuntor de acoplamento MDB52 → BUS comum → prédio/carga.** Não há concessionária, chave de transferência K1/K2 ou segundo gerador desenhado. O BUS tem somente um símbolo trifásico e suas próprias leituras.

- **MDB52:** 0 ABERTO, 1 FECHADO, conforme confirmação do usuário. Lâmina inclinada/vertical e texto explícito sob o contato. Valor diferente de 0/1: INVÁLIDO; ausente: SEM DADOS. Conflito no mesmo horário: posição desconhecida.
- A posição usa o último registro informado do campo dentro do período. Uma linha posterior com posição nula não apaga o estado. Não busca posições fora da janela. `GCB_INSTANTE` informa o horário da posição na resposta da consulta.
- Antes do disjuntor, a linha segue a tensão do gerador. Depois dele, a linha acompanha a tensão **medida do BUS**, inclusive com disjuntor aberto.
- O BUS e a saída ficam vermelhos pela medição MDB30–35, independentemente deste gerador. Outros grupos podem manter o BUS energizado. Isso não comprova sincronismo, corrente, direção de potência ou número de geradores em paralelo.
- O desenho mostra o último estado disponível do período; o histórico permite acompanhar as transições. Não comanda a manobra física.

## Melhorias aplicadas

- **Modo MDB40:** STOP, AUTO, MANUAL, teste com carga, teste sem carga e OFF. Valores iniciais 0/1/2/3/6/7; todos configuráveis por variáveis.
- **Cores do próprio gerador:** Warning/MDB41 amarelo, Trip/MDB42 laranja, Shutdown/MDB43 vermelho. Prioridade Shutdown → Trip → Warning. Sem alarme, aparência original. Sem informação suficiente, indicação ALARMES / SEM DADOS.
- **Internet:** GSM em dBm, com cinco barras, e Wi-Fi por `WiFi_rssi`/`wifi_rssi`. A leitura usa o último valor informado de cada campo dentro do filtro, preservando-a em pacotes parciais. Campos de rádio podem não existir na tabela sem derrubar o restante da consulta. Intensidade de rádio não é teste de acesso à internet.
- **Brasília:** dashboard e último registro em `America/Sao_Paulo`. Para `timestamp with time zone`, converte o instante armazenado. Se o banco usar `timestamp without time zone`, assume armazenamento em UTC, como no padrão DSE7420; ajuste a convenção se a tabela dessa planta armazenar hora local sem fuso.
- **Indisponibilidade/estouro:** traço **—** nos indicadores numéricos, preservando mensagens específicas dos estados e cálculos. Sem corte indevido de 32760 nos campos de 32 bits.
- **Atualização:** cinco segundos, limitada à chegada da telemetria.
- **Históricos:** curvas suaves conectadas, com os pontos reais visíveis, nos históricos analógicos. A conexão através de lacunas é apenas visual e não cria medições. Modo, disjuntor e alarmes usam degraus e pontos para representar estados. Acrescentados históricos de horímetro e energia: 11 painéis recolhidos na única seção de históricos/alertas.

Os 52 canais permanecem acessíveis, sem quadro redundante do BUS: suas sete grandezas estão ao lado do símbolo do barramento. Os seis resumos compactos mostram potência, FP, horímetro acumulado, energia acumulada, horas e energia do período.

## Horas e kWh do período

Mesma regra da V39 do DSE7420, aplicada a **MDB36** e **MDB37**:

1. Prefere a última base válida no início ou antes do filtro, se não for maior que a primeira leitura dentro da janela.
2. Sem base compatível, usa a primeira leitura interna e sinaliza **\*** (cobertura parcial/base descartada).
3. Calcula **último contador − contador inicial**, em ordem cronológica: /`Divisor_Horas` para horas e /`Divisor_Energia` para kWh.
4. Queda intermediária não apaga uma diferença final positiva, mas sinaliza **\*** como **variação líquida**, não total comprovado após reset. Final menor que inicial: **RESET / REVISAR**.
5. Sem duas leituras distintas, com conflito no mesmo horário ou divisor inválido, mostra o motivo específico. Zero é válido quando o contador não variou.

Exemplo: base 100 h e 200 kWh; final 103,5 h e 218 kWh → **3,50 h e 18,00 kWh**. Lacunas de coleta limitam a precisão nas bordas e podem esconder resets. O inspetor da consulta inclui contadores, horários, critério de base, quedas e situação. Funcionamento do motor, sozinho, não comprova geração de kWh: usa-se o contador de energia.

## Importar e configurar

1. Extraia [DSE8610_V3_IMPORTAR.zip](DSE8610_V3_IMPORTAR.zip).
2. Importe **DSE8610_V3_IMPORTAR.json** com **Import (Overwrite)** para atualizar a planta DSE8610 existente.
3. Em **Settings → Variables → Id_Logsis**, informe a tabela real do DSE8610. O valor distribuído é **`id_dse8610`**, um identificador de exemplo.
4. Confira o datasource PostgreSQL; preservado o UID `zKW_ld27k` usado nas versões anteriores. Ajuste se seu datasource tiver outro UID.

UID preservado: **`logsis-dse8610-v1-bus`**. Não substitui o DSE7420. Para outra planta, configure a própria tabela e um UID distinto; não há dashboard separado para celular.

## Mapa e constantes

| Canais | Leitura |
|---|---|
| MDB01–07 | Óleo, temperaturas, combustível, alternador DC, bateria e RPM |
| MDB08–28 | Frequência, tensões, correntes, potências e FP do gerador |
| MDB29–35 | Frequência e tensões do BUS |
| MDB36–39 | Horímetro, energia, partidas e manutenção |
| MDB40 | Modo |
| MDB41–43 | Warning, Trip elétrico, Shutdown |
| MDB44–51 | Entradas A–H |
| MDB52 | Disjuntor que acopla o gerador ao BUS |

Preservadas as escalas configuráveis da V2: `Divisor_Tensao=10`, `Divisor_Corrente=10`, `Divisor_Potencia=1000`, `Divisor_FP=100`, `Divisor_Horas=3600`, `Divisor_Energia=10`. Pressão /100; bateria, alternador DC e frequências /10. Os divisores de horas/energia são compartilhados entre acumulados, históricos e totais do período.

As constantes `Codigo_STOP=0`, `Codigo_AUTO=1`, `Codigo_MANUAL=2`, `Codigo_TESTE_CARGA=3`, `Codigo_TESTE_SEM_CARGA=6` e `Codigo_OFF=7` adotam o padrão solicitado do DSE7420. O BIN não é uma confirmação independente de todos esses códigos/escalas; as constantes permitem adequação à variante/coletor. Os códigos históricos são normalizados pelas mesmas constantes antes de exibir os nomes de modo.

Os três alarmes pressupõem os bits já extraídos pelo coletor, conforme BIT10/11/12 do BIN. O dashboard aceita 0/1, sem aplicar extração duplicada. Uma palavra bruta, como 1024 em MDB41, é indisponível, não é falsamente tratada como ausência de alarme.

## Validação

[SQL/configuração](DSE8610_V3_SQL_VALIDACAO.json): 27 combinações de gerador/BUS/disjuntor; nove casos de modo; 27 combinações de alarme; nove casos de rádio/telemetria parcial; 12 casos de fuso; 56 casos de período/divisores; execução das 11 consultas históricas. Confirmados 52 canais, um único gerador, ausência de MDB53 e UID próprio.

[Grafana](DSE8610_V3_UI_VALIDACAO.json): importação pela interface, larguras de 320 a 1920 px, todos os canais, textos sem cortes, valores 3,50 h / 18,00 kWh e atualização dos contatos/linhas sem recarregar a página. Inclui BUS energizado com gerador parado e disjuntor aberto, alarmes, seis modos e seleção do filtro antes/depois do fechamento.

Laboratório isolado em Grafana 11.2.2, Chromium e PostgreSQL com dados simulados. Nenhum acesso ao controlador ou banco de produção; a tabela original do laboratório é restaurada ao fim do teste.

[Computador](DSE8610_V3_DESKTOP.png) · [Celular](DSE8610_V3_CELULAR.png) · [Período](DSE8610_V3_PERIODO.png) · [BUS alimentado por outros grupos](DSE8610_V3_OUTROS_GRUPOS.png) · [Warning](DSE8610_V3_WARNING.png) · [Trip](DSE8610_V3_TRIP.png) · [Shutdown](DSE8610_V3_SHUTDOWN.png)

## Gerar e testar

`python tools/build_dse8610_v3.py` gera JSON/ZIP em `dist/`. Reaproveita definições vetoriais e de cálculo dos geradores anteriores sem executá-los nem modificar o DSE7420. O artefato importável é autossuficiente.

No laboratório Docker: `python tools/validate_dse8610_v3.py`. Para interface: `NODE_PATH=/caminho/node_modules node tools/validate_dse8610_v3_ui.cjs`, com Playwright/Chromium e os serviços isolados já iniciados.
