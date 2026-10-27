# DEIF — escopo de preparação para LogSis Studio/Grafana

Registro do planejamento inicial. A implementação correspondente foi incorporada ao Studio 9; consulte README_LOGSIS_STUDIO_9.md para o escopo efetivamente entregue e seus limites. SGC120/SGC410 ficaram fora por solicitação posterior do usuário. O conteúdo dos inventários preserva a pesquisa documental, não representa todos os canais selecionados para coleta.

## Equipamentos

| Equipamento | Fonte recebida | Referência de software | Diretório |
| --- | --- | --- | --- |
| AGC150 Extended | 4189341212, revisão Y | 1.38.0 | agc150_extended |
| SGC420 Mk II | 4189341402, revisão C | R19.0 | sgc420_mkii |
| SGC120 Mk II | 4189341403, revisão C | R18.0 | sgc120_mkii |
| CGC400 (CGC412/CGC413) | 4189340865A, opção H2 | 1.00.0 ou posterior | cgc400 |

AGC150: aplicações GEN, MAINS, ATS e ENG no inventário; GEN-H e BTB fora por solicitação do usuário. As possibilidades da versão Extended devem ser confirmadas no manual específico e na unidade instalada. Os SGC têm mapas próprios; não herdam a seleção de aplicações do AGC150.

## Requisitos compartilhados

Aplicam-se os requisitos de apresentação, integridade, exportação casada BIN/CSV/Grafana, horários, manutenção separada da cor de alarme, períodos e validação descritos em agc150_extended/REQUISITOS.md, com capacidades e registros conferidos para cada SGC. Não copiar endereços, número de manutenções, códigos de modo ou semântica de disjuntores entre famílias.

## Diferenças e pendências dos SGC

- Ambos trazem medições de gerador e tensões/frequências de companhia. A existência de contadores de energia de companhia não comprova disponibilidade de correntes/potências instantâneas nem sua origem. Selecionar somente o que a fonte e a configuração sustentam.
- Energia em FLOAT32, ordem CDAB, com escala fonte 0.1. Conferir a interpretação da escala e a ordem de bytes com amostras conhecidas antes de fechar o contrato; não converter como INT32 nem aplicar automaticamente escala de expoente do AGC.
- Horímetro: há diferenças de tipo e descrição entre as planilhas. SGC120: registro 60 como INT32u. SGC420: registros 60/61 separados como INT16u, com descrição alusiva a valor acima de 65535. Identificar montagem e unidade; não inventar combinação de palavras. Confirmar também uso dos contadores ECU versus controlador para cálculo por período.
- Alarmes codificados: enumeração na aba Description distingue desabilitado, inativo, warning, shutdown, electrical trip e notification. Linhas repetem o mesmo nome em grupos de bits: levantar máscara/largura e bit inicial correto; não ler cada bit como severidade independente. Estado desabilitado não equivale a sinal íntegro sem alarme.
- Modos: campos multibit e, onde presentes, registros adicionais próprios. Não usar enumeração DSE/AGC. Descrições de bits da fonte usam posições 1–16 em vários registros; manter o original e documentar conversão antes da exportação.
- Load on Mains/Load on DG e diagnósticos de saída não provam por si só retorno físico de contato. Distinguir estado lógico de alimentação, saída comandada e posição física da chave no desenho.
- SGC420: inventariar entradas multifunção/analógicas, sensores customizados e MIO100; recursos de expansão opcionais. Entradas também aparecem em FC02 e diagnóstico em registradores: evitar dupla coleta desnecessária.
- SGC120: entradas e saídas nos registradores de diagnóstico da planilha, sem presumir existência da aba/endereços FC02 do SGC420.
- Ambos: diagnósticos de motor/EIC, DTC e pós-tratamento opcionais conforme motor e firmware; preservar validade, unidades e origem.
- Manutenção: existe alarme de filtro/manutenção; não presumir que haja três temporizadores ou copiar os dois service timers do AGC. Localizar contador/intervalo real quando disponível e distinguir alarme nativo de manutenção calculada pelo sistema.
- Comandos de mudança de modo e DTC FC16 ficam isolados em referência; não fazem parte do monitoramento autorizado e não serão acionados.
- Orçamento de 100 slots MDB, suporte real a FLOAT32/CDAB e campos multibit são critérios de viabilidade antes da implementação. Inventário completo não equivale a coletar todas as linhas.

## Entregas de planejamento por SGC

INVENTARIO_LEITURAS.csv preserva endereço, função, bit, tipo, escala, enumeração e localização na planilha. REFERENCIA_COMANDOS_NAO_IMPLEMENTAR.csv mantém escritas separadas. FONTE_E_ESCOPO.json registra hash, revisão, versão e contagens; DESCRICAO_FONTE.txt conserva as notas da tabela. Nenhum desses arquivos representa validação em hardware.
