# Validação D-Max 0.10.0 — 10/11/2026

Base de desenvolvimento: Linux x86-64, CPython 3.12, Chromium e contêineres
PostgreSQL 16/Grafana 12.2 isolados. Não foi acessado o Raspberry do cliente.

## Verificações da entrega

Com dependências instaladas pelo `requirements.lock` e `--require-hashes`:

```sh
DMAX_PI_PACKAGE=/workspace/dmax-release/D-Max-Raspberry-0.10.0.zip \
DMAX_TEST_POSTGRES_CONTAINER=dmax-demo-postgres-1 \
/workspace/.venvs/dmax/bin/python -m unittest discover -s tests -v

/workspace/.venvs/dmax/bin/python tests/run_browser_v090.py tests/browser_v0100.cjs
node tests/browser_grafana_colors.cjs
```

O primeiro comando executa 199 testes, sem exclusões quando as duas fixtures
indicadas estão presentes. Inclui os testes anteriores e novas regressões para:

**Resultado desta entrega: 199 passaram, zero falhas e zero testes ignorados.**
Os testes de navegador do D-Max e Grafana também passaram.

- Prazos exatos 15/30/40 dias, reinícios, assinatura inválida, replay, reconexão e
  precedência da pendência financeira.
- Administração sem acesso operacional ao simulador, sessões renovadas e
  revogação, flash consumido e planta única na página principal.
- PDF com seleção múltipla, acumulado/subtotal e energia real/simulada separada.
- Filas preservadas por origem; PostgreSQL recusa origem incorreta, token
  inválido, lotes inválidos e acessos não autorizados, mantendo idempotência.
- SQLite consistente, identidade e credencial raiz preservadas ao restaurar;
  upload validado e atomizado, CSRF, permissões, assinatura e caminhos de ZIP.
- Comando OCPP rejeitado/aceito separado da potência medida e leitura zero;
  erro do multimedidor preserva idade, mas bloqueia novas admissões.
- OCPP por WebSocket com estações simuladas, reduções antes de novo início e
  retorno nativo com aceite/rejeição/ausência de comunicação.
- Ciclo de instalação, importação, atualização sem desinstalar, backup,
  retorno após falha de dependência, desinstalação preservando dados e
  confirmação de limpeza, tudo em árvore temporária. Python/SQLite e cópias
  são reais; UID, pip ARM64 e systemd são simulados nessa fixture.

O navegador verifica desktop/celular, leituras compactas com desenho maior,
campos preservados durante atualização, aviso que some em cinco segundos e não
volta, banners financeiros sem recarregar, PDF, exclusão com histórico e versão.
O navegador Grafana confirma persistência da paleta e aplicação aos desenhos SVG
na demonstração isolada.

O pacote usa 60 wheels ARM64/universais para CPython 3.11, 3.12, 3.13 e 3.14,
baixadas do PyPI com os hashes do lock. ZIP e manifesto foram conferidos; o
manifesto tem assinatura Ed25519. Não inclui banco do cliente, chave privada de
publicação, credenciais de demonstração ou arquivos de teste. SHA-256 do ZIP está
no arquivo adjacente `.zip.sha256`, evitando autorreferência no pacote.

## O que esta validação não comprova

- Boot/systemd, reinício automático, watchdog físico, RTC e execução nativa no
  Raspberry ARM64. Wheels para ARM64 foram obtidas e verificadas; não executadas
  neste host x86-64.
- Homologação física por marca/modelo OCPP, incluindo liberação dos próprios
  perfis e início/fim nativos após bloqueio comercial.
- Disponibilidade, configuração e credenciais de Supabase/Grafana de produção.
  A demonstração local usa outro banco, volume, credencial e fonte de dados.
- Atualização do Apps Script já publicado pelo proprietário. O código e seu
  contrato são testados; o serviço remoto e a aba Assinaturas exigem conferência
  administrativa na conta que possui a planilha.

O checkout anterior `/workspace/logsis` permanece intacto. A chave privada de
atualização fica fora do repositório e precisa ser guardada de forma segura para
futuras publicações. Nenhuma senha raiz foi alterada.
