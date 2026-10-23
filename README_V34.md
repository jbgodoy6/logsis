# LOGSIS / DSE7420 — V34 Modos de operação

Correção do MDB40 conforme o mapa confirmado pelo usuário:

| Código | Modo | Texto no indicador |
|---|---|---|
| 0 | Stop | STOP |
| 1 | Automático | AUTO |
| 2 | Manual | MANUAL |
| 3 | Teste com carga | TESTE C/ CARGA |
| 6 | Teste sem carga | TESTE S/ CARGA |
| 7 | Off | OFF |

Aplicado à consulta do unifilar e aos mapeamentos da instrumentação. Códigos não reconhecidos aparecem como INVÁLIDO no indicador; ausência de leitura aparece como SEM DADOS. A indicação do modo não determina a posição das chaves, que continua seguindo MDB52/MDB53.

Extraia [V34_IMPORTAR.zip](V34_IMPORTAR.zip) e importe **V34_IMPORTAR.json** com **Import (Overwrite)**. Mantidos o UID do DSE7420 e a variável `Id_Logsis` configurada como `id_269086509881540`.

Esta versão preserva o layout, as escalas, os históricos e a lógica elétrica da [V33](README_V33.md). Não altera o dashboard DSE8610.

Validação: os seis códigos, um código desconhecido e ausência de dados foram executados em PostgreSQL isolado. Conferidos os 11 mapeamentos de MDB40 nos painéis e a integridade do JSON/ZIP. [Resultado](V34_MODOS_VALIDACAO.json). Nenhum acesso ao controlador ou banco de produção.

Para gerar: `python tools/build_v34_modos_dse7420.py`. Saídas em `dist/`.
