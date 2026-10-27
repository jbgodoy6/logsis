"""Check every DSE8660 slot against the supplied GenComm 2.93 tables.

Addresses are zero-based page*256+offset, not 4xxxx notation. This checks
the document map, not support in a particular hardware/firmware revision.
"""
import csv
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from logsis_studio.core import Project

expected={}
def add(role,page,offset,bits,divisor,signed=False,bit=-1,printed_pages=''):
    expected[role]=(page,offset,bits,divisor,signed,bit,printed_pages)

for prefix,freq,volts,currents,watts,powers,pf in [
    ('mains',35,[36,38,40,42,44,46],[52,54,56,58],[60,62,64],[24,32,40],[42,43,44,45]),
    ('bus',67,[68,70,72,74,76,78],[80,82,84,86],[88,90,92],[48,56,64],[66,67,68,69]),
]:
    add(prefix+'_frequency',4,freq,16,10,printed_pages='33')
    for suffix,offset in zip(['l1n','l2n','l3n','l1l2','l2l3','l3l1'],volts):
        add(prefix+'_v_'+suffix,4,offset,32,10,printed_pages='33')
    for suffix,offset in zip(['l1','l2','l3','earth'],currents):
        add(prefix+'_i_'+suffix,4,offset,32,10,printed_pages='33–34')
    for suffix,offset in zip(['l1','l2','l3'],watts):
        add(prefix+'_kw_'+suffix,4,offset,32,1000,True,printed_pages='33–34')
    for kind,offset in zip(['kw','kva','kvar'],powers):
        add(prefix+'_'+kind,6,offset,32,1000,kind!='kva',printed_pages='45')
    for suffix,offset in zip(['_l1','_l2','_l3',''],pf):
        add(prefix+'_fp'+suffix,6,offset,16,100,True,printed_pages='45')
for role,offset in [('energy_mains',18),('energy_bus',26)]:
    add(role,7,offset,32,10,printed_pages='49')
add('mode',3,4,16,1,printed_pages='30')
for role,bit in [('warning',10),('trip',11),('shutdown',12)]:
    add(role,3,6,16,1,bit=bit,printed_pages='30')
for i,letter in enumerate('ABCDEFGH'):
    add('input_'+letter,170,1+i*2,16,1,printed_pages='136')
add('led_mains',190,19,16,1,printed_pages='173: model 8x60')
add('led_bus',190,20,16,1,printed_pages='173: model 8x60')

def audit():
    project=Project.new('DSE8660');rows=[]
    assert {c.role for c in project.profile.channels}==set(expected)
    for c in project.profile.channels:
        page,offset,bits,divisor,signed,bit,printed=expected[c.role]
        wanted=(page*256+offset,30 if bits==32 else 3,divisor,signed,bit)
        actual=(int(c.params['ADDR']),int(c.params['FNC']),c.divisor,c.signed,int(c.params['BIT']))
        assert actual==wanted,(c.role,actual,wanted)
        rows.append({'MDB':f'MDB{c.number:02}','role':c.role,'name':c.name,
                     'address_zero_based':wanted[0],'page':page,'offset':offset,
                     'Modbus_function':3,'register_count':bits//16,'LogSis_FNC':wanted[1],
                     'divisor':divisor,'unit':c.unit,'signed':signed,'bit':bit,
                     'manual_printed_pages':printed})
    return rows

if __name__=='__main__':
    rows=audit()
    report={'result':'passed','model':'DSE8660','manual':'GenComm 2.93, revision 13/04/2015, supplied Modbus - Deep Sea.pdf',
            'channels_checked':len(rows),'addresses_changed':False,'requested_variant':'DSE8660 MkII','specific_MkII_firmware_and_CT_wiring_validation':'pending; generic GenComm table is not a physical device test',
            'scope':'Addresses, quantity, function, scale and signedness checked against document. No physical device or production database test. LED contacts are controller indications. CT wiring and firmware support are not established by the generic table.',
            'rows':rows}
    (ROOT/'DSE8660_CONFERENCIA_MODBUS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (ROOT/'DSE8660_CONFERENCIA_MODBUS.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter=';');writer.writeheader();writer.writerows(rows)
    print('DSE8660: all 58 channels match the supplied manual; no address changes.')
