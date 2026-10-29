# Revisão dos controladores e proposta para o próximo Studio

Data: 29/10/2026. Escopo: análise, sem alteração do código do Studio, biblioteca Android ou dos BIN/JSON operacionais já entregues.

## Diretriz aprovada pelo usuário: preservar convencionais

Os perfis convencionais existentes ficam como estão, usando DSE7420 como referência aprovada. Não renumerar canais, retirar medições, trocar endereços ou modificar o comportamento desses perfis como consequência da criação dos eletrônicos. Somente alterações explicitamente já validadas pelo usuário entram no conjunto convencional; toda mudança adicional precisa ser apresentada e validada antes. Os achados desta auditoria são pendências de revisão, não autorização automática para mudar o legado.

Criar Eletrônico / ECU-CAN como **novo perfil**, com identidade própria e BIN/JSON correspondentes. Não sobrescrever o perfil convencional nem seu dashboard. Reutilização de código é permitida, mas a exportação convencional deve continuar compatível com sua referência preservada.

A preferência por mapas sequenciais aplica-se aos novos mapas e às renumerações já solicitadas/validadas, como DSE8620 sequencial. Não compactar retroativamente o DSE7420 convencional ou outros mapas preservados. Registrar separadamente a migração dos históricos quando houver nova revisão.

Os pacotes específicos já entregues, como DSE8620 sequencial e AGC150 ECU, são referências de trabalho para a consolidação futura; continuam fora do Studio até a etapa de implementação. A aceitação da organização não substitui os testes físicos pendentes.

## Organização dos novos perfis eletrônicos

Manter o perfil convencional existente e acrescentar uma opção eletrônica nos controladores/aplicações que realmente monitoram motor:

- **Convencional:** sensores locais, entradas analógicas/multifunção configuradas, RPM, bateria, combustível, horas, partidas e manutenção disponível.
- **Eletrônico / ECU-CAN:** núcleo elétrico e operacional compartilhado, mais os dados de motor que o controlador publica e a ECU instalada fornece. Permitir sensores locais complementares, sem presumir que todo motor eletrônico forneça todas as medições pela CAN.

Isto é uma seleção de capacidades de um único gerador de mapas, não duas cópias de programa ou milhares de dashboards mantidos manualmente. BIN, JSON e mapa de conferência devem nascer do mesmo contrato final de canais, com um identificador de revisão comum.

Não criar variantes de motor artificiais para **DSE8660, DSE8680, AGC150 MAINS ou AGC150 ATS**. Nesses casos, selecionar função elétrica, topologia, TCs, fontes e contatos. No AGC150 ENG há motor, mas não presumir geração elétrica. A opção ECU depende de suporte do hardware/firmware e documentação do modelo; não prometer CAN em qualquer revisão de qualquer controlador.

A proposta aplica-se também aos DSE7420/8620 e demais modelos do catálogo, mas a revisão técnica desta rodada examinou os **10 perfis** abaixo; não representa teste físico de todos os modelos do catálogo.

## Resultado por família

