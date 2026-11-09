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

