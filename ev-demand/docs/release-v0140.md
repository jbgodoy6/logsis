# D-Max 0.14.0 — curva adaptativa e contas individuais

Código preparado sobre `feat/dmax-cloud-visual`, base `83fb837` (Apps Script 0.13.1). A aplicação anterior é 0.13.0. Nenhuma tag ou distribuição anterior foi substituída.

## Curva

O registro nominal continua em 5 segundos. Após processar uma leitura, se total, carregadores ou outras cargas mudar mais de `max(15% do último valor registrado, curve_min_delta_kw)`, um ponto original é gravado imediatamente. A regra vale para subida e descida, com tolerância inicial de 1 kW, ajustável em Configurações ou na API. Mudanças de qualidade e limite também antecipam registros. Não há interpolação de medições ou mudança no ciclo de controle.

A supervisão real recebe aviso por SSE e busca a curva atualizada; se a conexão de avisos falhar, continua a consulta periódica. A latência inclui recebimento, processamento e transporte ao navegador. Demonstrações usam a consulta periódica. Redução visual, PDF e CSV preservam os extremos e as amostras existentes.

## Plataforma e acesso

Atualize o código da implantação existente do Apps Script com `google-apps-script/Code.gs`, mantendo seu ID e URL publicados. Execute o menu **D-Max → Preparar contas desenvolvedor/comercial**. A nova aba `Contas` tem as colunas:

`id | nome | login | perfil | situacao | valido_ate | verificador`

Use ID/login permanentes e individuais. Perfis: `desenvolvedor` ou `comercial`; situações: `ativo`, `bloqueado`, `excluido`. A validade segue as mesmas regras de data e fuso da aba Tecnicos. Aba Tecnicos, suas credenciais, Assinaturas e diretório remoto permanecem compatíveis. O novo snapshot acrescenta `accounts`; servidores antigos continuam recebendo `technicians`.

Gere o verificador em um computador confiável com `python tools/account_verifier.py`. O programa pede e confirma a senha sem exibi-la, exigindo 8 a 200 caracteres, e imprime somente PBKDF2-SHA256 (600.000 iterações, sal aleatório). Cole apenas esse verificador na coluna correspondente. Nunca escreva a senha nas células. Restrinja acesso à planilha e aos verificadores. Alterações de senha/perfil/situação/validade são feitas na plataforma; dispositivos não podem criar desenvolvedores/comerciais locais.

Configure a URL e a chave de equipamento já existentes; nenhuma nova autorização individual por equipamento é exigida para listar clientes remotos. A publicação no Google não foi executada neste ambiente.

Desenvolvedor assume administração, configuração, técnicos, manutenção e busca remota. Sua autorização offline expira em **1 hora desde o último snapshot autenticado**, mesmo com uso contínuo. Contas comerciais têm autorização de até **5 minutos** desde o snapshot. Havendo contas desses perfis, a sincronização tenta atualizar no máximo a cada 60 segundos (sujeita a falhas e duração da requisição). Bloqueios, exclusões e alterações de credencial revogam sessões na próxima atualização válida; falhas de rede não renovam a autorização.

Para evitar perda de administração na transição, root remoto permanece temporariamente disponível até o primeiro login bem-sucedido de desenvolvedor. Esse login ativa um bloqueio persistente de root pelo domínio público do gateway. **Valide o desenvolvedor e suas permissões antes de encerrar o acesso local.** Depois disso, senha e recuperação root ficam disponíveis localmente, com a credencial existente preservada. Restaurar backup pelo worker conserva o bloqueio remoto e exige nova consulta central para contas privilegiadas.

## Demonstração comercial

Cada login comercial cria controlador, usuários, equipamentos, configurações e histórico próprios em SQLite `:memory:`. Somente simuladores são aceitos. Não há workers de OCPP, Modbus, serial, nuvem ou diretório dentro da demonstração. Consultas à plataforma ficam restritas à autenticação/liberação no controlador principal.

