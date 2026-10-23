# LOGSIS / DSE7420 — V36 Horário de Brasília

O indicador de último registro agora converte explicitamente o instante armazenado para `America/Sao_Paulo` antes de formatar a data. O rótulo identifica **ÚLTIMO REGISTRO / BRASÍLIA**. O fuso do dashboard também foi fixado em `America/Sao_Paulo`, para alinhar o seletor de período e os históricos à hora de Brasília, independentemente do navegador.

Exemplo: 23/10/2026 14:58 UTC aparece como **23/10 11:58**. A conversão usa o fuso nomeado, com suas regras históricas, em vez de subtrair três horas manualmente.

Colunas PostgreSQL `timestamp with time zone` são convertidas a partir do instante armazenado, sem depender do fuso da sessão. Para colunas `timestamp without time zone`, os valores são interpretados como UTC, conforme a diferença de três horas relatada nesta instalação. Se outra planta armazenar horário local sem fuso, sua convenção deve ser ajustada na consulta para evitar conversão dupla. Nenhum dado armazenado é alterado.

Os filtros SQL continuam selecionando os instantes originais; a conversão é aplicada apenas à exibição textual. Os novos indicadores de horas/kWh do período, modos, chave e demais painéis permanecem como na V35.

## Importar

Extraia [V36_IMPORTAR.zip](V36_IMPORTAR.zip) e importe **V36_IMPORTAR.json** com **Import (Overwrite)**. Mantido o UID do DSE7420 e a tabela configurável `Id_Logsis`, inicialmente `id_269086509881540`.

## Validação

[12 casos da consulta completa](V36_FUSO_VALIDACAO.json), em PostgreSQL isolado: dois tipos de coluna, três fusos de sessão e conversões com/sem mudança de dia. Conferida a preservação dos demais painéis e consultas de período. Nenhum acesso à produção.

[Indicador no Grafana](V36_BRASILIA.png).

Gerar: `python tools/build_v36_fuso_dse7420.py`. Testar no laboratório Docker: `python tools/validate_v36_fuso.py`.
