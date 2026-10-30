# D-Max 0.7.0 — instalação no Windows x64

Este pacote contém a interface gerada pelo Python, sem JavaScript no navegador.
As dependências Windows x64 para Python 3.12, 3.13 e 3.14 estão em wheels/.
A instalação dessas dependências funciona sem internet e confere seus hashes.
O Python deve estar previamente instalado e acessível pela conta do usuário.
O Python 3.14.0 já confirmado no computador do usuário é compatível.

## Começar

1. Extraia o ZIP inteiro, incluindo wheels/, em uma pasta nova e gravável, por
   exemplo C:\D-Max-0.7.0. Não execute dentro do ZIP nem misture os arquivos com
   uma versão antiga.
2. Execute iniciar-windows.bat. A primeira execução cria .venv e instala os
   pacotes locais. Não é necessário executar como administrador do Windows.
3. Mantenha o terminal aberto e acesse http://127.0.0.1:8080 no navegador.
4. Na primeira instalação, defina somente a senha do administrador. Entre com
   admin e a senha definida. O acesso raiz usa autorização temporária; veja RECUPERACAO.txt.
5. Para validar, abra Simulador e clique em Carregar demonstração. Volte a
   Visão geral para acompanhar a distribuição, atualizada a cada 2 segundos.
6. Ctrl+C no terminal encerra o programa. Para iniciar outra vez, execute o
   mesmo iniciar-windows.bat.

O usuário root é uma conta do D-Max, separada do administrador do Windows.
A conta root não tem senha de login. Para habilitar a recuperação, copie sua chave
pública recovery-public.pem para esta pasta e reinicie. Gere o par de chaves uma única
vez no computador do proprietário, seguindo RECUPERACAO.txt; mantenha a chave privada
fora das instalações. O pacote não contém chaves de produção. Sem a pública válida,
a recuperação fica desabilitada e o login admin continua funcionando.
Na atualização, a senha raiz antiga e suas sessões são desabilitadas; as senhas dos
demais usuários são mantidas. Novos operadores e
técnicos usam a senha inicial acordada 12345678, com troca obrigatória no primeiro acesso.
Não há mais código de primeiro acesso. Senhas pessoais já definidas são mantidas.
A chave que autoriza o equipamento no Google continua obrigatória.

## Atualizar preservando os dados

Encerre a versão anterior e faça backup do banco antes de atualizar. Prepare e copie
sua chave pública antes de iniciar a atualização; veja RECUPERACAO.txt. Copie
somente a pasta data/ da instalação antiga para a nova pasta D-Max. Não copie
app/, arquivos HTML/JavaScript antigos, .venv ou configurações de teste.
Se já tiver um rede.ini personalizado, preserve-o também. As contas, carregadores, veículos e configurações existentes serão preservados
no banco; não crie uma instalação vazia se precisa desses dados. A migração
de usuários antigos, quando necessária, gera uma cópia privada de segurança.

## Páginas

- Visão geral: demanda, gráfico e estados; atualização automática a cada 2 s.
- Carregadores ao vivo: todos os conectores, também com atualização a cada 2 s.
- Simulador: outras cargas e demonstração, para validar sem hardware.
- Carregadores: cadastro, potência, pausa/retomada, veículo, emergência e teste.
- Veículos: nomes, identificadores e prioridade.
- Horários: bloqueios, dias e política durante o horário restrito.
- Multimedidor: TCP/IP ou RS485 e mapa manual, com teste antes de salvar.
- Configurações: demanda, circuitos e parâmetros conforme o perfil de acesso.
- Usuários: cadastro, bloqueio, exclusão e redefinição da senha inicial.
- Técnicos globais: Google Planilhas/Apps Script, chave e intervalo, para root.
- Minha senha: alteração da própria senha, exceto root, com novo login após trocar.

As páginas de configuração não atualizam automaticamente durante a digitação.
Nas outras páginas, use Atualizar quando desejar leituras mais recentes.

## Google Planilhas

