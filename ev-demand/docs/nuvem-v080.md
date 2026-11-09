# D-Max 0.8.1 · Planta visual e integração PostgreSQL/Grafana (piloto)

Esta entrega atualiza o D-Max local e prepara uma integração testável. Não cria uma
conta ou serviço na internet automaticamente. Dados reais na nuvem exigem criar o
projeto Supabase, publicar a função de recebimento e configurar credenciais. A
prévia HTML usa dados fictícios identificados como demonstração.

## O que será mostrado

- Ícones compactos em SVG. Padrões: verde carregando, azul cabo conectado, vermelho alarme e cinza cabo desconectado; paleta configurável no Grafana. Comunicação indicada separadamente. Veja CORES-E-VISUAL.md.
- Um cartão por conector (importante em carregadores com duas ou mais saídas).
- Estado do cabo e veículo associado, potência, limite aplicado e energia da sessão.
- Carregador offline permanece cadastrado. Potência sem leitura atual aparece como
  indisponível, nunca convertida em zero. A associação antiga do veículo é último
  estado conhecido quando o carregador perde comunicação.
- Falha OCPP (Faulted ou errorCode diferente de NoError), inclusive alarme geral no
  conector zero. Ausência de comunicação não é alarme elétrico por si só.
- Multimedidor com todas as grandezas efetivamente configuradas e recebidas, unidade,
  qualidade e horário. Nenhuma tensão ou corrente é inventada se o mapa não as ler.
- Veículo não identificado quando não existir associação confiável; OCPP 1.6 não
  garante VIN/identidade do carro nem SoC. Carro desenhado não é identificação.

## Começar pela interface local (sem conta na nuvem)

Atualize pelo pacote D-Max-v0.8.1-RaspberryPi-ARM64.zip, usando o instalador existente:
extraia fora de /opt/d-max, entre em D-Max-Raspberry e execute
`sudo bash instalar-raspberry.sh`. O instalador preserva banco, usuários, rede.ini e
variáveis em /etc/d-max e faz backup da instalação gerenciada. Não desinstale e não
apague a pasta data. Verifique antes `systemctl status d-max` e a disponibilidade da
porta configurada; outro programa nessa porta impede a inicialização.

Abra o D-Max, entre e selecione **Planta ao vivo** no menu. A nova aparência está
nessa tela, preservando as demais páginas. Para somente avaliar o desenho, abra
cloud/previa-planta.html no navegador: é uma demonstração estática, não uma planta
conectada nem um Grafana publicado.

## Banco gratuito: recomendação e capacidade

Recomendação para piloto: Supabase (PostgreSQL + Edge Function). Grafana OSS é
software gratuito e pode funcionar no Raspberry ou em servidor próprio. O banco
não inclui hospedagem gratuita ilimitada do Grafana. O pacote usa desenhos locais
e painéis nativos, sem plugins pagos, sem desativar sanitização ou segurança HTML.
Grafana Cloud requer uma estratégia diferente para hospedar os desenhos; este
pacote foi validado no Grafana OSS 12.2.0 com seus arquivos SVG montados localmente.

Google Sheets tem limite de células e cotas de API e não substitui bem um banco de
telemetria. Exemplo: 60 conectores x 1.440 minutos/dia = 86.400 leituras/dia; com 10
campos, 30 dias dariam 25.920.000 células, acima do limite usual de 10 milhões por
planilha. Eventos e leituras do multimedidor ainda aumentariam esse total.

O Supabase Free é tradicionalmente limitado a cerca de 500 MB de banco por
projeto, com cotas de funções, tráfego, projetos e possíveis pausas por inatividade.
Confirme os valores no plano vigente antes de contratar:
https://supabase.com/pricing . A consulta automática dessa página retornou HTTP 403
nesta implementação; não se afirma que as cotas comerciais atuais foram verificadas.
Não há promessa de gratuidade ilimitada, SLA ou retenção de 30 dias para 60 equipamentos.

