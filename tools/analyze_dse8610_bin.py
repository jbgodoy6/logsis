"""Extract the supplied LOGSIS configuration without exporting unrelated settings.

Usage: python tools/analyze_dse8610_bin.py INPUT.bin OUTPUT_DIRECTORY
Only the MDB allowlist and non-secret serial parameters enter the outputs.
No controller, database, or network access is performed.
"""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import re
import zipfile


FIELDS = ('DH', 'DM', 'DL', 'ID', 'FNC', 'ADDR', 'BIT', 'H', 'VR', 'TH', 'TL', 'SM')
SERIAL_KEYS = ('MDB_BAUD', 'MDB_TOUT', 'MDB_R_DELAY', 'MDB_RST_FAILURE')


def extract(raw):
    values = {}
    for number, line in enumerate(raw.decode('ascii').splitlines(), 1):
        key, sep, value = line.partition(';')
        if not sep or not key:
            raise ValueError(f'Linha {number}: esperado chave;valor')
        if key in values:
            raise ValueError(f'Chave duplicada: {key}')
        values[key] = value
    indices = sorted({int(m[1]) for k in values if (m := re.fullmatch(r'MDBA_ADDR(\d+)', k))})
    records = []
    for index in indices:
        missing = [f'MDBA_{f}{index}' for f in FIELDS if f'MDBA_{f}{index}' not in values]
        if missing:
            raise ValueError(f'Posição incompleta: {missing}')
        record = {'index_bin': index, 'mdb': f'MDB{index+1:02}', 'column_expected': f'mdb{index+1}'}
        record.update({f: values[f'MDBA_{f}{index}'] for f in FIELDS})
        address, function, device = (int(record[f]) for f in ('ADDR', 'FNC', 'ID'))
        record['status'] = ('configurado' if min(address, function, device) >= 0
                            else 'não configurado' if (address, function, device) == (-1, -1, -1)
                            else 'configuração parcial')
        records.append(record)
    return {
        'source_name': 'novo padrão dse8610.bin',
        'source_size_bytes': len(raw),
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'model_source': 'DSE8610 informado pelo usuário; variante e firmware não identificados neste mapeamento',
        'format': 'ASCII: uma chave;valor por linha, apesar da extensão BIN',
        'line_count': len(values),
        'index_convention': 'MDBA_*0 → MDB01/mdb1, conforme convenção LOGSIS da planta anterior; conferir ingestão',
        'serial': {k: values[k] for k in SERIAL_KEYS if k in values},
        'configured_count': sum(r['status'] == 'configurado' for r in records),
        'unconfigured_count': sum(r['status'] == 'não configurado' for r in records),
        'user_confirmations': {'MDB52_equipment': 'Disjuntor que acopla este gerador ao barramento BUS, confirmado pelo usuário', 'MDB52_open_closed_values': 'pendentes'},
        'function_codes_raw': dict(collections.Counter(r['FNC'] for r in records if r['status'] == 'configurado')),
        'records': records,
    }


