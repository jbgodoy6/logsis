import io
import json
import math
import os
import struct
import unittest
import zipfile
from decimal import Decimal
from unittest.mock import patch

from logsis_studio.core import Project,available_models,BinDocument
from logsis_studio.codecs import decode_value
from logsis_studio.transport import decode,parse_pdu,request_parameters


class DeifTests(unittest.TestCase):
    def test_catalog_and_sgc_exclusions(self):
        self.assertEqual(len(available_models()),17)
        self.assertIn('SGC420_MKII',available_models())
        self.assertNotIn('SGC120_MKII',available_models())
        self.assertNotIn('SGC410',available_models())

    def test_float_golden_values_and_invalid_payloads(self):
        p=Project.new('SGC420_MKII');c=next(c for c in p.profile.channels if c.role=='energy_gen')
        # IEEE754 0x42f60000 = 123.0, CDAB => 0x000042f6.
        self.assertEqual(decode_value(c,0x000042f6),Decimal('12.3'))
        self.assertEqual(decode_value(c,0x0000c120),Decimal('-1.0'))
        for raw in [0x00007fc0,0x00007f80,0x0000ff80,None,'not a number',1.1,4294967296,-2147483649]:self.assertIsNone(decode_value(c,raw))
        self.assertEqual(decode_value(c,0),0)
        for v in [-1234.5,-.1,.1,1234.5,1000000.25]:
            bits=int.from_bytes(struct.pack('>f',v),'big');wire=(bits&65535)<<16|bits>>16
            signed=wire if wire<2**31 else wire-2**32
            self.assertEqual(decode_value(c,wire),decode_value(c,signed))
            expected=struct.unpack('>f',struct.pack('>f',v))[0]/10
            self.assertAlmostEqual(float(decode_value(c,signed)),expected,places=6)
        self.assertEqual(decode(c,p.rows[c.index],(0,0x42f6)).engineering,Decimal('12.3'))

    def test_fc02_read_transport_and_bit_order(self):
        self.assertEqual(request_parameters(10,2,22591),(10,2,22591,1))
        self.assertEqual(parse_pdu(bytes([2,1,0b10100101]),2,8),(1,0,1,0,0,1,0,1))
        with self.assertRaises(ValueError):parse_pdu(bytes([2,2,1]),2,1)

    def test_all_deif_exports_roundtrip_contract_and_source(self):
        for model in available_models():
            p=Project.new(model)
            if p.profile.vendor!='DEIF':continue
            self.assertLessEqual(p.profile.count,100)
            self.assertFalse(p.validate())
            self.assertEqual(Project.from_bytes(p.bin_bytes(),model).bin_bytes(),p.bin_bytes())
            self.assertTrue(all(c.source_reference for c in p.profile.channels))
            with zipfile.ZipFile(io.BytesIO(p.bundle_bytes('id_test','Planta','ds'))) as z:
                d=json.loads(z.read(model+'_GRAFANA.json'));r=json.loads(z.read('COMPATIBILIDADE.json'))
                self.assertEqual(r['vendor'],'DEIF');self.assertIn('bits como inteiro',r['raw_contract'])
                self.assertEqual(d['timezone'],'America/Sao_Paulo')
                self.assertEqual(len(r['codecs']),p.profile.count)
                self.assertIn('FROM $Id_Logsis',d['panels'][0]['targets'][0]['rawSql'])

    def test_cgc_variants_do_not_fabricate_mains_fields(self):
        a={c.role:c for c in Project.new('CGC412').profile.channels}
        b={c.role:c for c in Project.new('CGC413').profile.channels}
        self.assertNotIn('mains_v_l1n',a);self.assertEqual(b['mains_v_l1n'].params['ADDR'],'542')
        self.assertEqual(a['hour_meter'].params['FNC'],'40')
        self.assertNotEqual(a['hour_meter'].codec,'float32_cdab')
        self.assertTrue(all(c.params['FNC']=='2' for c in b.values() if c.role.startswith('input_')))

    def test_sgc_power_remains_load_not_generator(self):
        rs={c.role:c for c in Project.new('SGC420_MKII').profile.channels}
        self.assertIn('load_kw',rs);self.assertNotIn('gen_kw',rs)
        self.assertEqual(rs['load_kw'].params['ADDR'],'29')
        self.assertEqual(rs['status_word'].params['BIT'],'-1')

    def test_8620_prefix_preserved_and_company_added(self):
        import subprocess
        old=json.loads(subprocess.check_output(['git','show','b679177:logsis_studio/resources/profiles.json']))['DSE8620']
        p=Project.new('DSE8620')
        current=json.loads((__import__('logsis_studio.core',fromlist=['RESOURCES']).RESOURCES/'profiles.json').read_text())['DSE8620']
        self.assertEqual(current['channels'][:59],old['channels'])
        rs={c.role:c for c in p.profile.channels}
        for role,addr in [('mains_i_l1',1076),('mains_kw',1560),('mains_kva',1568),('mains_kvar',1576),('mains_fp',1581),('energy_mains',1810)]:
            self.assertGreater(rs[role].number,59);self.assertEqual(int(rs[role].params['ADDR']),addr)
        self.assertEqual(p.profile.count,74)

    def test_studio8_8620_bin_is_upgraded_without_losing_existing_metadata(self):
        from logsis_studio.core import DEFAULT_MDB
        import copy
        p=Project.new('DSE8620');old=copy.deepcopy(p.rows[:59]);old[0]['DM']='Óleo personalizado'
        p.rows=old+[dict(DEFAULT_MDB) for _ in range(41)]
        updates={f'MDBA_{k}{i}':v for i,row in enumerate(p.rows) for k,v in row.items()}
        binary=p.document.render(updates)
        migrated=Project.from_bytes(binary)
        self.assertEqual(migrated.profile.model,'DSE8620')
        self.assertEqual(migrated.rows[:59],old)
        self.assertFalse(migrated.validate())


@unittest.skipUnless(os.environ.get('DISPLAY'),'Tk requer DISPLAY')
class DeifInterfaceTests(unittest.TestCase):
    def test_branding_and_all_deif_screens(self):
        from logsis_studio.app import Studio
        app=Studio();app.update()
        try:
            self.assertGreater(app._brand_source.width(),64)
            self.assertGreater(app._brand_source.get(500,500)[2],100)
            self.assertIn('Sistel',app.title())
            with patch('logsis_studio.app.messagebox.askyesno',return_value=True):
                for model in available_models():
                    if Project.new(model).profile.vendor!='DEIF':continue
                    app.switch_model(model)
                    for page in range(5):app.show_page(page);app.update()
                    self.assertFalse(app.project.validate());self.assertEqual(app.energy_var.get(),'1')
                    self.assertEqual(str(app.energy_entry.cget('state')),'disabled')
                app.switch_model('DSE7420');app.update()
                self.assertEqual(str(app.energy_entry.cget('state')),'normal')
        finally:app.destroy()
