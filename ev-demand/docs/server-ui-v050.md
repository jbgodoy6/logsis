# D-Max 0.5.0 — interface no servidor e pacote Windows

Validação de 29/10/2026, em Linux. O objetivo é uma edição de implantação sem a interface JavaScript anterior e sem exigir download de dependências nos computadores de destino. A execução nativa no Windows e a classificação pelo Defender continuam pendentes; não foi confirmado falso positivo.

## Arquitetura

- `app/server_ui.py` gera as páginas, formulários, tabelas e SVG no Python. Valores do usuário são escapados ao gerar HTML. O navegador não recebe scripts e a CSP contém `script-src 'none'`.
- As operações usam internamente a mesma API autenticada. Credenciais, permissões, validações, limites de tentativas e auditoria continuam no backend existente. O endereço real do cliente é preservado na chamada interna, inclusive na configuração inicial e no limite de login.
- Cada formulário tem HMAC-SHA256 vinculado à sessão, nonce HttpOnly/SameSite e validade de uma hora. O nonce sozinho não autoriza uma operação. Campos duplicados, tipo de conteúdo inesperado e corpo acima de 128 KiB são recusados.
- A configuração inicial exige origem de conexão e hostname locais. Um hostname externo apontado para loopback não pode executar a primeira configuração. A exceção do cliente de testes fica restrita ao banco em memória e hostname `testserver`.
- Demanda, gráfico e monitor de todos os conectores atualizam por navegação HTML a cada dois segundos. As páginas de edição não atualizam durante a digitação. O processo de controle continua independentemente do navegador.
- Senhas não são reapresentadas nos formulários; códigos de ativação aparecem somente na resposta correspondente. A mudança de senha encerra a sessão e exige login. Sem persistência de credenciais no navegador além do cookie HttpOnly da sessão.

O código de controle, OCPP 1.6J, Modbus, prioridade, limite elétrico, retenção e sincronização Google foi preservado. O modo físico permanece piloto e exige homologação dos equipamentos. O recurso de aprendizagem continua assistido e observacional.

## Pacote de execução

`tools/package_windows.py` usa uma lista explícita de arquivos, verifica as wheels contra os hashes do lock e produz ZIP, manifesto interno e SHA-256 do ZIP. Não muda a extensão dos arquivos nem os cifra/ofusca.

O ZIP inclui arquivos Python de execução, CSS, logos, iniciador, lock, guia e wheels oficiais do PyPI para Windows x64. Não inclui interface antiga `.js`/`index.html`, testes de desenvolvimento, relatórios antigos, código do serviço central opcional, banco, `.venv` ou credenciais reais. O projeto completo e os relatórios permanecem no repositório para revisão. O Apps Script é configurado pelo proprietário usando o guia do repositório, fora deste pacote local.

As wheels de terceiros incluem bibliotecas nativas. Não se trata de executável D-Max compilado, assinatura Authenticode ou aprovação da Microsoft. O iniciador instala dependências por `--no-index --find-links wheels --require-hashes`; não muda configurações do Defender, firewall, registro ou política do Windows.

## Evidências

- **84 testes aprovados com Python 3.12 e 3.14**, incluindo 11 novos testes da interface/formulários.
- Pacote extraído em diretório separado e iniciado por Python 3.14 no Linux, sem usar arquivos de interface do checkout.
- Fluxo real de navegador do pacote com **JavaScript desativado**: instalação inicial, login de admin/root, demonstração, demanda operacional, cadastro de veículo prioritário, carregador, pausa/retomada, emergência, horários, mapa Modbus, usuário/ativação/troca inicial, Google, histórico e mudança da própria senha.
- Sem requisições de script ou fora da origem do controlador no fluxo testado. Recursos antigos `/static/app.js` e `/static/index.html` retornam 404 no pacote. Verificados todos os conectores no monitor e layout móvel sem rolagem horizontal.
- Nomes contendo marcação HTML foram tratados como texto literal.
- `pip download` verificou os hashes dos artefatos PyPI; `pip install --dry-run --no-index --require-hashes`, com alvo Windows x64, resolveu todas as dependências para **3.12, 3.13 e 3.14** usando apenas a pasta local. Isso é validação de resolução, não instalação nativa Windows.
- `pip-audit` não encontrou avisos conhecidos nas dependências do lock na data da revisão. Bandit apresentou os quatro avisos baixos já analisados, sem novos avisos médios/altos. Relatórios: [dependências](security/dependencies-v050.json) e [Bandit](security/bandit-v050.json).

O teste de navegador é `tests/browser_server_ui.cjs`. Exige Playwright e Chromium somente no ambiente de desenvolvimento e um banco novo em simulação. Não o execute em uma instalação de produção. O pacote instalado não depende de Node ou Playwright.

## Limites e próximo passo

Não foram executados Microsoft Defender, esta versão nativamente no Windows/Raspberry, homologação física ou publicação real do Apps Script. A tentativa anterior de ClamAV não obteve definições válidas e não constitui uma varredura aprovada. Os resultados acima não certificam ausência de malware.

A aprovação pelo Defender precisa ocorrer no computador de destino. Se a nova edição for bloqueada, mantenha o bloqueio e encaminhe a amostra exata para análise do fabricante/TI; novas alterações sem identificar a causa não garantem resolver a classificação.

[Guia para instalar](instalar-windows-v050.md) · [Tela desktop](painel-server-v050.png) · [Tela móvel](painel-mobile-server-v050.png) · [Multimedidor](multimedidor-server-v050.png)

Para desenvolvimento, a interface anterior permanece disponível somente no checkout completo com `DMAX_WEB_UI=legacy`. A distribuição Windows fixa o modo `server` e não contém os arquivos dessa interface.
