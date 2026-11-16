# D-Max Raspberry 0.15.0 e Central Windows 1.3.0

## Senha inicial e troca obrigatória

No Windows, novos usuários recebem a senha inicial **12345678**. O desenvolvedor pode redefinir essa senha inicial, mas não escolher uma senha pessoal para outro usuário. No primeiro login, a conta fica restrita à troca de senha; clientes, simulação, usuários, equipamentos e configurações não ficam disponíveis até a conclusão. A nova senha pessoal exige de 8 a 200 caracteres e não pode repetir a inicial. Após a troca, o token é substituído sem expô-lo ao navegador. Redefinir a senha invalida as sessões anteriores na plataforma.

O Raspberry também mantém contas globais com senha inicial fora da demonstração e das funções normais até a troca. Desenvolvedor/comercial fazem a troca pela plataforma online, e as credenciais antigas do cache ficam sem autorização até a sincronização. A senha root local não foi alterada. O gerenciador de senha direto na planilha permanece disponível ao proprietário/editor.

## Mínimo de recarga aprendido em AC/DC

O aprendizado anterior gerava somente um relatório. Agora, um teste bem-sucedido memoriza o menor **limite comandado e sustentado**, por conector e veículo identificado, no banco local. O controle usa esse valor ao repartir a demanda. Se nem esse mínimo couber no orçamento, a alocação é zero, conforme a política de suspensão existente; não é escolhido um valor positivo abaixo do piso.

Configure o tipo elétrico AC/DC antes de aprender. Cadastros antigos continuam como “Não informado”, com o mínimo manual e testes apenas observacionais. Em AC, considera-se a referência de 6 A nas fases configuradas: 1,38 kW em 230 V monofásico ou 4,14 kW em 230 V por fase/trifásico. Não há troca automática de fases; a configuração deve corresponder ao equipamento. DC não recebe um piso universal de 6 A. Perfis DC em A usam a tensão atual de saída, sem multiplicação pelas fases AC; sem essa medição, não é emitido um perfil positivo em A. Use W quando suportado e comissionado pelo fabricante.

O teste é assistido: o técnico escolhe um limite menor durante uma recarga em andamento. São exigidos aceite do comando, recarga sem falhas, ao menos três medições atuais após acomodação, intervalo de observação e potência sustentada próxima do limite. Em DC/A, a corrente confirmada também deve estar estável; a autorização em kW acompanha a tensão medida. Zero, rejeição, SOC final, falta de dados e redução de consumo pelo veículo não são usados como “mínimo zero”. Um teste inconclusivo não substitui um mínimo válido. Se o perfil no próprio mínimo conhecido for rejeitado, o registro é preservado para auditoria, mas exige revalidação e o controle retorna ao mínimo manual.

A memória sobrevive ao reinício, distingue conectores/veículos identificados e deixa de ser aplicada quando muda a configuração elétrica, modelo, firmware ou serial informado. Dados de simuladores não viram um mínimo físico. Para veículo não identificado, o resultado vale para o contexto do conector; não é garantia universal para todos os veículos ou condições. Testes devem ser repetidos quando necessário, com homologação no equipamento real. Nenhum ensaio físico foi executado pelo agente.

## Entrar no cliente sem repetir a senha

Na central Windows, entre com sua conta individual e clique em **Acessar cliente**. A plataforma emite um passe de 60 segundos, utilizável uma vez e somente pelo D-Max escolhido. O Raspberry resgata o passe usando sua própria chave já configurada, confere o cadastro atual e cria a sessão local. Senha e token da central não vão para o navegador do cliente. O passe viaja no fragmento da URL, é removido antes do POST e não aparece em parâmetros de consulta ou no Referer.

Desenvolvedor/técnico recebem suas permissões normais. Comercial continua na demonstração descartável e isolada; a entrada não altera configurações ou carregamentos reais. Passe expirado, repetido, destinado a outro equipamento ou emitido antes de revogação/logout é recusado. Encerrar a central invalida passes ainda não resgatados; sessões já abertas no cliente continuam sujeitas às regras normais de sessão e sincronização do Raspberry.

O recurso exige **Central 1.3.0 + Raspberry 0.15.0 + Apps Script `central-sso-devices-2`**. Um Raspberry anterior ainda pode usar a autenticação normal, mas não oferece a nova página de entrada automática.

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

Antes de alterar a implantação, guarde uma cópia do código publicado. Substitua Code.gs e publique nova versão na **implantação existente**, conservando URL, propriedades e identidades. O GET anuncia `script_revision: central-sso-devices-2`.

Atualize o Raspberry pelo procedimento manual já documentado, sem desinstalar nem apagar seu banco/configuração; o ZIP continua sem assinatura para o atualizador automático. Instale o MSI 1.3.0 no computador central, preservando http://d-max.local:80 e a URL da plataforma. Os runtimes Microsoft continuam incluídos. Depois use o menu de organização da planilha ou salve um equipamento pela central para mover a situação para E.

Nenhuma implantação Google, planilha ou equipamento real foi alterado automaticamente pelo agente. Execução Windows real, Defender e Raspberry físico continuam exigindo validação no local. Não desative proteções do Windows.

## Verificação local

Os contratos Apps Script cobrem os dois layouts, backup/migração, prazos, autorização por perfil, cadastro completo, heartbeat preservando E e passes com vínculo ao equipamento, expiração, uso único, logout e revogação. Testes Python cobrem sessão no controlador, limites de perfil, redirecionamento sem replay de credenciais, comercial sem mudanças nos equipamentos reais e troca de perfil com demonstração existente. Chromium cobre os formulários da central, abertura com passe e chegada à visão geral sem uma segunda senha. O Google e os equipamentos são simulados nos testes.
