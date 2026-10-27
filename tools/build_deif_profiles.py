"""Build documented DEIF maps; openpyxl is a build-time dependency only.

Sources remain auditable by row/page in each channel. Never reuse a map for an
undocumented controller. CGC412 deliberately has no fabricated mains telemetry.
"""
from pathlib import Path
import copy
import json
import sys
import openpyxl

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'logsis_studio/resources/profiles.json'
data=json.loads(PATH.read_text())


def display_name(role,original):
    for prefix,label in [('gen','Gerador'),('mains','Companhia'),('bus','Barramento'),('s1','Fonte S1'),('s2','Fonte S2'),('load','Carga')]:
        if role.startswith(prefix+'_v_'):return label+' · tensão '+role.split('_v_',1)[1].upper().replace('N','–N')
        if role==prefix+'_frequency':return label+' · frequência'
        if role.startswith(prefix+'_i_'):return label+' · corrente '+role.split('_i_',1)[1].upper()
        for code,desc in [('kw','potência ativa'),('kva','potência aparente'),('kvar','potência reativa'),('fp','fator de potência')]:
            if role==prefix+'_'+code:return label+' · '+desc
            if role.startswith(prefix+'_'+code+'_'):return label+' · '+desc+' '+role.rsplit('_',1)[1].upper()
        if role=='energy_'+prefix:return label+' · energia ativa'
        if role=='reactive_energy_'+prefix:return label+' · energia reativa'
        if role=='apparent_energy_'+prefix:return label+' · energia aparente'
    if role.startswith('input_'):return 'Entrada '+role.removeprefix('input_')
    return original


def channel(rows, name, address, role, group, unit='', divisor=1, fnc=4, signed=False, codec='integer', source='', bit=-1, variable=''):
    n=len(rows)+1
    wide=fnc in [30,40]
    rows.append(dict(number=n,column=f'mdb{n}',name=name,group=group,unit=unit,divisor=divisor,
        params=dict(DH=name+' ALTO',DM=name,DL=name+' BAIXO',ID='10',FNC=str(fnc),ADDR=str(address),BIT=str(bit),H='100',VR='-1',TH='2147483647' if wide else '32767' if signed else '65535',TL='-2147483648' if wide else '-32768',SM='0'),
        role=role,signed_value=signed,label_variable=variable,codec=codec,source_reference=source))


def source_file(pattern):
    found=list((ROOT.parent/'attachments').glob('*/'+pattern))
    if not found:raise SystemExit('Fonte ausente: '+pattern)
    return found[0]


def finish(model,label,rows,application,topology,document,notes):
    assert len(rows)<=100,(model,len(rows))
    assert len({c['role'] for c in rows})==len(rows),model
    data[model]=dict(model=model,label=label,version='deif-1.0',count=len(rows),dashboard='deif',dashboard_version='D1',channels=rows,
        kind='deif',vendor='DEIF',application=application,topology=topology,source_document=document,
        manual_family=application,manual_notes=notes+['Validação documental e simulada; conferir firmware, sensores, unidades e estados na instalação antes do uso operacional.'])


