# LogSis Studio 9.1 — Sistel

Correção 9.1.2: contatos aberto/fechado/desconhecido com os mesmos vetores do DSE7420 e textos ABERTO/FECHADO/SEM DADOS. Nos modelos com indicação por LED no mapa, a posição exibida segue essa indicação do controlador, sem retorno físico independente. As ligações verticais têm largura visível no Canvas. As leituras locais mostram primeiro as três tensões entre fases, seguidas de fase–neutro, frequência, corrente L1, potência e FP; não se calcula tensão fase–neutro ausente. No DSE8660 preserva-se o caminho rede → MB → BUS → TB → carga.

Versão 9.1: dashboards organizados no padrão aprovado do DSE7420, incluindo os modelos de companhia/BUS e aplicações DEIF. O desenho mantém a topologia de cada controlador; mapas BIN e escalas permanecem iguais. O pacote desta versão contém código-fonte Python e recursos, sem iniciador BAT, executável EXE ou instalador. Para atualizar somente o Grafana, existe também uma entrega separada apenas com arquivos JSON.

Mantém a correção 9.0.1: leitura explícita em UTF-8 dos recursos DSE/DEIF, eliminando o erro `'charmap' codec can't decode byte 0x8d in position 18005` no Windows ao exportar. Extraia esta versão em uma pasta nova e mantenha os BINs já salvos.

Aplicativo desktop para preparar a configuração BIN do equipamento LogSis e exportar o dashboard Grafana correspondente. Identidade LogSis com o símbolo aprovado e cores azul e amarelo Sistel. Não configura o controlador DEIF/DSE nem envia comandos de partida ou disjuntores.

## Iniciar

1. Extraia a pasta inteira do ZIP, incluindo `logsis_studio/resources`.
2. No Windows, use Python 3.10 ou superior com Tcl/Tk. Abra `LogSis_Studio.py` com o Python, ou execute na pasta: `py -3 -X utf8 LogSis_Studio.py`.
3. Escolha o controlador/aplicação no seletor superior. Informe o Slave ID e os parâmetros do LogSis em Equipamento & rede.
4. Confira o mapa e ajuste nomes de entradas/manutenções e valores nominais. Endereços, funções e posições MDB são definidos pelo perfil.
5. Em Validar & exportar, informe nome da planta, tabela `Id_Logsis` e UID do datasource PostgreSQL. Exporte o pacote e importe seu arquivo `GRAFANA.json`.

O programa usa somente a biblioteca padrão. Para o teste opcional RS485/USB: `python -m pip install -r requirements-serial.txt`. O teste TCP aceita um gateway Modbus TCP; isso não significa TCP nativo em todos os controladores. O teste envia somente leituras FC02/03/04. openpyxl, Playwright, Docker e Pillow são ferramentas de desenvolvimento, não dependências do aplicativo distribuído.

## Perfis

| Perfil | Aplicação | Canais MDB |
| --- | --- | --- |
| DSE7420 | Companhia + gerador | 59 |
| DSE8610 | Gerador + BUS | 58 |
| DSE4520 MkII | Companhia + gerador | 57 |
| DSE6120 MkII | Companhia + gerador | 58 |
| DSE6320 | Companhia + gerador | 57 |
| DSE7320 MkII | Companhia + gerador | 57 |
| DSE8620 M2 | Companhia + gerador, com correntes/potências da companhia | 74 |
| DSE8660 | Companhia + BUS | 58 |
| DSE8680 | BUS 1 / BUS 2 | 58 |
| AGC150 Extended · GEN | Gerador + companhia | 84 |
| AGC150 Extended · GEN BUS | Gerador + barramento | 82 |
| AGC150 Extended · MAINS | Companhia + barramento | 67 |
| AGC150 Extended · ATS | Fontes S1 / S2 | 63 |
| AGC150 Extended · ENG | Motor | 43 |
| SGC420 Mk II | Companhia + gerador | 81 |
| CGC412 | Companhia + gerador; sinais limitados pelo manual | 53 |
| CGC413 | Companhia + gerador | 66 |

