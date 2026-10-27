# AGC150 Extended — inventário e requisitos de planejamento

Status: preparação documental. Não constitui mapa homologado, configuração do controlador, atribuição de slots MDB ou implementação no Studio/Grafana.

## Fonte, identidade e seleção

- Fonte primária: planilha DEIF 4189341212, revisão Y, software de referência 1.38.0; hash e contagens em FONTE_E_ESCOPO.json.
- Equipamento informado pelo usuário: AGC150 Extended. A planilha distingue aplicações, mas não comprova as licenças, os recursos habilitados e a possibilidade de trocar funções de uma unidade específica.
- Aplicações em escopo: GEN, MAINS, ATS, ENG. GEN-H e BTB excluídos por enquanto.
- Dentro de GEN: topologias gerador/companhia e gerador/BUS, condicionadas à configuração real. Em MAINS: companhia/BUS com MB e TB apenas quando presentes. ATS: fontes S1/S2 identificadas conforme instalação. ENG: motor sem geração elétrica presumida.
- Registrar versão de firmware, aplicação, configuração elétrica, opções, identificação da planta, tensão/frequência nominais, fases, relações TC/TP, unidade de temperatura/pressão, endereço do escravo e parâmetros TCP/RTU.
- Manuais oficiais de instalação, aplicação e protocolo ainda precisam ser consultados: acesso à internet bloqueado nesta sessão. Não registrar pesquisa externa como concluída.

## Medições elétricas e origem dos dados

- Inventariar tensões fase-neutro/fase-fase, frequência, correntes por fase, neutro/terra/quarto TC conforme função configurada.
- Potência ativa, aparente e reativa, por fase e total; distinguir FP de cos-phi, sinais, direção importação/exportação e indicação indutiva/capacitiva.
- Energia ativa/reativa e contadores totais e por direção disponíveis; não somar contadores de sentidos distintos sem definição explícita.
- Fonte principal, fonte secundária, BUS A/B, carga e agregados PMS devem ter identidade própria. Não renomear toda fonte secundária como companhia.
- Avaliar medições locais, quarto TC, transdutor e medições recebidas via gerenciamento de potência. Informar origem e disponibilidade; não apresentar agregado PMS como leitura local.
- Sincronismo: diferenças de tensão/frequência/ângulo, disponibilidade, estados de sincronização, compartilhamento de carga e potência de carga quando constarem para a aplicação selecionada.
- Percentuais, valores nominais, extremos, demanda e valores de alta resolução: identificar alternativas úteis, evitando duplicações e preservando resolução.

## Motor, contadores e manutenção

- RPM, bateria, pressão de óleo, temperatura do arrefecimento, combustível e demais sensores locais disponíveis.
- Medições EIC/J1939: temperaturas, pressões, consumo, combustível, pós-tratamento/DPF/SCR e diagnósticos disponíveis, vinculando bits de validade às leituras.
- Horímetro absoluto e relativo, minutos residuais se necessários e documentados, partidas, tentativas de partida e demais contadores pertinentes.
- Temporizadores de serviço 1 e 2 identificados na planilha; verificar separadamente horas, calendário, contagem e estados. Não inventar manutenção 3 nem presumir contagem crescente/decrescente.
- Nomes de manutenção, limiar de proximidade, indicação próxima/vencida e dados ausentes. Manutenção como texto sob o gerador; não altera a cor reservada aos alarmes.
- Horas e kWh por período: contador válido antes do início, amostra final dentro da seleção e alternativa parcial quando faltar histórico anterior. Diagnosticar reinício, rollover, lacunas, dados inválidos e relógio inconsistente. Não aplicar diferença temporal simples a um contador que zera periodicamente.

## Disjuntores, fontes, modos e estados

- Identificar GB, MB, TB, CB1/CB2 e acoplamentos aplicáveis. Registrar ON e OFF disponíveis, transição, estado desconhecido e incoerência quando houver sinais conflitantes.
- Separar retorno de posição, comando solicitado, permissão, disponibilidade, falha de abertura/fechamento e estado de LED.
- Não representar posição física com um comando remoto ou LED. Não inferir saída energizada apenas de um comando de fechamento.
- Modos: BLOCK, MANUAL, AUTO, TEST, No Regulation e outros somente conforme disponibilidade da aplicação; definir comportamento de nenhum/múltiplos bits ativos. Não reutilizar enumeração DSE.
- Motor parado, partida, funcionando, aquecimento, resfriamento, parada, emergência, pronto e indisponível conforme sinais documentados.
- Energização das linhas baseada em medições e topologia, com limiar e histerese definidos. Trecho sem medição deve indicar ausência de confirmação, sem falsa certeza.

## Alarmes e entradas/saídas

