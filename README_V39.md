# LOGSIS / DSE7420 — V39 Diferença dos contadores

## Problema corrigido

A V38 bloqueava a diferença inteira ao encontrar qualquer queda do contador. Isso incluía uma base anterior maior que a primeira leitura válida do período, mesmo quando a curva dentro da janela crescia normalmente. A imagem recebida mostra aproximadamente 5,89 → 6,58 h (variação de 0,69 h), enquanto o indicador exibia CONTADOR CAIU.

A imagem comprova a diferença visível, mas não revela o valor bruto da base anterior nem todas as leituras intermediárias. A correção trata a incompatibilidade de base e a restrição excessiva sem presumir qual leitura específica causou o bloqueio na produção.

## Regra única para horas e kWh

1. Busca a primeira leitura válida dentro da seleção e a última até o fim.
2. Prefere a última base válida no início ou antes do início, se ela não for maior que a primeira leitura interna.
3. Se a base anterior faltar ou for maior, usa a primeira leitura interna e marca o resultado com **\*** (cobertura parcial/base descartada).
4. Calcula explicitamente **último contador − contador inicial**, em ordem cronológica; não usa MAX−MIN e não soma aumentos após quedas.
5. Uma queda intermediária deixa de apagar uma diferença final positiva. O valor aparece com **\*** e situação **VARIAÇÃO LÍQUIDA / HOUVE QUEDA**. É a diferença líquida entre extremos, não o total comprovado de funcionamento ou geração após um reset.
6. Se o contador final for menor que o inicial, aparece **RESET / REVISAR**. Sem duas leituras distintas, com conflitos no mesmo horário ou divisor inválido, o painel continua indicando a impossibilidade específica.

A mesma função SQL implementa os dois indicadores: MDB36 /3600 para horas e MDB37 /`Divisor_Energia` para kWh. Escalas preservadas; `Divisor_Energia` inicialmente 10. Se o contador de energia não variar, o resultado continua zero, mesmo com funcionamento do motor. Não se fabrica kWh a partir de tensão ou horímetro.

Exemplo aproximado da imagem: 6,58 − 5,89 = **0,69 h**, cerca de 41 minutos. O cálculo usa valores brutos, então os extremos arredondados do gráfico podem produzir pequenas diferenças em relação ao valor final exibido.

A resposta da consulta inclui contadores inicial/final, horários, base anterior bruta, critério de base, quedas e situação, permitindo conferir o motivo do asterisco pelo inspetor do Grafana. Coleta esparsa limita a precisão das bordas; resets ocultos entre amostras não podem ser detectados apenas por esses dados.

## Importar

Extraia [V39_IMPORTAR.zip](V39_IMPORTAR.zip) e importe **V39_IMPORTAR.json** com **Import (Overwrite)**. Preservados UID, tabela configurável, Brasília, curvas conectadas com pontos e cores do gerador por alarme.

## Validação

[53 casos de período e regressões](V39_VALIDACAO.json): curva 5,89 → 6,19 → 6,58 h com base externa incompatível; diferença positiva com queda pequena; reinício com recuperação; final abaixo da base; base válida; ausente; nulos; sentinelas; conflitos; energia e divisores. Mantidos testes de 27 combinações de alarmes e oito históricos conectados com pontos.

[Grafana real](V39_UI_VALIDACAO.json): laboratório isolado com valores simulados e base incompatível; resultado **0,69 h \* / 18,00 kWh \***, com conferência das três cores de alarme. Sem acesso à produção. A tabela original do laboratório é restaurada ao fim.

[Resultado do período](V39_PERIODO.png).

Gerar: `python tools/build_v39_diferenca_contadores.py`. Validar no laboratório Docker: `python tools/validate_v39.py`.
