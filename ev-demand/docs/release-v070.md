# D-Max 0.7.0 — recuperação assinada, sem senha raiz compartilhada

A primeira instalação continua pedindo somente a senha de admin. Para acessar root,
o responsável autoriza um desafio do controlador usando uma única chave privada de
sua frota. Todos os equipamentos podem usar a mesma pública. Não há lista de senhas
por equipamento nem senha raiz alternativa.

## Fluxo e confiança

1. O proprietário gera uma chave Ed25519 no seu computador, com a ferramenta offline.
   A privada é salva em PKCS8 criptografado, protegida por uma senha e fora do programa.
2. Somente recovery-public.pem é provisionado nos controladores. O pacote genérico
   não contém chaves de produção. A recuperação fica desabilitada enquanto não houver
   uma pública Ed25519 válida. Admin e os demais logins continuam funcionando.
3. A tela Recuperar acesso produz um desafio de 15 minutos, com identificador aleatório
   de 128 bits, finalidade explícita, ID do equipamento e fingerprint da chave.
4. O proprietário confere o equipamento, confirma a operação e assina na sua ferramenta.
   A privada e sua senha nunca são recebidas pelo controlador ou pela nuvem.
5. A autorização deve retornar ao mesmo navegador/endereço. Uma assinatura válida
   consome o desafio uma única vez e abre uma sessão root de 15 minutos. A sessão
   permite recuperar admin ou executar as funções de raiz previstas no produto.

O cookie que vincula o navegador é aleatório e HttpOnly/SameSite. Só o hash desse
vínculo é guardado no SQLite. A assinatura usa domínio específico do produto e
serialização estrita; entradas não canônicas, esquemas diferentes, outro equipamento,
outra chave, prazos modificados ou assinatura inválida são recusados. Validação
Ed25519 é da biblioteca cryptography, sem algoritmo de assinatura próprio.

Tentativas de criar desafios e de autenticar são limitadas separadamente por IP.
Há no máximo 256 desafios pendentes, com limpeza de vencidos/consumidos. Desafios e
consumo persistem após reinício; alterar/remover a pública e reiniciar revoga desafios
e sessões root, preservando sessões dos demais usuários. A auditoria registra a ação
e a fingerprint pública, sem guardar assinatura, desafio, senha ou chave privada.

## Migração

O login por senha para root é recusado. Qualquer hash raiz legado é removido e suas
sessões antigas são revogadas. Senhas e cadastros de admin, operadores e técnicos,
configurações e históricos são mantidos. Provisione a pública antes da atualização
do banco. O código não muda firewall, políticas Windows, antivírus ou serviços.
Não volte a executar política antiga contra o banco novo; restaure código e backup
correspondentes para rollback. Faça backup antes de migrar.

## Distribuição e dependências

O ZIP continua com interface gerada no servidor, sem JavaScript, allowlist de arquivos,
manifesto interno e sidecar SHA-256. Inclui recuperacao-admin.py e RECUPERACAO.txt,
sem chaves privadas, públicas de teste, banco, testes ou arquivos do desenvolvedor.
As dependências novas cryptography 50.0.2, cffi 2.1.1 e pycparser 3.12 são fixadas
por hashes oficiais PyPI. As 49 wheels locais cobrem CPython normal 3.12/3.13/3.14
Windows x64; não há compilação ou download de dependências na máquina de destino.

## Evidência

- 118 testes aprovados em Python 3.12 e 3.14, no Linux. São 17 novos testes de
  recuperação, além das regressões anteriores adaptadas para autorização assinada.
- Casos de assinatura válida, senha universal recusada, adulteração, expiração,
  relógio futuro, reutilização, outro navegador, outro dispositivo, chave incorreta,
  rotação/remoção de chave, revogação seletiva, persistência após reinício,
  limites de tentativas/armazenamento, privada criptografada e ausência de segredos
  em status/auditoria. Casos anteriores de OCPP, Modbus e demanda preservados.
- Chromium com JavaScript desativado executou o pacote extraído em Python 3.14 no
  Linux: instalação somente com admin, desafio por formulário, assinatura fora do
  navegador e do servidor, sessão raiz, gestão de usuários, troca de senha, horários,
  medidor, veículos, carregadores, emergência, Google simulado e interface móvel.
- Ferramenta CLI do pacote executada de ponta a ponta: privada criptografada,
  assinatura offline, autorização aceita, redefinição de admin e novo login.
  Tela de recuperação móvel verificada sem JavaScript e sem rolagem horizontal.
- Resolução offline das 35 dependências Windows x64 validada nas três versões.
  Para essa checagem cruzada em Linux, o lock temporário omite uvloop, cujo marcador
  o exclui no Windows real; o lock distribuído mantém o marcador original.
- pip-audit: nenhum aviso conhecido. Bandit: quatro alertas baixos já conhecidos
  (senha inicial de usuários, fallback vazio OCPP, jitter e tratamento de parada OCPP)
  e três B104 médios do acesso LAN solicitado. Nenhum alerta alto. Sem suprimir avisos.

Relatórios: [dependências](security/dependencies-v070.json),
[Bandit](security/bandit-v070.json). [Instalar](instalar-windows-v070.md) ·
[Preparar e utilizar a recuperação](recuperacao-assinada.md).

## Limitações

Não houve execução nativa Windows/Raspberry, homologação elétrica ou publicação real
no Google nesta revisão. A migração precisa ser feita com backup e a recuperação deve
ser testada antes de entregar cada instalação. A perda da privada ou de sua senha
exige reprovisionar outra pública por acesso administrativo ao sistema operacional.
É necessária proteção dos arquivos do servidor e do computador do proprietário.
O uso de HTTPS e de relógios corretos é responsabilidade da implantação.

A alteração resolve um problema de autenticação identificado, não uma classificação
antivírus comprovada. Não há resultado de Microsoft Defender nem garantia de aceitação
do novo download. Nenhum arquivo foi enviado automaticamente para análise de terceiros.
