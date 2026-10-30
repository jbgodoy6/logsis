# D-Max 0.6.0 — primeiro acesso e rede local

Revisão de 30/10/2026. Mantida a interface gerada pelo servidor, sem JavaScript no navegador.

## Primeiro acesso sem código

Novas contas de operador, administrador adicional e técnico entram com login e senha inicial **12345678**. Antes de operar, devem definir uma senha pessoal. O formulário de código e o diálogo de ativação foram removidos das duas interfaces. O botão de gestão agora é **Redefinir senha inicial**: restaura a senha temporária, encerra sessões e exige outra troca.

Contas existentes mantêm senhas, validade, situação, permissões e histórico. A aplicação ignora códigos legados sem restaurar senhas pessoais. O campo de API antigo e a coluna de hash são mantidos apenas por compatibilidade de dados; não autorizam ou impedem acesso na versão 0.6.0. A auditoria não registra senhas ou códigos.

O Apps Script atualizado deixa de gerar códigos para novos técnicos e normaliza esse campo nos snapshots, preservando a senha e suas versões. Atualize no mesmo projeto e na implantação existente, preservando as propriedades. **A chave por equipamento continua necessária** para sincronizar o cadastro global; ela não é o antigo código de primeiro acesso.

## Nome e porta

- O servidor lê **rede.ini**, com seção `[web]`, campos `host`, `porta`, `nome` e `anunciar`.
- Padrão Windows: escutar em `0.0.0.0:8080`, nome automático `dmax-<oito caracteres do ID>.local` e anúncio mDNS. O nome fica estável enquanto a identidade do banco for preservada.
- Exemplo: `nome = dmax-garagem` e `porta = 9090` produzem **http://dmax-garagem.local:9090**. Reinicie o programa para aplicar alterações.
- Para nome sem `.local`, configure DNS/alias da rede. O aplicativo não renomeia o Windows, altera DNS ou cria regras de firewall.
- O nome `.local` depende de suporte mDNS no cliente e multicast disponível na rede. O painel e o terminal mostram IPs alternativos. É possível restringir a uma interface pelo campo `host` ou desativar o anúncio. `host = 127.0.0.1` desativa o acesso remoto e o anúncio.
- Falha de anúncio não interrompe a interface por IP nem o controle de demanda. O anúncio é iniciado fora do loop de controle e removido no encerramento.
- `DMAX_HOST`, `DMAX_PORT` e `DMAX_NAME` prevalecem sobre o arquivo; opções CLI prevalecem sobre ambos. O ambiente do serviço Raspberry anterior continua local por padrão, conforme seu arquivo de serviço.

A configuração inicial permanece restrita ao próprio servidor usando localhost/IP de loopback. Depois dela, os demais computadores acessam com navegador e login; não precisam de Python, outra instalação ou outra autorização Google para navegar no mesmo servidor. Instalar outro servidor D-Max independente continua exigindo sua própria chave de sincronização.

O acesso depende do firewall e roteamento da rede. Use somente os perfis privados necessários e configure HTTPS/WSS com certificado confiável para operação com credenciais reais. O anúncio mDNS não autentica a identidade do servidor. A porta escolhida é compartilhada com OCPP; ao mudá-la, atualize os endereços dos carregadores.

## Validação

- **98 testes aprovados em Python 3.12 e 3.14, em Linux**: preservados os casos de demanda, 60 carregadores, Modbus, OCPP, permissões e sincronização. Novos casos cobrem códigos antigos ignorados, técnico global novo sem ativação, redefinição sem código, acesso por navegador LAN, nome/porta, descoberta opcional, colisão/falha de anúncio e encerramento.
- Navegador com JavaScript desativado: fluxo de instalação, usuários e troca de senha sem campo/código, cadastro, medidor, horários, emergência, histórico e Google.
- Teste real mDNS em Linux: um segundo cliente Zeroconf encontrou o serviço anunciado como `dmax-validacao.local`, com porta 8101 e endereços IPv4. HTTP também respondeu pela interface de rede exigindo login. Isso não verifica o resolvedor nativo de outro computador Windows.
- Dependências novas: Zeroconf 0.151.5 e ifaddr 0.2.0, fixadas por hashes PyPI. Wheels Windows x64 verificadas para CPython padrão 3.12/3.13/3.14, sem compilação no computador de destino.
- `pip-audit`: nenhum aviso conhecido no lock na consulta da revisão. Bandit: quatro avisos baixos já revisados e três B104 médios referentes ao uso/comparação de `0.0.0.0`. A escuta LAN é uma mudança explicitamente solicitada; os avisos não foram ocultados. [Dependências](security/dependencies-v060.json) · [Bandit](security/bandit-v060.json).

Os contratos Apps Script foram testados com serviços Google simulados. A implantação real Google, resolução nativa Windows, execução nativa Windows/Raspberry, Defender e homologação física não foram executados neste ambiente. Não há promessa de aprovação por antivírus ou de descoberta em redes que bloqueiem multicast.

## Instalar e atualizar

Use o [guia Windows 0.6.0](instalar-windows-v060.md). Pare a instalação anterior, preserve o banco `data/` e, se já existir, seu `rede.ini`. Extraia em pasta nova e execute o iniciador. Não apague o banco para aplicar esta atualização: não é necessário recadastrar usuários, senhas, carregadores ou a chave do Google.

O ZIP contém somente a aplicação, CSS/logos, arquivo de rede, guia, lock e wheels aprovadas. Não inclui a interface JavaScript antiga, relatórios, testes ou banco. O Apps Script e o [guia Google atualizado](google-planilhas.md) ficam no repositório.