def agc():
    path=source_file('*agc-150*xlsx');w=openpyxl.load_workbook(path,data_only=True)
    sheet=w['Input register (04)'];values=list(sheet.values)
    alarm_specs={}
    for app,topology,suffix,caption in [('GEN','transfer','GEN','Gerador + companhia'),('GEN','gen_bus','GEN_BUS','Gerador + BUS'),('MAINS','mains_bus','MAINS','Companhia + BUS'),('ATS','transfer','ATS','Transferência S1 / S2'),('ENG','engine','ENG','Motor')]:
        rows=[];column={'GEN':13,'MAINS':12,'ATS':16,'ENG':15}[app]
        def add(addr,role,name=None,group='Controle',unit=None,bit=None,variable=''):
            matches=[(i,r) for i,r in enumerate(values,1) if r[1]==addr and r[column]=='X' and (bit is None or r[2]==bit)]
            if not matches:raise ValueError((app,addr,role))
            i,r=matches[0];typ=r[7];bits=bit if bit is not None else -1
            channel(rows,name or display_name(role,r[6]),addr,role,{'GEN':'Gerador','MAINS':'Companhia','BUS':'Barramento','S1':'Fonte S1','S2':'Fonte S2'}.get(group,group),unit if unit is not None else str(r[10] or ''),10**int(r[9] or 0),40 if '32' in typ else 4,typ.endswith('s'),
                    'boolean' if typ=='BOOL' else 'integer',f'{path.name} / Input register (04), linha {i}',bits,variable)
        if app!='ENG':
            prefix={'GEN':'gen','MAINS':'mains','ATS':'s1'}[app]
            for suffix_v,addr in zip(['l1l2','l2l3','l3l1','l1n','l2n','l3n'],range(501,507)):
                add(addr,prefix+'_v_'+suffix_v,group=prefix.upper())
            add(507,prefix+'_frequency',group=prefix.upper())
            for ph,addr in enumerate(range(513,516),1):add(addr,prefix+'_i_l'+str(ph),group=prefix.upper())
            for measure,start,unit in [('kw',516,'kW'),('kvar',520,'kvar'),('kva',524,'kVA')]:
                for ph in range(1,4):add(start+ph-1,prefix+'_'+measure+'_l'+str(ph),group=prefix.upper())
                add(start+3,prefix+'_'+measure,group=prefix.upper())
            add(538,prefix+'_fp',group=prefix.upper())
            add(536,'energy_'+prefix,group='Acumulados')
            add(528,'reactive_energy_'+prefix,group='Acumulados')
            secondary='s2' if app=='ATS' else 'mains' if topology=='transfer' else 'bus'
            for suffix_v,addr in zip(['l1l2','l2l3','l3l1','l1n','l2n','l3n'],range(539,545)):
                add(addr,secondary+'_v_'+suffix_v,group=secondary.upper())
            add(545,secondary+'_frequency',group=secondary.upper())
            if app=='GEN' and topology=='transfer':
                add(592,'mains_kw','Companhia · kW (TC/transdutor/PMS)','Companhia · origem configurada')
                add(759,'mains_kvar','Companhia · Q (TC/transdutor/PMS)','Companhia · origem configurada','kvar')
        if app in ['GEN','ENG']:
            for addr,role,name,unit in [(554,'hour_meter','Horímetro absoluto','h'),(556,'relative_hours','Horímetro relativo','h'),(566,'starts','Tentativas de partida',''),(576,'rpm','Rotação','rpm')]:add(addr,role,name,'Motor',unit)
            for i in [1,2]:
                add(567+2*i,'maintenance_'+str(i),'Manutenção '+str(i),'Manutenção','h',variable='Nome_Manutencao_'+str(i))
                add(568+2*i,'maintenance_days_'+str(i),'Manutenção '+str(i)+' · dias','Manutenção','d')
                add(1015,'service_alarm_'+str(i),'Serviço '+str(i)+' · alarme','Manutenção','',i-1)
            # Validity bits are collected alongside EIC values. Units follow ECU/controller configuration.
            add(26001,'coolant','Temperatura motor · EIC','Motor','°C/F configurado')
            add(26002,'oil_pressure','Pressão óleo · EIC','Motor','bar/psi configurado')
            add(26900,'valid_oil','Validade pressão óleo','Diagnóstico','',13)
            add(26900,'valid_coolant','Validade temperatura','Diagnóstico','',14)
        add(567,'battery','Alimentação DC','Motor' if app in ['GEN','ENG'] else 'Alimentação','V')
        add(558,'alarm_count','Quantidade de alarmes','Alarmes','')
        add(559,'alarm_unack','Alarmes não reconhecidos','Alarmes','')
        add(560,'alarm_active_ack','Alarmes ativos reconhecidos','Alarmes','')
        for addr,role in [(1018,'status_word'),(1019,'mode_word')]:
            # Whole words are unsigned bitfields even where individual rows are BOOL.
            channel(rows,'Estado nativo '+str(addr),addr,role,'Controle',source=f'{path.name} / Input register (04), registro {addr}',codec='word')
        if app=='ATS':
            # These flags exist in FC02; avoid inventing corresponding FC04 bit positions.
            for addr,role,name in [(8,'mode_manual','Modo manual'),(9,'mode_auto','Modo automático')]:
                channel(rows,name,addr,role,'Controle',fnc=2,codec='boolean',source=f'{path.name} / Discrete input contact (02), endereço {addr}')
            # ATS source contacts are not assumed equivalent to GEN GB/MB bits.
        for bit in list(range(8))+[11,12,13,14]:
            add(1142,'input_'+str(39+bit if bit<8 else 47+bit-11),group='Entradas',unit='',bit=bit,variable='Nome_Entrada_'+str(39+bit if bit<8 else 47+bit-11))
        for i,addr in enumerate([583,584,585,587],1):add(addr,'analog_'+str(i),'Multifunção '+str(19+i),'Analógicas','configurado',variable='Nome_Analogica_'+str(i))
        # Collect native alarm words and class flags, never infer severity from
        # alarm counts or from the text of an alarm name.
        alarms=[{'address':r[1],'bit':r[2],'name':r[6],'maintenance':str(r[6]).startswith('Service timer')} for r in values if isinstance(r[1],int) and 1000<=r[1]<=1015 and r[column]=='X' and r[0] in ['AC alarm','Alarm']]
        alarm_specs[app]=alarms
        for addr in sorted({a['address'] for a in alarms}):channel(rows,'Alarmes nativos '+str(addr),addr,'alarm_word_'+str(addr),'Alarmes nativos',codec='word',source=f'{path.name} / Input register (04), registro {addr}')
        channel(rows,'Classes de falha',1057,'fail_class_word','Alarmes',codec='word',source=f'{path.name} / Input register (04), registro 1057; bits disponíveis por aplicação')
        notes=['Planilha revisão Y, software 1.38.0. Aplicação selecionada deve corresponder ao controlador.',
               'Bits são extraídos pelo LogSis quando BIT>=0; palavras completas ficam inteiras para decodificação SQL.',
               'Classes de falha em 1057, bits específicos por aplicação; contagem de alarmes não é usada como código de severidade.',
               'Service timers 1 e 2: indicação independente da cor do gerador. EIC e unidades dependem da configuração.']
        if app=='GEN':notes.append('A fonte secundária medida é BB; nome Companhia no unifilar somente para a topologia com companhia. Potência em 592/759 pode vir do quarto TC/transdutor/PMS; não é medição trifásica local garantida.')
        if app=='ATS':notes.append('Modos FC02 exigem FNC2 no LogSis. Retornos físicos dos contatos ATS não são presumidos a partir dos bits GEN.')
        finish('AGC150_'+suffix,'AGC150 Extended · '+caption,rows,app,topology,'DEIF 4189341212 revisão Y / SW 1.38.0',notes)
    (ROOT/'logsis_studio/resources/agc150_alarms.json').write_text(json.dumps(alarm_specs,ensure_ascii=False,indent=2)+'\n')


