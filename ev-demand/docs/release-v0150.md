# D-Max Raspberry 0.15.0 e Central Windows 1.3.0

## Entrar no cliente sem repetir a senha

Na central Windows, entre com sua conta individual e clique em **Acessar cliente**. A plataforma emite um passe de 60 segundos, utilizável uma vez e somente pelo D-Max escolhido. O Raspberry resgata o passe usando sua própria chave já configurada, confere o cadastro atual e cria a sessão local. Senha e token da central não vão para o navegador do cliente. O passe viaja no fragmento da URL, é removido antes do POST e não aparece em parâmetros de consulta ou no Referer.

Desenvolvedor/técnico recebem suas permissões normais. Comercial continua na demonstração descartável e isolada; a entrada não altera configurações ou carregamentos reais. Passe expirado, repetido, destinado a outro equipamento ou emitido antes de revogação/logout é recusado. Encerrar a central invalida passes ainda não resgatados; sessões já abertas no cliente continuam sujeitas às regras normais de sessão e sincronização do Raspberry.

O recurso exige **Central 1.3.0 + Raspberry 0.15.0 + Apps Script `central-sso-devices-1`**. Um Raspberry anterior ainda pode usar a autenticação normal, mas não oferece a nova página de entrada automática.

## Equipamentos e situação na coluna E

Desenvolvedores têm a aba **Equipamentos** na central. Comercial/técnico não podem listar ou alterar o cadastro administrativo de equipamentos, mas continuam podendo buscar e abrir clientes.

O primeiro salvamento de equipamento, ou **D-Max → Organizar equipamentos (situação na coluna E)** no editor da planilha, faz uma migração com backup. Ela preserva IDs, URLs, informes, revisões e prazos já emitidos, e converte `regular` em `ativo`. A situação anterior estava em H; E guardava a última comunicação. Não substitua E manualmente antes dessa migração.

| Coluna | Conteúdo após a organização |
| --- | --- |
| A | controller_id do D-Max instalado |
| B | Nome da instalação |
| C | URL atual do túnel |
| D | Último estado informado da conexão |
| E | `ativo` ou `pendente`, editável pelo responsável |
| F | Última comunicação |
| G | Último sinal do túnel |
| H | Revisão do informe |
| I | Data do aviso |
| J | Prazo final |
| K | Mensagem |

Pendência mantém a regra existente de dez dias e o prazo fixo; editar mensagem ou receber um heartbeat não reinicia esse prazo. Ativo corresponde a regular. O Apps Script lê os layouts antigos até a migração ser executada, permitindo atualizar os clientes gradualmente. Cabeçalhos ou colunas adicionais desconhecidos são recusados para não sobrescrever conteúdo alheio.

## Cadastrar um D-Max já instalado

1. Copie o identificador exibido no próprio D-Max, em Configurações/Técnicos globais. Não invente outro ID.
2. Entre como desenvolvedor na central, abra **Equipamentos → Cadastrar D-Max instalado** e informe ID, nome, situação e, se conhecida, URL. A mensagem é opcional.
3. Salve. A linha administrativa completa é gravada; sem comunicação real, o equipamento fica como desconectado, com horários vazios e revisão zero. Nenhuma conexão é simulada.
4. Se o ID ainda não estava autorizado, a central mostra uma chave uma única vez. Configure-a no D-Max, junto à URL /exec da plataforma. Para um ID já autorizado, a chave existente é preservada.
5. O Raspberry passa a informar URL, conexão e horários automaticamente. Esses informes não sobrescrevem a situação E nem a mensagem administrativa. A URL não é mostrada como texto nos cartões de acesso aos clientes.

A chave de equipamento autoriza a sincronização; é diferente da senha individual e do verificador dos usuários. Não coloque a chave em uma coluna da planilha. Uma chave perdida pode ser substituída explicitamente pelo menu de autorização já existente, atualizando também a configuração do equipamento.

## Aplicar a atualização

Antes de alterar a implantação, guarde uma cópia do código publicado. Substitua Code.gs e publique nova versão na **implantação existente**, conservando URL, propriedades e identidades. O GET anuncia `script_revision: central-sso-devices-1`.

Atualize o Raspberry pelo procedimento manual já documentado, sem desinstalar nem apagar seu banco/configuração; o ZIP continua sem assinatura para o atualizador automático. Instale o MSI 1.3.0 no computador central, preservando http://d-max.local:80 e a URL da plataforma. Os runtimes Microsoft continuam incluídos. Depois use o menu de organização da planilha ou salve um equipamento pela central para mover a situação para E.

Nenhuma implantação Google, planilha ou equipamento real foi alterado automaticamente pelo agente. Execução Windows real, Defender e Raspberry físico continuam exigindo validação no local. Não desative proteções do Windows.

## Verificação local

Os contratos Apps Script cobrem os dois layouts, backup/migração, prazos, autorização por perfil, cadastro completo, heartbeat preservando E e passes com vínculo ao equipamento, expiração, uso único, logout e revogação. Testes Python cobrem sessão no controlador, limites de perfil, redirecionamento sem replay de credenciais, comercial sem mudanças nos equipamentos reais e troca de perfil com demonstração existente. Chromium cobre os formulários da central, abertura com passe e chegada à visão geral sem uma segunda senha. O Google e os equipamentos são simulados nos testes.
