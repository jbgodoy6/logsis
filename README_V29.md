# LOGSIS / DSE7420 — V29 Supervisão

Um único dashboard responsivo com instrumentação agrupada por subsistema. A V29 substitui a lista corrida da V28 por cartões alinhados, fases na ordem L1/L2/L3 e uma hierarquia visual próxima à organização da V26.

## Instalar

Baixe [V29_IMPORTAR.zip](V29_IMPORTAR.zip), extraia **V29_IMPORTAR.json** e importe em **Dashboards → New → Import → Upload dashboard JSON file**. Use **Import (Overwrite)** para atualizar a V26/V28 existente: o UID permanece `logsis-dse7420-v26-unifilar`. O ZIP contém somente um JSON, que já inclui os desenhos vetoriais.

Para atualizar outra planta com UID personalizado, mantenha seu UID, datasource e valor de `Id_Logsis`. O arquivo de exemplo preserva o datasource `zKW_ld27k` e a constante oculta `Id_Logsis=id_255880306351140` da V26.

## Organização visual

No computador, o unifilar ocupa a metade esquerda da primeira faixa. As leituras da concessionária e do gerador ficam à direita, com as três fases em colunas correspondentes. A faixa seguinte destaca potência ativa, fator de potência, horímetro e energia. A instrumentação continua em grupos abertos de potência/FP, motor/combustível, manutenção, controle/alarmes/QTA e entradas digitais.

No celular, esses mesmos painéis se empilham, mantendo os cartões, a identificação das fases e a ordem das seções. As colunas internas usam porcentagens. Não há navegação para outra planta, imagens externas nem dashboard duplicado por aparelho. Há rolagem vertical.

Os 56 canais pertencem, cada um, a um dos sete grupos de leitura. Os quatro indicadores de resumo repetem grandezas principais para supervisão, como na V26. Todos reutilizam a consulta do unifilar pelo datasource nativo Dashboard: não há uma consulta SQL por cartão. Históricos e alertas são a única seção recolhível.

Nos cartões de três colunas, a unidade aparece no rótulo, por exemplo `L1–N · V` ou `Ativa · kW`, para o valor não quebrar de linha no celular. Nos cartões mais largos, a unidade acompanha o número. A apresentação não muda os valores nem as conversões. As cores das seções identificam os subsistemas; não representam limites de alarme.

## Lógica preservada

O SQL elétrico, os critérios de validade, as casas decimais e as conversões da V26 permanecem. Vermelho indica tensão nos trechos antes/depois da transferência. A saída continua **inferida** pelas tensões das fontes e posições dos contatos. Ausência de dados continua `SEM DADOS`/`###`. O diagnóstico de contatos simultaneamente fechados permanece.

Alarmes e entradas exibem códigos do controlador. Contatos aparecem como `ABERTO`/`FECHADO` no grupo de controle; seus símbolos permanecem no unifilar. Os 13 painéis de históricos/alertas preservam as consultas da V26.

## Evidências

- [Desktop / visão geral](V29_DESKTOP_PREVIEW.png)
- [Desktop / instrumentação agrupada](V29_INSTRUMENTACAO_PREVIEW.png)
- [Celular / rede e gerador](V29_CELULAR_PREVIEW.png)
- [Celular / cartões de potência e motor](V29_CELULAR_CARTOES.png)
- [Relatório de validação](V29_VALIDACAO.json)

Validação no Grafana 11.2.2 com Chromium e PostgreSQL em laboratório isolado, usando dados simulados. Testes de importação pela interface, 56 canais acessíveis, largura de 320 a 1920 pixels, ajuste ao redimensionar sem recarregar, texto dos cartões, ausência de transbordamento horizontal e estados elétricos. As capturas de celular usam dimensões de viewport; são evidências de navegador, não de aparelhos físicos.

## Gerar

Execute `python tools/build_v29_supervisao.py`. O gerador usa a V26 como fonte e grava um único JSON universal e seu ZIP em `dist/`. Para usar a versão pronta, basta importar o JSON da V29; nenhum arquivo de versão anterior é necessário no Grafana.
