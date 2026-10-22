# LOGSIS / DSE7420 — V30 Supervisão

Ajustes sobre a V29, no mesmo dashboard responsivo:

- Potência ativa, FP, horímetro e energia em quatro indicadores compactos: altura reduzida de quatro para três unidades da grade, com fonte do valor fixada em 26 px para não crescer exageradamente no computador.
- Abaixo da torre: tensões L1–N, L2–N, L3–N, L1–L2, L2–L3 e L3–L1, além da frequência da rede.
- Abaixo do gerador: tensões L1–N, L2–N e L3–N, frequência, rotação, temperatura da água e pressão do óleo.
- As duas listas ficam embaixo de seus respectivos desenhos também no celular. Os grupos completos de instrumentação da V29 permanecem disponíveis.

## Importar

Baixe [V30_IMPORTAR.zip](V30_IMPORTAR.zip), extraia **V30_IMPORTAR.json** e use **Dashboards → New → Import → Upload dashboard JSON file**. Escolha **Import (Overwrite)** para atualizar a V26/V28/V29 existente. O UID continua `logsis-dse7420-v26-unifilar`.

O ZIP contém apenas um JSON, com os vetores incorporados. Não existe uma segunda planta para celular ou desktop. O datasource e a variável oculta `Id_Logsis` continuam os da V26. Para outra planta com UID personalizado, preserve seu UID, datasource e `Id_Logsis` ao aplicar a atualização.

As novas leituras locais usam os campos já retornados pela consulta principal. Os grupos completos e os quatro resumos reutilizam essa consulta pelo datasource nativo Dashboard. Não há consultas extras por leitura, imagens externas ou plugins novos.

## Dados e cores

Mesmos valores, conversões, casas decimais e critérios de validade da V29/V26. O caminho vermelho indica presença de tensão. A saída segue inferida por tensões das fontes e contatos K1/K2; não representa uma medição direta do barramento. Dados desconhecidos continuam `SEM DADOS`/`###`. Os 13 painéis de históricos/alertas conservam suas consultas.

As leituras locais e os resumos repetem grandezas da instrumentação completa, como referências próximas aos equipamentos. Os 56 canais continuam organizados em sete grupos; não são duplicações de dashboards.

## Evidências

[Desktop](V30_DESKTOP_PREVIEW.png) · [Celular](V30_CELULAR_PREVIEW.png) · [Validação](V30_VALIDACAO.json)

Importação pela interface do Grafana 11.2.2, Chromium e PostgreSQL de laboratório com dados simulados. Verificados os 56 canais, textos sem corte e ausência de transbordamento horizontal em larguras de 320, 390, 768, 1366 e 1920 px. Também verificados os estados de alimentação por rede/gerador, contatos abertos, dados ausentes e contatos simultaneamente fechados. As capturas mostram dados simulados; testes de viewport não equivalem a testes em todos os aparelhos físicos.

## Gerar

Execute `python tools/build_v30_leituras.py`. O script lê a V26 como fonte de geração e grava o JSON universal e seu ZIP em `dist/`. Para importar e usar a exportação pronta, basta o JSON da V30.
