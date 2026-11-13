# D-Max 0.14.2

- Root não exibe Usuários, Buscar clientes remotos nem Acesso remoto.
- Técnicos globais passa para Configurações para root/desenvolvedor.
- Simulação permanece na Visão geral, sem aba separada.
- O gerador de verificadores de desenvolvedor/comercial aceita senhas de 8 a 200 caracteres. Credenciais existentes continuam válidas.
- Carregadores e planta exibem SOC recebido do veículo; quando ausente, indicam que não foi informado. O simulador usa bateria fictícia de 60 kWh com SOC inicial de 20%, encerra a sessão em 100% e só reinicia após nova conexão.
- Formulários, navegação e atualização preservam a posição da página. Requer JavaScript, sem scripts externos.
- Comercial continua em demonstração isolada em memória: login, pausa, desconexão e criação de demonstração não alteram carregamentos do controlador real.

## Atualizar a planilha

Atualize o Apps Script com `google-apps-script/Code.gs`, salve e atualize a implantação existente. No menu D-Max da planilha, execute **Unificar assinaturas e acesso remoto**. A ação valida os dados, cria backups ocultos e reúne assinaturas nas colunas H:K de DMax_Remoto. A aba Assinaturas antiga é preservada e ocultada. Prazos e revisões já emitidos são mantidos. A migração é repetível e rejeita duplicidades. Antes dela, o código continua lendo o formato anterior.

Não exclua propriedades do Apps Script: elas mantêm identidades e prazos. O pacote não altera a planilha ou implantação automaticamente.

## Raspberry

Pacote sem assinatura de atualização automática: SHA-256 verifica integridade, não autentica o fornecedor. Extraia em diretório separado e use o instalador conforme LEIA-ME. Não envie este ZIP ao mecanismo de atualização que exige assinatura do proprietário. Não inclui chave privada nem altera a senha root.
