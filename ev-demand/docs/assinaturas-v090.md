# Assinaturas por D-Max — Google Planilhas

O recurso é opcional. Instalar a atualização sem uma linha na aba Assinaturas não
altera o funcionamento atual. A mesma plataforma de técnicos é utilizada; não
precisa contratar um servidor. Não foi alterada sua planilha remotamente nesta entrega.

## Atualizar o Apps Script uma vez

1. Na planilha existente, abra Extensões → Apps Script.
2. Faça uma cópia do código anterior para backup. Substitua Code.gs pelo arquivo
   completo google-apps-script/Code.gs deste pacote. Salve.
3. Em Implantar → Gerenciar implantações, edite a implantação atual, escolha **Nova
   versão** e implante. Preserve o endereço /exec, execução como proprietário e
   permissões da implantação já usada. Não crie outro endereço sem necessidade.
4. Reabra a planilha e escolha **D-Max → Preparar aba Assinaturas**.
5. Não apague propriedades do script nem gere novamente chaves já configuradas.
   As abas Tecnicos e as senhas pessoais existentes continuam funcionando.

## Cadastrar uma instalação

Cabeçalhos preparados pelo menu:

| controller_id | instalacao | situacao | aviso_em | prazo_final | mensagem |
| --- | --- | --- | --- | --- | --- |
| identificador exibido no D-Max | Garagem do cliente | regular | automático | automático | Regularize sua assinatura com o fornecedor. |

Copie controller_id de raiz → Técnicos globais de **cada Raspberry**, nunca o MAC,
nome de rede ou identificador de carregador. Cada D-Max precisa estar autorizado
na plataforma, com chave configurada e consulta ativada. O cadastro de técnicos
continua global; a assinatura é individual por instalação. Uma linha por D-Max.
Não insira senhas ou chaves nas células. Compartilhe a edição apenas com o fornecedor.

## Avisar, vencer e regularizar

- Troque situacao para **pendente**. Na próxima consulta autenticada, a plataforma
  emite o aviso e fixa dez dias corridos (240 horas). aviso_em e prazo_final são
  preenchidos pelo serviço, em ISO/UTC. O D-Max mostra o prazo no fuso da instalação.
- O Raspberry salva o aviso e continua contando sem internet. Reinícios não criam
  outro prazo. Editar a mensagem não reinicia os dez dias. Desativar a consulta ou
  apagar a linha não cancela um aviso já recebido.
- No vencimento, deixa de aplicar demanda, prioridade, rampa e horário de ponta.
  Solicita **ClearChargingProfile apenas dos IDs usados pelo D-Max**; não envia um
  perfil de potência máxima, não apaga rede/OCPP e não restaura fábrica. Preserva
  limites nativos do equipamento e perfis externos com outros IDs.
- Cada conector mostra confirmação ou **liberação pendente**. Em ausência de OCPP,
  rejeição, timeout ou resposta Unknown, o D-Max não declara liberação confirmada e
  tenta novamente quando possível. Não pode garantir remotamente a potência que o
  firmware vai adotar. Homologue o comportamento de cada modelo antes de uso.
- Após confirmação, envia RemoteStartTransaction sem perfil limitador para um
  veículo conectado, quando o modelo suportar. O próprio carregador controla o
  fim físico da recarga; StopTransaction fecha o histórico, sem reiniciar no mesmo
  cabo até desconectar. Não se usa SoC como garantia universal de término.
- A página permanece disponível para aviso, supervisão, histórico e manutenção.
  Pausa/emergência/aprendizado gerenciados ficam indisponíveis no modo nativo.
- Para regularizar, altere situacao para **regular**. Na próxima consulta válida,
  remove o aviso e retoma o controle com reinicialização dos perfis. Sem internet
  não há como receber uma regularização nova. Não apague a linha para liberar.

O aviso na visão geral/planta ao vivo se atualiza sem recarregar a página; nas
outras páginas aparece ao abri-las/atualizá-las. O intervalo normal é o mesmo da
consulta de técnicos (por padrão cerca de cinco minutos). Bloquear a chave de um
D-Max impede novas consultas, não revoga por si só um aviso já persistido.

## Autenticação, relógio e limites

O aviso tem HMAC-SHA256, domínio próprio, identificador de instalação e revisão
crescente, usando uma chave derivada da chave privada de sincronização do aparelho.
Alterações/replays antigos não podem renovar o prazo. Chaves não são enviadas na
telemetria e não ficam nas células. Somente o serviço autenticado emite avisos;
não há botão para o cliente cancelar a cobrança localmente.

A contagem combina relógio do sistema, tempo monotônico e maior horário persistido.
Ao detectar retrocesso de mais de cinco minutos durante pendência, considera o
prazo vencido, sem conceder tempo adicional. Avanço incorreto do relógio também pode
vencer antes: ajuste NTP/fuso e relógio corretamente antes da ativação. Uma nova
confirmação regular deve ser enviada depois de corrigir o relógio.

**Use um RTC com bateria no Raspberry Pi 4 para medir tempo desligado sem internet.**
Sem RTC ou referência externa confiável é impossível garantir quantas horas se
passaram com o equipamento sem energia. Este recurso não impede reinstalação,
restauração de backups antigos ou manipulação por alguém com root no Linux/acesso
ao cartão. Não apresentá-lo comercialmente como inviolável.

O funcionamento nativo remove a proteção de demanda fornecida pelo D-Max. A
instalação precisa suportar esse estado e ter suas proteções elétricas próprias.
Esta versão não inclui um meio de pagamento nem consulta bancos: o fornecedor
marca a situação na planilha. Cotas e disponibilidade do Apps Script se aplicam.
