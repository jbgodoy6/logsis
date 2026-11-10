# D-Max 0.12.0 — Cloudflare automático e curva histórica

Atualização para Raspberry Pi OS ARM64, sobre a 0.11.0. Mantém o D-Max local,
usuários, senha raiz, configurações, histórico e serviços Grafana existentes.
Não desinstale a versão anterior. O ambiente antigo de desenvolvimento permanece
preservado. Esta versão substitui o piloto tunnl.gg pelo Cloudflare Quick Tunnel.

## Atualizar pelo terminal do Windows

Encerre as recargas antes da manutenção. No PowerShell, entre no Raspberry:

```powershell
ssh energycube@IP-DO-RASPBERRY
```

Execute dentro do Raspberry, uma linha por vez:

```sh
cd ~
mkdir -p atualizar-dmax-0120
cd atualizar-dmax-0120
wget -c https://raw.githubusercontent.com/jbgodoy6/logsis/dmax-v0.12.0/ev-demand/releases/D-Max-Raspberry-0.12.0.zip
wget -c https://raw.githubusercontent.com/jbgodoy6/logsis/dmax-v0.12.0/ev-demand/releases/D-Max-Raspberry-0.12.0.zip.sha256
sha256sum -c D-Max-Raspberry-0.12.0.zip.sha256
```

Prossiga somente se aparecer `OK`. Se o download parar, repita o mesmo `wget -c`:
ele continua do ponto salvo. Em caso de checksum divergente, remova apenas os dois
arquivos baixados desta versão e baixe novamente; não instale um ZIP divergente.

```sh
unzip -o D-Max-Raspberry-0.12.0.zip
cd D-Max-Raspberry
sudo bash instalar-raspberry.sh --check
sudo bash instalar-raspberry.sh
sudo systemctl status d-max --no-pager
```

O instalador confere o manifesto, faz backup e tenta restaurar a instalação
anterior se a atualização falhar. As dependências Python e o cliente Cloudflare
ARM64 estão no ZIP; não é necessário instalar cloudflared à parte. Reabra a tela
local e confirme `v0.12.0` no rodapé. Não é obrigatório reiniciar o Raspberry:
o serviço D-Max já é reiniciado pelo instalador.

## Ativar e consultar o Cloudflare

Após confirmar o funcionamento local:

```sh
sudo bash /opt/d-max/acesso-remoto.sh ativar
sudo bash /opt/d-max/acesso-remoto.sh status
```

O endereço será `https://algumas-palavras.trycloudflare.com`. Abra o endereço
completo no navegador de outra rede e faça login com seu usuário D-Max. Não se
usa logsis.com.br, conta Cloudflare, DNS próprio ou abertura de porta no roteador.
O gateway publica somente a interface e APIs autenticadas; OCPP e configuração
inicial permanecem bloqueados. A chave antiga tunnl.gg é preservada, sem uso.
Grafana continua com seus serviços e endereços existentes; ele não é publicado
por este túnel.

Os serviços iniciam no boot e tentam reconectar automaticamente. A URL pode mudar
quando o processo/túnel for recriado. Queda de internet interrompe o acesso remoto;
o controle local e a gravação da curva continuam. A planilha recebe o novo endereço
quando a sincronização autenticada conseguir contato com o Google. Durante uma
falha, a linha da planilha mostra somente a última informação recebida.

Se não aparecer endereço conectado:

```sh
sudo journalctl -u d-max-remote -u d-max-remote-gateway -n 60 --no-pager
```

A criação usa HTTPS 443 para api.trycloudflare.com e o transporte HTTP/2 usa saída
TCP 7844 para a rede Cloudflare. O cliente mantém a verificação TLS; não ignore
erros de certificado. A rede corporativa pode precisar liberar o serviço conforme
sua política. O fato de outras aplicações Cloudflare funcionarem nessa rede é
favorável, mas não garante liberação deste hostname/transporte. O Quick Tunnel
é gratuito para teste, sem garantia de disponibilidade, com limites do provedor;
não equivale a um túnel nomeado com endereço fixo.

Para desligar somente o acesso remoto:

```sh
sudo bash /opt/d-max/acesso-remoto.sh desativar
```

## Registrar automaticamente os endereços na planilha

