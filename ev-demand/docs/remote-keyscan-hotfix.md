# Correção pontual da ativação remota da 0.11.0

Se a ativação informar `Chave de servidor inválida` e o ssh-keyscan apresentar
a chave oficial acompanhada de comentários/banners ou linhas vazias, atualize
somente o auxiliar de validação. Não ignore a validação da identidade SSH.

A chave pública apresentada pelo equipamento foi conferida e tem exatamente o
fingerprint esperado `SHA256:5uQ6VobmUpY4wyMmm5jnAwFtt3aX06WYDDM4ER+2WUw`.
O parser anterior rejeitava linhas de comentário se presentes no arquivo capturado.
A correção aceita esses metadados, mas continua recusando chaves diferentes,
registros de outros hosts, ausência de chave e saídas incompletas.

No terminal SSH do Raspberry, em uma pasta do usuário, execute uma linha por vez:

```sh
wget -O remote-corrigido.py https://raw.githubusercontent.com/jbgodoy6/logsis/8c657a7e0b667fed738ac9dd82858358ce1715bd/ev-demand/deploy/remote.py
echo 'f9dace079ee2a70fea7c50b7c90742ce4a98833a97a3630549dfcaee478026e3  remote-corrigido.py' | sha256sum -c -
```

Somente após aparecer `remote-corrigido.py: OK`:

```sh
sudo cp --backup=numbered /opt/d-max/deploy/remote.py /opt/d-max/deploy/remote.py.before-keyscan-fix
sudo install -o root -g root -m 0644 remote-corrigido.py /opt/d-max/deploy/remote.py
sudo bash /opt/d-max/acesso-remoto.sh ativar
```

Isso não troca a credencial raiz, banco, configurações ou identidade do túnel,
não desinstala e não precisa reiniciar o controlador ou Grafana. A versão da
interface continua 0.11.0. O ZIP/tag original não foi sobrescrito: reinstalar o
ZIP 0.11.0 original pode repor o auxiliar anterior. A correção está na branch e
será incorporada aos próximos pacotes gerados a partir dela.

Validação: 21 testes remotos passaram, incluindo a chave pública exata recebida
do equipamento com comentários e linhas vazias, rejeição de outro host/chave,
ativação repetida preservando identidade e testes de autenticação do gateway.
Confirmar a ativação real após aplicar no Raspberry.
