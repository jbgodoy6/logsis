# DSE7420 V43 — entradas flexíveis e manutenção textual

[JSON](V43_IMPORTAR.json) · [ZIP](V43_IMPORTAR.zip) · [Manutenção próxima](DSE7420_V43_PROXIMA.png) · [Vencida](DSE7420_V43_VENCIDA.png) · [Entradas](DSE7420_V43_INPUTS.png) · [Celular](DSE7420_V43_CELULAR.png)

A manutenção aparece somente na indicação abaixo do gerador: amarela quando próxima, laranja quando vencida. O desenho mantém a cor determinada pelos alarmes Warning/Trip/Shutdown. Os três contadores, seus nomes personalizados e o limite de proximidade configurável foram preservados.

O PDF completo fornecido, GenComm 2.93, identifica as entradas flexíveis como digitais Q/R/S (p. 133, nota 6). Seus estados processados estão na tabela 8xxx/74xx da página 137: página GenComm 170, offsets 33/35/37.

| Entrada | MDB / coluna SQL | Endereço | Leitura |
|---|---|---|---|
| Q | MDB57 / mdb57 | 43553 | FC03, 16 bits, processada |
| R | MDB58 / mdb58 | 43555 | FC03, 16 bits, processada |
| S | MDB59 / mdb59 | 43557 | FC03, 16 bits, processada |

0 = inativa, 1 = ativa. Leituras inválidas ou ausentes mostram traço. Os estados processados já consideram a inversão do DSE; não são contato aberto/fechado. Use quando a entrada estiver configurada como digital. A disponibilidade física depende da configuração e do firmware.

Configure `Nome_Entrada_Q`, `Nome_Entrada_R` e `Nome_Entrada_S` nas variáveis do Grafana ou o DM dos canais correspondentes no Studio. Os nomes são exibidos no painel 08 / Entradas flexíveis · uso digital.

Para atualizar: extraia o **LogSis Studio 7.2**, abra a configuração, reaplique o perfil do modelo e exporte novamente BIN + Grafana. Isso redefine os textos/limites das MDBs, conforme a confirmação do Studio; personalize os nomes após aplicar o perfil. Os três canais foram acrescentados ao final, sem deslocar os existentes. O coletor precisa gravar suas novas colunas SQL; o Studio não altera o banco.

A tabela começa em `id_dse7420` e é configurável por `Id_Logsis`. Para substituir o dashboard existente, mantenha seu UID e use Overwrite.

[Mapa conferido](DSE_GENCOMM_MAPA_CONFERIDO.json) · [Guia do Studio](README_LOGSIS_STUDIO_7.md) · [Validação SQL](LOGSIS_ENTRADAS_FLEXIVEIS_VALIDACAO.json) · [Validação visual](LOGSIS_MANUTENCAO_UI_VALIDACAO.json).
