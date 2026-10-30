# Técnicos globais — somente Google Planilhas + Apps Script

Não é necessária uma VPS. O Google hospeda o Apps Script associado à planilha. O cadastro fica nas células e os hashes das senhas ficam nas propriedades privadas do script. Cada D-Max mantém uma cópia local para autenticação offline.

Planilha informada: https://docs.google.com/spreadsheets/d/17HCp2CX3eUZXqQsTkTNDZvrLkGqzZQrJkCfeHo-toPQ/edit

## 1. Preparar o script na conta Google

1. Abra a planilha e escolha **Extensões → Apps Script**.
2. Em um projeto vazio, substitua o código inicial pelo conteúdo de [google-apps-script/Code.gs](../google-apps-script/Code.gs). Se já houver automações, preserve uma cópia e integre os pontos `onOpen`, `doGet` e `doPost`, evitando funções duplicadas. Não sobrescreva scripts existentes sem revisão.
3. O ID da planilha já está no início do código. A aba utilizada é `Tecnicos`.
4. Salve. No editor, selecione e execute `onOpen`, autorizando o acesso solicitado à planilha. Volte à planilha e recarregue a página.
5. No menu **D-Max**, escolha **Preparar aba Tecnicos**. Uma aba existente com outros cabeçalhos não será substituída.

O arquivo `appsscript.json` fornecido documenta o runtime V8, fuso e escopos. Os escopos também podem ser detectados automaticamente pelo editor. Compartilhe a planilha/projeto somente com responsáveis autorizados a administrar o cadastro global: editores de uma planilha com script vinculado podem ter acesso ao projeto e às propriedades do script.

## 2. Publicar no próprio Google

1. No Apps Script, use **Implantar → Nova implantação → Aplicativo da Web**.
2. Escolha executar como **você, proprietário autorizado da planilha**.
3. Configure o acesso do aplicativo da Web como **Qualquer pessoa**, para permitir chamadas sem login interativo do Raspberry. A API exige uma chave privada por equipamento e não fornece cadastros em uma chamada anônima.
4. Copie a URL publicada terminada em **`/exec`**. Não use a URL `/edit` da planilha nem a URL `/dev` do editor.

Se a política da sua organização Google não permitir essa publicação, é necessária a liberação do administrador Google. O D-Max não contorna essa restrição. Depois de alterar o código do script, atualize a implantação para uma nova versão.

## 3. Autorizar cada equipamento D-Max

Essa autorização identifica o produto que consulta a plataforma; **não é uma liberação de técnico por cliente**. Todos os técnicos ativos são globais.

1. Na versão 0.7.0, entre como `root` por [autorização de recuperação assinada](recuperacao-assinada.md) e abra **Técnicos globais**. A chave privada de recuperação é diferente da chave de autorização do equipamento no Google.
2. Copie o **Identificador do D-Max**.
3. Na planilha, use **D-Max → Autorizar um D-Max** e cole esse identificador.
4. Copie a chave exibida uma única vez no diálogo do Google. Ela não é escrita em células.
5. No D-Max, cole a URL `/exec`, a chave e o período de consulta. O padrão é cinco minutos. Ative e salve.
6. Clique em **Sincronizar agora** e confirme o resultado.

A chave é salva no banco local protegido e não é devolvida pela API ou registrada na auditoria. `DMAX_DIRECTORY_TOKEN`, se definida no ambiente, tem precedência. Backups desse banco devem ser protegidos, pois contêm credenciais de sincronização e hashes para acesso offline. Nunca envie chaves ou senhas pelo chat, inclua-as no Git ou publique a planilha com senhas.

## 4. Colunas da aba Tecnicos

| Coluna | Regra |
|---|---|
| `id` | Identificador permanente, por exemplo `TEC-001`; não renomear para outra pessoa |
| `nome` | Nome exibido; pode ser alterado |
| `login` | Permanente, minúsculo, de 3 a 40 letras/números/ponto/hífen/sublinhado; `root` e `admin` são reservados |
| `situacao` | `ativo`, `bloqueado` ou `excluido` |
| `valido_ate` | Vazio: sem vencimento; data `2026-12-31` ou `31/12/2026`: até o fim do dia no fuso da planilha; data/hora ISO deve informar fuso |