def sgc():
    path=source_file('*sgc-420*xlsx');values=list(openpyxl.load_workbook(path,data_only=True)['Holding & Read (03;04;16)'].values);rows=[]
    def add(addr,role,name=None,group='Controle',unit=None,variable=''):
        i,r=next((i,r) for i,r in enumerate(values,1) if r[1]==addr and r[2] is None)
        typ=str(r[5]);scale=float(r[7]);divisor=round(1/scale)
        channel(rows,name or display_name(role,r[4]),addr,role,group,r[8] if unit is None else unit,divisor,40 if '32' in typ else 4,typ.endswith('s'),'float32_cdab' if typ=='FLOAT32' else 'integer',f'{path.name} / Holding & Read, linha {i}',variable=variable)
    for suffix,addr in zip(['l1n','l2n','l3n','l1l2','l2l3','l3l1'],range(1,7)):add(addr,'gen_v_'+suffix,group='Gerador')
    add(7,'gen_frequency',group='Gerador')
    for ph,addr in enumerate(range(10,13),1):add(addr,'gen_fp_l'+str(ph),group='Gerador')
    add(13,'gen_fp',group='Gerador')
    for suffix,addr in zip(['l1n','l2n','l3n','l1l2','l2l3','l3l1'],range(14,20)):add(addr,'mains_v_'+suffix,group='Companhia')
    add(20,'mains_frequency',group='Companhia')
    for ph,addr in enumerate(range(23,26),1):add(addr,'load_i_l'+str(ph),group='Carga')
    for measure,start in [('kw',26),('kva',31),('kvar',35)]:
        for ph in range(1,4):add(start+ph-1,'load_'+measure+'_l'+str(ph),group='Carga')
        add(start+3,'load_'+measure,group='Carga')
    for addr,role,unit in [(39,'energy_gen','kWh'),(41,'apparent_energy_gen','kVAh'),(43,'reactive_energy_gen','kvarh'),(45,'energy_mains','kWh'),(47,'apparent_energy_mains','kVAh'),(49,'reactive_energy_mains','kvarh')]:add(addr,role,group='Acumulados',unit=unit)
    for addr,role,name in [(51,'oil_pressure','Pressão óleo'),(52,'coolant','Temperatura motor'),(53,'fuel','Combustível'),(54,'fuel_litres','Combustível em litros'),(55,'charge','Alternador carga'),(56,'battery','Bateria'),(57,'rpm','Rotação'),(58,'starts','Partidas')]:add(addr,role,name,'Motor')
    for addr,role,name in [(60,'hours_hi','Horímetro · palavra alta'),(61,'hours_lo','Horímetro · horas'),(62,'hours_minutes','Horímetro · minutos'),(63,'mains_hours','Companhia · horas'),(64,'mains_minutes','Companhia · minutos')]:add(addr,role,name,group='Acumulados')
    for addr in [65,66,67,68,96,97,98,99]:add(addr,'analog_'+str(addr),'Auxiliar S'+str(addr-64) if addr<69 else {96:'Sensor de óleo',97:'Sensor combustível',98:'Sensor temperatura',99:'Sensor do abrigo'}[addr],group='Analógicas',variable='Nome_Analogica_'+str(addr))
    for addr in list(range(72,89))+[158]:
        channel(rows,'Alarmes nativos '+str(addr),addr,'alarm_word_'+str(addr),'Alarmes',codec='word',source=f'{path.name} / Holding & Read, registro {addr}, nibbles de quatro bits')
    for addr,role in [(89,'input_word'),(90,'output_word'),(91,'status_word')]:channel(rows,'Diagnóstico '+str(addr),addr,role,'Controle',codec='word',source=f'{path.name} / Holding & Read, registro {addr}')
    finish('SGC420_MKII','SGC420 Mk II',rows,'SGC420','transfer','DEIF 4189341402 revisão C / SW R19.0',[
        'FLOAT32/CDAB recebido como inteiro bruto de 32 bits; decoder IEEE754 no SQL, antes da escala 0,1.',
        'Correntes e potências 23–38 são da CARGA; não são atribuídas automaticamente à companhia ou ao gerador.',
        'Estado Load on DG/Mains é lógico, não confirmação independente da posição física do contato.',
        'Horímetro ECU: palavras 60/61 e minutos 62. Conferir rollover e montagem com o horímetro real.',
        'Manutenção disponível como alarme nativo de filtro; não há temporizadores de manutenção 1/2/3 confirmados nesta tabela.'])


