# D-Max Acesso Desktop 1.0 — reconstrução nativa

Aplicativo Windows reimplementado em C#/.NET Framework 4.8 com Windows Forms. Interface em janela própria: não usa Python, BAT, HTML, JavaScript ou servidor local para funcionar. O navegador padrão só é aberto ao clicar em Acessar cliente. A implementação anterior em Python e a interface web não compõem o instalador.

## Instalar

1. Atualize o Code.gs completo da implantação Google existente com o Code.gs desta entrega. Salve e escolha Nova versão em Gerenciar implantações, mantendo a URL e as propriedades. O GET da URL agora apenas informa que o serviço desktop está ativo; os POST antigos dos Raspberry continuam compatíveis.
2. No Windows 10/11 de 64 bits com .NET Framework 4.8, execute D-Max-Acesso-Desktop-1.0.0.msi. A instalação é por usuário, sem exigir scripts ou administrador. Cria atalhos no menu Iniciar e na área de trabalho e pode ser removida em Aplicativos do Windows.
3. Abra D-Max Acesso Desktop, informe a URL /exec e seu login e senha da aba Usuarios. Não é necessária chave de equipamento para a central: cada operação autentica o usuário individual. O primeiro desenvolvedor precisa existir na planilha.

## Funções preservadas

Visão geral: busca dos clientes publicados, último estado recebido e botão Acessar cliente, sem exibir a URL como texto. O botão abre o D-Max remoto no navegador para login próprio; não envia senhas nem comandos aos carregadores.

Desenvolvedor: clientes, simulação, configurações e administração de membros (desenvolvedor, comercial, técnico), incluindo criação, edição, bloqueio, exclusão, reativação e novas senhas/verificadores. A seleção do membro permanece correta mesmo após ordenar a tabela. Alterações exigem a senha do desenvolvedor novamente e são autorizadas no servidor.

Comercial e técnico: clientes e simulação, sem administração de membros. No Raspberry 0.14.x, o login comercial continua em demonstração isolada.

Simulação: quatro carregadores fictícios, limite de 60 kW, bateria de 60 kWh, tempo acelerado 60× e parada em 100%. Apenas em memória, isolada por login e descartada ao sair. Comercial encerra após 15 minutos sem interação. A autorização é conferida online aproximadamente a cada minuto e em toda operação protegida.

Só a URL pública é salva em %LOCALAPPDATA%\EnergyCube\DMaxAcessoDesktop\settings.json. Não há cache persistente de contas, senhas, verificadores ou tokens. A janela de resultado mostra o verificador gerado apenas ao desenvolvedor reautenticado. O código não instala componentes de controle de hardware, serviços, drivers, tarefas agendadas ou inicialização automática.

## Compilação e proveniência

- SDK .NET 10.0.404 oficial da Microsoft, baixado de builds.dotnet.microsoft.com; SHA-512 conferido contra os metadados oficiais de versão. O usuário final NÃO precisa desse SDK: o executável usa o .NET Framework 4.8 do Windows.
- Referências de compilação Microsoft.NETFramework.ReferenceAssemblies.net48 1.0.3, com lockfile e hashes do NuGet. Nenhuma referência de compilação é distribuída como biblioteca dentro do MSI.
- Instalador produzido por wixl/msitools 0.106. Pacotes Debian foram conferidos por SHA-256 contra índice cuja assinatura foi verificada com o chaveiro Debian fornecido pela imagem.
- Manifesto do EXE solicita asInvoker. Sem ofuscação, empacotador de executável, download de código ou execução de scripts.
- tools/package_desktop.py confere tabelas do MSI: exatamente três arquivos, zero CustomAction, zero ServiceInstall/ServiceControl, zero Environment e somente dois marcadores HKCU para atalhos. A extração do gabinete foi comparada byte a byte ao EXE compilado.

## Validação e limitações

Compilação Release sem avisos/erros. Treze asserções do núcleo nativo verificam distribuição fictícia, SOC em 100%, parada persistente, pausa, nova sessão, isolamento, entradas inválidas e leitura de números com cultura pt-BR. A suíte do Apps Script exercita autenticação individual, permissões, gestão, revogação e logout pelos endpoints desktop e a compatibilidade dos POST antigos dos Raspberry.

Não foi possível executar o Windows Forms/Windows Installer nativamente nem rodar o Defender nesta máquina Linux. O MSI e o EXE não possuem certificado Authenticode de publicação da empresa. A integridade conferida e os testes não garantem aprovação por Defender/SmartScreen. Não desative a proteção nem crie exceções diante de um alerta de ameaça. Uma assinatura reconhecida exige certificado de assinatura de código da empresa.

Não houve acesso à planilha real ou a equipamentos de clientes. A implantação Google deve ser atualizada pelo proprietário e o primeiro login validado no Windows.