A sincronização exige publicar o Apps Script na conta Google do proprietário.
Ela não é ativada automaticamente ao instalar o programa. O código e o guia
estão no repositório, fora deste pacote de execução:

https://github.com/jbgodoy6/logsis/blob/feat/ev-demand-v0.1/ev-demand/docs/google-planilhas.md

O cadastro de técnicos é global e mantém exatamente a validade da última
sincronização bem-sucedida quando estiver sem internet.

## Segurança e limites da validação

O pacote não contém a interface JavaScript antiga, testes de desenvolvimento,
relatórios com exemplos de vulnerabilidades, banco ou credenciais reais.
As wheels são artefatos oficiais do PyPI conferidos pelo requirements.lock.
Elas contêm bibliotecas nativas de terceiros necessárias ao Python; não são
um executável D-Max compilado ou um instalador assinado pela Microsoft.

Não foram executados Microsoft Defender nem esta versão nativamente no
Windows neste ambiente de desenvolvimento Linux. A classificação dos pacotes
anteriores não está esclarecida. Portanto, este pacote ainda precisa ser
validado pelo Defender: se houver alerta, mantenha o bloqueio. Não desative a
proteção, crie exclusões ou renomeie arquivos para contorná-lo.

O serviço permite acesso pela rede local por padrão, escutando em 0.0.0.0.
A primeira configuração continua restrita ao próprio servidor por localhost
ou 127.0.0.1. Depois, outros computadores podem acessar pelo navegador.

## Nome e porta na rede

Edite rede.ini na pasta do D-Max. Exemplo:

[web]
host = 0.0.0.0
porta = 9090
nome = dmax-garagem
anunciar = true

Pare as recargas e reinicie o D-Max para aplicar. Não apague data/; mudar nome
ou porta não apaga dados nem altera a identidade de autorização do Google.
O terminal e o painel mostram os endereços disponíveis, por exemplo:

http://dmax-garagem.local:9090

Com nome = auto, o nome será dmax-<oito caracteres do identificador>.local.
Para restringir ao computador servidor, use host = 127.0.0.1; nesse modo não
há anúncio para outros computadores.

Os outros computadores precisam somente de navegador, login e senha do D-Max,
não de Python ou outra instalação. Devem estar em uma rede que alcance o
servidor. O nome .local depende de mDNS/multicast, suportado por clientes
compatíveis; VPNs, VLANs ou Wi-Fi isolado podem impedir a descoberta. Use o
endereço IP mostrado pelo D-Max se o nome não resolver.
Se houver VPN ou adaptadores virtuais, você pode definir host com o IP da
interface LAN desejada; mantenha esse endereço estável na rede.

Para usar http://dmax-garagem:9090 sem .local, configure um registro/alias no
DNS da rede apontando ao servidor, preferencialmente com reserva de IP no DHCP.
O programa não renomeia o Windows nem altera o DNS do roteador.

Se houver solicitação de acesso pelo Firewall do Windows, autorize somente
a rede privada necessária. Se bloqueado por política da empresa, peça à TI
a configuração: TCP na porta escolhida e UDP 5353/multicast para mDNS.
Não é necessário desativar firewall ou antivírus.

A porta também atende OCPP: ao mudá-la, atualize os endereços dos carregadores.
Para operação em rede com credenciais reais, configure HTTPS/WSS usando
--tls-cert e --tls-key com certificado confiável para o nome escolhido.

DMAX_HOST, DMAX_PORT e DMAX_NAME, quando definidos no ambiente, prevalecem sobre
rede.ini. As opções --host, --port e --name do iniciador prevalecem sobre ambos.
Exemplo temporário: iniciar-windows.bat --port 9090 --name dmax-garagem.

Não há serviço de inicialização automática do Windows neste pacote.

O modo físico preserva o adaptador OCPP 1.6J e Modbus existentes, mas permanece
piloto: exige homologação do medidor, carregadores e proteções elétricas
independentes antes de operar uma instalação real.

O arquivo SHA256SUMS.txt permite conferir a integridade dos arquivos. Os hashes
não substituem análise antivírus ou assinatura de editor confiável.