def report(data):
    active = [r for r in data['records'] if r['status'] == 'configurado']
    rows = '\n'.join(f"| {r['mdb']} | {r['DM']} | {r['ADDR']} | {r['FNC']} | {r['BIT']} |" for r in active)
    return f'''# DSE8610 / análise do BIN LOGSIS

Foram extraídos **{len(data['records'])} slots MDB**, dos quais **{data['configured_count']} estão configurados** e **{data['unconfigured_count']} não configurados**. O arquivo tem {data['source_size_bytes']} bytes e {data['line_count']} chaves sem duplicações. A extensão é BIN, mas o conteúdo deste arquivo é ASCII no formato `chave;valor`.

SHA-256: `{data['source_sha256']}`.

Esta análise comprova o que está configurado no arquivo, sem ler o controlador ou o banco de produção. O modelo DSE8610 foi informado pelo usuário; a variante e o firmware não estão confirmados. A correspondência índice zero → MDB01/mdb1 segue a convenção LOGSIS da planta anterior e deve ser conferida na ingestão. Os endereços abaixo são os números armazenados no BIN, sem deslocar base ou acrescentar prefixo 4xxxx.

## Resultado para a nova planta

| Função | Posições |
|---|---|
| Motor e combustível | MDB01–MDB07 |
| Frequência do gerador | MDB08 |
| Tensões do gerador, fase-neutro e fase-fase | MDB09–MDB14 |
| Correntes do gerador e terra | MDB15–MDB18 |
| Potências do gerador | MDB19–MDB24 |
| Fatores de potência do gerador | MDB25–MDB28 |
| Frequência do BUS comum | MDB29 |
| Tensões do BUS, fase-neutro e fase-fase | MDB30–MDB35 |
| Horímetro, energia e partidas | MDB36–MDB38 |
| Horas de manutenção | MDB39 |
| Modo de operação | **MDB40**, endereço 772 |
| Warning / trip elétrico / shutdown | **MDB41 / MDB42 / MDB43**, endereço 774, BIT 10 / 11 / 12 |
| Entradas A–H | **MDB44–MDB51** |
| Sinal rotulado disjuntor do barramento | **MDB52**, endereço 48659 |
| Sem configuração | **MDB53–MDB100** |

O BUS existe como medição própria. Não há necessidade de representá-lo como concessionária. O total ativo MDB22 pertence ao gerador monitorado: não comprova a potência total dos outros grupos nem a potência total consumida pela carga comum.

## Diferenças que impedem copiar o mapeamento do DSE7420

- MDB29–MDB35 deixam de representar rede e passam a representar **BUS**, com endereços 1091 e 1092/1094/1096/1098/1100/1102.
- O modo muda de MDB43 para **MDB40**. Reutilizar MDB43 como modo faria a planta interpretar **shutdown como modo de operação**.
- Neste BIN há somente MDB39 identificado como horas de manutenção. MDB40–MDB42 não são três contadores adicionais de manutenção.
- Alarmes e entradas mudam de posição: warning/trip/shutdown em MDB41–MDB43; entradas A–H em MDB44–MDB51.
- MDB52 não é a antiga entrada F: é o sinal denominado disjuntor do barramento.
- MDB55/MDB56 continuam sem configuração e não podem ser usados como os dois contatos da antiga chave de transferência.

## Modo: rótulos e limiares encontrados

No índice 39 (MDB40) constam `DM=AUTOMATICO`, `DH=MANUAL`, `DL=STOP`, `TH=1`, `TL=1`, `BIT=-1`, `FNC=3`, endereço 772.

Essa organização é compatível com **0=STOP, 1=AUTO, 2=MANUAL**, caso o coletor use as comparações usuais abaixo/igual/acima de 1. É uma **hipótese baseada nos rótulos e limiares**, não uma tabela de enumeração explicitamente declarada no arquivo. Não copiar automaticamente o mapeamento legado 0=STOP/1=MANUAL/2=AUTO da planta DSE7420. Conferir um valor bruto em cada modo ou a documentação da variante do controlador.

## Disjuntor e paralelismo

MDB52 contém `DM=DISJUNTOR DO BARRAMENTO INATIVA`, `DH=DISJUNTOR DO BARRAMENTO ATIVA`, `TH=0`, `TL=0`, `BIT=-1`, `FNC=3`, endereço 48659.

O arquivo **não declara** que esse campo seja um contato auxiliar de posição, que 0 signifique aberto ou que 1 signifique fechado. O nome no BIN, isoladamente, não distingue esses papéis nem separa comando de retorno de posição. O usuário confirmou que o equipamento associado a MDB52 é **o disjuntor que acopla este gerador ao BUS**. Essa confirmação identifica sua função na planta; os valores de aberto/fechado e a natureza do sinal ainda precisam ser conferidos antes de animar o contato.

Não foram encontrados canais explicitamente rotulados como sincronismo, ângulo de fase, autorização de fechamento, quantidade de grupos em paralelo ou potência agregada do BUS. A existência de tensões nas duas fontes não comprova sincronismo nem paralelismo. Os demais geradores podem ser desenhados como referência ao sistema compartilhado, sem inventar quantidade ou estados individuais.

## Comunicação e decodificação

- Identificador `ID=10` nos 52 canais configurados; `MDB_BAUD=19200`; `MDB_TOUT=10`; `MDB_R_DELAY=600`. A unidade dos dois últimos parâmetros não é declarada neste arquivo. Paridade e bits de parada não foram identificados por esses campos.
- 26 canais com código `FNC=3` e 26 com `FNC=30`. O código 30 é armazenado pelo configurador; **não presumir que seja uma função Modbus padrão enviada no fio**. O avanço de dois endereços em tensões/correntes é um indício de leitura em pares de registradores, cuja largura, ordem de palavras e sinal dependem do coletor/protocolo.
- `BIT=10/11/12` está configurado nos três alarmes do endereço 774. Verificar se o coletor já entrega o bit extraído em cada coluna para não aplicar uma segunda extração no dashboard.
- `H`, `VR`, `SM`, `TH` e `TL` foram preservados como parâmetros brutos na planilha. **H=100 ou H=1000 não comprova divisor de escala**. Tampouco os limiares de alarme comprovam o tipo, o valor de indisponibilidade ou a unidade de engenharia.
- Não transpor indiscriminadamente o corte de 32760 para campos que possam ser de 32 bits. Confirmar escalas de tensão, corrente, potências, energia e tempo comparando dados brutos com o controlador. O BIN sozinho não confirma os divisores SQL.

## Composição proposta para o desenho

```mermaid
flowchart LR
    G["Gerador DSE8610"] --> D["Disjuntor do gerador / MDB52 / polaridade a confirmar"]
    D --> B["BUS comum / MDB29 a MDB35"]
    O["Outros geradores / referência"] --- B
    B --> C["Carga / edifício"]
```

O desenho não terá concessionária nem chave de transferência entre rede e gerador. As leituras do GMG ficam associadas ao seu desenho; as leituras MDB29–MDB35 ficam associadas ao BUS. O padrão visual e o comportamento responsivo da V32 podem ser mantidos em um único JSON para a nova planta. O dashboard DSE8610 deverá ter UID e tabela `Id_Logsis` próprios, preservando a planta DSE7420 já aprovada; não haverá dashboards distintos para celular e computador.

A cor do BUS deve decorrer de suas próprias medições, após validar escalas e indisponibilidade. Ele pode estar energizado pelos outros grupos com o disjuntor deste gerador aberto. O desenho não deve apagar o BUS apenas porque este gerador parou, nem indicar corrente/direção de potência somente por haver tensão. Sem retorno de posição validado, o disjuntor deve permanecer como posição desconhecida. Ausência de dado não equivale a zero.

## Mapeamento completo dos canais configurados

`FNC` e `BIT` abaixo são os valores literais do arquivo.

| Posição esperada | Rótulo configurado | Endereço decimal | FNC | BIT |
|---|---|---:|---:|---:|
{rows}

Os 48 slots MDB53–MDB100 têm ID, função e endereço iguais a −1 e rótulo principal vazio. A planilha e o JSON incluem também esses slots para rastreabilidade. Nenhum slot com configuração parcial foi encontrado.

## Para fechar a vinculação da planta

1. Confirmar a variante DSE8610 e o que o coletor entrega em `mdb1`…`mdb52`: tipos, ordem de palavras, escalas e eventual extração de bits.
2. Comparar MDB40 com STOP/AUTO/MANUAL no controlador.
3. A função do equipamento MDB52 já foi confirmada pelo usuário: acoplamento deste gerador ao BUS. Falta observar os valores de aberto/fechado e confirmar a natureza do sinal.
4. Se a tela precisar afirmar “sincronizado” ou “em paralelo”, identificar os registros específicos; este BIN não os nomeia.

O pacote contém apenas a análise de mapeamento, não um dashboard importável. As configurações não relacionadas aos MDBs não foram incluídas nos arquivos de saída.
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input', type=Path)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    data = extract(args.input.read_bytes())
    args.output.mkdir(parents=True, exist_ok=True)
    names = ('DSE8610_MAPEAMENTO.csv', 'DSE8610_AUDITORIA.json', 'DSE8610_ANALISE.md')
    columns = ('index_bin', 'mdb', 'column_expected', 'status', *FIELDS)
    with (args.output / names[0]).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns, delimiter=';')
        writer.writeheader()
        writer.writerows(data['records'])
    (args.output / names[1]).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (args.output / names[2]).write_text(report(data), encoding='utf-8')
    with zipfile.ZipFile(args.output / 'DSE8610_ANALISE_BIN.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for name in names:
            z.write(args.output / name, name)
    print(json.dumps({k: data[k] for k in ('source_sha256', 'configured_count', 'unconfigured_count', 'function_codes_raw')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