SGC120, SGC410, GEN-H e BTB ficaram fora desta versão por solicitação do usuário. Selecionar uma aplicação no Studio prepara o monitoramento; não muda a aplicação/licença do controlador.

## Compatibilidade e fontes

- AGC150: planilha DEIF 4189341212 revisão Y, software de referência 1.38.0. Registro e interpretação dependem da aplicação configurada.
- SGC420 Mk II: planilha DEIF 4189341402 revisão C, software R19.0.
- CGC412/413: PDF DEIF 4189340865A, Option H2, software 1.00.0 ou posterior. Entradas digitais/multifunção usam FC02, portanto exigem suporte à função LogSis 2 no coletor. Modos ATS do AGC também usam FC02.
- DSE: GenComm 2.93 e os mapas já entregues. DSE7420/8610 conservam seus arquivos e posições. Os primeiros 59 canais do DSE8620 foram preservados; correntes, potências, FP e energia da rede ocupam MDB60–74. BIN antigo DSE8620 de 59 canais é reconhecido e recebe os canais adicionais sem perder nomes/limites anteriores.

CGC412: a topologia companhia + gerador é mantida, mas a tabela fornecida não disponibiliza as medições BB e o retorno MB do CGC413. Esses campos ficam como desconhecidos, sem endereços inventados. CGC413 usa as medições BB como companhia na topologia de transferência solicitada. Sensores EIC/motor CGC nas áreas remetidas a H5/H7 aguardam esses manuais; não foram copiados do AGC.

AGC GEN: o conjunto secundário de tensão é BB; sua identificação como companhia depende da topologia selecionada. As potências da companhia em 592/759 dependem de quarto TC, transdutor ou PMS conforme configuração. Não representam garantia de medição trifásica local completa. SGC420: correntes e potências 23–38 são da **carga**, sem atribuição automática à companhia ou ao gerador.

## Inteiro bruto e FLOAT32 dos SGC

O LogSis não precisa ler uma variável float. Nos canais FLOAT32, ele lê duas palavras consecutivas com função LogSis 40 (FC04) e transmite o conteúdo bruto como um inteiro de 32 bits. A palavra do primeiro endereço ocupa os 16 bits altos desse inteiro, seguindo o contrato já usado por 30/40.

A consulta PostgreSQL do dashboard:

1. Valida que o valor recebido é um inteiro no intervalo de 32 bits, aceitando representação assinada ou não assinada.
2. Preserva os bits com módulo 2^32.
3. Troca as duas palavras para desfazer a ordem CDAB.
4. Decodifica sinal, expoente e mantissa IEEE754, inclusive subnormais.
5. Transforma NaN/infinito em nulo e aplica a escala do canal.

Exemplo verificável: FLOAT 123,0 = bits IEEE `42F60000`; palavras CDAB são `0000 42F6`; inteiro bruto 17142. Após reconstrução e escala 0,1 da planilha, o dashboard mostra 12,3 kWh. Se chegar somente uma palavra de 16 bits ou um inteiro já convertido/arredondado numericamente, os bits perdidos não podem ser recuperados. Não aplicar escala nem troca de palavras extra no coletor para esses canais.

`codecs.py` implementa a mesma interpretação no teste local. O relatório de cada pacote relaciona codec, divisor e fonte por coluna. As escalas DEIF ficam vinculadas ao mapa; o ajuste global de energia do DSE fica desativado ao selecionar DEIF.

## Grafana e banco

