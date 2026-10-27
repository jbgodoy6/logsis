import hashlib,io,json,os,unittest,zipfile
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch
from logsis_studio.core import Project,BinDocument,RESOURCES,available_models
from logsis_studio.transport import decode

NEW=['DSE4520','DSE6120','DSE6320','DSE7320','DSE8620','DSE8660','DSE8680']
class ManualProfilesTests(unittest.TestCase):
 def test_catalog_and_generations(self):
  self.assertEqual(len([m for m in available_models() if m.startswith('DSE')]),9)
  for model in ['DSE4520','DSE6120','DSE7320']:self.assertIn('MkII',Project.new(model).profile.label)
 def test_delivered_legacy_bin_definitions_and_dashboards_unchanged(self):
  expected=json.loads((Path(__file__).parent/'fixtures/studio72_legacy_hashes.json').read_text())
  raw=json.loads((RESOURCES/'profiles.json').read_text())
  for model,hashes in expected.items():
   p=Project.new(model)
   self.assertEqual(hashlib.sha256(p.bin_bytes()).hexdigest(),hashes['bin_sha256'])
   self.assertEqual(hashlib.sha256(json.dumps(raw[model],sort_keys=True,ensure_ascii=False).encode()).hexdigest(),hashes['definition_sha256'])
   self.assertEqual(hashlib.sha256((RESOURCES/p.profile.dashboard).read_bytes()).hexdigest(),hashes['dashboard_sha256'])
 def test_every_profile_roundtrips_with_explicit_model_and_reserved_slots(self):
  for model in NEW:
   p=Project.new(model);self.assertEqual(p.validate(),[])
   opened=Project.from_bytes(p.bin_bytes(),model)
   self.assertEqual(opened.profile.model,model);self.assertEqual(opened.bin_bytes(),p.bin_bytes())
   params=BinDocument.from_bytes(p.bin_bytes()).params
   for n in range(p.profile.count,100):self.assertEqual(params[f'MDBA_ID{n}'],'-1')
 def test_shared_map_is_not_silently_identified_as_another_controller(self):
  binary=Project.new('DSE4520').bin_bytes()
  with self.assertRaisesRegex(ValueError,'Mapa compartilhado'):Project.from_bytes(binary)
  p=Project.from_bytes(binary,'DSE7320');self.assertEqual(p.profile.model,'DSE7320');self.assertIn('DSE6320',p.model_candidates)
 def test_6120_flexible_sources_and_no_qrs_local_inputs_on_73xx(self):
  roles={c.role:c for c in Project.new('DSE6120').profile.channels}
  self.assertEqual([int(roles['input_flex_'+letter].params['ADDR']) for letter in 'ABCD'],[43533,43535,43537,43539])
  self.assertNotIn('input_G',roles)
  for model in ['DSE4520','DSE6320','DSE7320']:
   p=Project.new(model);self.assertFalse(any(c.params['ADDR'] in ['43553','43555','43557'] for c in p.profile.channels))
 def test_manual_leds_are_not_reported_as_physical_contacts(self):
  expected={'DSE4520':{'led_mains':48653,'led_gen':48654},'DSE8620':{'led_mains':48659,'led_gen':48660},'DSE8660':{'led_mains':48659,'led_bus':48660},'DSE8680':{'led_tie':48659,'led_bus_live':48658,'led_bus2_live':48661}}
  for model,signals in expected.items():
   p=Project.new(model);roles={c.role:c for c in p.profile.channels}
   for role,address in signals.items():
    c=roles[role];self.assertEqual(int(c.params['ADDR']),address)
    self.assertEqual(decode(c,p.rows[c.index],(1,)).state,'LED ATIVO')
    self.assertEqual(decode(c,p.rows[c.index],(0,)).state,'LED INATIVO')
 def test_non_engine_profiles_have_no_fictitious_engine_or_maintenance(self):
  for model in ['DSE8660','DSE8680']:
   p=Project.new(model);roles={c.role:c for c in p.profile.channels}
   self.assertNotIn('hour_meter',roles);self.assertNotIn('energy_gen',roles)
   self.assertFalse(any(role.startswith('maintenance_') for role in roles))
   c=roles['energy_bus'];self.assertEqual(decode(c,p.rows[c.index],(0,1000)).engineering,Decimal('100'))
  roles={c.role:c for c in Project.new('DSE8680').profile.channels}
  self.assertEqual(int(roles['bus2_frequency'].params['ADDR']),1119)
  self.assertEqual(int(roles['bus2_fp'].params['ADDR']),1621)
  self.assertNotIn('energy_bus2',roles)
 def test_custom_names_report_and_dashboard_columns_share_the_same_map(self):
  for model in NEW:
   p=Project.new(model);c=next(c for c in p.profile.channels if c.input_letter)
   p.rows[c.index]['DM']="Porta d'água"
   with zipfile.ZipFile(io.BytesIO(p.bundle_bytes('id_demo','Planta','ds'))) as archive:
    report=json.loads(archive.read('COMPATIBILIDADE.json'));d=json.loads(archive.read(model+'_GRAFANA.json'))
    self.assertEqual(report['role_columns'][c.role],c.column)
    variables={v['name']:v['query'] for v in d['templating']['list']}
    self.assertEqual(variables[c.label_variable],"Porta d'água")
    self.assertEqual(d['timezone'],'America/Sao_Paulo')
    self.assertIn('LED indicators',report['signal_semantics'])
    self.assertIn("payload->>'"+c.column+"'",d['panels'][0]['targets'][0]['rawSql'])
 def test_nominal_limits_follow_roles_not_legacy_numeric_positions(self):
  p=Project.new('DSE8660');roles={c.role:c for c in p.profile.channels}
  c=roles['bus_i_earth'];self.assertEqual(p.rows[c.index]['TH'],c.params['TH'])
  c=roles['mains_v_l1n'];self.assertGreater(int(p.rows[c.index]['TH']),2000)

@unittest.skipUnless(os.environ.get('DISPLAY'),'Tk requer DISPLAY')
class ManualInterfaceTests(unittest.TestCase):
 def test_all_nine_models_are_selectable_and_exportable(self):
  from logsis_studio.app import Studio
  app=Studio();app.update()
  try:
   self.assertEqual(len(app.model_labels),len(available_models()))
   with patch('logsis_studio.app.messagebox.askyesno',return_value=True):
    for model in NEW:
     app.switch_model(model);app.show_page(4);app.update()
     self.assertEqual(app.project.profile.model,model)
     self.assertEqual(app.project.validate(),[])
     self.assertEqual(app.table_var.get(),'')
     self.assertEqual(app.uid_var.get(),'')
     self.assertTrue(app.project.bundle_bytes('id_demo','Teste'))
  finally:app.destroy()
 def test_6120_flex_name_and_source_uid_in_interface(self):
  from logsis_studio.app import Studio
  app=Studio();app.update()
  try:
   with patch('logsis_studio.app.messagebox.askyesno',return_value=True):app.switch_model('DSE6120')
   c=next(c for c in app.project.profile.channels if c.role=='input_flex_A')
   app.show_page(1);app.tree.selection_set(str(c.index));app.tree.event_generate('<<TreeviewSelect>>');app.update()
   app.editor['DM'].set('Reservatório');self.assertTrue(app.flush())
   d=app.project.dashboard('id_demo','Teste','ds');self.assertEqual(next(v['query'] for v in d['templating']['list'] if v['name']==c.label_variable),'Reservatório')
   app.reference_uid();self.assertIn('dse6120',app.uid_var.get())
  finally:app.destroy()
