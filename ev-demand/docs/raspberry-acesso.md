# Acesso ao D-Max no Raspberry Pi

O pacote já contém o hash da palavra-passe combinada com o proprietário, idêntico ao
da versão Windows 0.7.1. Você não precisa criar outra senha root, gerar chaves ou
preparar o pacote por cliente. O acesso funciona sem internet.

Na primeira instalação, cadastre SOMENTE a senha de admin pelo túnel SSH indicado
no LEIA-ME.txt. Depois, entre pela rede com usuário root e a palavra-passe combinada,
respeitando exatamente seus caracteres. A sessão raiz dura 15 minutos; para continuar,
faça login novamente. O usuário root pertence ao D-Max, não ao Linux do Raspberry.

A credencial não aparece legível nos arquivos: app/root-credential.json contém um
verificador PBKDF2-SHA256 com salt e 600.000 iterações. A migração preserva senhas dos
demais usuários. Não copie app/ do Windows por cima do aplicativo instalado no Linux.

A conta raiz gerencia técnicos, configura Técnicos globais e pode recuperar a senha
do administrador em Configurações. Não é possível alterar a palavra-passe central
pelo navegador de uma instalação; uma troca pelo proprietário exige distribuir o
novo verificador/pacote. Não edite manualmente o hash nem o coloque em colunas Google.

Mantenha a palavra-passe em sigilo: ela é compartilhada pelas unidades desse pacote.
Um hash não elimina risco de adivinhação offline ou de credenciais já expostas.
Configure HTTPS para credenciais reais e restrinja acesso aos arquivos do servidor.
Se o arquivo verificador for removido/corrompido, restaure-o do pacote oficial.

Recuperação por assinatura é alternativa opcional e não é necessária para esse login.
Uma chave pública previamente preparada pode ser configurada no ambiente por
DMAX_RECOVERY_PUBLIC_KEY=/etc/d-max/recovery-public.pem, com arquivo root:dmax 0640;
a privada permanece somente com o proprietário. Não há chave privada neste pacote.
