# Revisão de segurança — D-Max 0.3.1

Revisão em 27/10/2026 após relato de bloqueio do ZIP pelo Windows.

## Alerta do Windows

O ZIP 0.3.0 foi comparado, arquivo por arquivo, com o código do repositório: 59 entradas correspondentes, integridade ZIP válida, sem executáveis PE embutidos, ambientes Python, bancos ou credenciais de instalação. O SHA-256 do ZIP original é `17565665fcf82b45220f7705085df55c30c8ad2987664a6896e481685917f894`.

Essa inspeção não equivale a uma varredura antivírus. Este ambiente é Linux e não executou Microsoft Defender. Sem o nome da detecção e os itens afetados, a causa do alerta continua **não determinada**. A versão revisada não é uma garantia de ausência de malware ou de aceitação pelo Windows. Não desative a proteção nem crie exclusões para instalar o pacote bloqueado. A distribuição continua ZIP com código legível e os mesmos tipos de scripts; não foi renomeada, cifrada ou ofuscada para contornar o antivírus.

## Problemas encontrados e corrigidos

- **Dependência vulnerável:** `pip-audit` registrou 14 entradas de avisos, correspondentes a 7 identificadores distintos, para Starlette 0.46.2. Incluem esgotamento de CPU ao processar Range e, no Windows, resolução de caminhos UNC capaz de iniciar conexão SMB e expor credenciais NTLM. FastAPI foi atualizado para 0.162.0 e Starlette para 1.10.0, versões compatíveis entre si. Isso corrige problemas reais, mas não estabelece relação com o alerta de vírus.
- **Tentativas de autenticação:** login bem-sucedido reiniciava o contador de endereço. Agora a janela de oito tentativas por cinco minutos inclui sucessos; o armazenamento tem limite e expira entradas. Alteração de senha tem limite por conta e OCPP por carregador. Reiniciar o processo reinicia os limites locais; não são proteção distribuída contra negação de serviço.
- **Verificação de senha:** hashes ausentes ou malformados agora são recusados sem exceção; somente o formato PBKDF2 esperado e 600.000 iterações são aceitos. OCPP exige explicitamente o esquema Basic e limita o tamanho do cabeçalho.
- **Disponibilidade do controle:** verificação PBKDF2 do login/OCPP executa fora do loop assíncrono, com no máximo duas verificações simultâneas. O login revalida situação, sessão e credenciais após a espera para não aceitar uma conta revogada durante a verificação. Alterações administrativas ainda devem ocorrer durante manutenção operacional; não é um sistema de tempo real certificado.
- **Origem das requisições:** verificação inclui esquema e autoridade, rejeita origens malformadas e cabeçalhos Host com caminhos, credenciais ou portas inválidas. Mantidas as restrições de origem do WebSocket, cookies HttpOnly/SameSite, CSP e ausência de cache na API. A validação sintática de Host não é uma lista de equipamentos autorizados.
- **Instalação das dependências:** todas as versões do lock têm hashes SHA-256 dos artefatos publicados no PyPI. Os iniciadores Windows/Raspberry usam `--require-hashes`. Isso detecta conteúdo diferente dos artefatos aprovados; não certifica a segurança do código publicado por terceiros.

## Evidências

- Relatórios públicos: [dependências anteriores](security/dependencies-before.json), [dependências revisadas](security/dependencies-after.json), [dependências do serviço opcional](security/dependencies-optional-after.json), [análise estática](security/bandit.json).
- Consulta `pip-audit` do lock revisado: nenhum aviso conhecido encontrado na data da revisão. Uma consulta sem avisos não prova ausência de vulnerabilidades.
- Bandit: quatro avisos de severidade baixa, nenhum médio/alto. Revisados individualmente: senha inicial solicitada 12345678 (exige código individual e troca), `random.uniform` usado somente no intervalo de consulta, string vazia na recusa de autenticação e exceção tratada no comando de parada OCPP. Os avisos não foram ocultados.
- 73 testes aprovados em Python 3.12 e 3.14, em Linux. Incluem isolamento dos perfis, revogação, validade offline, redirecionamentos Google sem vazamento da chave, hashes malformados, origem/Host, limite de tentativas, loop livre durante PBKDF2 e revogação durante o login. O lock foi instalado com verificação de hashes nos dois ambientes.

## Limites e operação

Não foram executados Defender, antivírus independente, teste de intrusão completo, execução nativa Windows/Raspberry, homologação física ou implantação real do Apps Script. Os testes automatizados não substituem essas etapas.

O lançador Windows continua limitado a `127.0.0.1`. Para acesso pela rede, configure HTTPS/WSS, firewall e rede segregada; não publique diretamente as portas na internet. OCPP Basic sobre WS e login sobre HTTP em rede permitem captura de credenciais. O serviço systemd utiliza usuário próprio e restringe escrita ao diretório de dados.

O Google entrega hashes de técnicos aos controladores para permitir autenticação offline, conforme o requisito. Uma cópia do banco ou comprometimento de um equipamento pode permitir ataques offline a essas senhas. A chave do equipamento autoriza sincronização e alterações globais: mantenha os equipamentos, o banco e os editores do Apps Script sob controle de pessoas confiáveis. Bloqueios remotos somente chegam após uma sincronização bem-sucedida, conforme a regra de validade offline solicitada.

Use a versão 0.3.1 nas próximas validações. Preserve o banco existente e faça backup antes de atualizar. Se o Windows bloquear a versão revisada, mantenha o bloqueio e registre o nome da ameaça, caminho afetado e SHA-256 para análise do arquivo exato.