| Perfil atual | Canais atuais no Studio | O que manter | O que corrigir ou completar antes da próxima geração |
| --- | ---: | --- | --- |
| DSE8610 | 58 | Gerador → acoplamento → BUS comum → carga; sem companhia. Instrumentação, horas/kWh por período, entradas e manutenção | Corrigir sentinelas unsigned recebidas como inteiro negativo; usar uma única amostra final coerente; rever campos EIC opcionais por firmware e configuração; migrar o mapa legado para papéis de dados explícitos |
| DSE8660 | 58 | Rede e BUS independentes, contatos simétricos com saídas comuns; quadro local com três tensões fase-fase, frequência e potência | Confirmar firmware MkII e TCs/origem da potência. Não zerar potência porque o contato está aberto. Não aplicar automaticamente a remoção de fases do DSE8620. Não incluir motor/ECU/manutenção de motor |
| AGC150 GEN, rede + gerador | 84 | Tensões, correntes, totais, modos e retornos nativos | Incorporar de forma controlada a revisão ECU entregue em pacote separado; priorizar motor e resumo de alarmes; tornar explícitos No Regulation, MANUAL do protocolo e o rótulo SEMI-AUTO do equipamento; apresentar função elétrica separadamente do modo |
| AGC150 GEN, gerador + BUS | 82 | Gerador acoplado ao BUS e carga; sem torre da companhia | Aplicar a mesma separação convencional/ECU, sem importar origem de potência de rede de outra aplicação; conferir sincronismo, permissões e estados nativos |
| AGC150 MAINS | 67 | Rede/BUS e dados próprios da aplicação | Selecionar topologia real, contatos e origem dos TCs; não copiar o motor de GEN nem assumir que todo MAINS tenha a mesma conexão de saída do DSE8660 |
| AGC150 ATS | 63 | Fontes S1/S2 e leituras que a coluna ATS da tabela autoriza | Completar somente estados de contatos documentados para ATS; não reutilizar bits GB/MB de GEN. Os contatos atualmente permanecem desconhecidos por falta de mapeamento específico implementado |
| AGC150 ENG | 43 | Motor, horas, serviço e entradas | Perfis convencional/ECU conforme recursos; retirar qualquer instrumentação de geração não aplicável; tratar No Regulation e validade de cada leitura de motor |
| SGC420 Mk II | 81 | Medições de carga, tensões das fontes, estados próprios SGC e codec FLOAT32/CDAB | Selecionar dados EIC adicionais documentados; confirmar unidades que a tabela omite, horímetro e contadores compostos antes de fechar escala/composição; reduzir alarmes por conjunto opcional, preservando resumo nativo |
| CGC412 | 53 | Dados do gerador e sinais previstos no H2 | O manual H2 recebido não marca BB/rede nem retorno MB como implementados neste modelo. A topologia física com companhia não autoriza inventar telemetria. Para ECU, obter H5/H7 antes de inserir registros de motor |
| CGC413 | 66 | Gerador + companhia/BB, contatos e modos próprios | Identificar sensores locais e unidades; obter H5/H7 para pacote ECU. Não copiar o modo semiautomático ou as classes de falha do AGC150 para o CGC |

As contagens são do Studio atual, **não a proposta de quantidade final**. Os pacotes AGC150 ECU e DSE8620 sequencial entregues separadamente ainda não foram incorporados ao Studio. O ME96SS é independente e deve continuar um módulo de medição separado, sem se tornar parte obrigatória de qualquer AGC150.

## Problemas reproduzidos nesta revisão

As reproduções usaram PostgreSQL isolado e dados sintéticos, sem acesso à planta do usuário.

1. **DSE8610: -1 em uma tensão unsigned de 32 bits aparece como -0,1 V.** O padrão de bits `0xFFFFFFFF` deve indicar leitura não implementada, não tensão negativa. A correção deve respeitar tipo e largura: -1 pode ser uma potência signed legítima em outra variável.
2. **DSE8610: posição antiga pode reaparecer quando o último registro não tem o estado do disjuntor.** No cenário ensaiado, um 0 antigo foi reaproveitado. O painel atual deve indicar posição desconhecida quando o registro final não confirma a posição. Históricos continuam históricos; não se deve apagar medições anteriores.
3. **AGC150 GEN/GEN_BUS/MAINS/ENG: bit 1 de 1019 resulta em “OUTRO MODO”.** A planilha identifica esse bit como No Regulation; ele precisa ser apresentado explicitamente. O bit 2 consta como MANUAL na tabela. A equivalência do rótulo SEMI-AUTO do painel deve ser registrada por modelo/firmware, não extrapolada ao CGC.
4. **AGC150: canal bruto da ECU continua utilizável por consumidores não protegidos.** Com temperatura 65535 e validade 0, a saída validada fica nula, mas o campo bruto ainda devolve 65535. Todos os cartões e históricos de engenharia precisam consumir a leitura validada.

Os 69 testes existentes passaram, e as consultas principais dos 10 perfis executaram. Os casos acima foram acrescentados como cenários de auditoria e expõem lacunas que a suíte atual não cobre. Passar os testes existentes não elimina essas lacunas.

## Regras que precisam ser comuns

