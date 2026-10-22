# LOGSIS / DSE7420 — V28 Responsivo

Um único dashboard e um único JSON para computador, tablet e smartphone. A mesma planta ajusta a largura do unifilar sem carregar outro dashboard ou duplicar os canais. As ilustrações vetoriais estão incorporadas no JSON; o navegador ajusta seu tamanho mantendo a proporção. Os indicadores nativos do Grafana reorganizam-se conforme a largura disponível.

## Importar

1. Baixe [V28_IMPORTAR.zip](V28_IMPORTAR.zip) e extraia **V28_IMPORTAR.json**, o único arquivo dentro do ZIP.
2. No Grafana, abra **Dashboards → New → Import → Upload dashboard JSON file**.
3. Selecione o JSON e use **Import (Overwrite)** para substituir a V26 existente.

A V28 mantém o UID `logsis-dse7420-v26-unifilar` para atualizar a planta da V26. Não importe também a V27 Mobile: a V28 atende às duas telas. A atualização não exclui dashboards antigos que já existam no servidor.

Para outra planta que já tenha seu próprio UID, conserve esse UID e sua configuração de datasource/`Id_Logsis` ao aplicar a atualização. A variável constante oculta `Id_Logsis` mantém o valor de exemplo da V26: `id_255880306351140`. Não é necessário criar um segundo dashboard para cada tipo de aparelho.

## Comportamento

- Um único unifilar com torre, contatos K1/K2 simétricos, QGBT e prédio da carga. Sem links para outra versão desktop ou mobile.
- Ajuste horizontal automático, inclusive ao mudar o tamanho da janela sem recarregar. A página mantém rolagem vertical para preservar a legibilidade no celular.
- Vermelho indica presença de tensão antes e depois dos contatos. A saída permanece **inferida** pelas tensões das fontes e posições dos contatos, sem alegar medição direta do barramento.
- Dados desconhecidos aparecem como `SEM DADOS` ou `###`; não são convertidos em tensão zero. O diagnóstico de contatos simultaneamente fechados permanece disponível.
- Potência, FP, horímetro e energia reutilizam o resultado da consulta principal pelo datasource nativo Dashboard. Não há consultas distintas por aparelho.
- Os 56 canais aparecem em uma tabela aberta abaixo do unifilar. Somente históricos e alertas ficam na seção recolhível.
- Consultas, conversões e critérios de validade da V26 preservados. Nenhum plugin adicional, JavaScript de produto ou alteração nas configurações do Grafana.

## Validação

Importação pela interface do Grafana 11.2.2, usando PostgreSQL e dados simulados em laboratório isolado. Testes em Chromium nas larguras de 320, 360, 390, 430, 768, 844, 1366 e 1920 pixels, mudando a largura do mesmo dashboard sem recarregar. Verificados carregamento e ajuste dos vetores, ausência de transbordamento horizontal, 56 canais e indicadores. Também testada a interface normal do Grafana no celular emulado e em contexto desktop.

Verificadas as cores com rede alimentando, fontes energizadas e contatos abertos, dados ausentes e contatos simultaneamente fechados. Os 13 painéis históricos/alertas e o SQL elétrico da V26 foram comparados com a versão original. Evidências: [V28_VALIDACAO.json](V28_VALIDACAO.json). Emulação no navegador não equivale a teste em todos os aparelhos físicos.

[Prévia no celular](V28_CELULAR_PREVIEW.png) · [Prévia no desktop](V28_DESKTOP_PREVIEW.png) · [Instrumentação a 320 px](V28_LEITURAS_PREVIEW.png)

## Gerar novamente

Execute `python tools/build_v28_responsivo.py` na raiz do repositório. O script usa a V26 como fonte de geração e grava em `dist/` somente o JSON universal e seu ZIP. Essa dependência existe apenas para gerar a exportação: para importar e usar o dashboard basta o único JSON da V28.
