# DSE8610 V2 / apenas um gerador no desenho

Foi removida a ilustração de outros geradores do lado do BUS. Nesse espaço há somente um símbolo neutro de barramento trifásico, com as leituras do BUS abaixo. O desenho mantém apenas o gerador monitorado, seu disjuntor MDB52, o BUS comum e a carga.

Consultas, 52 canais, escalas, variáveis, históricos e demais painéis são idênticos aos da V1. O UID permanece `logsis-dse8610-v1-bus` para atualizar a mesma planta.

Baixe [DSE8610_V2_IMPORTAR.zip](DSE8610_V2_IMPORTAR.zip), extraia o único JSON e importe com **Import (Overwrite)**. Configure `Id_Logsis` com a tabela da sua planta nas variáveis; o arquivo distribuído mantém o identificador de exemplo da V1. As configurações de escala e códigos estão descritas no [README da V1](README_DSE8610_V1.md).

[Desktop](DSE8610_V2_DESKTOP_PREVIEW.png) · [Celular](DSE8610_V2_CELULAR_PREVIEW.png) · [Validação](DSE8610_V2_VALIDACAO.json)

Importação e desenho conferidos no Grafana 11.2.2 com dados simulados em Chromium, em larguras de 1366 e 390 px. A comparação estrutural confirmou que as consultas, variáveis e demais painéis não mudaram.

Para gerar: `python tools/build_dse8610_v2.py`. O JSON e seu ZIP são gravados em `dist/`.