def cgc():
    for model in ['CGC412','CGC413']:
        rows=[];source='DEIF 4189340865A / Option H2'
        def add(addr,role,name,group='Gerador',unit='',div=1,wide=False,signed=False,codec='integer',page=16,fnc=None):
            channel(rows,name,addr,role,group,unit,div,fnc or (40 if wide else 4),signed,codec,f'{source}, p.{page}')
        for suffix,addr in zip(['l1l2','l2l3','l3l1','l1n','l2n','l3n'],range(501,507)):add(addr,'gen_v_'+suffix,'Gerador · '+suffix.upper(),unit='V')
        add(507,'gen_frequency','Frequência gerador',unit='Hz',div=100)
        for ph,addr in enumerate(range(513,516),1):add(addr,'gen_i_l'+str(ph),'Corrente L'+str(ph),unit='A')
        for measure,start,unit in [('kw',516,'kW'),('kvar',520,'kvar'),('kva',524,'kVA')]:
            for ph in range(1,4):add(start+ph-1,'gen_'+measure+'_l'+str(ph),unit+' L'+str(ph),unit=unit,signed=measure!='kva')
            add(start+3,'gen_'+measure,unit+' total',unit=unit,signed=measure!='kva')
        add(538,'gen_fp','Fator de potência',unit='',div=100,signed=True,page=17)
        add(536,'energy_gen','Energia gerador','Acumulados','kWh',wide=True,page=17)
        add(528,'reactive_energy_gen','Energia reativa gerador','Acumulados','kvarh',wide=True)
        if model=='CGC413':
            for suffix,addr in zip(['l1l2','l2l3','l3l1','l1n','l2n','l3n'],range(539,545)):add(addr,'mains_v_'+suffix,'Companhia / BB · '+suffix.upper(),'Companhia','V',page=17)
            add(545,'mains_frequency','Frequência companhia / BB','Companhia','Hz',100,page=17)
        for addr,role,name,unit,wide,div in [(554,'hour_meter','Horímetro absoluto','h',True,1),(556,'relative_hours','Horímetro relativo','h',True,1),(566,'starts','Tentativas de partida','',False,1),(567,'battery','Alimentação DC','V',False,10),(576,'rpm','Rotação','rpm',False,1)]:add(addr,role,name,'Motor',unit,div,wide,page=17 if addr<570 else 18)
        for i,addr in enumerate([569,571],1):
            add(addr,'maintenance_'+str(i),'Manutenção '+str(i),'Manutenção','h',page=17 if addr==569 else 18)
            rows[-1]['label_variable']='Nome_Manutencao_'+str(i)
            add(addr+1,'maintenance_days_'+str(i),'Manutenção '+str(i)+' · dias','Manutenção','d',page=18)
        for addr,role in [(558,'alarm_count'),(559,'alarm_unack'),(560,'alarm_active_ack')]:add(addr,role,role,'Alarmes',page=17)
        for addr,role in [(1018,'status_word'),(1019,'mode_word'),(1015,'service_word')]:add(addr,role,'Estado '+str(addr),'Controle',codec='word',page=26 if addr!=1015 else 25)
        for i,addr in enumerate([583,584,585]+([588,589] if model=='CGC413' else []),1):
            add(addr,'analog_'+str(i),'Multifunção '+str([6,7,8,58,59][i-1]),'Analógicas','configurado',page=18)
            rows[-1]['label_variable']='Nome_Analogica_'+str(i)
        for terminal,addr in [(10,22500),(11,22501),(12,22502),(13,22503),(14,22504),(15,22505),(20,22516),(8,22591),(7,22592),(6,22593)]+([(56,22506),(57,22507),(59,22581),(58,22582)] if model=='CGC413' else []):
            add(addr,'input_'+str(terminal),'Entrada '+str(terminal),'Entradas',codec='boolean',page=38,fnc=2)
            rows[-1]['label_variable']='Nome_Entrada_'+str(terminal)
        finish(model,model,rows,model,'transfer',source+' / SW 1.00.0+',[
            'Topologia companhia + gerador solicitada pelo usuário. Não presumir medições ausentes.',
            'CGC412: o manual fornecido não implementa medições BB nem retorno MB; a companhia e o contato ficam sem dados nessa variante.' if model=='CGC412' else 'CGC413: tensões/frequência BB apresentadas como companhia na topologia de transferência configurada.',
            'Entradas digitais e multifunção em FC02 exigem função LogSis 2 no firmware coletor; estados principais seguem FC04.',
            'Contadores Hi/Lo são inteiros, não FLOAT32. Manutenção 1/2 indicada separadamente dos alarmes.',
            'Sensores de motor/EIC em 593–641 dependem do manual complementar H5/H7, ainda não recebido; não há endereços inventados.'])


