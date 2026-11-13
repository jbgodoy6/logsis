# D-Max Acesso Windows v1.0

Central simples para os computadores da empresa acessarem os clientes. Não é um controlador de demanda: não abre OCPP, Modbus, serial, túneis ou portas de controle. A simulação usa somente dados fictícios em memória, separados por login.

## Instalar e abrir

1. Instale Python 3.11, 3.12, 3.13 ou 3.14 do site https://www.python.org/downloads/windows/, incluindo o Python Launcher. Não precisa instalar bibliotecas, banco externo ou Node.
2. Extraia TODO o ZIP em uma pasta própria, por exemplo Documentos\D-Max-Acesso. Não extraia sobre a instalação do controlador antigo. Preserve a pasta `data` nas próximas atualizações.
3. Abra `iniciar-windows.bat`. O navegador abre automaticamente em http://127.0.0.1:8765. Mantenha o terminal aberto; Ctrl+C encerra. Outra porta: `iniciar-windows.bat --port 8766`.

## Configuração única por computador

- A primeira tela mostra o identificador WIN-... desta central, persistente entre reinícios.
- Na planilha da empresa, abra D-Max → Autorizar um D-Max e informe esse identificador. Copie a chave emitida para a tela inicial da central. Não use a identidade de um Raspberry.
- Informe também a URL da implantação Google Apps Script terminada em /exec. Salve; a central valida chave e cadastro antes de aceitar a configuração.
- Entre com um login da aba Usuarios. Não há root, administrador local ou senha padrão nesta central. O primeiro desenvolvedor deve existir na planilha; contas de técnico com troca inicial pendente precisam regularizar a senha antes de usar a central.

## Apps Script necessário

O ZIP inclui `planilha/Code.gs` completo e o manifesto. Antes de gerenciar membros pela central, atualize o Code.gs da implantação EXISTENTE, salve e em Implantar → Gerenciar implantações → Editar selecione Nova versão. Preserve a URL, propriedades, chaves e abas.

O script mantém sincronização, assinaturas e catálogo dos Raspberry compatíveis. A operação de gerenciamento exige a chave da central E a senha atual de um desenvolvedor ativo. Recalcula PBKDF2-HMAC-SHA256, 600.000 iterações, no servidor. A senha não é escrita na planilha, propriedades nem logs. Contas não desenvolvedoras não podem usar essa operação, mesmo fazendo chamadas diretas. Esse cálculo pode tornar a confirmação mais demorada; aguarde antes de repetir.

Se ainda não existe Usuarios unificada, execute D-Max → Preparar/migrar usuários (aba única) na planilha antes de usar o gerenciamento. A migração preserva backups. Campos: id, nome, login, perfil, situacao, valido_ate, verificador.

## Perfis e navegação

- Visão geral: lista os clientes publicados na planilha, informa a última conexão recebida, permite buscar por nome e abrir pelo botão Acessar cliente. Não exibe a URL como texto. O navegador necessariamente usa o endereço do cliente ao abri-lo; a central não é um proxy nem oculta o endereço da barra do navegador.
- Desenvolvedor: acesso a todas as funções da central, aos clientes, à simulação, às configurações e à criação/edição/bloqueio/exclusão/reativação das contas de desenvolvedor, comercial e técnico. Gera automaticamente o ID e o verificador para novas senhas, de 8 a 200 caracteres. Requer reautenticação para alterar a planilha.
- Comercial e técnico: busca e acesso aos clientes e simulação. Sem gerenciamento de contas ou configuração da central.
- Cada D-Max de cliente pede seu próprio login. A central não transmite senhas nem cria links com credenciais. No Raspberry 0.14.x, o login comercial continua abrindo demonstração isolada, sem parar ou alterar carregamentos reais.
- Para trocar um login: crie nova conta e exclua/bloqueie a anterior. O ID/login antigo é preservado para não misturar históricos. Isso não bloqueia a criação de novos membros com novos IDs/logins.

## Simulação

Quatro carregadores fictícios, limite de 60 kW e bateria de 60 kWh; duas conexões começam ativas. Permite conectar/desconectar, pausar/retomar e variar outras cargas. SOC sobe conforme energia simulada, com tempo acelerado 60× para demonstração, e encerra em 100%. Desconectar e conectar novamente inicia outra bateria a 20%. Não existe comando para nenhum equipamento real.

Cada login tem sua própria simulação. Sair descarta os dados. Comercial é descartado após 15 minutos sem requisições, como no Raspberry. Sem internet, comercial vale no máximo 5 minutos desde a última sincronização bem-sucedida; desenvolvedor até 1 hora. Técnico também exige autorização central renovada em até 1 hora nesta central. Consultas periódicas tentam renovar a lista a cada 60 segundos. Falhas não prorrogam a autorização. Bloqueios, exclusões, mudanças de perfil e senha revogam as sessões na próxima sincronização válida.

## Dados e operação

A pasta `data` contém configuração e cache privado (chave da central e verificadores de contas); não a envie por email nem publique. Use contas Windows próprias e restrinja o acesso à pasta na empresa. Os processos e simulações não sobrevivem ao fechamento; o cadastro autoritativo permanece na planilha.

O programa escuta apenas no próprio computador (127.0.0.1), porta 8765. Não substitui o controlador Raspberry nem o atualiza. Não cria conexão remota automaticamente: o cliente deve ter publicado seu endereço em DMax_Remoto.

## Verificação desta entrega

Testes automatizados do servidor local, autenticação, revogação, simulação em 100%, isolamento entre sessões, proteção de formulários e regras de gerenciamento do Apps Script; validação no Chromium/Linux. O lançador é para Windows e usa apenas a biblioteca padrão do Python; execução nativa no Windows e confirmação contra a implantação Google real precisam ser verificadas no computador de destino. Nenhuma planilha ou equipamento real foi modificado durante o desenvolvimento.
