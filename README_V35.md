# LOGSIS / DSE7420 — V35 Totais do período

Dois novos indicadores compactos acompanham o filtro de tempo do Grafana:

- **HORAS / PERÍODO:** variação do MDB36, dividida por 3600 para exibir horas de funcionamento.
- **ENERGIA / PERÍODO:** variação do MDB37, dividida pela variável `Divisor_Energia` para exibir kWh.

Os totais acumulados continuam disponíveis. Os seis indicadores ficam na mesma faixa compacta no computador e se reorganizam no celular. Mantidos os modos completos da V34, o unifilar e os históricos.

## Como o cálculo funciona

As consultas usam exclusivamente as leituras válidas dentro do período selecionado. Por exemplo, horímetro de 100 h na primeira amostra e 103,5 h na última resulta em **3,50 h**. Energia de 200 kWh para 218 kWh resulta em **18,00 kWh**. Não se calcula o tempo entre datas: o horímetro contabiliza as horas em que o gerador funcionou.

O cálculo confere a sequência cronológica dos contadores. Se qualquer leitura válida diminuir, há possível reset, troca de equipamento ou erro: o indicador mostra **SEM CÁLCULO**, em vez de adivinhar o consumo. O mesmo ocorre com menos de duas amostras válidas ou leituras conflitantes no mesmo horário. Valores nulos e sentinelas são descartados; contador estacionário com duas amostras resulta em zero.

O resultado cobre o intervalo entre a primeira e a última amostra válida dentro do filtro. Não há interpolação nem busca fora da janela: coleta esparsa pode deixar trechos nas bordas sem cobertura. Um reset inteiramente oculto entre amostras não pode ser detectado apenas pelos contadores. Consulte os históricos para avaliar lacunas.

## Escalas

A conversão de MDB36 permanece /3600. `Divisor_Energia` permanece configurado como **10**, conforme a V34; se o MDB37 já estiver em kWh, altere a variável para **1**. O divisor deve ser positivo. A mesma escala é usada no acumulado e no período.

## Importar

Extraia [V35_IMPORTAR.zip](V35_IMPORTAR.zip) e importe **V35_IMPORTAR.json** com **Import (Overwrite)**. O UID permanece o do DSE7420 e `Id_Logsis` continua configurável, inicialmente `id_269086509881540`.

## Validação

[29 casos SQL e regressão dos painéis](V35_PERIODO_VALIDACAO.json): funcionamento normal, amostragem irregular, zero, contador parado, reset, reset que recupera o valor, amostra única, janela vazia, sentinelas, nulos, dados fora do filtro, duplicatas e divisores. PostgreSQL em laboratório isolado, sem acesso à produção. O teste verifica que os painéis anteriores foram preservados, exceto pelas posições/larguras dos quatro indicadores acumulados.

[Interface no Grafana](V35_UI_VALIDACAO.json) · [Computador](V35_DESKTOP.png) · [Celular](V35_CELULAR.png)

Gerar: `python tools/build_v35_periodo_dse7420.py`. Validar SQL no laboratório Docker: `python tools/validate_v35_periodo.py`.