- Inventariar alarmes AC, motor/EIC, proteção elétrica, controlador e PMS; localizar resumos e lista de alarmes ativos. A descrição da planilha cita faixa 28000–28099, não enumerada na aba de registros: exige documentação complementar para decodificação.
- Classificar severidade e ação usando documentação DEIF; não transportar automaticamente warning/trip/shutdown do DSE nem tratar reconhecido como resolvido.
- Indicar alarme ativo, reconhecido e histórico quando disponíveis; cores de gerador condicionadas à classificação confirmada. Sem dados deve permanecer estado desconhecido.
- Entradas digitais, multifunção/analógicas, estados processados, unidades configuradas e validade; não equiparar entrada analógica a digital sem configuração demonstrável.
- Saídas digitais/relés e M-Logic em monitoramento; nomes editáveis por variável e no Studio, preservando identidade técnica para diagnóstico.
- Expansões, IDs de motores e nós PMS: identificar e selecionar por instalação, sem coletar milhares de registros sem necessidade.

## Contrato Modbus e coleta LogSis

- Preservar endereço Modbus e endereço PLC como campos distintos; base de endereçamento verificada, sem soma automática de 1 ou prefixo 300001/400001.
- Preservar FC, largura, signed/unsigned, ordem AB/ABCD, escala 10^-x, unidades e bit conforme a fonte. Convenção de bits e valores inválidos deve ser confirmada antes de converter.
- Priorizar leitura FC04 e estados equivalentes documentados em registradores. Avaliar FC02/FC01 somente se houver necessidade e suporte do coletor real.
- Comandos FC05/06/15/16 estão apenas em referência separada; monitoramento não autoriza comando remoto. Leitura de comando pode retornar zero e não constitui estado.
- Validar valores inválidos/sentinelas, flags EIC, timeout, exceção Modbus, dado congelado e qualidade; valor inválido vira nulo, apresentado como travessão.
- Orçar slots: Studio atual possui 100 canais MDB. Selecionar conjunto essencial e opcionais por aplicação antes de atribuir slots; não prometer exportar todo inventário em um BIN.
- Planejar agrupamento de leituras, cadência rápida/lenta, carga do barramento, retries, identificação do escravo e isolamento de falhas.
- Verificar suporte real do dispositivo LogSis a inteiros assinados, largura de 32 bits, bits e funções necessárias, além do simulador do Studio.
- Definir esquema por aplicação, versionamento, compatibilidade e migração. Não reutilizar MDB para outro significado sem contrato/versionamento explícito; BIN, CSV e SQL devem compartilhar o mapa final.

## Studio, Grafana e apresentação

- Seleção equipamento → aplicação → topologia → recursos instalados, com resumo de dependências e campos não disponíveis.
- Edição de nomes de entradas e manutenções, tabela Id_Logsis, datasource, UID por planta, nominais e limiares pertinentes.
- Validação e prévia do mapa; exportação conjunta de BIN, CSV, JSON Grafana e relatório de compatibilidade com fonte e limites.
- Um dashboard por planta, responsivo em desktop/celular. Unifilar coerente, contatos alinhados, carga identificada e leituras junto à fonte correta.
- Cartões compactos, unidades consistentes, indicadores de conectividade GSM/Wi-Fi vindos do LogSis (não presumidos como registros DEIF), barras de sinal e valor RSSI conforme unidade/origem.
- Hora America/Sao_Paulo, horário do último registro selecionado, distinção entre histórico e atual, idade/qualidade do dado e ausência de amostras.
- Históricos com pontos e linhas interligadas, interpolação linear, eixos/unidades compatíveis e lacunas tratadas com critério explícito; não sugerir continuidade real durante falha prolongada.
- Leituras e históricos de companhia: pendência separada do DSE8620, acrescentar correntes, kW, kVA, kvar, FP e energia suportada, preservando slots atuais e validando medição local/configurada.

## Verificação antes de entrega

- Conferência independente de endereços por aplicação, bit, escala, sinal, largura e unidades contra as fontes.
- Testes relevantes de BIN/CSV/SQL, limites de slots, valores negativos, ausência de campo, valores inválidos, reinícios de contador e períodos com operação real/simulada conhecida.
- Cenários de disjuntor aberto/fechado/transição/incoerente, falta/retorno de tensão, sincronismo e mudança de modo; confirmar prioridade de alarmes e manutenção independente.
- Conferência visual desktop/celular e regressão dos nove DSE existentes.
- Exportação sem senhas/chaves; monitoramento somente leitura. Validar artefato publicado e instruções de importação.
- Teste de campo no AGC150 Extended com aplicação, firmware e sensores identificados; separar validação documental, simulação e evidência física.

## Arquivos auxiliares

- INVENTARIO_LEITURAS.csv: todas as linhas de leitura da planilha marcadas para GEN, MAINS, ATS ou ENG, com localização e metadados originais; ainda não é seleção de canais.
- REFERENCIA_COMANDOS_NAO_IMPLEMENTAR.csv: áreas de comando separadas para impedir confusão com estados; nenhuma escrita implementada.
- FONTE_E_ESCOPO.json: proveniência, hash e contagens. Uma linha de variante não equivale a um endereço único.