def dse8620():
    profile=data['DSE8620'];rows=profile['channels']
    # Append only: preserve all delivered 59 MDB positions and metadata.
    if any(c['role']=='mains_i_l1' for c in rows):
        rows=rows[:59];profile['channels']=rows
    for role,addr,name,unit,div,wide,signed in [
        ('mains_i_l1',1076,'Corrente rede L1','A',10,True,False),('mains_i_l2',1078,'Corrente rede L2','A',10,True,False),('mains_i_l3',1080,'Corrente rede L3','A',10,True,False),('mains_i_earth',1082,'Corrente terra rede','A',10,True,False),
        ('mains_kw_l1',1084,'Potência rede L1','kW',1000,True,True),('mains_kw_l2',1086,'Potência rede L2','kW',1000,True,True),('mains_kw_l3',1088,'Potência rede L3','kW',1000,True,True),
        ('mains_kw',1560,'Potência ativa rede','kW',1000,True,True),('mains_kva',1568,'Potência aparente rede','kVA',1000,True,False),('mains_kvar',1576,'Potência reativa rede','kvar',1000,True,True),
        ('mains_fp_l1',1578,'FP rede L1','',100,False,True),('mains_fp_l2',1579,'FP rede L2','',100,False,True),('mains_fp_l3',1580,'FP rede L3','',100,False,True),('mains_fp',1581,'FP médio rede','',100,False,True),('energy_mains',1810,'Energia positiva rede','kWh',10,True,False)]:
        channel(rows,name,addr,role,'Companhia · TC',unit,div,30 if wide else 3,signed,source='GenComm 2.93 / páginas 4, 6 e 7 (numeração impressa a conferir no PDF)')
    profile.update(count=len(rows),version='manual-1.1',dashboard_version='M2')
    note='M2: correntes/potências/FP/energia da rede acrescentados após MDB59; conferir TC e suporte da variante em campo. Posições anteriores preservadas.'
    if note not in profile['manual_notes']:profile['manual_notes'].append(note)


if __name__=='__main__':
    agc();sgc();cgc();dse8620()
    PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    for key,p in data.items():print(key,p['count'])
