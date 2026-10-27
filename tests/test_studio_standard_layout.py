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
