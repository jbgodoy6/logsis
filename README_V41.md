# LOGSIS / DSE7420 — V41 Indicadores com traço

Substitui **###** por **—** nos valores de estouro/indisponíveis, incluindo os textos de reserva dos elementos Canvas, os mapeamentos de nulos e `noValue`.

Preserva as consultas, a validação dos valores, os cálculos de período, as posições K1/K2, os alarmes, as curvas e o horário de Brasília da V40. Mensagens específicas de diagnóstico permanecem como estavam.

Extraia [V41_IMPORTAR.zip](V41_IMPORTAR.zip) e importe **V41_IMPORTAR.json** usando **Import (Overwrite)**. Mantido o UID para atualizar o dashboard DSE7420 existente.

Conferidos JSON/ZIP e comparação estrutural com a V40: somente o texto substituído e a identificação da versão mudaram. Importado no Grafana isolado e verificada a exibição do traço nos indicadores indisponíveis, sem ### visível. [Prévia](V41_PREVIA.png).

Gerar: `python tools/build_v41_traco_indisponivel.py`.
