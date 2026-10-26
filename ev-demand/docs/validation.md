# Validação da versão 0.1 — 26/10/2026

Ambiente executado: Linux x86-64, Python 3.12.14, Chromium. Dependências utilizadas registradas em `requirements.lock`.

## Verificado

- 27 testes automatizados com `python -m unittest discover -s tests -v`.
- Alocação para 60 carregadores de 320 kW com orçamento de 15.000 kW.
- 200 cenários determinísticos de potências, prioridades, mínimos, limites de circuito e compartilhamento.
- Redução confirmada por telemetria antes do início de outra recarga.
- Teste com servidor HTTP/WebSocket real e dois clientes OCPP 1.6J simulados: BootNotification, perfis, RemoteStartTransaction, StartTransaction e MeterValues.
- Uso de TxProfile ligado à transação ativa para atualizar seus limites.
- Leitura Modbus TCP de float32 contra um servidor local de teste.
- Bloqueio de horário, fila, emergência, pausa, retorno e teste temporário de limite zero.
- Autenticação, bloqueio de requisição de outra origem, recuperação de admin pelo root e não exposição de hashes.
- Retenção preserva registros não confirmados, mesmo além de 30 dias; registros confirmados podem expirar.
- Fluxo no navegador: primeira configuração, login, demonstração, navegação, cadastro de carregador e resposta ao aumento da carga do cliente.
- Layout em 1440 × 1100 e 390 × 844; ausência de transbordamento horizontal no celular e de erros JavaScript/console no fluxo final.
- `pip check` sem dependências quebradas; `node --check` para o JavaScript.

## Ainda não verificado

- Execução nativa no Windows e no Raspberry Pi 4/ARM64.
- 60 conexões físicas ou 60 conexões WebSocket simultâneas em ensaio prolongado.
- Modelos reais de carregadores, smart meter, Autocharge, potência mínima, zero e retomada.
- Recuperação após corte físico de energia, desgaste de SSD e volume real de 30 dias.
- Serviço de nuvem, autenticação por instalação, banco central e Grafana.
- Limites de corrente por fase e demanda faturável por janela de integração.

Esta é uma versão de validação. O comissionamento físico e os limites de proteção precisam ser concluídos antes de operação em uma instalação real. Consulte as restrições detalhadas no README.
