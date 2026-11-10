# Entregue na 0.12.0 — curva histórica auditável na Visão geral

Solicitado em 10/11/2026 após a entrega da 0.10.0. **Somente registrar agora;
não implementar, alterar o pacote publicado ou gerar versão para este pedido.**

- Posicionar a curva no topo da área de dados da Visão geral, imediatamente
  abaixo do multimedidor e antes dos cartões do parque de carregadores.
- Permitir consultar a curva por período, com início e fim selecionáveis e
  horários no fuso da instalação.
- Armazenar histórico local persistente por até um mês, adotando 30 dias como
  referência de projeto, com limpeza automática dos dados mais antigos.
  A política de descarte desse histórico deve ser independente da fila de envio
  à nuvem: não apagar registros pendentes de confirmação para cumprir a janela.
- Ao passar o mouse, mostrar data/hora e os valores registrados naquele instante,
  incluindo demanda total, potência dos carregadores, outras cargas e limite
  operacional vigente. Prever consulta equivalente por toque no celular.
- Exportar relatório do período selecionado, com a curva e seus dados de origem.
  Definir a apresentação e os formatos na implementação; o formato não foi
  escolhido pelo usuário nesta solicitação.
- Tornar a consulta auditável: preservar timestamps, origem real/simulada,
  qualidade/ausência de medição e valores efetivamente registrados; não apresentar
  interpolação como leitura real. Registrar mudanças do limite para representar
  corretamente o limite de cada instante, sem aplicar o limite atual ao passado.
- Manter origens real e simulada separadas, atualização ao vivo sem piscar e
  persistência entre reinícios. Definir resolução/amostragem e eventuais agregações
  de forma explícita para os 30 dias, considerando recursos do Raspberry Pi 4.

Situação na 0.10.0: a curva usa os últimos 180 pontos em memória e não oferece
consulta histórica por período, exportação própria ou tooltip. Os relatórios
atuais de sessões não substituem o histórico da curva.
Essa pendência permaneceu aberta na 0.11.0. O usuário autorizou a implementação
na 0.12.0: entregue com 30 dias locais, resolução nominal de 5 s, separação real/simulado,
filtros, tooltip/toque e PDF/CSV. Consulte release-v0120.md e validation-v0120.md.

# Escopo retomado da conversa anterior

Os ajustes aprovados foram retomados na 0.10.0. Consulte release-v0100.md e validation-v0100.md. Implantação real de nuvem, atualização do Apps Script publicado, RTC e homologação dos carregadores físicos dependem da instalação do proprietário e não foram presumidos. O histórico abaixo é mantido como registro.

# Atualização 0.9.0

Incluídos: exclusão de veículos preservando histórico, relatórios PDF por período/veículo/carregador, multimedidor ampliado, suporte à porta 80 e avisos de assinatura por instalação com contagem offline e solicitação de funcionamento nativo. Ver release-v090.md e assinaturas-v090.md. Homologação física por modelo OCPP permanece necessária.

# Melhoria solicitada: incluída na atualização 0.8.5

Envio imediato implementado com fila durável e proteção de edições durante envio. Versão instalada permanece fixa no rodapé. Veja release-v085.md para validação e limites.

# Pendências para a próxima atualização

Registradas em 09/11/2026 a pedido do responsável pelo D-Max. Não implementar nem
gerar nova versão somente para estas melhorias; incluir na próxima atualização.

- **Envio imediato de novos técnicos:** ao cadastrar um técnico no D-Max, acionar
  uma tentativa de sincronização com o Google Planilhas sem esperar a consulta
  periódica. Preservar a fila em falhas ou falta de internet e manter as consultas
  periódicas para receber alterações e bloqueios. O cadastro relatado pelo usuário
  foi enviado com sucesso após o intervalo: não houve falha confirmada de envio.
  Validar também cadastro seguido de edição/troca de senha durante um envio, para
  uma confirmação antiga não apagar alterações mais recentes da fila.
- **Versão instalada visível:** garantir que o usuário identifique facilmente a
  versão em algum local da página, preferencialmente em rodapé sempre visível no
  desktop e no monitor do Raspberry. A versão 0.8.4 já implementa rodapé fixo;
  conferir a presença e legibilidade na instalação real na próxima validação.

