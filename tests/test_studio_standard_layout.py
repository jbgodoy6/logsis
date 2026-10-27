import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import unittest
import zipfile

from logsis_studio.core import Project,available_models,RESOURCES


class StandardLayoutTests(unittest.TestCase):
    def test_company_and_bus_cards_include_all_measured_phase_voltages(self):
        p=Project.new('DSE8660');d=p.dashboard('id_demo','Planta','ds')
        es=d['panels'][0]['options']['root']['elements']
        for side,prefix in [(0,'mains'),(1,'bus')]:
            rows=[e for e in es if e['name'].startswith(f'Fonte leitura {side} ')]
            self.assertEqual(len(rows),5)
            labels=[e['config']['text']['fixed'] for e in es if e['name'].startswith(f'Fonte rótulo {side} ')]
            self.assertEqual(labels,['L1–L2','L2–L3','L3–L1','Freq.','Potência'])
            roles={c.role:f'MDB{c.number:02}' for c in p.profile.channels}
            for row,suffix in enumerate(['v_l1l2','v_l2l3','v_l3l1','frequency','kw']):
                self.assertEqual(rows[row]['config']['text']['field'],roles[prefix+'_'+suffix])
                self.assertLessEqual(rows[row]['placement']['top']+rows[row]['placement']['height'],456)

    def test_interconnection_conductors_have_visible_canvas_width(self):
        p=Project.new('DSE8660');es=p.dashboard('id_demo','Planta','ds')['panels'][0]['options']['root']['elements']
        for name in ['Traço fluido 14','Traço fluido 15','Traço fluido 20','Traço fluido 21','Traço fluido 24','Traço fluido 25','Traço fluido 28']:
            e=next(e for e in es if e['name']==name)
            self.assertLess(e['placement']['left']+e['placement']['right'],100,name)
            self.assertGreater(e['placement']['height'],0,name)

    def test_8660_switch_outputs_join_like_7420_without_series_bridge(self):
        p=Project.new('DSE8660');es=p.dashboard('id_demo','Planta','ds')['panels'][0]['options']['root']['elements']
        by_name={e['name']:e for e in es}
        self.assertFalse(any(name.startswith(('MB até BUS','BUS antes do TB','TB até carga')) for name in by_name))
        for name,alias in [('Traço fluido 15','WIRE_OUT_MAINS_V'),('Traço fluido 21','WIRE_OUT_BUS_V'),('Traço fluido 24','WIRE_OUT_H'),('Traço fluido 25','WIRE_OUT_V')]:
            self.assertEqual(by_name[name]['background']['image']['field'],alias)
        bar=by_name['Traço fluido 24']['placement']
        self.assertEqual((bar['left'],bar['right'],bar['top']),(25,25,609))
        for name in ['Traço fluido 15','Traço fluido 21']:
            wire=by_name[name]['placement']
            self.assertEqual(wire['top']+wire['height'],bar['top'])
        self.assertEqual(by_name['Traço fluido 25']['placement']['top'],bar['top'])

    def test_all_contact_drawings_reuse_exact_7420_vectors_not_led_circles(self):
        from logsis_studio.manual_dashboard import contact_assets
        from logsis_studio.deif_dashboard import switch
        from urllib.parse import unquote
        approved=contact_assets()
        for key,state in [('open','aberto'),('closed','fechado'),('unknown','desconhecido')]:
            self.assertIn('viewBox="0 0 60 44"',unquote(approved[key]))
        self.assertEqual(switch(0),approved['open'])
        self.assertEqual(switch(1),approved['closed'])
        self.assertEqual(switch(None),approved['unknown'])
        for model in available_models():
            p=Project.new(model)
            if p.profile.kind=='legacy':continue
            d=p.dashboard('id_demo','Planta','ds');elements=d['panels'][0]['options']['root']['elements']
            contacts=[e for e in elements if e['name'] in ['Posição MDB52','Posição MDB53','Disjuntor posição','Contato do acoplador']]
            if p.profile.topology!='engine':self.assertTrue(contacts,model)
            for e in contacts:
                name=e['background']['image']['field']
                self.assertTrue(name.startswith('CONTACT_LED_') or name in ['B1_SVG','B2_SVG'],(model,name))
            sql=d['panels'][0]['targets'][0]['rawSql']
            self.assertNotIn("THEN 'IND. ATIVA'",sql)
            if p.profile.vendor!='DEIF':self.assertIn("THEN 'FECHADO'",sql)
            for panel in d['panels']:
                for e in panel.get('options',{}).get('root',{}).get('elements',[]):
                    self.assertNotIn('LED',e.get('config',{}).get('text',{}).get('fixed',''),model)
                    if e.get('background',{}).get('image'):
                        self.assertLess(e['placement']['left']+e['placement']['right'],100,(model,e['name']))
            for c in p.profile.channels:
                if c.role.startswith('led_'):
                    self.assertIn('CONTACT_'+c.role.upper()+'_SVG',sql)
                    for uri in approved.values():self.assertIn(uri,sql)

    def test_all_models_follow_approved_grid_and_local_source_cards(self):
        for model in available_models():
            with self.subTest(model=model):
                p=Project.new(model);d=p.dashboard('id_demo','Planta','ds');first=d['panels'][0]
                self.assertEqual(first['gridPos'],{'x':0,'y':0,'w':12,'h':27})
                panels=d['panels']
                self.assertTrue(any(x['gridPos']=={'x':12,'y':0,'w':12,'h':16} for x in panels))
                self.assertTrue(any(x['gridPos']=={'x':12,'y':16,'w':12,'h':11} for x in panels))
                self.assertTrue(any(e['name'].startswith('Fonte leitura ') for e in first['options']['root']['elements']))
                for stat in (x for x in panels if x['type']=='stat'):
                    if '/ PERÍODO' in stat['title'] or ' / PERÍODO' in stat['title']:
                        self.assertLessEqual(stat['gridPos']['h'],3)

    def test_nonlegacy_references_bind_to_real_sql_fields(self):
        for model in available_models():
            p=Project.new(model)
            if p.profile.kind=='legacy':continue
            d=p.dashboard('id_demo','Planta','ds');sql=d['panels'][0]['targets'][0]['rawSql']
            names=set(re.findall(r'AS\s+"([^"]+)"',sql,re.I))
            for panel in d['panels']:
                if panel['type']!='canvas':continue
                for e in panel['options']['root']['elements']:
                    for ref in [e.get('config',{}).get('text',{}).get('field'),e.get('background',{}).get('image',{}).get('field')]:
                        if ref:self.assertIn(ref,names,(model,e['name'],ref))

    def test_nonengine_models_use_bus_artwork_and_no_motor_maintenance(self):
        for model in ['DSE8660','DSE8680','AGC150_MAINS']:
            p=Project.new(model);d=p.dashboard('id_demo','Planta','ds')
            elements=d['panels'][0]['options']['root']['elements']
            self.assertFalse(any(e['name']=='Gerador vetorial' for e in elements))
            self.assertFalse(any(e['name']=='Indicação de manutenção' for e in elements))

    def test_bin_maps_are_identical_to_pre_style_release(self):
        previous=json.loads(subprocess.check_output(['git','show','1932128:logsis_studio/resources/profiles.json']))
        self.assertEqual(json.loads((RESOURCES/'profiles.json').read_text(encoding='utf-8')),previous)
