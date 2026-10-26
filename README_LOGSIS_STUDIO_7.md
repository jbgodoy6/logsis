# LogSis Studio 7 — DSE7420 / DSE8610

Editor e gerador de configuração LogSis com **perfis fixos alinhados aos dashboards DSE7420 V42 e DSE8610 V4**. Interface escura, navegação lateral, busca de canais, conferência de compatibilidade e exportação conjunta do BIN e do Grafana.

[Baixar programa completo](LOGSIS_STUDIO_7_1.zip) · [Interface](LOGSIS_STUDIO_7_INICIO.png) · [Mapa de canais](LOGSIS_STUDIO_7_MAPA.png) · [Exportação](LOGSIS_STUDIO_7_EXPORTACAO.png)

Na versão **7.1**, os três contadores de manutenção foram acrescentados ao final de cada perfil, preservando todas as posições existentes e a correção das chaves do DSE7420 da 7.0.1. Para atualizar um BIN anterior, abra-o, reaplique o perfil do modelo e gere novamente o BIN e o JSON. Os novos contadores precisam ser coletados pelo equipamento e armazenados nas respectivas colunas SQL; o Studio não altera seu banco.

## Abrir o programa

1. Baixe o ZIP e **extraia a pasta inteira**.
2. Tenha **Python 3.10 ou superior com Tkinter/Tcl-Tk** instalado. O instalador oficial do Python para Windows oferece Tcl/Tk.
3. No Windows, abra **INICIAR_LOGSIS_STUDIO.bat**. Também pode executar `python LogSis_Studio.py` dentro da pasta extraída.

A interface e a geração de arquivos usam a biblioteca padrão do Python. O teste TCP também funciona sem pacotes adicionais. Para testar RS485/USB, instale o componente opcional: `python -m pip install -r requirements-serial.txt`. Use o driver correspondente ao seu adaptador USB/RS485.

## Fluxo recomendado

1. Escolha **DSE7420** ou **DSE8610**. O novo projeto já recebe o perfil completo, sem lacunas.
2. Em **Equipamento & rede**, configure Slave ID, comunicação, identificação e, conforme a instalação, Wi-Fi/GSM. As credenciais de um BIN aberto são preservadas; novos projetos não trazem senhas pré-preenchidas.
3. Ajuste os valores nominais e use **Recalcular limites e reaplicar perfil**, se necessário. Essa ação pede confirmação porque substitui textos e limites das MDBs e desativa os slots fora do perfil. Outros parâmetros do equipamento são preservados.
4. Em **Mapa de variáveis**, pesquise o canal e ajuste textos/limites. Endereço, função e bit são definidos pelo perfil e ficam visíveis para conferência. A seleção e os filtros da tabela não mudam a ordem de gravação.
5. Em **Validar & exportar**, informe nome da planta, tabela SQL, UID do datasource e, opcionalmente, UID do dashboard existente. Clique em **Exportar BIN + Grafana**.

**Salvar BIN** grava somente a configuração do equipamento. Os dados de destino do Grafana entram no pacote exportado, não no BIN. O Studio não envia a configuração ao equipamento nem importa automaticamente o dashboard em um servidor.

## O pacote de cada planta

A exportação ZIP contém:

- `DSE7420.bin` ou `DSE8610.bin`: configuração do LogSis.
- `DSE7420_GRAFANA.json` ou `DSE8610_GRAFANA.json`: um dashboard responsivo, com tabela e datasource configurados.
- Arquivo `_MAPA.csv`: relação entre canal Grafana, coluna SQL, índice BIN, endereço, função, bit, divisor e unidade.
- `COMPATIBILIDADE.json`: mapa e hash do BIN para rastrear a correspondência.
- `LEIA-ME.txt`: identificação do pacote e instruções.

Importe o JSON pelo Grafana. Para atualizar um dashboard existente, informe seu UID no Studio e use **Import (Overwrite)**. Com UID vazio, o Studio gera uma identidade estável por **modelo + tabela**, evitando que plantas diferentes substituam o mesmo dashboard. O botão **Usar UID do dashboard de referência** preenche o UID das versões já usadas nesta conversa; use-o somente para atualizar essa planta.

A tabela aceita nomes como `id_269086509881540` ou `public.id_planta`. O UID inicial do datasource é `zKW_ld27k`; ajuste ao UID real do seu PostgreSQL no Grafana. A troca de modelo ou abertura de outro BIN limpa tabela/UID de destino para evitar reaproveitar uma planta anterior.

## Correspondência que não pode deslocar

