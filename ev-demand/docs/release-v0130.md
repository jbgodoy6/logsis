# D-Max 0.13.0 — clientes remotos e curva mais legível

## O que mudou

**Buscar clientes remotos**, exclusiva do root, consulta a aba DMax_Remoto da
plataforma ao abrir a página, atualizar ou pesquisar. Mostra nome da instalação,
identificador, última comunicação, último estado informado e botão Abrir D-Max.
O botão usa a URL mais recente devolvida pela planilha e abre outra aba; o usuário
faz login no equipamento de destino. Não transmite senha, cookie ou chave entre
clientes. Não há consulta periódica dessa lista em segundo plano.

O nome é o campo Nome da instalação em Configurações de cada D-Max. O vínculo é
feito pelo identificador permanente, portanto mudanças de endereço não exigem
recadastro do cliente. O estado recebido é a última informação, não uma prova de
que a página esteja acessível agora. Comunicação acima de 15 minutos é destacada.
Falhas na plataforma aparecem na própria aba; não se apresenta lista antiga como
recém-atualizada.

A curva ganhou linhas mais fortes, área discreta para total, cores distintas,
legenda com valores, marcação do último ponto, escala mais legível e tooltip em
português com uma linha por valor. Leituras incompletas aparecem com aviso.
Foi corrigida a comparação de horário que invalidava amostras do simulador
capturadas poucos milissegundos após o início do ciclo. A curva considera somente
carregadores da origem consultada e preserva lacunas antigas; não inventa dados
para preencher registros anteriores. Degraus reais de carga são mantidos.

**A atualização visual da curva ocorre a cada 5 segundos.** O histórico mantém
amostragem nominal de 5 segundos e registro de mudanças de limite. O ciclo de
controle de demanda não foi desacelerado e os outros indicadores continuam na
cadência anterior. PDF/CSV, filtro por período e retenção de 30 dias permanecem.

A receita do acesso remoto confirmado pelo proprietário está em
RECEITA-ACESSO-REMOTO.md. O supervisor da 0.12.1, Cloudflare e Grafana são mantidos.

## Atualizar o Raspberry pelo SSH

Encerre recargas antes da atualização completa. Não desinstale. Execute no
terminal já conectado ao Raspberry:

```sh
cd ~
mkdir -p atualizar-dmax-0130
cd atualizar-dmax-0130
wget -c https://raw.githubusercontent.com/jbgodoy6/logsis/dmax-v0.13.0/ev-demand/releases/D-Max-Raspberry-0.13.0.zip
wget -c https://raw.githubusercontent.com/jbgodoy6/logsis/dmax-v0.13.0/ev-demand/releases/D-Max-Raspberry-0.13.0.zip.sha256
sha256sum -c D-Max-Raspberry-0.13.0.zip.sha256
```

Somente após aparecer OK:

```sh
unzip -o D-Max-Raspberry-0.13.0.zip
cd D-Max-Raspberry
sudo bash instalar-raspberry.sh --check
sudo bash instalar-raspberry.sh
sudo systemctl status d-max --no-pager
sudo bash /opt/d-max/acesso-remoto.sh status
```

Reabra a página local e confirme v0.13.0. O instalador preserva banco, usuários,
credencial raiz, histórico, plataforma, configurações e Grafana. O túnel ativo é
reiniciado com a atualização, podendo gerar outra URL. Não é obrigatório reiniciar
o Raspberry. Os arquivos da versão anterior continuam nos backups do instalador.

## Atualizar a plataforma uma vez

1. Copie o Code.gs desta versão para o mesmo projeto Apps Script da sua planilha:
   https://raw.githubusercontent.com/jbgodoy6/logsis/dmax-v0.13.0/ev-demand/google-apps-script/Code.gs
2. Salve e atualize a implantação existente em Implantar → Gerenciar implantações
   → lápis → Nova versão. Preserve a mesma URL /exec e as propriedades/chaves.
3. Reabra a planilha. No menu D-Max → Permitir busca de clientes remotos, informe
   o identificador do D-Max que você usa como console do proprietário. Ele aparece
   em Técnicos globais ou Acesso remoto desse equipamento.
4. Entre como root nesse D-Max e abra Buscar clientes remotos. Os clientes precisam
   estar enviando sua URL à mesma planilha para aparecer.

Essa permissão é exclusiva de consulta ao catálogo completo, armazenada no servidor.
Ela evita que a chave de qualquer cliente comum seja suficiente para listar os
outros clientes. O envio da própria URL e a sincronização de técnicos continuam
independentes e não exigem nova autorização. Para remover o acesso ao catálogo,
use D-Max → Revogar busca de clientes remotos. Não publique a planilha.

A implantação real do Apps Script depende da conta do proprietário; o ambiente de
desenvolvimento não possui acesso a ela. O pacote inclui o código pronto.

## Validação

Em desenvolvimento: 249 testes Python passaram, sem falhas ou testes ignorados,
com as fixtures do pacote ARM64 e PostgreSQL. O Apps Script exato foi executado
com doubles do Google, incluindo permissão de catálogo, revogação e URL atual.
Chromium validou consulta apenas na aba, atualização do link ao reabrir, layout
móvel, curva com cadência de 5 segundos, tooltip, PDF/CSV e gateway HTTPS local.
A implantação Google real e o Raspberry não foram acessados por este executor.
A confirmação do acesso remoto funcionando veio do proprietário antes desta
melhoria; o supervisor e o binário Cloudflare foram preservados byte a byte.
