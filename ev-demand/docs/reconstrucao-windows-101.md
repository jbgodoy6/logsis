# D-Max Acesso Windows 1.0.1 — reconstrução da distribuição

O usuário relatou bloqueio da v1.0 com a mensagem “Falha — Vírus detectado”. O nome da ameaça e o arquivo interno indicado pelo Defender não foram disponibilizados. Não foi possível reproduzir ou atestar a aceitação pelo Defender nesta máquina Linux.

Revisão funcional de distribuição:

- Retirados o lançador BAT e o verificador auxiliar. O programa é iniciado diretamente pelo Python oficial e confere internamente o manifesto antes de criar estado ou iniciar o servidor.
- Retirada a imagem PNG e seus metadados; a marca é renderizada como texto/CSS.
- Apps Script e biblioteca criptográfica dele são distribuídos separadamente, fora do ZIP Windows. Nenhuma mudança na implantação é exigida caso o Apps Script da central v1.0 já esteja aplicado.
- Removida a abertura automática do navegador pelo sistema operacional. O terminal mostra a URL local para abertura manual.
- O ZIP é gerado por uma lista explícita de cinco arquivos UTF-8, com permissões sem execução e metadados determinísticos. Não contém executáveis compilados, bibliotecas de terceiros, credenciais ou bancos de dados.
- Preservados autenticação, permissões, administração de contas, simulação isolada e botões de clientes. Nenhuma verificação TLS, de senha, de integridade ou de autorização foi removida.

Validação: 11 testes de aplicação/distribuição; fluxo completo no Chromium com o módulo e os recursos extraídos do ZIP; inicialização pelo Python e resposta HTTP do pacote; manifesto e ZIP conferidos. Isso verifica conteúdo e funcionamento, não constitui uma análise de antivírus nem garantia de aprovação do Defender. Não se orienta desativar proteção, criar exclusões ou restaurar arquivos bloqueados.

Iniciar em pasta extraída vazia: `py DMaxAcesso.py`. Abrir manualmente http://127.0.0.1:8765. A aplicação continua local e não controla equipamentos reais.
