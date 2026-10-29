# D-Max 0.4.0 — interface DOM

Revisão de 29/10/2026. A interface foi reescrita depois que o Defender indicou os arquivos da distribuição anterior. Esta entrega altera a implementação de segurança da interface; **não confirma falso positivo nem garante liberação pelo Windows**.

## Mudanças

- `app.js`: aplicação reescrita usando componentes DOM, elementos SVG e nós de texto. Nomes, identificadores, eventos e demais valores não são interpretados como HTML. Foram eliminados os pontos de construção dinâmica com `innerHTML` e `insertAdjacentHTML`.
- `dom.js`: componentes com listas explícitas de elementos HTML/SVG. Rejeita elementos como script, atributos de evento e os atributos `src`, `href`, `srcdoc` e `style`. Campos usam a propriedade `value`, células usam nós de texto.
- `transport.js`: módulo exclusivo de comunicação. Aceita somente caminhos da API do controlador, exige a mesma origem, recusa redirecionamentos e mantém cookies restritos à mesma origem. WebSocket acompanha o servidor da página.
- O servidor aplica `form-action 'self'`, `base-uri 'none'`, `object-src 'none'` e Trusted Types sem políticas permitidas. Em navegadores compatíveis, isso bloqueia atribuições de texto a pontos que interpretam HTML/scripts. Outros navegadores continuam protegidos pela implementação DOM e pelas demais diretivas CSP.
- Formulários de senha e chave têm limpeza ao sair ou fechar o editor. A interface descarta resultados de consultas de uma sessão anterior após logout. Os campos da configuração inicial ficam desabilitados durante o login normal, e vice-versa.
- HTML organizado por elemento, módulo JavaScript explícito e MIME corrigido do ícone PNG. Sem empacotador, minificação, scripts externos, bibliotecas JavaScript baixadas em execução ou necessidade de Node no equipamento.

O controle de demanda, o banco de dados, OCPP, Modbus, a hierarquia de usuários e o protocolo Google mantêm a mesma base revisada da 0.3.1. A reescrita da interface não implica homologação elétrica nem aprovação por antivírus.

## Validação

- 73 testes aprovados em Python 3.12 e 3.14, em Linux.
- Teste real de navegador `tests/browser_ui.cjs`: primeira instalação, login, demonstração, limite administrativo, acesso técnico ao medidor TCP/RTU, cadastro/edição de carregador, veículo prioritário, horários, operador, ativação individual, troca inicial de senha, configuração Google, histórico, pausa/retomada e emergência em simulação.
- Valores com marcação HTML foram cadastrados como nomes e permaneceram texto literal nas tabelas, cartões, editor e perfil; nenhum elemento da marcação foi criado.
- Tentativas de destinos externos/travessia na API e de elementos/atributos proibidos nos componentes foram recusadas. Não houve requisições da página fora da origem do controlador no fluxo testado, nem dados em localStorage/sessionStorage, nem erros JavaScript.
- Verificadas permissões do operador, remoção de campos de senha ao fechar o editor, limpeza do código de ativação, chave Google não retornada e ausência de rolagem horizontal no celular.
- `pip-audit`: nenhum aviso conhecido nas versões do lock na data da revisão. [Relatório](security/dependencies-v040.json).
- Bandit: quatro avisos baixos, nenhum médio/alto. Os mesmos avisos já analisados na revisão 0.3.1: senha inicial com ativação, jitter de consulta, senha vazia na recusa e tratamento de falha de parada OCPP. [Relatório](security/bandit-v040.json).

Testes de navegador requerem Playwright e Chromium no ambiente de desenvolvimento, um banco novo e servidor em simulação. Não execute esse teste em uma instalação de produção. O aplicativo instalado não depende dessas ferramentas.

```bash
EV_DB_PATH=/tmp/dmax-ui-test.sqlite3 python run.py --port 8094
# Em outro terminal, com Playwright disponível:
DMAX_TEST_URL=http://127.0.0.1:8094 node tests/browser_ui.cjs
```

## Pacote e Windows

O ZIP inclui código legível, dependências fixadas com hashes e `SHA256SUMS.txt` para os arquivos distribuídos. A soma do ZIP fica no arquivo `.zip.sha256` ao lado dele no repositório. Não contém ambiente Python, banco de instalação ou credenciais reais.

Não foram executados Microsoft Defender, outro antivírus, homologação física ou esta versão nativamente no Windows/Raspberry. A classificação dos ZIPs antigos permanece em investigação, registrada em [defender-investigation.md](defender-investigation.md). Esta versão ainda precisa ser analisada pelo Defender. Se for bloqueada, mantenha o bloqueio e encaminhe a amostra exata ao fabricante para análise, sem criar exclusões ou alterar o pacote para contornar a proteção.

Para atualizar, encerre o D-Max, faça backup do banco e preserve `data/` no Windows. O início permanece por `iniciar-windows.bat`, com Python 3.12, 3.13 ou 3.14 acessível. Código novo não substitui o banco de uma instalação existente. A configuração do Apps Script continua dependendo de publicação na conta Google do proprietário.

[Tela desktop](painel-dom-v040.png) · [Tela móvel](painel-mobile-dom-v040.png) · [Configuração inicial](login-dom-v040.png)
