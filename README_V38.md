# LOGSIS / DSE7420 — V38 Cobertura parcial e motivo do cálculo

## Correção

A V37 exigia uma leitura no início ou antes do filtro. Sem essa base, mostrava SEM CÁLCULO mesmo com duas leituras válidas dentro da janela. A V38 preserva a preferência pela base anterior, mas oferece resultado parcial quando há dados suficientes dentro do filtro.

- Com base anterior: última leitura válida até o início versus última até o fim.
- Sem base anterior: primeira versus última leitura válida dentro da janela, com **\*** ao lado do resultado. O asterisco significa **PARCIAL**: o trecho anterior à primeira leitura não está coberto, portanto o valor não é o total comprovado de toda a janela.
- Com duas leituras iguais em horários distintos: zero é válido.

Os resultados continuam vindo dos contadores MDB36 (horímetro /3600) e MDB37 (energia /Divisor_Energia). Não são estimados pela tensão, tempo de relógio ou duração da seleção.

## Mensagens específicas

| Exibição | Motivo |
|---|---|
| SEM LEITURAS | Nenhuma leitura válida disponível até o fim na faixa usada |
| FALTA 2ª LEITURA | Apenas um horário válido; não existe diferença calculável |
| CONTADOR CAIU | Há queda do contador, possível reset ou leitura incorreta |
| DADO CONFLITANTE | Valores diferentes do mesmo contador no mesmo instante |
| DIVISOR INVÁLIDO | Divisor de energia nulo, zero ou negativo |
| Valor com * | Resultado apenas do trecho coberto, sem base anterior |

A consulta retorna também situação, horários usados, contadores brutos, quantidade de amostras e quedas. O painel filtra apenas a coluna textual EXIBICAO para apresentação; os campos completos podem ser examinados na resposta da consulta pelo inspetor do Grafana. Isso permite identificar a causa real na planta, sem substituir um reset por um valor inventado.

Sem acesso aos dados de produção, os testes não determinam qual condição causou o SEM CÁLCULO informado pelo usuário. A versão trata a falta de base e torna os demais bloqueios explícitos.

## Importar

Extraia [V38_IMPORTAR.zip](V38_IMPORTAR.zip) e importe **V38_IMPORTAR.json**, usando **Import (Overwrite)**. Mantidos UID, tabela configurável, fuso de Brasília, curvas conectadas com pontos e cores do gerador por alarme.

## Validação

[SQL/configuração](V38_VALIDACAO.json): 41 casos de período, 27 combinações de alarmes e oito curvas conectadas com pontos. Conferidos os motivos específicos e o asterisco de cobertura parcial.

[Interface](V38_UI_VALIDACAO.json): no Grafana isolado, 3,50 h / 18,00 kWh com base anterior e os mesmos valores com * quando o filtro começa antes da primeira amostra. Nenhum acesso à produção; tabela original do laboratório restaurada.

[Base anterior](V38_PERIODO.png) · [Cobertura parcial](V38_PARCIAL.png)

Gerar: `python tools/build_v38_diagnostico_periodo.py`. Validar no laboratório: `python tools/validate_v38.py`.