Uma lista explícita de rotas bloqueia APIs reais, manutenção, recuperação, credenciais, integrações e WebSockets, inclusive chamadas diretas. Usuários fictícios não podem ganhar perfil técnico, desenvolvedor ou root, nem entrar na produção. Cookies de sessão internos não são entregues ao navegador. Logout descarta o banco; 15 minutos sem requisições ou expiração/revogação central também descartam a demonstração. Fechar uma aba não pode ser detectado instantaneamente. Demonstrações simultâneas não compartilham estado. Limite inicial: 32 sessões.

## Atualizar o Raspberry — somente com pacote assinado validado

**A chave privada anterior não existe neste ambiente. Nenhum ZIP desta versão foi apresentado como atualização assinada compatível. Não substitua a chave pública de confiança instalada.** O empacotador rejeita uma chave privada que não corresponda a `deploy/update-public.pem`.

Quando a assinatura original estiver disponível em ambiente seguro:

1. Encerre recargas e desconecte sessões OCPP antes da manutenção. Garanta recuperação local/SSH antes de alterar acessos. Não mude Wi-Fi nem DNS para atualizar.
2. Faça backup consistente do banco e guarde `/etc/d-max` e os overrides systemd. Use a função de backup da manutenção ou `deploy/manage.py backup-db`; não copie somente o arquivo SQLite com WAL ativo.
3. Gere o pacote em um computador de desenvolvimento com as wheels ARM64 verificadas e o cloudflared oficial conferido:

   ```sh
   python tools/package_raspberry.py --wheels /caminho/wheels --cloudflared /caminho/cloudflared-linux-arm64 --signing-key /caminho-seguro/update-private.pem --output /caminho/D-Max-v0.14.0-RaspberryPi-ARM64.zip
   ```

4. Atualize pela Manutenção do D-Max com o ZIP assinado, ou siga a instalação de atualização descrita em `docs/release-v0130.md`, sem desinstalar. Preserve `/var/lib/d-max/controller.sqlite3`, `/etc/d-max/rede.ini`, usuários, credencial raiz e Grafana. A nova tabela de autorizações tem backup SQLite automático anterior à migração.
5. O serviço será reiniciado; reboot não é necessário por esta mudança. Confirme versão 0.14.0, histórico, configurações, Grafana, controlador e acesso público. Prontidão local do cloudflared não comprova acesso público.
6. Atualize o Apps Script e crie/valide o desenvolvedor; teste o bloqueio remoto do root e recuperação local. Faça login comercial em duas sessões e confirme isolamento.

As configurações existentes de Quick Tunnel, protocolo HTTP/2, região `us`, URL automática e publicação no diretório não foram alteradas. Esta entrega não diagnostica nem resolve a instabilidade 1033/502 da rede do cliente. Não houve acesso ao Raspberry, teste físico ou publicação Google. O pacote Raspberry não serve para Windows; o empacotador Windows acompanha o código, sem validação de um ZIP Windows novo.

## Pacote manual sem assinatura

O pacote `D-Max-Raspberry-0.14.0-SEM-ASSINATURA.zip` destina-se à instalação manual por SSH, usando o instalador existente. O instalador confere o manifesto SHA-256; nenhuma verificação foi removida. Esse pacote não contém `SHA256SUMS.sig` e não é aceito pelo atualizador autenticado da página Manutenção. SHA-256 verifica integridade, mas não substitui a autenticação do assinante. Obtenha o ZIP e o checksum pelo canal de entrega confiável.

Antes de atualizar, encerre as recargas, faça backup e preserve o acesso SSH/local. Extraia fora de `/opt/d-max`, execute `sudo bash instalar-raspberry.sh --check` e depois `sudo bash instalar-raspberry.sh`. Não é necessário parar o serviço antecipadamente: o instalador faz essa etapa. Não execute o desinstalador e não substitua a chave pública para fazer a Manutenção aceitar um arquivo sem assinatura. Uma distribuição assinada compatível continua dependendo da chave privada original.
