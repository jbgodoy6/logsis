# D-Max 0.11.0 — acesso remoto opcional, Grafana preservado

Base: 0.10.0, com as pendências registradas no commit `83f21d9`.
Esta entrega implementa o piloto remoto tunnl.gg. A curva histórica de 30 dias,
filtro/exportação/tooltip e reposicionamento abaixo do multimedidor continuam
registrados para implementação posterior; não são entregues nesta versão.

## Atualizar pelo SSH do Windows

Encerre as recargas antes da atualização. Não desinstale o D-Max.
No PowerShell do Windows: `ssh energycube@IP-ATUAL-DO-RASPBERRY`.
Já dentro do Raspberry, execute uma linha por vez:

```sh
cd ~
mkdir -p atualizar-dmax-0110
cd atualizar-dmax-0110
wget -c https://raw.githubusercontent.com/jbgodoy6/logsis/dmax-v0.11.0/ev-demand/releases/D-Max-Raspberry-0.11.0.zip
wget -c https://raw.githubusercontent.com/jbgodoy6/logsis/dmax-v0.11.0/ev-demand/releases/D-Max-Raspberry-0.11.0.zip.sha256
sha256sum -c D-Max-Raspberry-0.11.0.zip.sha256
unzip D-Max-Raspberry-0.11.0.zip
cd D-Max-Raspberry
sudo bash instalar-raspberry.sh --check
sudo bash instalar-raspberry.sh
sudo systemctl status d-max --no-pager
```

Só prossiga após `OK` no SHA-256 e conferência sem erros. O instalador mantém
banco, usuários, histórico, credencial raiz, porta e configuração existente,
com backup anterior e tentativa de retorno em falha. Dependências Python ARM64
continuam offline no ZIP. `openssh-client` é necessário somente para ativar o
remoto; em Raspberry Pi OS com SSH normalmente já está disponível.

## Ativar o acesso remoto

Após atualizar e confirmar a tela local e o cadastro inicial já configurado:

```sh
sudo bash /opt/d-max/acesso-remoto.sh ativar
```

O comando confere o D-Max local, busca a chave pública do provedor na porta TCP
22 e compara seu fingerprint com o publicado no projeto do provedor. Se houver
mudança, não aceita automaticamente: pare e confira a identidade antes de atualizar
a referência. Não é usado `StrictHostKeyChecking=no`.
A chave pública verificada fica em `/etc/d-max-remote/known_hosts`, separada das
credenciais do D-Max. O processo SSH usa usuário próprio e não precisa ler o banco
ou as chaves de Grafana/plataforma do controlador.

É criada uma identidade Ed25519 própria dessa instalação, fora do banco e do ZIP,
em `/var/lib/d-max-remote/id_ed25519`. Reativar reutiliza essa chave. Não copie a
mesma identidade para outros clientes: uma chave só mantém um túnel ativo, e a
nova conexão substitui a anterior. Não envie chaves privadas pelo chat.

O script habilita no boot o gateway local e o supervisor SSH. Ao receber a
confirmação do serviço, imprime um endereço `https://...tunnl.gg`. Abra esse
endereço de outra rede e entre com seu usuário do D-Max. Pode haver uma página
de aviso do provedor antes do login, sem aprovação individual de cada acesso.
Não é necessário comprar domínio nem instalar VPN no computador remoto.

O endereço também aparece para técnico e raiz na aba **Acesso remoto**, com
estado e atualização periódica. O estado representa o último sinal do túnel;
não substitui abrir a página e confirmar o funcionamento de ponta a ponta.

## Consultar ou desativar

```sh
sudo bash /opt/d-max/acesso-remoto.sh status
sudo journalctl -u d-max-remote -u d-max-remote-gateway -n 60 --no-pager
sudo bash /opt/d-max/acesso-remoto.sh desativar
```

Desativar para os dois serviços remotos e preserva a identidade para reativação.
O D-Max local, OCPP e Grafana continuam funcionando. A desinstalação normal do
D-Max remove as unidades remotas gerenciadas e preserva a identidade fora do
aplicativo; revise e arquive essa identidade antes de descartar o equipamento.

## Funcionamento e isolamento

O túnel encaminha somente para `127.0.0.1:8766`. O gateway publica os caminhos da
interface, APIs autenticadas e arquivos estáticos, mantendo login, permissões,
cookies Secure/HttpOnly e validação de origem/CSRF. OCPP, WebSockets e configuração
inicial são bloqueados no gateway, inclusive o OCPP na porta compartilhada do
D-Max. Nenhum segundo controlador é iniciado. Somente proxies em loopback são
confiáveis para os cabeçalhos de HTTPS; não se confia em cabeçalhos de visitantes
da rede local. Nenhuma porta de entrada do roteador é aberta pelo instalador.

