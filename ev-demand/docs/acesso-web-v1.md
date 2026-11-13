# D-Max Acesso Web v1.0

Alternativa de arquitetura à distribuição Windows bloqueada pelo antivírus. A central é servida por HTTPS no Google Apps Script, sem ZIP, Python, BAT, executável, serviço ou servidor local nos computadores da empresa. O programa bloqueado não precisa ser liberado ou executado.

## Ativar — um único arquivo

1. Abra o projeto Apps Script EXISTENTE vinculado à planilha.
2. Substitua TODO o conteúdo de Code.gs pelo Code.gs desta versão. A interface HTML está incluída no próprio arquivo; não é preciso criar arquivos HTML no projeto. Os arquivos Acesso.html e portal-server.gs do repositório são fontes de desenvolvimento, já incorporadas ao Code.gs; não os cole como scripts adicionais.
3. Salve. Em Implantar → Gerenciar implantações → Editar, selecione Nova versão e implante mantendo o mesmo ID e a mesma URL. Preserve as propriedades e chaves.
4. Abra no navegador a URL publicada terminada em /exec. Ela agora abre a central. Não é o link da planilha nem o link do editor de código.
5. Entre com seu login e senha da aba Usuarios. O primeiro desenvolvedor deve estar ativo, com verificador válido e sem conflito de ID/login. Não há senha padrão para desenvolvedor.

As consultas POST autenticadas dos Raspberry continuam disponíveis no mesmo endereço. Não é necessário reinstalar ou alterar as configurações dos Raspberry. A migração para Usuarios unificada deve ter sido concluída antes de usar a central. O nome da planilha e os cabeçalhos não mudam.

## Funções

- Visão geral com busca dos equipamentos publicados, último estado informado e botão Acessar cliente. A URL não é exibida como texto; ao abrir o cliente em outra aba, ela naturalmente aparece na barra do navegador. Não é proxy nem acesso remoto ao sistema operacional.
- Desenvolvedor gerencia membros, perfis, situações, validade e senhas/verificadores. Cada alteração exige novamente sua senha atual, verificada no servidor. Comercial e técnico não podem gerenciar usuários.
- Login, senha ou perfil não são enviados aos D-Max dos clientes pelo botão; faça login no cliente conforme as permissões locais. O login comercial no Raspberry 0.14.x continua isolado em demonstração, sem parar os carregamentos reais.
- A simulação da central acontece somente na memória da página, com quatro carregadores, bateria de 60 kWh, tempo acelerado 60× e parada em 100%. Não faz chamadas a APIs de controle. Sair ou fechar a página descarta a simulação.
- Comercial encerra após 15 minutos sem interação na página. O servidor confere situação, validade, perfil e credencial atuais em toda operação; bloquear ou excluir revoga a sessão na próxima operação/poll. A página verifica a sessão aproximadamente a cada minuto. A central exige internet e não oferece autorização offline.
- Sessões são aleatórias, armazenadas no servidor por hash; o navegador guarda apenas o token de sessão, sem senha. Senhas não entram em propriedades, registros ou URLs. Apenas o desenvolvedor que acabou de reautenticar recebe o verificador que gerou.
- Os menus de manutenção da planilha exigem o contexto do editor vinculado e não podem ser executados anonimamente por RPC da página web.

## Limites da validação

Testados o Code.gs exato com serviços Google simulados e a interface embutida no Chromium: autenticação, ausência de verificadores na listagem, administração por desenvolvedor, bloqueio de comercial, revogação, logout, simulação e isolamento de comandos. As consultas e contratos antigos dos Raspberry também passaram nos testes locais. Publicação no GitHub não é implantação Google: a aplicação real depende de o proprietário atualizar sua implantação e validar o login. Não houve acesso à planilha real, a clientes ou a Raspberry durante o desenvolvimento.

Apps Script tem cotas e limites de execução. A verificação PBKDF2 pode demorar alguns segundos; aguarde a confirmação e evite repetir solicitações. A alternativa web não certifica o antigo ZIP como seguro nem requer exceções no Defender.
