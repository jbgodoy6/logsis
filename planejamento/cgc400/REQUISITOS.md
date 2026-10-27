# CGC400 — escopo e parâmetros identificados

Preparação documental, sem alteração do Studio ou dos perfis entregues. Fonte: 4189340865A, Option H2, 42 páginas. O documento cobre expressamente CGC412 e CGC413 com software 1.00.0 ou posterior (p.3); não presumir todos os produtos com nome CGC400.

## Variantes e disponibilidade

- CGC412 e CGC413 compartilham medições do gerador e motor, estados GB e dois temporizadores de serviço.
- CGC413 acrescenta medições de tensão/frequência do barramento, estados MB, AMF/LTO e entradas adicionais indicadas nas colunas de disponibilidade.
- Não tratar tensão do BUS como corrente/potência da companhia. O quadro fixo apresentado não documenta corrente, kW, kVA, kvar ou kWh locais de companhia equivalentes aos dados do gerador.
- Estado MB ou medição BB não prova, isoladamente, a topologia física da instalação; escolher desenho coerente com a configuração real.

## FC04, registros fixos

| Endereço | Parâmetro | Observação |
| --- | --- | --- |
| 501–506 | Tensões gerador LL e LN | V |
| 507–509 | Frequências gerador | Hz/100 conforme fonte; validar divisor com amostra |
| 510–512 | Ângulos entre fases gerador | Deg/10 |
| 513–515 | Correntes gerador | A |
| 516–519 | Potência ativa fases e total | kW |
| 520–523 | Potência reativa fases e total | kvar |
| 524–527 | Potência aparente fases e total | kVA |
| 528/529 | Energia reativa exportada | Hi/Lo, kvarh |
| 530/531, 532/533, 534/535 | Energia ativa exportada dia, semana, mês | Hi/Lo; contadores com reinício periódico |
| 536/537 | Energia ativa exportada total | Hi/Lo, kWh; candidato para período |
| 538 | FP gerador | cosPhi/100 |
| 539–545 | Tensões e frequência BB | Somente CGC413 |
| 548, 551–553 | Ângulos BB e BB/gerador | Somente CGC413 |
| 554/555, 556/557 | Horímetros absoluto e relativo | Hi/Lo; validar montagem, unidade e sinal |
| 558–560 | Contagens de alarmes | Total, não reconhecidos, ativos reconhecidos |
| 563, 564 | Operações GB e MB | MB somente CGC413 |
| 566 | Tentativas de partida | Não confundir com partidas bem-sucedidas |
| 567 | Alimentação DC | V/10 |
| 569–572 | Serviço 1 e 2 | Horas e dias, respectivamente; verificar contagem e estado |
| 573–574 | Cos-phi e indutivo/capacitivo | Fonte distingue 0 indutivo / 1 capacitivo |
| 576 | RPM | Motor |
| 580–585 | Entradas multifunção 6/7/8 | Leitura elétrica e leitura escalada configurada |
| 586–589 | Entradas multifunção 58/59 | Somente CGC413 |
| 700 | Potência ativa nominal | Conforme conjunto nominal configurado |

Energia adicional em 790–809: consultar integralmente a p.19. Há descrições de energia reativa rotuladas [kWh] na fonte; preservar a inconsistência e validar unidade, não corrigir silenciosamente. Faixas encaminhadas ao manual H5/H7 exigem esse documento para leituras de motor/EIC, alarmes e escalas complementares. Há sobreposição literal de faixas não usadas e H5/H7 na p.18: não assumir implementação de todos os endereços.

## Estados e alarmes FC04

- Páginas 20–30: inventariar cada bit com disponibilidade CGC412/413, sem transportar a enumeração do AGC150.
- 1018 bit 4 GB ON, bit 11 GB OFF; CGC413 também bit 1 MB ON, bit 12 MB OFF. Bit 6 motor funcionando. Bit 13 BB Hz/V OK apenas CGC413.
- 1019 bit 0 BLOCK, bit 1 MANUAL, bit 3 AUTO, bit 4 TEST, bit 5 ISLAND. CGC413 inclui bit 6 AMF, bit 10 load takeover e bit 15 AMF active. São bits de modos/funções distintos, não um único enum de código DSE.
- 1015 bits 0 e 1: alarmes service timer 1/2. Não presumir três manutenções; manter indicação de manutenção independente da cor do gerador.
- A área configurável e a tabela de alarmes descrevem campos de estado; verificar largura/legenda antes de classificar severity. Não inferir cores apenas do nome do alarme.

## FC02 e multifunção digital

- Página 37: GB ON endereço 0, MB ON endereço 1 (413), running 3; modos e disponibilidade conforme tabela. FC04 oferece vários estados equivalentes para priorização no coletor atual.
- Página 38: digitais físicas 10–15 em 22500–22505; digitais 56/57 em 22506/22507 só 413; emergência 20 em 22516.
- Multifunção em modo digital: 59/58 em 22581/22582 só 413; 8/7/6 em 22591/22592/22593 para ambos. Não renomear como Q/R/S.
- A faixa textual 22508–22015 é inconsistente no PDF; não importar como faixa válida.
- Relés 23001–23008 estão na tabela de leitura FC02; saída não equivale a posição física do disjuntor.

## Contrato de dados e implementação futura

- O documento declara valores inteiros assinados na área configurável (p.8). Não foi identificado FLOAT32/CDAB no quadro fixo consultado. Pares de contadores são explicitamente Hi/Lo; não usar o decoder IEEE754 dos SGC nesses pares.
- Confirmar por campo sinal, largura, unidade, palavra alta/baixa e sentinelas. Combinação Hi/Lo deve preservar os 16 bits de cada palavra, com tratamento de sinal somente após montagem e conforme definição.
- Preferir quadro fixo FC04 às áreas configuráveis, para evitar dependência de mapeamento local oculto.
- Somente leitura: quadros FC16, FC15 e parâmetros graváveis permanecem referência. Configuração e comando remoto não fazem parte deste escopo.
- Adaptar suporte RTU/ASCII de acordo com o coletor real; p.6 indica RS485 9600/8N1 e parâmetros 7510/7520. Não presumir Modbus TCP nativo.
- Aplicar orçamento de 100 MDB, exportação casada, nomes editáveis, BRT, períodos com base anterior, travessão para inválidos e dashboard único responsivo, conforme requisitos gerais DEIF.
- Pendentes: modelo exato instalado, firmware, topologia, recursos de motor H5/H7, semântica de alarmes, testes de leitura real e montagem de contadores. A análise documental não equivale a homologação física.

TEXTO_FONTE.txt conserva a extração integral. INDICE_LINHAS_TABELAS.csv é um índice candidato com página e linha, não um mapa executável nem uma transcrição validada de células.