É usada a mesma planilha e autenticação de **Técnicos globais**. A aba separada
`DMax_Remoto` contém uma linha por identificador permanente de D-Max. Não torne a
planilha pública e não coloque chaves/senhas em células.

No computador, baixe o código desta versão:
https://raw.githubusercontent.com/jbgodoy6/logsis/dmax-v0.12.0/ev-demand/google-apps-script/Code.gs

1. Na planilha existente, abra **Extensões → Apps Script**.
2. Substitua o conteúdo de `Code.gs` pelo arquivo desta versão e salve. Preserve
   o mesmo projeto, propriedades e chaves de equipamentos autorizados.
3. Em **Implantar → Gerenciar implantações**, edite a implantação web existente,
   selecione **Nova versão** e implante. Preserve a URL `/exec` já configurada;
   somente salvar o código não atualiza a implantação em execução.
4. Reabra a planilha e use **D-Max → Preparar diretório de acesso remoto**.
   A sincronização também cria essa aba se ela ainda não existir.
5. No D-Max, confirme **Técnicos globais** habilitado, com URL `/exec` e chave
   deste equipamento já configuradas. Não precisa autorizar novamente se essas
   credenciais continuam válidas. A aba **Acesso remoto** mostra o identificador,
   endereço e confirmação/pendência do envio.

Cada cliente usa seu próprio identificador e chave. A atualização da URL substitui
a linha daquele D-Max; não cria uma linha por reconexão. Revisões impedem uma
confirmação antiga de apagar uma atualização recente. Reenvio após falha é
permitido. Um Apps Script antigo continua sincronizando técnicos, mas não confirma
o registro remoto até ser atualizado.

Colunas: `controller_id`, `instalacao`, `url`, `ultimo_estado_informado`,
`ultima_comunicacao`, `ultimo_sinal_tunel`, `revisao`. As datas da planilha são ISO
em UTC. `CONECTADO` é o último estado informado, não uma checagem ao vivo: confira
a data da comunicação e teste o endereço. O intervalo é o configurado em Técnicos
globais (padrão 5 minutos); mudanças detectadas de URL/conexão antecipam uma tentativa.

## Curva auditável por período

A curva fica imediatamente abaixo do multimedidor, antes dos carregadores. Ela
grava pontos locais persistentes a cada 5 segundos, além de mudanças do limite.
Escolha início, fim e origem real/simulada e clique **Aplicar período**. O filtro
usa o fuso da instalação; fim vazio acompanha o horário atual, e sem filtro são
exibidos os últimos 15 minutos. Início incluso e fim exclusivo. São consultáveis
até 30 dias, com limpeza automática independente da fila de envio à nuvem.
Registros não confirmados dessa fila não são apagados por esta política da curva.

Passe o mouse, toque ou foque uma amostra para ver data/hora, total, carregadores,
outras cargas, limite vigente e qualidade. Leituras ausentes ficam vazias e
interrompem a série; zero medido continua sendo zero. Modos real e simulado são
armazenados e consultados separadamente. O limite histórico usa seu valor no
instante registrado. Alterações de filtros ainda não aplicadas permanecem durante
a atualização automática dos dados.

**Relatório PDF da curva** apresenta período, origem, gráfico e mínimos/máximos.
**CSV com todos os registros** contém os pontos completos do intervalo, horário
com fuso e qualidade. Exportações são registradas na Auditoria. Períodos longos
reduzem somente a visualização, selecionando amostras originais e extremos, com
até 1.200 pontos; o CSV mantém todas as amostras. Linhas ligam amostras e não
representam medições intermediárias. Esta curva de potência em kW não substitui
um medidor de energia em kWh ou certificação metrológica.

O histórico começa após instalar esta versão: a curva antiga era mantida apenas
em memória e não permite recuperar um mês anterior. Até 518.400 registros nominais
por origem em 30 dias, mais mudanças do limite; planeje espaço e backups no Raspberry.

## Validação e limites

Consulte VALIDACAO-0.12.0.md no pacote (validation-v0120.md no repositório) para os testes executados. A instalação
física, o acesso público na rede do cliente e a implantação real do Apps Script
precisam ser conferidos no equipamento e conta do proprietário. Nenhum desses
passos é realizado remotamente pelo pacote de desenvolvimento.