Este piloto mantém somente o estado mais recente da planta, 7 dias de leituras por
minuto e 30 dias de eventos na nuvem. Não apaga cadastro por ausência de comunicação.
Um controlador envia aproximadamente 43.200 lotes/mês em repouso (um por minuto),
além dos eventos. Cada lote pode conter até 200 registros, de vários carregadores.
Dimensione pelo tamanho real do banco e índices. Se necessário, reduza a retenção
ou migre para plano pago; nunca descarte a fila local sem confirmação da nuvem.

## Demonstração completa com Grafana e PostgreSQL locais

Requer Python 3.11+ e Docker Compose v2 já instalados. Não execute scripts obtidos
de fontes desconhecidas para instalar Docker. Na raiz D-Max-Nuvem (ou ev-demand):

```
python3 cloud/prepare_demo.py
docker compose --env-file cloud/.demo/environment -f cloud/compose.yaml up -d
```

No navegador do próprio computador: http://127.0.0.1:3000/d/dmax-energycube .
Usuário `admin`; veja a senha gerada em cloud/.demo/grafana-password. Essa pasta é
privada e não deve ser enviada a ninguém. A demo cria dados fictícios e mantém o
estado simulado atualizado. Não a aponte para carregadores reais. O PostgreSQL da
demo não publica nenhuma porta. TLS é desabilitado apenas na rede interna isolada
do Compose; para Supabase/Grafana real use TLS com verificação.

Para parar: `docker compose --env-file cloud/.demo/environment -f cloud/compose.yaml stop`.
Os volumes e as senhas são preservados. Para retomar, use `up -d`, sem executar o
prepare novamente. A demo não instala serviços no sistema nem altera o D-Max.
Os segredos gerados e os volumes não fazem parte do ZIP distribuído.

## Configurar Supabase real

1. Crie um projeto no Supabase e guarde a senha do banco. No SQL Editor, execute
   cloud/supabase/schema.sql como proprietário. O schema dmax é privado; não exponha
   tabelas por API pública e não adicione políticas anônimas de leitura/escrita.
2. Em **D-Max > Configurações > Integração com a nuvem**, copie o identificador do
   controlador. Gere credenciais no seu computador, na raiz do pacote:
   `python3 cloud/new_controller.py --id IDENTIFICADOR --site "Nome da instalação"`.
   A pasta credenciais-dmax terá permissões privadas e conterá token exclusivo e SQL.
   Não envie o token pelo chat; não use a palavra-passe root como token.
3. Execute `credenciais-dmax/cadastrar-controlador.sql` no SQL Editor do Supabase.
   Apenas o hash SHA-256 do token aleatório é armazenado no banco. Um dispositivo
   desconhecido não consegue criar sua própria planta. Para bloquear, execute:
   `update dmax.controllers set enabled=false where id='IDENTIFICADOR';`.
4. Publique a função `dmax-ingest` com o código cloud/supabase/functions/dmax-ingest/index.ts.
   Pode usar o editor de Edge Functions do Supabase ou o CLI oficial. Com CLI já
   autenticado: entre em cloud, vincule o projeto via `supabase link --project-ref REF`
   e use `supabase functions deploy dmax-ingest --no-verify-jwt`.
   A opção é necessária: Authorization contém o token exclusivo do D-Max, não um JWT
   de usuário Supabase. O banco valida o token e o controlador em cada requisição.
   SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY devem existir somente no ambiente da
   função (o Supabase normalmente os disponibiliza). A chave service_role NUNCA vai
   ao Raspberry, ao Grafana, ao navegador ou ao GitHub.
5. No Raspberry, inclua a linha do arquivo token-controlador.env em
   `/etc/d-max/d-max.env`, preservando as demais variáveis, e mantenha o arquivo
   root:dmax com modo 0640. Reinicie `sudo systemctl restart d-max`.
6. No D-Max, como técnico/raiz, configure API de nuvem:
   `https://SEU-PROJETO.supabase.co/functions/v1/dmax-ingest`.
   Confira o status de sincronização e registros pendentes na mesma tela.
