# D-Max 0.7.1 — acesso raiz já preparado

Este pacote já contém o verificador da palavra-passe do proprietário. O cliente não
precisa preparar chave, responder perguntas ou configurar a credencial raiz.
Não é necessário pendrive, ferramenta adicional ou internet para fazer login.

## Entrar

1. Execute iniciar-windows.bat e mantenha o terminal aberto.
2. Na primeira instalação, abra http://127.0.0.1:8080 no próprio servidor e cadastre
   SOMENTE a senha do administrador. Se a porta foi alterada em rede.ini, use essa porta.
3. Na tela de login informe usuário root e, no campo Senha / palavra-passe, a credencial
   combinada com o proprietário. Digite exatamente a grafia e os caracteres combinados.
4. A sessão raiz vale 15 minutos; depois basta entrar novamente com a palavra-passe.

A credencial não está escrita neste guia nem no código. O pacote contém apenas um
hash PBKDF2-SHA256, salt aleatório de 16 bytes e 600.000 iterações. A comparação é
feita automaticamente no controlador, inclusive sem internet. Todos os equipamentos
que recebem este pacote usam a mesma credencial, sem cadastro por cliente.

A conta raiz pode administrar técnicos, configurar a plataforma Google e recuperar a
senha de admin em Configurações > Recuperar administrador. Ela é uma conta do D-Max,
separada de root do Linux ou de administrador do Windows. Os perfis de operadores,
administradores e técnicos continuam com suas permissões e senhas individuais.

## Atualizar

Pare o controlador com Ctrl+C e faça backup. Extraia o ZIP em pasta nova e copie a
pasta data/ inteira e o arquivo rede.ini da versão antiga. NÃO copie app/ ou .venv
antigos. O arquivo app/root-credential.json já vem pronto e deve permanecer como
entregue neste pacote. Inicie iniciar-windows.bat na pasta nova.

O programa instala/sincroniza o hash raiz na inicialização e revoga sessões root se
essa credencial mudou. As senhas dos demais usuários, cadastros, históricos e dados
operacionais são mantidos. Reiniciar com o mesmo pacote não muda o hash nem revoga
sessões válidas. Não é necessário apagar o banco para atualizar. A credencial raiz
não pode ser redefinida pelo navegador de uma instalação; uma mudança pelo proprietário
exige distribuir outro verificador/pacote e reiniciar os controladores atualizados.

## Recuperação alternativa, opcional

A recuperação assinada da 0.7.0 continua disponível como alternativa APENAS se você
quiser preparar uma chave pública. Ela NÃO é necessária para entrar com root e a
palavra-passe do pacote. Não gere chaves para o uso normal. Se precisar da alternativa,
consulte RECUPERACAO-ALTERNATIVA.txt e a ferramenta recuperacao-admin.py.

## Proteção da credencial

Guarde a palavra-passe com o proprietário; não a repasse aos operadores/clientes que
não devem ter acesso raiz. O hash não torna uma credencial compartilhada exclusiva:
quem souber a palavra-passe pode entrar em qualquer equipamento que use este pacote.
Um hash distribuído pode sofrer tentativas offline de adivinhação. Uma frase longa,
exclusiva e imprevisível oferece mais proteção; hashes não recuperam sigilo de valores
expostos em conversas ou outros canais. Não use credenciais de outros serviços.

O login tem limite de tentativas, auditoria sem credenciais, cookies HttpOnly/SameSite
e Secure quando se utiliza HTTPS. Configure HTTPS em uma implantação com credenciais
reais; o pacote não muda firewall, Defender ou políticas do Windows.

Se o verificador for removido/corrompido, a senha raiz é desabilitada; restaure o arquivo
do pacote oficial. O login admin permanece disponível. O pacote deve ser instalado em
pasta protegida contra alterações de pessoas sem autorização administrativa.

A inclusão do hash não é uma aprovação antivírus. Não houve teste nativo no Windows ou
no Raspberry nesta revisão, e não há garantia de aceitação do download pelo Defender.