- PostgreSQL 12 ou superior, datasource `grafana-postgresql-datasource`; consultas DEIF usam CTEs materializadas para evitar repetição da decodificação. Não exigem extensão, função instalada ou escrita no banco.
- Grafana com painel Canvas nativo compatível com schema 39 e os recursos usados nos dashboards; a versão do laboratório consta no relatório de validação visual. A compatibilidade física/produção depende da versão instalada pelo usuário.
- A tabela precisa de coluna `time` e colunas `mdb1...mdbN` do mapa exportado. `time` preferencialmente `timestamptz`; `timestamp` sem zona é interpretado como UTC para apresentação em Brasília, conforme contrato anterior.
- Números brutos precisam preservar integralmente os bits. São aceitos campos numéricos ou textos numéricos válidos. Colunas opcionais ausentes viram nulo, sem falha SQL.
- Conectividade vem do LogSis: `gsm_rssi` em dBm e `WiFi_rssi` configurável pela variável `Campo_WiFi_RSSI`. Os símbolos e as barras refletem os dados do período, não um teste de internet ao vivo.
- UID vazio gera identidade estável por modelo e tabela. Para atualizar uma planta, informe o UID do dashboard correspondente. Trocar de aplicação exige exportar o mapa e o JSON correspondentes.

## Comportamento visual e operacional

Um único dashboard por planta, adaptável ao computador/celular. Leituras junto às fontes, contatos simétricos na transferência e edifício para carga. Antes do contato, a linha fica vermelha quando a fonte tem tensão medida; após os contatos, a energização depende de medição e estado coerente, ou da medição do BUS. A cor vermelha indica tensão, não necessariamente fluxo ou consumo.

ON/OFF conflitantes mostram INCOERENTE; estados ausentes mostram SEM DADOS e contato com `?`. SGC420 indica NA CARGA/FORA DA CARGA: é estado lógico documentado, sem alegar retorno independente do contato físico. ATS mantém contatos desconhecidos quando a tabela não documenta retornos correspondentes.

Classes de falha AGC são interpretadas pelo registro 1057, com bits por aplicação. SGC420 usa resumos e nibbles documentados, com prioridade shutdown/vermelho, trip/laranja e warning/amarelo. Manutenção isolada é excluída da alteração da cor do gerador quando os registros necessários permitem identificá-la. CGC não recebe uma severidade inventada a partir da contagem de alarmes; mantém indicação de alarmes registrados sem classificar a ação.

Manutenção aparece como texto, com nomes ajustáveis e aviso de proximidade. AGC/CGC trazem dois serviços; SGC420 apresenta o alarme nativo de filtro/manutenção, sem inventar três temporizadores. Sensores multifunção conservam sua origem/configuração e entradas podem receber nomes por variáveis Grafana; no Studio os canais individuais expostos têm nomes editáveis.

Horas e energia por período usam contador válido antes do início, quando compatível, e amostra final dentro da seleção. Sem base anterior usa-se o primeiro valor dentro do período, marcado com `*`. Quedas/reinícios e amostras conflitantes geram diagnóstico em STATUS; resultados insuficientes aparecem como travessão. O horímetro SGC420 combina palavras ECU 60/61 e minutos 62: conferir a montagem com o equipamento real. Históricos mantêm pontos e linhas lineares interligadas.

## Validação

Na entrega 9.1, o relatório de antivírus acompanha os downloads como arquivo separado, com o hash dos arquivos verificados, versão do ClamAV e data das assinaturas disponíveis. Ausência de detecção nessa análise não é uma garantia de que o Microsoft Defender ou o navegador não emitirá outro alerta. Se houver bloqueio, mantenha a proteção ativa e identifique o nome exato da detecção para análise. O programa não solicita exclusão no antivírus nem altera as proteções do Windows.

Os relatórios distribuídos distinguem testes de software, consultas em PostgreSQL/Grafana local com dados sintéticos e pendências físicas. Foram verificados mapas, exportação, tipos e escalas, FLOAT32/CDAB, nulos, conflitos de modo, manutenção, cálculos por período e regressão DSE. Antes do uso operacional, conferir leituras, horários, polaridade dos contatos, relações TC/TP, unidades EIC e funções suportadas pelo firmware LogSis na instalação.

Os pacotes não incluem credenciais de produção. O código de teste de comunicação é somente leitura; nenhuma função de escrita Modbus é executada pelo Studio.
