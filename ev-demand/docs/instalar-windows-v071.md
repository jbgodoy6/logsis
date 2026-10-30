# D-Max 0.7.1 — instalar no Windows x64

1. Extraia o ZIP inteiro, incluindo wheels/, para uma pasta nova e gravável, como
   C:\D-Max-0.7.1. Não execute de dentro do ZIP nem misture app/ de versões diferentes.
2. Execute iniciar-windows.bat. O iniciador procura Python x64 3.13, 3.12 e 3.14 e
   usa a primeira versão que a sua conta puder executar. Ele prepara .venv e instala
   as dependências locais por hashes, sem precisar de internet ou administrador.
   O Python deve estar previamente instalado. Python 3.14.0 é compatível.
3. Mantenha o terminal aberto. Acesse http://127.0.0.1:8080 no próprio servidor.
4. Na primeira instalação, cadastre APENAS a senha de admin. Depois entre como admin
   com a senha cadastrada, ou root com a palavra-passe combinada com o proprietário.
   O acesso root já vem preparado: não precisa cadastrar nada, gerar chaves ou códigos.
5. Para validar, abra Simulador > Carregar demonstração e acompanhe a Visão geral.
6. Ctrl+C encerra o programa, preservando o banco. Abra o mesmo BAT para iniciar novamente.

O login root por palavra-passe funciona sem internet; a sessão vale 15 minutos.
Consulte RECUPERACAO.txt. Novos operadores e técnicos entram com 12345678 e devem
escolher senha pessoal antes de operar. Não há código de primeiro acesso de usuários.

## Atualização preservando tudo

Pare o D-Max e faça backup consistente do banco. Extraia em pasta nova. Copie apenas
os dados data/ e seu rede.ini personalizado da instalação anterior. Não copie app/,
.venv ou requirements.lock antigos. O arquivo app/root-credential.json já vem pronto.
Inicie o BAT da pasta nova. A credencial raiz é atualizada e suas sessões anteriores
são revogadas se ela mudar; senhas dos demais usuários e dados operacionais são mantidos.
Não é necessário apagar o banco nem refazer o cadastro Google ao preservar data/.

## Rede local

O arquivo rede.ini contém:

[web]
host = 0.0.0.0
porta = 8080
nome = auto
anunciar = true

Com nome = dmax-garagem e porta = 9090, o endereço será
http://dmax-garagem.local:9090, em clientes/redes compatíveis com mDNS.
O terminal também mostra os endereços IP. A descoberta depende da rede e do firewall;
o D-Max não muda regras automaticamente. O nome sem .local exige DNS/alias na rede.

A primeira configuração deve usar localhost/127.0.0.1 no próprio servidor. Depois,
outros computadores da mesma rede usam somente navegador e suas contas. Não precisam
instalar Python, outro D-Max ou autorizar outra chave Google para esse mesmo servidor.
A porta é compartilhada com OCPP: ao alterá-la, atualize a URL nos carregadores.
Pare as recargas e reinicie o controlador para aplicar mudanças de rede. O programa
não instala serviço automático do Windows nesta entrega. Configure HTTPS/WSS com
certificado confiável em uma implantação com credenciais reais.

## Funções

Visão geral e Carregadores ao vivo atualizam a cada 2 segundos, sem JavaScript.
Simulador, Carregadores, Veículos, Horários, Multimedidor, Configurações, Usuários,
Técnicos globais e Minha senha mantêm as funções disponíveis conforme o perfil.
Formulários de edição não atualizam automaticamente durante a digitação.

O modo físico permanece piloto: OCPP 1.6J, Modbus TCP/RTU com endereços manuais,
limites e confirmações de redução exigem homologação com os equipamentos reais.
Não use o simulador como proteção elétrica. A operação depende do controlador em
execução, não da existência de uma conexão de internet.

## Integridade e limites

SHA256SUMS.txt permite conferir o conteúdo. As 49 wheels são artefatos oficiais do
PyPI aprovados pelo requirements.lock, para CPython normal Windows x64 3.12/3.13/3.14.
Não há compilação de dependências no cliente. O verificador raiz não é uma chave
privada e não contém a palavra-passe legível. O pacote não inclui banco de clientes,
testes, interface JavaScript antiga ou chaves privadas.

Esta revisão é de autenticação e usabilidade. Não existe aprovação pelo Defender
ou teste nativo Windows/Raspberry a relatar. Mantenha a proteção do Windows ativa;
nenhuma regra, política ou exceção é alterada pelo programa.
