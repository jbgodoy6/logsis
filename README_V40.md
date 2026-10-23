# LOGSIS / DSE7420 — V40 Posições K1/K2 no período

## Problema encontrado

Na V39, MDB52 e MDB53 vinham exclusivamente da última linha com algum dado elétrico. Uma linha de tensões com posições nulas apagava a indicação das chaves, mesmo quando as posições estavam registradas anteriormente dentro do filtro.

## Correção

O unifilar reconstrói o último valor informado de cada campo elétrico dentro da janela selecionada. Assim, pacotes parciais não apagam posições nem tensões anteriormente informadas no período.

- **K1 / REDE = MDB52:** 0 ABERTO, 1 FECHADO.
- **K2 / GERADOR = MDB53:** 0 ABERTO, 1 FECHADO.
- Zero é um estado válido, nunca confundido com ausência de dados.
- O contato aberto aparece inclinado; o fechado, vertical. Acrescentados textos **ABERTO/FECHADO** sob as duas lâminas.
- Se nenhum valor foi informado para uma chave dentro do filtro: **SEM DADOS** e posição desconhecida. Não busca posições fora do filtro, não deduz fechamento pela tensão e não presume posição em função do modo AUTO/MANUAL.
- Um valor diferente de 0/1 no último registro informado aparece como **INVÁLIDO**, sem reaproveitar um fechamento antigo.
- Valores diferentes da mesma chave no mesmo instante resultam em posição desconhecida, em vez de escolha arbitrária.

Os campos `K1_INSTANTE` e `K2_INSTANTE`, na resposta da consulta, identificam os horários de cada posição. Os sinais podem ter horários diferentes: representam o último estado informado de cada campo até o fim da janela, não necessariamente um único pacote. Registros nulos posteriores são tratados como campos não informados; a indicação não comprova atualização contínua de um sensor.

O desenho mostra o estado final disponível do período. Para acompanhar todas as manobras, use o histórico **CHAVE / REDE E GERADOR NA CARGA**, preservado sem alterações. O filtro não reproduz as manobras como uma animação. Se ambos forem 1, mantém as duas chaves fechadas com alerta, sem presumir intertravamento.

Mantida a regra de tensão: antes de cada contato segue a fonte correspondente; após os contatos representa o barramento comum inferido. Não há comando enviado ao equipamento.

## Importar

Extraia [V40_IMPORTAR.zip](V40_IMPORTAR.zip) e importe **V40_IMPORTAR.json** usando **Import (Overwrite)**. Mantidos UID, tabela configurável, Brasília, cálculos de horas/kWh da V39, curvas com pontos e cores de alarme.

## Validação

[93 casos SQL](V40_CHAVES_VALIDACAO.json): 81 combinações de fonte/posição e 12 casos de filtro/telemetria parcial. Incluem última linha de tensão sem posições, posições recebidas em horários diferentes, zero, valor inválido, conflito no mesmo instante, dados fora da seleção, janela vazia e seleção antes/depois da transferência. Os dois painéis de período e toda a seção de históricos foram comparados à V39 e permanecem idênticos.

[Grafana](V40_UI_VALIDACAO.json): seleção de três finais de período, conferindo rede fechada/gerador aberto → ambos abertos → rede aberta/gerador fechado, em 390 e 1366 px. Conferidos vetores e textos de posição sem corte. Laboratório isolado com dados simulados; tabela original restaurada. Sem acesso à produção nem teste físico de manobra.

[Computador](V40_DESKTOP.png) · [Celular](V40_CELULAR.png)

Gerar: `python tools/build_v40_chaves_periodo.py`. Validar no laboratório Docker: `python tools/validate_v40_chaves.py`.