**MDB01 no Grafana = coluna `mdb1` = índice 0 do BIN (`MDBA_ADDR0`, etc.).** O número mostrado no Studio segue a numeração do Grafana; o índice zero do BIN aparece nos detalhes e no CSV.

| Faixa Grafana | DSE7420 — 56 canais | DSE8610 — 55 canais |
|---|---|---|
| MDB01–07 | Motor | Motor |
| MDB08–28 | Grandezas do gerador | Grandezas do gerador |
| MDB29–35 | Frequência e tensões da rede | Frequência e tensões do BUS |
| MDB36 | Horímetro acumulado | Horímetro acumulado |
| MDB37 | Energia acumulada | Energia acumulada |
| MDB38–39 | Partidas e manutenção | Partidas e manutenção |
| MDB40 | Modo | Modo |
| MDB41/42/43 | Warning / Trip / Shutdown | Warning / Trip / Shutdown |
| MDB44–51 | Entradas A–H | Entradas A–H |
| MDB52 | K1, rede na carga | Disjuntor de acoplamento ao BUS |
| MDB53 | K2, gerador na carga | Manutenção 1 / 1836 |
| MDB54 | Manutenção 1 / 1836 | Manutenção 2 / 1840 |
| MDB55 | Manutenção 2 / 1840 | Manutenção 3 / 1844 |
| MDB56 | Manutenção 3 / 1844 | Reservado/desativado |

O DSE8610 continua **sem concessionária e com apenas um gerador desenhado**. Seu BUS é medido independentemente do estado do disjuntor. Os slots restantes até 100 são desativados no perfil completo.

Endereços centrais: modo 772; alarmes no registro 774, com BIT10/11/12; horímetro 1798; energia 1800. As fontes se distinguem pelo MDB29: rede/1059 no DSE7420 e BUS/1091 no DSE8610. No DSE7420, MDB52/K1 (rede) usa endereço **48653** e MDB53/K2 (gerador) usa **48654**. No DSE8610, MDB52 (disjuntor de acoplamento) permanece em **48659**. Os estados continuam 0 = aberto e 1 = fechado.

A exportação bloqueia posições, endereços, funções, bits ou Slave IDs incompatíveis e slots extras ativos. Ao abrir um BIN divergente, o Studio **aponta o problema e não reorganiza nem corrige os canais silenciosamente**. Aplique explicitamente o perfil para normalizar. Textos e limites podem ser editados sem alterar a posição dos canais.

## Escalas e modos

As escalas seguem os dashboards aprovados: pressão /100; tensões, correntes e frequências /10; potências /1000; FP /100; horas /3600; energia /10 inicialmente. O **divisor de energia** pode ser alterado no formulário de exportação e é aplicado ao JSON, ao CSV e ao teste local. Os campos **H, VR e SM não são usados como divisores de engenharia**.

Modo MDB40: 0 STOP, 1 AUTO, 2 MANUAL, 3 teste com carga, 6 teste sem carga, 7 OFF. Os textos DH/DM/DL do BIN são comparativos de três faixas; o nome exato dos seis modos vem do valor bruto interpretado no Grafana/Studio, não de uma suposição sobre a faixa DH.

Os limites nominais iniciais são 380 V L–L, 60 Hz, bateria 24 V e 1800 rpm. São valores para geração que devem ser ajustados à instalação, não uma identificação automática do equipamento. Limites de tensão/frequência/RPM usam ±10%; bateria usa 80–120%. Outros limites seguem o perfil importado do mapa auditado. Os valores TH/TL ficam explícitos e editáveis; alterar um limite não altera a escala da medição.

Os recursos do Grafana preservam Brasília, traços nos valores indisponíveis, cores de alarme, curvas com pontos, posições filtradas e as regras aprovadas de horas/kWh do período. O BIN define os registros e bits; as conversões de engenharia continuam no dashboard.

## Manutenções e nomes personalizados

Manutenções 1, 2 e 3: registros **1836, 1840 e 1844**, função LogSis 30 (FC03, dois registradores), /3600 para horas. Os valores zero ou negativos indicam vencimento. Valores indisponíveis mostram traço, sem substituir por uma leitura anterior válida. MDB39 continua sendo o contador geral até manutenção e não foi substituído.

No desenho, manutenção próxima deixa o gerador amarelo; vencida, laranja. Um texto separado mostra o nome da manutenção. Os alarmes Warning, Trip e Shutdown têm prioridade sobre a cor de manutenção; a indicação textual de manutenção permanece. Dados ausentes não são tratados como manutenção em dia.

