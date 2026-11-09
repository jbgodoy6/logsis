# D-Max 0.8.1 · Cartões compactos e paleta configurável

- Grafana: quatro cartões por linha, altura reduzida de 12 para 7 unidades.
- Desenhos de contorno pequenos, com potência e veículo como informações principais.
- Estados padrão: cinza desconectado/não confirmado, azul conectado, verde carregando,
  vermelho alarme. Cor escolhida nos Thresholds do cartão modelo atinge os repetidos.
- Indicador de comunicação separado, com ícone e texto, distinguindo perda OCPP de
  perda de comunicação entre controlador e nuvem. Sem inferir a causa da rede.
- Campos novos da view PostgreSQL são acrescentados sem apagar dados ou credenciais.
  O dashboard novo aceita a telemetria anterior (0.8.0), sem exigir atualização do Pi.
- D-Max local recebe os desenhos e disposição compactos; controle OCPP inalterado.

Verificação: 147 testes Python passaram (incluindo PostgreSQL real, OCPP e o ciclo
simulado do instalador). Navegador real: alteração da cor de carregamento para uma
cor de teste foi salva no Grafana provisionado, persistiu após recarregar e atingiu
o SVG; os padrões foram restaurados após a verificação. Planta local autenticada
verificada sem JavaScript em desktop e celular; prévia independente também.

Persistem os limites do piloto: sem homologação física ARM/Windows/carregadores,
sem publicação automática em conta Supabase. Veja CORES-E-VISUAL.md para atualizar
a view, importar os assets e configurar/salvar a paleta no Grafana.
