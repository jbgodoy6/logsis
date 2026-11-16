# Um Apps Script para Windows e Raspberry

Esta revisão mantém os protocolos existentes: `desktop_login`, `desktop_state`, `desktop_logout`, `desktop_clients`, `desktop_members`, `desktop_save_user` para a central Windows 1.2.0/1.2.1, e `snapshot`, `update`, `manage_user`, `remote_directory` com identificação/chave do Raspberry. Nenhuma troca de chaves ou recriação de usuários é necessária por causa desta revisão.

## Simplificação

Uma única função compara os cabeçalhos de Usuarios, Tecnicos, Contas, Assinaturas e do diretório remoto. Diferenças de maiúsculas/minúsculas, espaços nas extremidades e BOM não provocam mais recusa. A ordem e os nomes das colunas continuam necessários para ler os campos corretamente. A leitura não reescreve as células.

O menu D-Max oferece **Verificar cadastro (sem alterar dados)**. O diagnóstico aparece na tela, além do log. Se o cadastro legado for válido mas o unificado não estiver habilitado, a mensagem explicita que esse resultado não valida o login Windows. Não habilitar propriedades ou migrar contas às cegas.

Continuam o login individual, as permissões, os verificadores de senha, a autenticação dos equipamentos e a preservação das identidades. Retirar essas verificações não resolveria o bloqueio do instalador pelo Windows e poderia alterar quem consegue acessar os clientes.

## Aplicar no Google — atualização ainda não executada

Antes de aplicar, guarde uma cópia do código atualmente publicado. A revisão foi entregue no GitHub; isso não atualiza o Google.

1. Abra o projeto Apps Script vinculado à planilha correta e substitua o conteúdo de `Code.gs` pelo arquivo desta revisão. Preserve os outros arquivos, as propriedades do script e todas as abas. Confira `DMAX_SHEET_ID` contra o projeto existente; não aponte para outra planilha.
2. Salve. Recarregue a planilha e execute **D-Max → Verificar cadastro (sem alterar dados)**. Este passo lê o cadastro; não migra usuários. Um erro de identidade exige diagnóstico, não exclusão de registros.
3. Para publicar a revisão, use **Implantar → Gerenciar implantações → Editar → Nova versão**, na implantação existente, conservando a URL `/exec`. Isso é uma atualização de produção; avise o responsável antes de executá-la. Preserve as opções de execução/acesso já usadas pelos clientes existentes.
4. Confirme o banner GET e, em seguida, o login Windows e a sincronização Raspberry. O banner confirma a interface anunciada, não valida credenciais nem o funcionamento dos equipamentos.

Não houve acesso à planilha ou atualização da implantação nesta tarefa: a rede deste ambiente continua bloqueando o Google. O 422 real permanece sem causa confirmada. A compatibilidade validada foi com os contratos e serviços fictícios do repositório, incluindo login Windows e snapshot Raspberry lendo os mesmos cabeçalhos formatados. Não foi teste em Raspberry ou Windows reais.

## Bloqueio do Defender

O Apps Script não faz parte do MSI analisado pelo Windows. Esta revisão não remove esse bloqueio. O MSI atual não tem assinatura Authenticode; isso não prova qual foi o motivo da recusa. Para distinguir reputação/editor desconhecido de detecção de ameaça, é necessário o texto exato do aviso e, se houver, o nome da detecção. Não desativar o Defender ou criar exclusões.
