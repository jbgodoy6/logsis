# DSE7420 V42 — manutenções e nomes configuráveis

[Baixar JSON](V42_IMPORTAR.json) · [ZIP](V42_IMPORTAR.zip) · [Manutenção próxima](DSE7420_V42_PROXIMA.png) · [Vencida](DSE7420_V42_VENCIDA.png) · [Celular](DSE7420_V42_CELULAR.png)

Três contadores acrescentados sem deslocar nenhuma MDB existente:

| Manutenção | Coluna SQL | Registro | Função | Escala |
|---|---|---|---|---|
| 1 | mdb54 | 1836 | 30 / FC03, dois registros | segundos /3600 → h |
| 2 | mdb55 | 1840 | 30 / FC03, dois registros | segundos /3600 → h |
| 3 | mdb56 | 1844 | 30 / FC03, dois registros | segundos /3600 → h |

Use o perfil atualizado do **LogSis Studio 7.1** para gerar o BIN e o dashboard juntos. Os novos campos precisam ser coletados e gravados no banco. Enquanto faltarem colunas ou leituras, o dashboard mostra traço e indicação sem dados. Configure `Id_Logsis` na importação/configuração das variáveis; o valor inicial é `id_dse7420`.

- `Nome_Manutencao_1` a `Nome_Manutencao_3`: nomes nos cartões e no aviso do desenho.
- `Nome_Entrada_A` a `Nome_Entrada_H`: nomes dos instrumentos de entradas.
- `Manutencao_Alerta_h`: proximidade em horas, inicialmente 50 h.

Zero ou negativo indica manutenção vencida; acima de zero e até o limite, próxima; acima do limite, em dia. Gerador amarelo para próxima e laranja para vencida. Warning, Trip e Shutdown do controlador têm prioridade de cor; o aviso de manutenção permanece separado. Nenhum contador de manutenção é calculado a partir do horímetro do período: são registros de tempo restante do controlador.

O mapa técnico original do DSE7420 traz 1836/1840/1844. Esses registros comuns GenComm também foram aplicados ao perfil DSE8610; o BIN DSE8610 recebido não os continha e não houve validação física desse firmware. [Escopo e detalhes](README_LOGSIS_STUDIO_7.md).

Estados das entradas analógicas usadas como digitais permanecem pendentes: os arquivos enviados só documentam as digitais A–H.

Validação: [PostgreSQL](LOGSIS_MANUTENCAO_VALIDACAO.json) · [Grafana desktop/celular e nomes personalizados](LOGSIS_MANUTENCAO_UI_VALIDACAO.json).
