# Desktop 1.0.1 — abertura e diagnóstico

O usuário relatou que a versão 1.0 começava a abrir e não mostrava a janela. A causa específica no Windows ainda não foi confirmada. A versão anterior abriu no ambiente de compatibilidade Mono/WinForms; portanto não se atribui o relato a um erro reproduzido ali.

Esta revisão corrige deficiências observadas na inicialização:

- O ponto de entrada trata falhas antes de criar a janela. A versão anterior não tinha esse tratamento.
- Falhas da interface são registradas e apresentadas em mensagem, em vez de simplesmente encerrar sem diagnóstico.
- Relatórios técnicos locais ficam em %LOCALAPPDATA%\EnergyCube\DMaxAcessoDesktop\Logs, com alternativa na pasta temporária. Guardam versão, etapas, tipos e pilhas; não copiam mensagens arbitrárias de exceção ou dados dos formulários.
- O instalador verifica a presença do .NET Framework 4.8 antes da instalação inicial/atualização. A leitura é HKLM somente leitura, pela tabela padrão RegLocator, sem CustomAction.
- A janela inicial é ajustada à área útil da tela.
- Novo modo --self-test-ui exige que a janela seja exibida com os três campos iniciais e encerra automaticamente. É uma opção de teste, não executa comandos de equipamentos.

Validação: compilação Release; quinze asserções do núcleo, incluindo sanitização do diagnóstico; abertura e encerramento automático do EXE compilado e do EXE extraído do MSI, em Mono/WinForms sob tela X virtual. O relatório desses testes registra UI STARTUP TEST PASSED. O MSI foi auditado novamente: três arquivos, zero scripts/CustomAction, serviços e mudanças de ambiente, somente atalhos e marcadores HKCU.

Esse ambiente não é o Windows do usuário e não executa Defender. O teste de compatibilidade não confirma a resolução da causa específica no computador de destino. A revisão não altera a planilha, APIs ou Raspberry e não exige reconfigurar a URL.

Instale D-Max-Acesso-Desktop-1.0.1.msi sobre a versão anterior, no mesmo usuário Windows. O instalador faz a atualização pelo UpgradeCode. Se o aplicativo voltar a falhar, a mensagem e o relatório local permitem identificar a causa; não são necessários comandos PowerShell nem alterações no antivírus.
