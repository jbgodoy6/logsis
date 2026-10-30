# D-Max 0.7.0 — recuperação com uma chave do proprietário

Você mantém UMA chave privada para autorizar recuperação em toda a frota. Todos os
D-Max recebem a mesma chave PÚBLICA, que não permite produzir autorizações. Não há
lista de senhas por instalação nem senha raiz universal. A primeira instalação pede
somente a senha do administrador. Após provisionar a pública, a recuperação funciona
sem internet e independentemente do Google Planilhas.

## 1. Gerar sua chave UMA ÚNICA VEZ

Use seu computador de confiança, onde você autorizará as recuperações. Não gere uma
nova chave em cada instalação; distribua sempre a mesma pública.

1. Extraia o pacote em pasta nova. Execute iniciar-windows.bat para preparar .venv e
   as dependências locais. Encerre com Ctrl+C. Não copie ainda dados de versões antigas.
2. Abra PowerShell na pasta D-Max e crie uma pasta pessoal fora da instalação:

   New-Item -ItemType Directory -Force "$env:USERPROFILE\DMax-Chave"

3. Execute em uma linha:

   .\.venv\Scripts\python.exe recuperacao-admin.py gerar-chave --privada "$env:USERPROFILE\DMax-Chave\proprietario.pem" --publica recovery-public.pem

4. Escolha uma senha de pelo menos 12 caracteres para proteger sua chave privada.
   Você só a digitará na sua ferramenta; ela não é a senha dos controladores.
5. Faça backup seguro de proprietario.pem e da senha que o protege. Restrinja a pasta
   à sua conta no Windows: o arquivo herda as permissões da pasta. A perda do arquivo
   ou da senha impede produzir novas autorizações com essa chave.

proprietario.pem é a chave PRIVADA criptografada: guarde somente com você, fora das
instalações e do repositório. recovery-public.pem é a chave PÚBLICA: copie para todos
os equipamentos. A ferramenta recusa sobrescrever chaves existentes. Nenhuma chave
de produção foi gerada pelo desenvolvedor ou incluída no pacote.

## 2. Preparar cada D-Max

1. Copie somente recovery-public.pem para a pasta D-Max, ao lado de run.py.
2. Inicie/reinicie iniciar-windows.bat. O terminal deve informar
   "Recuperação por assinatura habilitada".
3. Na primeira instalação, abra http://127.0.0.1:8080 no próprio servidor e cadastre
   apenas a senha do admin. A porta pode ser outra conforme rede.ini.

Sem uma pública válida, admin funciona, mas a recuperação fica desabilitada, sem
senha alternativa. Teste a recuperação antes de entregar a instalação. No Raspberry,
configure DMAX_RECOVERY_PUBLIC_KEY no ambiente do serviço para um arquivo protegido.
Quem pode alterar os arquivos do servidor pode substituir a pública ou o programa;
restrinja esse acesso à administração do equipamento.

## 3. Recuperar um equipamento

No navegador do controlador:

1. Saia da sessão atual se necessário. No login, clique em
   "Recuperar acesso / acesso raiz" e em "Gerar desafio de recuperação".
2. Copie o desafio DMAX-C1. completo e envie ao responsável pela chave.
   Não limpe os cookies ou troque de navegador/endereço. O desafio vale 15 minutos.

No computador do proprietário, abra PowerShell na pasta com a ferramenta:

   .\.venv\Scripts\python.exe recuperacao-admin.py autorizar --privada "$env:USERPROFILE\DMax-Chave\proprietario.pem"

3. Cole o desafio. Confira o ID do equipamento e a validade apresentados. Autorize
   somente solicitações e equipamentos reconhecidos: a autorização dá acesso RAIZ,
   incluindo recuperação de admin e gestão dos técnicos globais.
4. Confirme com SIM e informe a senha de proteção da sua chave privada.
5. Devolva a autorização DMAX-R1. completa ao solicitante.

No MESMO navegador/endereço que gerou o desafio:

6. Cole em "Autorização recebida" e clique em "Entrar como raiz por 15 minutos".
7. Para recuperar admin, use Configurações > Recuperar administrador e defina outra
   senha. Usuários e Técnicos globais também ficam disponíveis conforme a operação.
8. Saia ao terminar. A sessão raiz expira após 15 minutos mesmo sem clicar em Sair.

Cada autorização só serve para o equipamento, chave, navegador e desafio informados,
e pode ser usada uma única vez. Após logout é necessário outro desafio. Desafio e
sessão duram até 15 minutos cada. Os relógios do controlador e do proprietário devem
estar corretos. Outro navegador ou endereço (IP em vez de .local) exige novo desafio.
A chave privada e sua senha nunca são enviadas ao D-Max ou ao Google.

## Atualização e troca de chave

Pare o controlador e faça backup. Prepare a ferramenta e a chave pública na pasta nova
antes de copiar data/ e rede.ini da instalação antiga. Preserve a privada fora dela.

Na 0.7.0, qualquer senha de login root anterior, inclusive a fixa da 0.6.1, é removida
e suas sessões antigas são revogadas. Senhas de admin, técnicos e operadores, dados
e configurações são preservados. Não execute versão antiga contra o banco migrado:
uma política antiga poderia restaurar a senha universal. Para voltar, use um backup
correspondente ao código antigo.

Se precisar trocar a chave: gere novo par no computador de confiança, distribua só a
pública e reinicie cada controlador. Desafios e sessões raiz anteriores são revogados
quando o servidor carrega a nova chave; sessões admin são preservadas. Remover ou
invalidar a pública e reiniciar também revoga os acessos raiz. Guarde backup da chave.

## Segurança e validação

Ed25519 é implementado pela biblioteca cryptography; a chave privada usa PKCS8
criptografado. Não há algoritmo criptográfico próprio nem chave de produção padrão.
Desafios e consumo persistem no SQLite para impedir reutilização após reinício. Há
limites de tentativas e de desafios pendentes. Auditoria não armazena autorizações,
chaves privadas ou senhas. Cookies são HttpOnly/SameSite; HTTPS ativa também Secure.

Essa alteração corrige a senha raiz compartilhada. Não representa aprovação pelo
Microsoft Defender nem promessa de aceitação do download. Não houve validação nativa
em Windows/Raspberry nesta revisão. Use HTTPS em instalações com credenciais reais;
o programa não configura certificado ou firewall automaticamente.
