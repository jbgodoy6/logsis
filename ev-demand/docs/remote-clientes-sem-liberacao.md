# Clientes remotos sem liberação manual — plataforma 0.13.1

A pedido do proprietário, a consulta retorna todos os registros válidos da aba
DMax_Remoto sem a permissão adicional remote_directory.<controller_id>.
A interface e a API do D-Max continuam exclusivas do root. O Apps Script continua
exigindo o identificador e a chave normais de um equipamento autorizado, já usados
na sincronização. Não se exige outra autorização para catálogo ou para cada cliente.

Ao abrir Buscar clientes remotos, clicar em Atualizar ou pesquisar, o D-Max busca
novamente a plataforma. Não há consulta periódica do catálogo em segundo plano.
O nome, URL e última comunicação vêm da planilha, com vínculo pelo identificador
permanente. Abrir D-Max abre o endereço recebido para login no cliente.

## Aplicar no D-Max 0.13.0 já instalado

Não reinstale nem reinicie o Raspberry. Atualize somente a plataforma:

1. Abra o código atualizado:
   https://raw.githubusercontent.com/jbgodoy6/logsis/dmax-sheets-v0.13.1/ev-demand/google-apps-script/Code.gs
2. Na planilha, Extensões → Apps Script: substitua Code.gs e salve. Mantenha o
   mesmo projeto, propriedades, chaves e identificadores existentes.
3. Implantar → Gerenciar implantações → lápis → Nova versão → Implantar.
   Preserve a URL /exec configurada. Apenas salvar não atualiza a implantação web.
4. Reabra Buscar clientes remotos no D-Max, usando root. Todos os clientes
   registrados em DMax_Remoto serão listados sem outra liberação.

Os menus de permitir/revogar busca foram retirados. Se permissões antigas já
existirem nas propriedades, são ignoradas; não apague as chaves device.*.
Esta é uma atualização independente do Apps Script, identificada pela tag
`dmax-sheets-v0.13.1`. O aplicativo e o ZIP Raspberry 0.13.0 permanecem inalterados.
Para instalações a partir desse ZIP, use o Code.gs deste guia em vez da cópia antiga
incluída no pacote. A receita remota, curva de 5 segundos e Grafana não mudam.

## Validação

O script exato é testado em Node com doubles do Google: chave incorreta recusada,
lista completa sem propriedade de permissão, propriedades antigas ignoradas,
URL nova recebida na consulta seguinte, nomes/URLs validados e ausência de
credenciais na resposta. Os testes da API/UI do D-Max verificam acesso exclusivo
do root e consulta somente quando a aba é aberta/atualizada. A implantação na
conta Google é feita pelo proprietário; não foi acessada por este executor.
