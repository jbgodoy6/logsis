# D-Max v0.2.3 — pacote Raspberry/Linux com início automático

Verificado no ambiente de desenvolvimento:

- 44 testes do aplicativo aprovados em Linux x86-64 com Python 3.13; validações anteriores também cobrem 3.12 e 3.14.
- Dependências de `requirements.lock` disponíveis como wheels Linux ARM64/aarch64 para Python 3.13. Esse download não é execução em ARM64.
- `bash -n instalar-raspberry.sh` e modo não mutante `--check` sem erros.
- Unidade `systemd` validada estaticamente com `systemd-analyze verify`, usando uma raiz temporária com caminhos executáveis de validação. Nenhum serviço foi instalado no host de desenvolvimento.
- Servidor iniciado de fato com `DMAX_HOST`, `DMAX_PORT` e `EV_DB_PATH`; GET local de `/api/setup` retornou JSON esperado.

O boot físico e o reinício pelo systemd não foram executados em um Raspberry Pi. Devem ser verificados após instalar no destino, assim como acesso à porta serial, TLS, desempenho e recuperação após falta de energia. A instalação local continua sendo piloto até homologar o hardware.