O gateway preserva a porta existente e exige acesso ao controlador por loopback.
O padrão `host=0.0.0.0` atende a isso. Se a configuração limitar o servidor apenas
a um IP específico da LAN, a ativação é recusada sem alterar a configuração.
Instalações com TLS local precisam de certificado válido para o endereço usado;
uma CA privada pode ser adicionada com `DMAX_REMOTE_CA_FILE` no ambiente do serviço,
mantendo a verificação TLS habilitada.

Se internet ou SSH cair, o supervisor reconecta com a mesma chave, usando espera
progressiva para não exceder os limites de conexões. A expiração de 24 horas e
inatividade do provedor também encerram uma sessão SSH; a reconexão não cria uma
identidade nova. Há uma interrupção durante esse processo. Se a chave do servidor
do provedor mudar, a conexão será recusada até revisão; o endereço pode mudar
quando essa identidade externa for alterada.

Atualizações ao vivo têm compressão gzip no gateway. Em uma fixture local com
60 carregadores e 180 pontos, uma resposta passou de aproximadamente 194 kB para
7 kB. Isso reduz bastante o consumo, mas não garante uma franquia fixa: nomes,
leituras, curvas, telas abertas, navegadores e tráfego do provedor variam.

## Limites do serviço gratuito e vários clientes

Segundo a documentação pública consultada em 10/11/2026:

- Até 3 túneis por IP público de saída; clientes sob CGNAT podem compartilhar IP.
- 5 GB de transferência por dia por IP, com identidade estável também considerada
  na contagem; trocar chave ou reconectar não reinicia a franquia.
- Sessão de até 24 horas, encerramento por 2 horas inativa e limites de requisições.
- Até 64 MB por arquivo/requisição/resposta. ZIP atual cabe; backups maiores devem
  ser baixados pela rede local. A manutenção do D-Max mantém seus próprios limites.
- O endereço é fornecido pelo serviço, sem nome de cliente escolhido gratuitamente.

O gateway não encaminha Grafana: sua integração, fila e configuração atuais
permanecem independentes. Não foram apagados ou desabilitados serviços Grafana.
Também não há provisionamento de Grafana/Supabase de produção nesta entrega.
Abrir o D-Max remotamente não conta como contato autenticado com a plataforma do
fornecedor para as regras de assinatura: esse contato continua sendo verificado
separadamente pelo envelope assinado.

HTTPS termina na infraestrutura do provedor do túnel e o trecho até o Raspberry
usa SSH; portanto o serviço participa do transporte da interface e seus dados.
Use contas individuais e mantenha as permissões existentes. A licença MIT do
software do túnel não é, por si só, garantia de condições do serviço hospedado.
Termos comerciais, privacidade, franquias e disponibilidade precisam ser
confirmados antes de padronizar várias instalações. Este é um piloto opcional;
não há promessa de disponibilidade ou gratuidade permanente do provedor.

## Validação e pendências externas

Resultado local: **217 testes Python passaram, sem falhas nem testes ignorados**,
com PostgreSQL e o ZIP ARM64 habilitados nas fixtures. Também passaram o Chromium
do gateway HTTPS local, o navegador da interface/PDF e o navegador Grafana. Após
o ajuste de recuperação do arquivo público da chave, a fixture de ativação foi
executada novamente e passou, preservando a chave privada existente.

Testes do gateway exercitam autenticação, cookies seguros, formulários/CSRF,
logout, compressão, restrição de origem e bloqueio de OCPP/configuração inicial.
Chromium testa HTTPS com certificado efêmero local fixado por chave, atualização
ao vivo, campos preservados e layout móvel. O instalador remoto é executado em
árvore temporária com OpenSSH real para geração/fingerprint; provedor e systemd
são simulados, inclusive repetição sem trocar identidade e chave externa inválida.
As regressões anteriores de banco, atualização e OCPP simulado continuam no conjunto.

A conexão ao serviço público não pôde ser validada neste executor: a tentativa de
`ssh-keyscan` terminou em `Temporary failure in name resolution` para
`proxy.tunnl.gg`. Isso não comprova indisponibilidade do provedor. Ative no Raspberry
e confirme pela internet externa, incluindo queda/reconexão e reinício físico.
Boot, hardware watchdog e carregadores reais também exigem validação no equipamento.

Fonte do protocolo, identidade e limites:
https://github.com/klipitkas/tunnl.gg#keep-the-same-url
https://github.com/klipitkas/tunnl.gg#limits-and-protection