- **Zero é leitura válida** e permanece 0, 0 A, 0 kW etc. Não convertê-lo globalmente em traço.
- **Traço significa dado ausente/inválido**, conforme sentinelas, tipo, largura e validade nativa de cada fabricante. Não copiar os sentinelas DSE para qualquer DEIF sem documentação.
- **Motor parado exige estado documentado.** Estouro de sensor sozinho não comprova motor parado. Se o motor estiver parado, o estado aparece como tal e os sensores indisponíveis ficam em traço. Se estiver funcionando, mostrar indisponibilidade da leitura, sem falsificar a parada ou criar um alarme sintético.
- **Quadro atual: uma amostra final coerente** no período selecionado para contatos, tensões e estado. Não montar uma imagem juntando últimas leituras válidas de horários diferentes.
- **Contatos:** distinguir comando, LED, retorno ON/OFF e estado lógico de alimentação. Tratar dados ausentes, estados contraditórios e transições.
- **Unifilar:** preservar a linguagem gráfica DSE7420 e respeitar a topologia de cada aplicação. O DSE8660 acordado usa saídas unidas; isso não transforma todo MAINS em uma transferência igual.
- **Cor da linha:** fonte medida antes do contato; trecho de saída inferido apenas com tensão da fonte e estado coerente do contato, incluindo o nó comum das duas saídas. Não afirmar medição direta onde ela não existe.
- **Alarmes:** resumo nativo prioritário; pacote de detalhe opcional. A retirada de palavras de alarmes não pode deixar warning/trip/shutdown incorretos. Separar manutenção dos alarmes operacionais com evidência suficiente; contagem de alarmes sozinha não identifica severidade.
- **Manutenção:** nomes configuráveis e aviso próximo/vencido; indicação sob o gerador, sem usar a cor do motor como manutenção. DSE: habilitar temporizadores realmente disponíveis. AGC/CGC: dois service timers documentados. SGC: não inventar três temporizadores a partir de um alarme de filtro.
- **Horas/kWh por período:** base válida anterior ao início e final dentro do filtro; alternativa parcial explícita; tratar ausência de amostras, reinício, rollover e diferenças de unidade. Não substituir energia acumulada por média de potências.
- **Contadores de duas partes:** identificar base, ordem e escala por fabricante. A composição decimal solicitada para o ME96SS não autoriza usar 10000 no SGC; dois endereços também não provam automaticamente base 65536.
- **Gráficos:** pontos preservados, interpolação linear e linhas conectadas conforme a regra já aprovada. Manter unidades coerentes por eixo e qualidade das amostras.
- **Tempo:** America/Sao_Paulo e conversão conforme o tipo efetivo da coluna de tempo, sem subtrair três horas duas vezes.
- **Entradas:** nomes editáveis e escolha analógica/digital conforme configuração e manual. Não supor que todo sensor flexível de qualquer família corresponde a Q/R/S.
- **Slots:** somente canais selecionados, em sequência 1…N, até 100. Ao renumerar, BIN e JSON mudam juntos e a revisão do mapa precisa impedir misturar históricos com significados diferentes nas mesmas colunas.

## Pacote de motor recomendado

Núcleo convencional: óleo, arrefecimento, combustível, alternador de carga, bateria, RPM, horas, partidas e manutenção, limitados ao que existe no equipamento. Entradas multifunção devem receber nome, unidade, função e origem configurados; não deduzir o sensor só pelo número da entrada.

Pacote ECU: pressão de óleo, temperatura do arrefecimento e do óleo, pressão de alimentação do combustível, pressão de rail quando disponível, consumo instantâneo, temperatura do combustível, carga do motor, temperatura de escape, pressão/temperatura de admissão, níveis de óleo/arrefecimento e água no combustível. Incluir somente os itens documentados e efetivamente publicados pela ECU. Diagnósticos DTC e pós-tratamento ficam opcionais, com nomes e estados próprios.

Exemplos que já estão documentados para AGC150 GEN/ENG na planilha recebida:

| Leitura | Endereço FC04 | Divisor de engenharia | Validade |
| --- | ---: | ---: | --- |
| Alimentação de combustível | 26022 | 100 | 26901 bit 9 |
| Pressão de rail genérica | 620 | 1 | Validar sentinela do registro; não substituir por endereço específico Cummins/Wise10 |
| Consumo instantâneo | 26009 | 10 | 26900 bit 6 |
| Temperatura combustível | 26005 | 1 | 26900 bit 10 |
| Temperatura óleo | 26004 | 10 | 26900 bit 11 |
| Carga motor | 26015 | 1 | 26900 bit 0 |

As unidades de pressão e temperatura acima seguem a configuração do controlador (bar/psi, °C/°F). Seleção de unidade de apresentação e conversão matemática são coisas distintas; não trocar somente o sufixo.

No SGC420, a planilha contém EIC em 131–157: temperatura do óleo 133, pressão de rail 139, consumo 140/141, entre outros. Várias unidades aparecem como “-”; 140/141 não têm montagem explicitada. Estes itens são **candidatos**, não conversões prontas. Preservar a decodificação FLOAT32/CDAB e a escala 0,1 dos contadores 39–49 já descritos, mas confirmar a interpretação com valores reais.

No CGC412/413, H2 remete os registros de motor 593–641 e 900–999 aos manuais H5/H7. A edição eletrônica fica dependente desses documentos e dos recursos do controlador; não reutilizar os endereços AGC como prova.

## Fluxo proposto no Studio

1. Selecionar fabricante, modelo e revisão/firmware, quando relevante.
2. Selecionar aplicação e topologia reais.
3. Nas aplicações com motor, selecionar Convencional ou ECU-CAN; permitir sensores locais complementares.
4. Selecionar somente os recursos instalados: TCs, neutro, entradas/flexíveis, sensores, temporizadores e detalhes opcionais de alarmes/ECU.
5. Definir nomes, nominais, relações TC/TP, unidades e comunicação. Ao abrir backup, preservar parâmetros de rede, credenciais e campos não relacionados ao mapa.
6. Exibir prévia do mapa final sequencial, origem, escala, validade e dependências; impedir exportar combinações incompatíveis.
7. Exportar BIN e JSON do mesmo contrato, com mapa/relatório de conferência. Datasource, Id_Logsis, nomes e UID continuam configuráveis.
8. Registrar a troca de revisão do mapa. Históricos anteriores precisam da interpretação anterior ou de migração explícita; não aplicar uma nova numeração retroativamente.

Campos mínimos do contrato: modelo/aplicação/variante, slot, endereço/base, função, largura, sinal, ordem de palavras/bytes, divisor/offset, unidade de origem/apresentação, bit de validade, sentinelas, papel do dado, dependência de hardware e fonte documental.

## Antes de implementar

- Levar as quatro lacunas reproduzidas à validação específica antes de alterar os perfis convencionais preservados. Implementar a proteção correspondente nos novos perfis eletrônicos, sem regressão do legado.
- Consolidar somente as alterações convencionais já validadas, preservando os demais comportamentos atuais.
- Definir os pacotes essenciais e opcionais por perfil, sem número final de slots decidido antes da seleção.
- Conferir firmware, recursos e leituras reais de cada unidade; a tabela genérica não prova que todo registro exista naquela revisão.
- Obter os manuais complementares CGC H5/H7 e a documentação específica necessária para os itens SGC sem unidade/composição definida.
- Validar a correspondência dos nomes de modos AGC com o painel, mantendo os bits originais do protocolo como referência.
- Verificar capacidades reais do firmware LogSis para FC02 e leitura/empacotamento de inteiros de 32 bits.
- Executar regressões por família e cenários inválido/zero/parado/funcionando/aberto/fechado, além de conferir a interface desktop/celular.

## Evidências e limites

Fontes: GenComm 2.93 recebido em PDF; planilha AGC150 4189341212 revisão Y / SW 1.38.0; planilha SGC420 MkII 4189341402 revisão C / SW R19.0; CGC400 opção H2 4189340865A recebido em PDF. A revisão usa os documentos já disponíveis, código e fixtures locais; não representa nova pesquisa web nem teste físico.

Arquivos desta revisão: `INVENTARIO_ATUAL.csv` registra o mapa atual; `REVISAO_TECNICA.json` registra os modelos, testes e reproduções. Estes documentos não são um novo BIN, um dashboard pronto nem uma alteração do Studio.
