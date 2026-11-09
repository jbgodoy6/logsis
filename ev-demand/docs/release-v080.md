# D-Max 0.8.0 — piloto de supervisão visual e nuvem

## Alteração

Acrescenta Planta ao vivo ao console existente, com desenhos locais em SVG para
carregador, carro/cabo e multimedidor. Mantém páginas e credencial raiz existentes.
Exporta inventário e estado por conector, associações de veículo conhecidas, todas
as grandezas atuais do medidor, minutos agregados e eventos selecionados. A fila é
persistida em SQLite: estado coalescido e eventos recentes têm prioridade sobre
minutos antigos. Índices específicos evitam ordenar toda a fila offline a cada
verificação. As sessões consultadas para a planta são somente as ativas.

O receptor Supabase valida token exclusivo por controlador e confirma lotes em
transação PostgreSQL. Views de leitura separam informação atual de dado antigo;
sem comunicação não se elimina equipamento. Dashboard Grafana Canvas nativo repete
cartões pelo cadastro e muda a cor conforme alarme/comunicação. Credenciais nunca
são transmitidas no inventário. Auditoria sensível fica local e recebe apenas uma
confirmação opaca no protocolo de exportação.

## Verificação

- 146 testes passaram em Python 3.12 / Linux x86_64, incluindo OCPP por WebSocket,
  permissões e recuperação existentes, entrega/ACK, backlog offline e alarmes OCPP.
- PostgreSQL 16 real: bloqueio por token incorreto/revogado, ausência de permissão
  anônima, usuário Grafana sem leitura de tokens nem escrita, lotes atômicos,
  idempotência, inventário offline, novo carregador, rejeição de snapshot antigo e
  invalidação da potência quando o controlador fica desatualizado.
- Contrato do handler TypeScript: oito cenários sob Node com remoção de tipos e
  simulação do runtime Deno/HTTP. Não substitui teste em Edge Function hospedada.
- Grafana OSS 12.2.0 real / Chromium: campos e SVGs carregados sem erro JavaScript;
  carregador inserido durante a visita ganhou cartão sem recarregar a página.
- D-Max autenticado em Chromium com JavaScript desativado: primeiro cadastro,
  login, simulação, Planta ao vivo e arquivos estáticos; sem transbordamento de
  largura em 1440 e 390 pixels. Prévia independente também verificada nessas larguras.
- Ciclo do instalador/importador/desinstalador contra o ZIP real em filesystem e
  serviços simulados; manifesto e dependências ARM64 verificados. Não é execução
  nativa ARM nem ativação de systemd/hardware nesta máquina.

## Limitações

Sem criação/publicação em conta Supabase real. Sem homologação física de Raspberry,
carregadores ou multimedidor. Sem teste Windows nativo. Tarifas e cotas Supabase
não foram verificadas ao vivo (pricing retornou HTTP 403); ver guia de capacidade.
O pacote é para piloto e requer configurar credenciais, TLS, limpeza, permissões e
backup antes de uma entrega de produção. O Grafana fornecido é OSS autohospedado;
não pressupõe hospedagem gratuita irrestrita de banco, Grafana ou serviço externo.
