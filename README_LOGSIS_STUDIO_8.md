# LogSis Studio 8 — nove perfis DSE

[Baixar programa completo](LOGSIS_STUDIO_8_0.zip) · [Dashboards dos novos modelos](LOGSIS_CONTROLADORES_MANUAL_M1.zip) · [Mapa completo CSV](LOGSIS_STUDIO_8_MAPA_MANUAL.csv)

O Studio 8 acrescenta sete perfis conforme o manual fornecido, mantendo os dois perfis já entregues. BIN, mapa CSV e consultas do Grafana dos novos modelos são gerados a partir da mesma definição de canais.

| Seleção no Studio | Canais | Perfil da instalação | Base documental |
|---|---:|---|---|
| DSE7420 | 59 | Rede e gerador | Perfil 7.2 preservado, inclusive a indicação de campo dos endereços 48653/48654 |
| DSE8610 | 58 | Gerador e BUS | Perfil 7.2 preservado |
| DSE4520 MkII | 57 | Motor, gerador e rede | Família 4xxx do manual |
| DSE6120 MkII | 58 | Motor, gerador e rede; flexíveis A–D | Tabela própria 61xx MkII |
| DSE6320 | 57 | Motor, gerador e rede | Família 6xxx |
| DSE7320 MkII | 57 | Motor, gerador e rede | Família 72xx/73xx do manual |
| DSE8620 | 59 | Motor, gerador e rede; flexíveis Q/R/S | Família 8xxx/74xx |
| DSE8660 | 58 | Rede e BUS | Família 8xxx e LEDs 8x60 |
| DSE8680 | 58 | BUS 1, acoplador e BUS 2 | Registros específicos de BUS 2 e LEDs do modelo 8680 |

## Abrir e exportar

1. Extraia **a pasta inteira** do ZIP.
2. Instale Python 3.10 ou superior com Tcl/Tk. No Windows, execute `INICIAR_LOGSIS_STUDIO.bat`.
3. Escolha o controlador na lista da parte superior. O nome MkII fica explícito nas três versões confirmadas pelo usuário.
4. Ajuste identificação, Slave ID, comunicação, limites nominais e textos dos canais.
5. Em **Validar & exportar**, preencha planta, tabela `Id_Logsis`, datasource e, opcionalmente, UID do dashboard que deseja atualizar.
6. Exporte **BIN + Grafana**. Use o BIN e o JSON do mesmo pacote/modelo. Com UID vazio, a identidade é estável por modelo + tabela. O botão de UID de referência serve apenas para atualizar o dashboard de referência desse modelo; não o reutilize para cadastrar plantas diferentes.

A interface e a exportação usam apenas a biblioteca padrão do Python. O teste Modbus TCP também. Para RS485/USB: `python -m pip install -r requirements-serial.txt` e o driver do adaptador.

O Studio gera a configuração do **coletor LogSis**; não reprograma o firmware do DSE, não aciona disjuntores, não envia configurações ao equipamento e não altera o banco de dados ou o servidor Grafana. O teste Modbus é somente de leitura.

## BINs compartilhados e posições de variáveis

MDB01 corresponde ao índice zero `MDBA_ADDR0` no BIN. Todos os slots até 100 que não pertencem ao perfil ficam desativados.

As posições dos DSE7420/DSE8610 continuam intactas. Para os novos perfis, a sequência é definida no CSV e no JSON juntos: não se deve importar um dashboard de outro controlador esperando que suas MDBs tenham a mesma função.

DSE4520/DSE6320/DSE7320 têm mapas de registradores iguais nas tabelas de família usadas aqui. Um BIN do coletor, sozinho, não identifica qual é o controlador físico. Se houver ambiguidade, o Studio mantém o modelo selecionado quando ele é compatível; se não for, pede que selecione o modelo antes de abrir. Não escreve uma chave de modelo inventada no BIN e não troca o modelo silenciosamente por um palpite.

Ao abrir um BIN divergente, o Studio aponta endereços/funções/bits incompatíveis. **Reaplicar perfil** substitui explicitamente canais, textos e limites, conforme a confirmação da interface. Outros parâmetros do equipamento são preservados. Ajuste nomes personalizados depois de aplicar o perfil.

## O que segue o manual

Fonte: **Modbus - Deep Sea.pdf**, GenComm **2.93**, revisão **13/04/2015**. O endereço absoluto é `página × 256 + offset`, em base zero. Função LogSis 3 = FC03/16 bits; 30 = FC03/dois registradores. Bits do coletor são numerados de zero. Inteiros de 32 bits usam palavra mais significativa primeiro.

