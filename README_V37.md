# LOGSIS / DSE7420 — V37 Período, curvas e alarmes

## Horas e energia do período: base anterior ao filtro

Corrigida a limitação da V35/V36 que exigia duas leituras dentro do filtro e ignorava a base anterior. Cada indicador agora busca, independentemente:

1. **Base:** última leitura válida do respectivo contador no início ou antes do início do filtro.
2. **Final:** última leitura válida até o fim do filtro, posterior ao início.
3. **Resultado:** final menos base; MDB36 /3600 para horas, MDB37 /`Divisor_Energia` para kWh.

Uma única leitura dentro do filtro já permite o cálculo se houver uma base válida anterior. A amostra exatamente no início tem preferência sobre amostras mais antigas. Amostras depois do fim nunca entram no resultado. Exemplo: base 100 h e 200 kWh anterior ao filtro; final 103,5 h e 218 kWh dentro do filtro → **3,50 h e 18,00 kWh**.

As leituras intermediárias são conferidas: queda do contador indica possível reset e mantém **SEM CÁLCULO**, sem adivinhar o valor perdido. Base ausente, nenhuma leitura posterior ao início, dados conflitantes no mesmo horário ou divisor inválido também impedem o cálculo. Nulos, negativos e sentinelas não servem como contadores válidos.

O resultado corresponde à diferença entre as amostras disponíveis nas bordas. Se a base for muito antiga ou a leitura final estiver distante do fim, a precisão para os limites exatos do filtro fica limitada pela coleta. Não há interpolação de consumo ou horas; reinícios ocultos entre amostras podem não ser detectados.

Energia zero significa que o MDB37 não variou entre base e final. Funcionamento do motor não comprova geração de kWh: pode estar sem carga. A correção não substitui o contador por uma estimativa baseada no horímetro. Mantido `Divisor_Energia=10`; ajuste para 1 se o dado bruto já estiver em kWh.

## Curvas conectadas com pontos

Conforme solicitado, os oito históricos de medições mantêm os pontos reais e o traçado suave em curva, com linha de 2 px. As leituras válidas passam a ser conectadas através dos intervalos com valores ausentes (`spanNulls=true`), evitando os segmentos soltos mostrados na imagem.

A conexão sobre uma lacuna é apenas visual: não cria amostras nem altera os dados. Não substitui valores ausentes por zero e não remove quedas reais. Os históricos de alarmes/chave preservam a representação de estados. Consultas históricas, escalas e valores permanecem intactos.

## Gerador com cor de alarme

O próprio desenho vetorial do gerador muda de cor, preservando sua geometria e sombreamento:

| Alarme ativo | Campo | Cor | Prioridade |
|---|---|---|---|
| Shutdown | MDB43 = 1 | Vermelho | 1 |
| Trip elétrico | MDB42 = 1 | Laranja | 2 |
| Warning | MDB41 = 1 | Amarelo | 3 |
| Nenhum | MDB41/42/43 = 0 | Original | — |

O título identifica o alarme exibido. Se nenhum ativo for conhecido e algum campo estiver sem leitura, o desenho mantém a aparência original com **ALARMES / SEM DADOS**, sem afirmar ausência de alarme. Os sinais seguem a última leitura válida de cada campo dentro do período selecionado; representam supervisão histórica quando o filtro é histórico.

## Importar

Extraia [V37_IMPORTAR.zip](V37_IMPORTAR.zip), importe **V37_IMPORTAR.json** e selecione **Import (Overwrite)**. Mantidos o UID do DSE7420, a tabela configurável `Id_Logsis` inicialmente `id_269086509881540` e o horário de Brasília `America/Sao_Paulo` da V36. O DSE8610 não é alterado.

## Validação

[SQL/configuração](V37_VALIDACAO.json): 41 casos de período, incluindo base anterior com uma única leitura interna, limites do filtro, base ausente, reset, sentinelas, duplicatas e divisores; 27 combinações de alarmes; oito curvas conectadas com pontos. As consultas históricas foram comparadas à V36.

[Interface real no Grafana](V37_UI_VALIDACAO.json): base anterior ao filtro e resultado 3,50 h / 18,00 kWh; conferidos título e mudança dos vetores nos três níveis de alarme. PostgreSQL/Grafana isolados com dados simulados; sem acesso à produção. A tabela original do laboratório é restaurada ao fim do teste.

[Período](V37_PERIODO.png) · [Warning](V37_WARNING.png) · [Trip](V37_TRIP.png) · [Shutdown](V37_SHUTDOWN.png)

Gerar: `python tools/build_v37_periodo_curvas.py`. Validar no laboratório Docker: `python tools/validate_v37.py`.
