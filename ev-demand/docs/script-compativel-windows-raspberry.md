# Um Apps Script para Windows e Raspberry

## Criação de usuários pelo Windows

A revisão `sheet-user-write-1` grava os perfis em português na planilha, mantendo os nomes internos em inglês no protocolo dos aplicativos. Quando D/E têm validação por lista ou intervalo, escolhe o texto equivalente permitido pela própria lista (por exemplo `Comercial`, `Técnico`, `Ativo`, `Excluído`), sem apagar a validação. Uma opção não disponível em uma lista restritiva é recusada antes da escrita.

A confirmação de gravação agora compara ID, nome, login, perfil, situação e verificador; perfil ou situação ausente não podem resultar em sucesso. Os testes cobrem um usuário novo enviado por `desktop_save_user` com ID automático, senha fictícia convertida em verificador, D/E/G preenchidas e verificador validado independentemente. Também cobrem listas com acentos/maiúsculas, listas baseadas em intervalo e falhas de persistência de D ou E.

Esta é uma incompatibilidade confirmada no código anterior: o protocolo enviava `commercial`, e a gravação não o convertia para `comercial`. Não foi possível confirmar se a planilha real possui uma lista que rejeita esse valor; o usuário foi consultado. Não apresentar essa hipótese como causa já comprovada da tentativa real.

Uma linha já incompleta não é apagada ou reconstruída automaticamente. Se estiver sem D/E, o responsável deve selecionar o perfil e a situação corretos para essa conta. A função de definir senha pela planilha pode então preencher G. Não adivinhar o perfil e não recriar o ID/login para recuperar a linha.

## Administração direta pela planilha

A revisão `sheet-password-1` acrescenta **D-Max → Definir senha da linha selecionada**. Na aba Usuarios, selecione uma célula da linha do usuário, abra esse menu, informe e confirme a senha e clique em **Salvar senha na planilha**. O verificador é preenchido automaticamente em G. Mantenha E como `ativo` para permitir acesso; bloqueados, excluídos e vencidos não são liberados automaticamente.

Esta ação usa a permissão de edição que a pessoa já tem na planilha. Não pede login Windows, sessão desktop nem senha de outro desenvolvedor. Não exige um gerador externo ou instalação. O diálogo exige de 8 a 200 caracteres, calcula PBKDF2-SHA256/600000 no navegador e envia somente o verificador pelo canal do Apps Script. A senha não é escrita em célula, enviada à função de gravação ou registrada em logs. Para manter a mesma senha, informe a senha atual da conta.

O servidor confirma o contexto do editor, a planilha configurada, o ID/login e se a linha mudou durante a edição. Grava somente G e relê a célula para confirmar. Não altera situação, perfil, identidades históricas ou outras contas. A sincronização normal do Raspberry continua responsável por atualizar seu cache. Uma mudança de senha invalida sessões dessa conta conforme o comportamento existente.

Para usar o menu, substitua Code.gs no projeto vinculado à planilha, salve e recarregue a planilha. Para disponibilizar também a revisão aos aplicativos, publique nova versão na implantação existente, conservando a URL. A implantação e a planilha reais não foram alteradas pelo agente. O diálogo foi testado no Chromium com o canal Google simulado; a escrita foi testada com serviços de planilha fictícios. A execução real no Google ainda não foi validada.

Esta revisão mantém os protocolos existentes: `desktop_login`, `desktop_state`, `desktop_logout`, `desktop_clients`, `desktop_members`, `desktop_save_user` para a central Windows 1.2.0/1.2.1, e `snapshot`, `update`, `manage_user`, `remote_directory` com identificação/chave do Raspberry. Nenhuma troca de chaves ou recriação de usuários é necessária por causa desta revisão.

## Simplificação

Uma célula `verificador` vazia em Usuarios agora significa **conta pendente de senha**, em vez de erro 422 para todo o cadastro. Ela não autentica nem recebe uma senha padrão. As demais contas válidas podem entrar normalmente, inclusive na central Windows anterior. Não é necessário instalar outro programa para obter esse comportamento.

Na sincronização Raspberry, uma identidade já conhecida com verificador vazio é enviada inativa, preservando o verificador histórico e a versão de credencial, sem marcá-la como excluída. Uma conta nova sem credencial não é enviada até ter senha configurada. As células da planilha não são preenchidas ou alteradas automaticamente por essa leitura. Limpar a célula não serve para manter uma conta acessível; serve apenas para deixá-la pendente sem bloquear as demais.

Se a própria conta usada para entrar estiver sem verificador, ela ainda precisa de uma senha configurada. Um desenvolvedor com acesso válido pode defini-la pela gestão de usuários existente. Se nenhuma conta de desenvolvedor tiver credencial válida, é necessário tratar a recuperação de acesso; não existe autenticação válida sem credencial.

Na edição pelo Windows, preencher **Nova senha**, a confirmação e a senha do desenvolvedor faz o Apps Script gerar o verificador e gravá-lo automaticamente em G, na mesma linha/ID. Não é necessário copiá-lo manualmente. Para uma conta pendente, deixar a nova senha vazia permite salvar os outros campos, mantendo G vazia e a conta sem acesso. A revisão corrige a rejeição desse salvamento de metadados. Depois de escrever a linha, o serviço faz `flush` e relê o ID e o verificador; uma gravação não confirmada retorna erro em vez de sucesso. O cliente antigo continua compatível.

Os testes incluem a operação real `desktop_save_user`, geração de verificador para uma linha já existente sem credencial, gravação em G, login posterior com a senha fictícia, manutenção do mesmo ID e rejeição de uma escrita simulada que não persistiu. Nenhuma senha ou verificador real foi usado.

## Se o Windows ainda retornar erro genérico ao salvar

O banner informado pelo usuário confirmou as seis operações, mas `diagnostics_version: 1` não distingue as revisões anteriores. A revisão de rastreamento anuncia `diagnostics_version: 2` e `script_revision: "save-trace-1"` no GET. Isso permite confirmar se a URL realmente passou a executar este código.

Depois de publicar esta revisão na implantação existente, repita uma tentativa de salvar no Windows. Em **Execuções** no Apps Script, abra a execução **doPost** correspondente ao horário da tentativa e leia as linhas `DMAX_SAVE` / `DMAX_SAVE_FAILURE`. Elas registram somente a etapa fixa, a revisão, o código e o tipo do erro; não incluem senhas, tokens, verificadores, identidades ou mensagens brutas de exceção. Não é necessário executar `doPost` manualmente no editor.

Etapas: validação da sessão, validação dos campos, geração do verificador, preparação do diretório, leitura do cadastro, confirmação da senha do desenvolvedor, validação do registro, escrita, flush, confirmação da escrita e sincronização da identidade. Se o Google interromper a execução por tempo, a última etapa iniciada ainda estará registrada. Esse rastreamento não confirma que a causa real já foi encontrada: ele fornece a evidência que o aplicativo anterior oculta.

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