7. Para rotacionar o token, gere outro aleatório, atualize seu hash no cadastro
   e atualize EV_CLOUD_TOKEN no dispositivo. Não altere controller_id ao atualizar
   o aplicativo, para preservar o histórico da instalação.

## Configurar Grafana para o banco real

Execute `credenciais-dmax/grafana-leitura.sql` no SQL Editor para criar o usuário de
leitura (uma vez por projeto). Este piloto usa um projeto dedicado a uma instalação
ou a um único responsável autorizado a consultar todas as plantas desse projeto.
Não compartilhe essa credencial entre clientes que não possam ver os mesmos dados.
Para operação multicliente será necessário separar projetos ou implementar papéis e
views por cliente; um filtro de dashboard NÃO é controle de acesso.

Instale Grafana OSS 12.2+ em host de sua escolha. Copie cloud/grafana/assets para
`/usr/share/grafana/public/img/dmax`, ou use a imagem preparada com
`docker build -t dmax-grafana cloud/grafana` (Dockerfile fornecido). Os SVGs são
locais; não carregam scripts nem dependem de sites externos.

No Grafana, adicione uma fonte **PostgreSQL**, UID `dmax-pg`, com:
- host/porta e nome de usuário do **Session Pooler IPv4**, obtidos em Connect no
  Supabase (o usuário normalmente inclui o identificador do projeto);
- banco postgres, senha de dmax_viewer, TLS **verify-full**, PostgreSQL 16 ou versão
  efetiva do projeto. Configure o certificado CA se o seu Grafana precisar dele.
- nunca use postgres, service_role, root do D-Max ou a credencial de escrita.

Importe cloud/grafana/dmax-planta.json. Selecione a fonte PostgreSQL em Banco D-Max
(variável oculta por padrão; ajuste nas configurações do dashboard se não usar o
UID indicado). Selecione a planta e mantenha Conectores = All para incluir os novos.
A variável é atualizada no refresh do intervalo; o painel se repete por conector.
Um dashboard salvo com seleção fixa de conectores não exibirá automaticamente os
novos enquanto essa seleção fixa for mantida.

Configure limpeza diária usando Supabase Cron (habilite pg_cron no projeto):
`select cron.schedule('dmax-retencao','17 3 * * *','select public.dmax_cleanup()');`.
Verifique a execução e o tamanho do banco. Sem essa tarefa a retenção não é aplicada.
Nenhuma limpeza elimina cadastros ou dados ainda pendentes no Raspberry.

## Tempos e qualidade

Amostras e estado completo são enviados no máximo a cada 60 s quando há conexão.
Mudanças de cabo, sessão, alarme, comunicação, associação de veículo e cadastro são
observadas a cada 1 s pelo remetente; eventos já registrados entram na mesma fila.
O tempo final depende da rede, da API e do refresh de 5 s do Grafana, não é garantia
de tempo real. Eventos conservam horário original e IDs; o servidor confirma em
transação. Falha ou confirmação inválida preserva os registros locais e aplica
repetição com espera progressiva de até 60 s. O estado mais recente tem prioridade
sobre histórico antigo. Reinícios/reenvios não duplicam minutos nem eventos.

Na nuvem, após 150 s sem comunicação/estado recente, todos os cartões indicam dados
desatualizados e a potência fica indisponível. Não se confunde perda da internet do
Raspberry com carregador individual offline. A última leitura tem horário visível;
o Grafana não recebe leituras contínuas a cada 5 s só por atualizar a página.

## Limites desta validação

Testes em Linux x86_64, PostgreSQL 16 e Grafana OSS 12.2 com navegador Chromium.
A integração SQL foi executada em banco real, com autenticação e permissões. A
publicação em uma conta Supabase real, a rede externa, o Windows nativo, o ARM64,
o multimedidor e os carregadores físicos precisam de validação no local. O controle
OCPP continua no Raspberry e a nuvem não envia comandos de carga nesta versão.