Há um [CSV de modelo](../platform_service/tecnicos-modelo.csv) para referência. Não adicione coluna de senha. Contas de administrador e operador são locais; a planilha é o cadastro global de técnicos.

## 5. Primeiro acesso e senha — D-Max 0.6.0

1. Adicione o técnico na planilha e sincronize o D-Max.
2. O técnico entra com seu login e a senha inicial **12345678**, sem código de ativação.
3. No primeiro acesso, define uma senha pessoal. Antes da troca, não acessa painel ou comandos.
4. Sincronize o equipamento onde a senha foi alterada para enviar o hash ao Google. Os demais D-Max recebem a alteração em suas consultas.

A senha alterada é transmitida como hash, não como texto legível. Mudanças de nome, situação ou validade não restauram a senha inicial. Em **Usuários → Redefinir senha inicial**, um gestor autorizado pode restaurar 12345678; isso encerra sessões e exige uma nova troca.

Contas existentes mantêm suas senhas e validade. A versão 0.6.0 deixa de exigir códigos antigos sem redefinir senhas pessoais. Atualize o código no mesmo projeto Apps Script e publique uma nova versão na implantação existente, preservando as propriedades, a URL e as chaves dos equipamentos.

**A chave do equipamento continua obrigatória.** Ela autoriza a sincronização do servidor D-Max e é diferente do antigo código de primeiro acesso de usuário. Navegadores de outros computadores que acessam o mesmo servidor não precisam de outra chave ou instalação.

## 6. Offline e desligamentos

- Não existe prazo adicional de 24 horas ou outro vencimento por falta de internet. Vale exatamente a última validade recebida da planilha.
- Sem data de vencimento, a conta pode autenticar offline sem vencimento de autorização; a sessão normal continua tendo duração de oito horas e pode exigir novo login.
- Bloqueio, exclusão e remoção de uma linha revogam o acesso na próxima sincronização bem-sucedida. Um equipamento desconectado ainda não recebeu essa alteração.
- A exclusão preserva identificação e auditoria; não apaga o histórico de ações.
- O raiz pode cadastrar um técnico localmente sem internet. O cadastro fica pendente e é enviado ao Google quando a conexão/configuração permitir.
- Alterações concorrentes de senha ou cadastro são conciliadas por versões; a plataforma prevalece em conflitos. Pode ser necessário entrar novamente com a senha global após reconectar.
- Falhas de leitura, cabeçalhos inválidos, duplicações e listas parciais não substituem a última cópia válida por uma lista vazia.

## 7. Permissões no D-Max

| Ação | Operador | Administrador | Técnico | Raiz |
|---|---|---|---|---|
| Monitorar, consultar histórico, pausar/retomar | Sim | Sim | Sim | Sim |
| Emergência | Se autorizado | Sim | Sim | Sim |
| Gerenciar operadores | Não | Sim | Sim | Sim |
| Gerenciar administradores | Não | Não | Sim | Sim |
| Ajustar demanda operacional e horário de ponta | Não | Sim | Sim | Sim |
| Teto técnico, circuitos, multimedidor, comissionamento | Não | Não | Sim | Sim |
| Gerenciar técnicos e consulta global | Não | Não | Não | Sim |

O teto técnico limita a demanda que o administrador pode selecionar. As permissões são verificadas pelo servidor, inclusive em chamadas diretas à API. Mudanças que bloqueiem uma conta revogam suas sessões locais e o WebSocket.

## 8. Cotas e validação

Apps Script e propriedades têm cotas do Google, incluindo tempo de execução, chamadas e armazenamento (500 KB para propriedades). Esta solução deve ser dimensionada para a quantidade real de técnicos e produtos; não representa capacidade ilimitada. O script aplica limites de tamanho e identificadores para falhar sem apagar o último cadastro local. Monitore as execuções no editor Google.

O código do script foi exercitado em Node com simulações dos serviços Google; o cliente foi testado com respostas e redirecionamentos simulados. **A implantação na sua conta Google e a consulta da planilha real ainda precisam ser executadas e validadas.** Nenhum Apps Script foi publicado automaticamente nesta sessão.

O diretório `platform_service/` contém uma implementação alternativa em Python para quem futuramente preferir hospedar um serviço próprio. Ele não é necessário para a opção Google Apps Script.
