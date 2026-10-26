# Contrato de sincronização — primeira versão

O EnergyCube D-Max envia HTTPS POST para a URL configurada, uma vez por minuto, com `Authorization: Bearer <EV_CLOUD_TOKEN>`. Verificação TLS permanece habilitada. Não há redirecionamento automático, nem envio direto ao Grafana.

```json
{
  "controller_id": "identificador-persistente-da-instalacao",
  "records": [
    {
      "id": "uuid-do-registro",
      "ts": 1793012400.0,
      "kind": "minute",
      "payload": {
        "minute_utc": 1793012400,
        "source": "DC-01:1",
        "avg_kw": 230.0,
        "min_kw": 180.0,
        "max_kw": 250.0,
        "samples": 60,
        "energy_kwh": 3.8
      }
    }
  ]
}
```

O servidor deve autenticar a instalação, verificar que a credencial tem acesso ao `controller_id`, inserir em transação com unicidade `(controller_id, id)` e responder **somente depois do commit**:

```json
{"acknowledged_ids": ["uuid-do-registro"]}
```

Uma retransmissão idêntica deve retornar a mesma confirmação sem duplicar dados. Conteúdo diferente sob o mesmo identificador deve ser rejeitado. O controlador aceita confirmação parcial, remove da fila apenas os IDs reconhecidos desse lote e mantém os demais. HTTP 2xx sem confirmação válida não autoriza exclusão. Campos `ts` e `minute_utc` preservam o horário de origem, não o horário de recepção.

`source=site` corresponde ao multimedidor da entrada; outros sources representam conectores. A energia total da instalação é obtida pelo registrador `energy_import_kwh`, quando habilitado e válido. Na ausência de energia medida, `energy_kwh=null`; isso não deve ser tratado como zero físico. Na primeira leitura válida o acumulador recebe uma linha de base. Reinícios ou mudanças de mapa reiniciam essa linha de base, evitando atribuir energia desconhecida ao intervalo. Resets são registrados como eventos.

Sessões e intervenções são transmitidas como eventos (`session_start`, `session_end`, `limit_changed`, etc.). O resumo final de sessão preserva kWh e pico medido. Eventos de sessão interrompida sinalizam falhas de continuidade.

Sugestão para o banco central: PostgreSQL com timestamp UTC e payload JSONB, índice único por instalação/registro e views para o Grafana. A API receptora, autenticação por instalação, banco central e dashboards serão implementados e homologados quando o destino de nuvem for definido.