- Motor, gerador, rede e BUS: páginas 33–34; potências e FP: páginas 42–46.
- Horímetro 1798, energia do gerador 1800, partidas 1808, manutenção geral 1794 e manutenções 1836/1840/1844: página 49.
- Rede usa energia 1810; BUS usa 1818, quando implementados.
- DSE6120 MkII: seis digitais A–F e flexíveis A–D em **43533/43535/43537/43539**, página 134. Não usa Q/R/S como flexíveis locais.
- Família 72xx/73xx: entradas A–I conforme página 135. Os offsets 33/35/37 da página 170 são expansão, não flexíveis locais.
- DSE8620: Q/R/S processadas em 43553/43555/43557, conforme tabela 8xxx/74xx e nota da página 133.
- DSE8660: LEDs rede/BUS em **48659/48660**; DSE8680: LED acoplador em **48659**, BUS 1/BUS 2 disponíveis em **48658/48661**, página 173.
- Modo em 772; Warning/Trip/Shutdown em 774, bits 10/11/12. Nos perfis novos, os modos 4 (automático/retorno manual) e 5 (configuração) também são reconhecidos.

A tabela de família não garante que todos os registradores estejam implementados em cada unidade. Os perfis DSE4520 MkII e DSE7320 MkII seguem as famílias disponíveis no PDF de 2015, sem alegar uma tabela individual de revisão que esse documento não fornece. Entradas A–I documentadas não significam nove bornes físicos em todos os modelos. Recursos de potência dependem de medição/TCs/configuração. Leituras inválidas ou não implementadas mostram traço.

## LEDs e representação da energia

**Os novos perfis mostram LEDs, não contato físico aberto/fechado.** A página 190 é de leitura de saídas/LEDs e o manual informa que o teste de lâmpadas pode afetá-los. Os indicadores são identificados como LED ATIVO, LED INATIVO ou sem dados.

O desenho dos novos modelos com gerador preserva o caminho rede/gerador/carga, mas usa círculos de indicação em lugar de presumir a posição da chave. A saída não medida permanece sem indicação de tensão inferida por LED. Nos perfis de barramento, a cor dos trechos medidos vem da tensão do próprio barramento, independentemente do LED. O DSE8680 apresenta dois barramentos e nenhum gerador desenhado.

Os perfis DSE7420/DSE8610 continuam com suas regras anteriores, sem mudanças nesta entrega.

## Manutenção, nomes, histórico e período

Nos novos modelos com motor, manutenção próxima/vencida aparece **somente no texto abaixo do gerador**. A imagem é colorida apenas por Warning/Trip/Shutdown do controlador. Manutenções são tempos restantes em segundos, com sinal, divididos por 3600. Zero/negativo indica vencida; o limite inicial de proximidade é 50 h, ajustável em `Manutencao_Alerta_h`.

Nomes de entradas e manutenções são variáveis do Grafana. Editar o DM no Studio preenche essas variáveis ao exportar. No 6120 MkII, as flexíveis têm `Nome_Entrada_Flex_A` até `Nome_Entrada_Flex_D`; no 8620, `Nome_Entrada_Q/R/S`. Nomes com acentos e apóstrofos são tratados como texto, sem inserção livre no SQL.

Horas e energia do período usam a regra já aprovada: base válida anterior ao filtro, quando compatível, e último contador do período; cobertura parcial e quedas são sinalizadas. DSE8660/DSE8680 não recebem horímetro nem manutenção de motor. Não foi inventado contador de energia do BUS 2: o 8680 recebe energia do BUS 1 documentada; valores do BUS 2 só são medidos nos registros explicitamente definidos.

Os gráficos mantêm pontos e linhas interligadas, com interpolação linear. Horários são exibidos em Brasília. Um único dashboard atende desktop e celular.

## Arquivos e verificação

O pacote de cada planta contém BIN, JSON do Grafana, CSV de canais, relatório de compatibilidade com funções lógicas e notas de família, além do guia. O ZIP separado de dashboards M1 e a planilha CSV são úteis para revisão; para implantação, prefira exportar a planta no Studio para preencher tabela, datasource e UID corretamente.

- `LOGSIS_STUDIO_8_VALIDACAO.json`: testes do programa e preservação dos perfis anteriores.
- `LOGSIS_STUDIO_8_VALIDACAO_SQL.json`: registradores sintéticos → slots reais do BIN → SQL exportado nos sete novos modelos, incluindo períodos e sinais.
- `LOGSIS_STUDIO_8_VALIDACAO_UI.json`: conferência dos sete dashboards em 1440 e 390 pixels, sem corte de texto nos instrumentos verificados.

A validação foi realizada em Linux/Tk, simuladores e PostgreSQL/Grafana locais isolados. Não houve acesso ao banco de produção nem teste físico dos sete controladores. Isso valida a implementação do mapa, não homologa o hardware/firmware de uma instalação.

Para desenvolvimento:

```sh
python tools/build_manual_profiles.py
DISPLAY=:87 python -m unittest discover -s tests -p 'test_studio*.py' -v
python tools/validate_manual_profiles.py
python tools/seed_manual_lab.py
node tools/validate_manual_ui.cjs
python tools/build_manual_exports.py
python tools/build_studio_release.py
```

As validações SQL/UI usam apenas o laboratório Docker local; a interface Tk exige DISPLAY. A execução normal do programa não precisa de Docker, PostgreSQL local ou Node.
