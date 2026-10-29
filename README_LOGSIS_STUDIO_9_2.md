# LogSis Studio 9.2 — Sistel

Esta versão preserva os 17 perfis anteriores e acrescenta 10 perfis Eletrônico/ECU-CAN e o DSE8620 com TC único, sequencial. O aplicativo gera BIN e JSON do Grafana juntos, além do mapa CSV e relatório de compatibilidade.

## Abrir no Windows

1. Instale Python 3.10 ou superior com a opção Tcl/Tk.
2. Extraia **todo** o ZIP em uma pasta. Não abra o programa dentro do ZIP.
3. Abra `LogSis_Studio.py`. Se a associação de arquivos não iniciar o Python, execute na pasta: `py -3 LogSis_Studio.py`.
4. Para teste serial RS485, instale a dependência opcional: `py -3 -m pip install -r requirements-serial.txt`. A interface e a geração de arquivos não exigem esse pacote.

Falhas de abertura exibem uma mensagem e tentam salvar um diagnóstico em `%LOCALAPPDATA%/LogSisStudio/logs`, ou na pasta temporária. Não é necessário desativar antivírus. A distribuição contém código Python e dados; não inclui EXE, BAT, PowerShell ou instalador.

## Selecionar o perfil

- **Convencional:** mantém o mapa anterior. Os BINs e dashboards dos 17 perfis originais foram comparados com a versão 9.1.4 e permanecem iguais.
- **Eletrônico / ECU-CAN:** novo perfil para DSE7420, DSE8610, DSE4520 MkII, DSE6120 MkII, DSE6320, DSE7320 MkII e DSE8620; e AGC150 GEN com companhia, GEN com BUS e ENG. Os canais dependem de CAN, firmware e recursos efetivamente suportados na unidade. Registros não implementados aparecem como traço.
- **DSE8620 · TC único · sequencial validado:** mapa de 65 canais, com corrente do TC e totais de rede. O mapa anterior de 74 canais continua disponível para compatibilidade, identificado no seletor.
- **DSE8660, DSE8680, AGC150 MAINS/ATS:** permanecem como aplicações elétricas, sem criar um motor ou uma variante CAN fictícios.

SGC420 MkII e CGC412/413 permanecem com os perfis recebidos. O SGC já possui algumas leituras ECU na tabela atual. Sua expansão EIC contém unidades/contadores que precisam de confirmação. Para o pacote ECU adicional dos CGC, o H2 recebido remete aos manuais H5/H7 ainda não disponíveis. Não foram inventados endereços, escalas ou variantes eletrônicas desses modelos. SGC120/410, GEN-H e BTB continuam fora do catálogo conforme o escopo acordado.

## Abrir um backup e gerar o par de arquivos

Abra o BIN atual antes de selecionar a nova variante. Ao mudar o perfil de um backup, o Studio preserva rede, campos desconhecidos, comunicação e Slave ID. Dentro do mesmo modelo, também preserva nomes e limites dos canais que têm endereço/função/bit idênticos. Os novos canais recebem o mapa da variante selecionada.

Confira os valores nominais, sensores realmente instalados e campos editáveis. Na tela Validar & exportar, informe nome da planta, tabela `id_...`/`public.id_...`, datasource e UID, quando necessário. Exporte o pacote e use **o BIN e o JSON do mesmo pacote**.

Cada variante tem um identificador próprio. Ao trocar a numeração do mapa, os registros históricos continuam com a interpretação antiga: não aplique retroativamente a nova leitura das colunas. Separe a revisão/histórico ou migre-o explicitamente.

Um novo perfil parte dos padrões do catálogo. Para preservar as configurações de uma instalação, use o backup dessa instalação; não substitua um backup por um modelo de outra planta.

## Leituras e apresentação

Os novos perfis eletrônicos incluem, conforme a tabela de cada modelo: pressão de alimentação de combustível, pressão de rail, consumo, temperaturas, carga do motor, níveis, água no combustível, horas, partidas, modos e manutenção. DSE usa a página 5 de instrumentação estendida GenComm. AGC usa os registros EIC e seus bits de validade, com rail genérico 620.

Pressão de combustível não é automaticamente pressão do rail. Nos DSE, kPa é convertido para bar quando indicado; rail permanece MPa conforme a escala do registro. No AGC, pressão e temperatura seguem as unidades configuradas no controlador/ECU. Não mude só o sufixo para simular uma conversão.

Zero continua zero. Sentinelas e validade nativa produzem traço. Motor parado depende de RPM válido ou estado nativo, nunca apenas de um sensor inválido. Warning, trip e shutdown mantêm prioridade; manutenção tem indicação separada. O perfil AGC eletrônico usa resumo das classes de falha e manutenção, sem a lista completa de proteções individuais do perfil anterior.

No AGC, os bits de 1019 permanecem documentados no mapa: bit 1 No Regulation apresentado como MANUAL sem regulação; bit 2 MANUAL do protocolo apresentado como SEMI-AUTO conforme o padrão acordado. A função elétrica (AMF, ilha, potência fixa etc.) é separada do modo. Confirme a terminologia no firmware instalado.

A planta segue a linguagem visual DSE7420, com topologia própria de cada aplicação. O modo convencional não foi redesenhado. No eletrônico, o quadro atual usa uma amostra final coerente do período; históricos mantêm pontos e linhas lineares. O horário é America/Sao_Paulo. Horas e kWh por período usam base válida anterior ao filtro, com indicação de período parcial quando necessário.

O multimedidor Mitsubishi de uma instalação específica continua independente: ele não é acrescentado automaticamente a todo perfil eletrônico do AGC.

## Verificação

Foram verificados abertura/interface Tk, todos os perfis e pacotes de exportação, preservação dos mapas anteriores, consultas em PostgreSQL isolado e importação/renderização representativa no Grafana em computador/celular. Os relatórios acompanham o pacote. Esses testes não substituem conferência no controlador real e não representam execução nativa em Windows.