O limite inicial é **50 h**, ajustável no formulário de exportação do Studio ou na variável `Manutencao_Alerta_h` do Grafana. O valor vale para os três contadores; não reprograma os intervalos no controlador. Na comparação, 0 é vencida; acima de 0 e até o limite, próxima; acima do limite, em dia.

Em **Dashboard settings → Variables**, altere `Nome_Manutencao_1`, `Nome_Manutencao_2`, `Nome_Manutencao_3` e `Nome_Entrada_A` até `Nome_Entrada_H`. Por exemplo: “Troca de óleo” ou “Porta da sala”. Os nomes de manutenção aparecem nos cartões e no aviso junto ao gerador; os nomes das entradas aparecem nos instrumentos. As variáveis de nome não mudam endereços nem polaridade.

No Studio, editar **Nome / descrição no Grafana (DM)** nos respectivos canais preenche essas variáveis ao exportar. Esse texto também é gravado no DM do BIN. Reaplicar o perfil redefine textos e limites, conforme a confirmação do programa; ajuste os nomes após essa etapa.

Origem dos três registros: `LOGSIS_DSE7420_MAPEAMENTO_TECNICO.csv` recebido no pacote original, página GenComm 7, offsets 44/48/52. O perfil DSE8610 reutiliza esses registros comuns GenComm; o BIN DSE8610 recebido não continha os três canais e não constitui confirmação independente deles no firmware. A escala em segundos segue a memória técnica enviada. A implementação foi validada com dados sintéticos, sem leitura física do DSE8610.

**Entradas analógicas usadas como digitais:** os arquivos recebidos documentam apenas os estados A–H. Os endereços dos estados analógicos digitais ainda não foram fornecidos; não foram atribuídos registros por aproximação nem confundidas as leituras dos sensores com estados de contato.

## Teste Modbus

A tela **Teste Modbus** executa somente leituras, sem comandos de partida, parada ou fechamento de disjuntores. Informe a conexão e selecione o canal.

- Funções LogSis 3/4 leem um registrador por FC03/FC04. Funções LogSis 30/40 leem dois registradores por FC03/FC04; não são enviadas como FC30/FC40 no fio.
- O resultado mostra registradores, valores signed/unsigned, bit extraído e engenharia conforme o canal.
- A ordem High→Low/Low→High selecionada vale para a leitura local; não é um novo parâmetro inventado para o BIN.
- TCP trata respostas fragmentadas, transação, protocolo, Slave ID, tamanho e exceções. RTU confere Slave ID, função, quantidade e CRC.
- A leitura ocorre em uma thread separada; os controles Tk são atualizados pela fila na thread da interface.

Os endereços e bits seguem os mapas usados no projeto. Variantes/firmwares, escalas efetivas do coletor e comportamento do equipamento devem ser conferidos em campo; a validação de software não substitui o teste físico. Nos alarmes, o BIT configurado permite ao coletor entregar 0/1 ao Grafana; não se aplica uma segunda extração na consulta.

## Validação da versão

30 testes automatizados: 21 de núcleo/transporte e nove fluxos reais da interface Tk. Cobrem geração, reabertura, preservação de parâmetros/encoding/CRLF/BOM, divergências, slots reservados, limites, exportação, UID por planta, gravação atômica, TCP em simulador local e RTU com respostas simuladas.

O teste de integração **BIN → valores pelos slots → SQL do JSON exportado** passou nos dois modelos, inclusive com valores diferentes para rede e BUS, bits de Warning/Shutdown e resultado de período **3,50 h / 18,00 kWh**. [Resultado](LOGSIS_STUDIO_GRAFANA_VALIDACAO.json).

A interface foi conferida em 1460×920 e 1120×740, com leitura local sem travar a janela. [Resumo da validação](LOGSIS_STUDIO_VALIDACAO.json). Testes executados em Linux com Tk, simuladores e PostgreSQL isolado; sem acesso ao controlador ou banco de produção.

Para desenvolvimento: `python -m unittest discover -s tests -p 'test_studio*.py' -v`. Os testes de interface exigem DISPLAY; a integração opcional usa o laboratório Docker: `python tools/validate_studio_grafana.py`.

As regras de manutenção foram verificadas no PostgreSQL para os dois modelos: normal, limite, próxima, zero, negativo, negativo em complemento de dois, sentinelas, falta de dados, ausência de coluna e prioridade de shutdown. [Resultado](LOGSIS_MANUTENCAO_VALIDACAO.json).
