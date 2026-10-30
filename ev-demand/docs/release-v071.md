# D-Max 0.7.1 — acesso raiz por palavra-passe, pronto no pacote

O proprietário pode entrar com usuário root e a palavra-passe combinada, sem
preparar chaves, responder perguntas ou copiar códigos. A primeira instalação continua
pedindo somente a senha de admin. Não existe preparação por cliente e o login funciona
totalmente offline. O pacote contém apenas o verificador da credencial, não seu texto.
A recuperação assinada da 0.7.0 continua disponível como alternativa opcional.

## Comportamento

- app/root-credential.json contém versão de formato e hash PBKDF2-SHA256, salt
  aleatório de 16 bytes e 600.000 iterações. O arquivo não é servido pela interface.
- Ao criar a instalação, root recebe o verificador do pacote e não exige troca inicial.
  Login usa a verificação em thread já existente, limite de tentativas, rechecagem de
  revogação, cookie HttpOnly/SameSite e Secure quando houver HTTPS. A sessão raiz
  expira em 15 minutos; sessões comuns mantêm sua duração anterior.
- A tela de login aceita a palavra-passe no campo Senha / palavra-passe e informa que
  root já está configurado. Não exige chave pública/privada para esse acesso.
- A migração sincroniza o verificador root com o pacote e revoga suas sessões se ele
  mudou. Reiniciar com o mesmo hash preserva sessões válidas. Senhas de admin, técnicos
  e operadores, configurações e dados operacionais são preservados.
- Uma instalação não pode alterar a palavra-passe central pelo navegador. A troca
  pelo proprietário exige distribuir outro verificador/pacote e reiniciar as unidades.
- Se o verificador estiver ausente/corrompido, o login root por senha falha fechado.
  O login admin permanece disponível. A assinatura alternativa só funciona se sua
  própria chave pública tiver sido provisionada, como na versão anterior.

A credencial escolhida pelo proprietário foi convertida uma única vez em hash.
O texto não foi colocado em código, documentação, testes ou pacote. Testes unitários
usam credenciais fictícias. O teste real do pacote recebeu o valor pela entrada de
terminal sem eco; o teste de navegador o recebeu apenas no ambiente temporário do
processo, sem gravá-lo no teste ou no log. A grafia final informada foi preservada.

## Segurança e compromisso

Esta configuração atende à escolha de uma credencial compartilhada pelo proprietário.
Ela não oferece isolamento por equipamento: conhecer a palavra-passe permite acesso
raiz a todas as unidades que a usam. Distribuir somente o hash não impede tentativas
offline de adivinhação nem torna confidencial um valor já exposto em outro canal.
Uma frase longa e imprevisível é mais resistente; o risco da credencial escolhida foi
informado na conversa. O código não afirma que um hash elimina esses riscos.

Não se introduziu criptografia de arquivos para esconder o programa nem alterações
em regras do antivírus/firewall. A mudança é de autenticação e usabilidade, solicitada
pelo proprietário, e não comprova resolução da classificação Microsoft Defender.

## Validação

- 126 testes aprovados em Python 3.12 e 3.14 no Linux: 118 anteriores e oito novos
  casos de login raiz, grafia exata, expiração, limites de tentativas, recuperação
  de admin, privacidade das respostas/auditoria, política de arquivo e migração.
- Pacote extraído iniciado em Python 3.14 no Linux sem qualquer chave pública ou
  privada. O verificador do pacote conferiu com a credencial final fornecida.
- Chromium com JavaScript desativado: primeira instalação com apenas admin, login
  raiz pela palavra-passe empacotada, usuários, senhas, Google simulado, multimedidor,
  horários, veículos, carregadores, emergência, histórico e interface móvel.
- Manifesto SHA-256 e código distribuído conferidos. As dependências e suas 49 wheels
  são idênticas às da 0.7.0, cuja resolução offline Windows x64 foi validada para
  CPython normal 3.12/3.13/3.14. Não foi adicionada dependência nesta revisão.
- Bandit: seis avisos baixos (incluindo dois valores vazios que desabilitam root),
  três B104 médios referentes à LAN solicitada e nenhum alto. Não foram suprimidos.
  [Relatório](security/bandit-v071.json).

Não houve validação nativa no Windows/Raspberry nem resultado de Microsoft Defender.
Não existe promessa de aceitação do download. Para atualizar, preserve data/ e rede.ini,
faça backup e use app/ do pacote novo; consulte [instalação](instalar-windows-v071.md)
e [acesso raiz](acesso-raiz.md). A credencial combinada não é reproduzida nesses guias.
