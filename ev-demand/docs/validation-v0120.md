# Validação D-Max 0.12.0 — 10/11/2026

Ambiente: Linux x86-64, CPython 3.12, Chromium, PostgreSQL e Grafana isolados.
Nenhuma alteração foi feita no Raspberry ou na conta Google do proprietário.
O checkout anterior e seus arquivos foram preservados.

## Resultados

- 233 testes Python passaram, zero falhas e zero ignorados, com as fixtures
  `DMAX_PI_PACKAGE` e `DMAX_TEST_POSTGRES_CONTAINER` habilitadas.
- Chromium: multimedidor, curva abaixo do medidor e antes dos carregadores,
  filtros preservados entre atualizações, tooltip por mouse/foco/toque,
  downloads PDF/CSV, ausência de erros de script e layout móvel sem transbordar.
- Gateway HTTPS local com certificado de fixture fixado: login, cookie Secure,
  formulários assinados, dados comprimidos e DOM estável; OCPP e configuração
  inicial bloqueados. Não é um teste do provedor público.
- Grafana: cores persistentes, SVGs e disposição dos cartões preservados.
- Apps Script exato distribuído executado em Node com doubles dos serviços
  Google: autenticação, credenciais fora de células, assinatura por equipamento,
  diretório remoto por ID, troca de URL, revisão e rejeição de duplicatas.
- Histórico: persistência entre aberturas do banco, resolução nominal de 5 s,
  mudanças de limite, real/simulado separados, zero versus ausência de medição,
  lacunas, extremos preservados na redução, filtros com fuso, CSV completo e
  exportação registrada na auditoria. Limpeza independente da outbox pendente.
- Supervisor: URL criada não é declarada conectada antes do registro de conexão,
  perda de todas as conexões gera offline; falha de certificado é reportada sem
  desabilitar TLS; reconexão com espera e erro sanitizado.
- Ativação/reativação/desativação/remoção em árvore temporária com systemd
  simulado: identidade antiga preservada, cliente corrompido recusado e
  configuração existente preservada.
- Instalador: ciclo de instalação/atualização/rollback em árvore temporária com
  pacote ARM64 real e dependências simuladas; não foi executado código ARM64 no
  host x86-64. Manifesto e assinatura Ed25519 do ZIP conferidos.

## Carga de um mês

Com 518.400 registros sintéticos em SQLite em disco, a consulta de 30 dias
retornou 518.399 amostras do intervalo e selecionou 300 pontos originais para
visualização. Tempo medido: 4,554 s; maior intervalo do heartbeat de 10 ms no
loop assíncrono: 19,2 ms. A consulta usa conexão de leitura própria em worker e
cache limitado; o CSV não reduz as amostras. Esse resultado é do executor e não
estima o tempo de um cartão SD/Raspberry. O banco real precisa de espaço livre.

## Cliente Cloudflare e limites da homologação

cloudflared 2026.10.7 Linux ARM64, binário oficial incluído no ZIP. SHA-256:
`3df43aedc9ff291d1735b5cb576cb97e0b157488796db2e32b28aecabb445775`.
Referência de origem e licença em deploy/cloudflared-release.json e
cloudflared-LICENSE. Hash conferido contra a página oficial da release, além da
arquitetura ELF AArch64 e do manifesto assinado do pacote.

A variante oficial x86-64 da mesma versão foi executada para conferir as opções
da CLI. A tentativa real de criar Quick Tunnel falhou na resolução de
api.trycloudflare.com no executor; não se criou nem homologou uma URL pública.
A implantação real do Apps Script também não foi acessada. O proprietário deve
atualizar a implantação existente e validar a linha da planilha e o login por
uma rede externa depois de instalar. Não há garantia de liberação pelo Fortinet
ou de disponibilidade de Quick Tunnel; nenhuma política de rede foi contornada.

## Reproduzir

```sh
DMAX_PI_PACKAGE=/workspace/dmax-release/D-Max-Raspberry-0.12.0.zip \
DMAX_TEST_POSTGRES_CONTAINER=dmax-demo-postgres-1 \
/workspace/.venvs/dmax/bin/python -m unittest discover -s tests
/workspace/.venvs/dmax/bin/python tests/run_browser_v090.py tests/browser_v0120.cjs
/workspace/.venvs/dmax/bin/python tests/run_browser_remote.py
node tests/browser_grafana_colors.cjs
```

Os paths e contêineres acima são fixtures de desenvolvimento, não comandos para
rodar no Raspberry do cliente. Credenciais efêmeras dos testes não são empacotadas.
