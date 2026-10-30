# D-Max 0.6.1 — recuperação fixa

A primeira instalação pede somente a senha do administrador. A conta de recuperação
é `root`, com a senha fixa `31011986`, conforme requisito explícito do proprietário
do produto. Ela não precisa ser cadastrada, não expira e não exige troca inicial.
Quem conhece essa senha pode entrar como raiz em qualquer instalação desta versão.
Não existe uma segunda senha de recuperação oculta.

O servidor cria o hash PBKDF2 com salt individual durante a instalação. O formulário
e as respostas públicas não divulgam a senha. A definição fixa existe no código
fornecido, portanto o hash não torna esse segredo exclusivo de cada equipamento.
Limitação de tentativas, verificação de origem, permissões e auditoria permanecem.

Na atualização, a inicialização substitui a senha root antiga pela fixa e revoga
sessões root quando aplica essa mudança. Reinicializações seguintes preservam o hash
e as sessões enquanto a política já estiver aplicada. Senhas de admin, técnicos e
operadores, bem como cadastros e dados operacionais, são preservadas. Não apague data/.
A própria conta root não pode mudar sua senha nem ser redefinida pelo gerenciamento
de usuários. A página Minha senha informa essa condição, sem oferecer o formulário.

A API aceita o antigo campo opcional root_password somente para compatibilidade,
mas ignora seu valor; ele não substitui a senha fixa. O fluxo local de configuração,
restrito ao computador servidor, continua obrigatório para definir admin. Nenhuma
conta é criada antes dessa configuração. Google Planilhas e a chave do equipamento
não mudaram nesta versão.

## Validação

- 101 testes aprovados em Python 3.12 e 3.14 no Linux, incluindo instalação somente
  com senha admin, senha root fixa, bloqueio de alteração, migração, revogação e
  preservação da senha admin. Mantidas as regressões OCPP, Modbus, demanda e permissões.
- Fluxo real no Chromium com JavaScript desativado, usando o pacote extraído e Python
  3.14 no Linux: instalação sem campo root, login e operação com perfis, senhas,
  horários, veículos, carregadores, multimedidor e integração Google simulada.
- Pacote e manifesto SHA-256 verificados; mesmas wheels Windows x64 aprovadas no lock
  da versão 0.6.0. Nenhuma dependência nova nesta revisão.

Não houve validação nativa em Windows, Raspberry Pi ou hardware físico nesta revisão.
Não houve nova varredura do Microsoft Defender e não se afirma aprovação antivírus.
