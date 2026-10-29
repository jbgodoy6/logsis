import hashlib,io,json,os,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from logsis_studio.core import Project,load_profile,available_models,BinDocument,RESOURCES

class ElectronicProfilesTests(unittest.TestCase):
    def test_preserved_profiles_have_exact_baseline_content(self):
        baseline=json.loads((RESOURCES.parent.parent/'planejamento/REVISAO_CONTROLADORES_2026_10_29/REFERENCIAS_PRESERVADAS.json').read_text())
        data=json.loads((RESOURCES/'profiles.json').read_text())
        for model,ref in baseline['models'].items():
            actual=hashlib.sha256(json.dumps(data[model],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            self.assertEqual(actual,ref['profileSha256'],model)

    def test_new_profiles_contiguous_and_backup_detection_roundtrips(self):
        for model in available_models():
            p=Project.new(model)
            if not p.profile.base_model:continue
            self.assertEqual([c.number for c in p.profile.channels],list(range(1,p.profile.count+1)))
            self.assertLessEqual(p.profile.count,100)
            self.assertFalse(p.validate())
            b=p.bin_bytes();self.assertEqual(Project.from_bytes(b,model).bin_bytes(),b,model)
            if p.profile.motor_type=='ecu':
                self.assertTrue(any(c.role.startswith('ecu_') for c in p.profile.channels))
                self.assertNotIn(p.profile.base_model,['DSE8660','DSE8680','CGC412','CGC413'])

    def test_8620_approved_total_slots_and_raw_communication(self):
        p=Project.new('DSE8620_TC_UNICO');rs={c.role:c for c in p.profile.channels}
        self.assertEqual(p.profile.count,65)
        self.assertEqual([(rs[r].number,rs[r].params['ADDR']) for r in ['mains_i_l1','mains_kw_l1','mains_kw','mains_kva','mains_kvar','mains_fp_l1']],[(60,'1076'),(61,'1084'),(62,'1560'),(63,'1568'),(64,'1576'),(65,'1578')])
        self.assertNotIn('energy_mains',rs);self.assertNotIn('mains_i_l2',rs)
        p.general['WIFI_STA_SSID']='rede-de-teste';p.general['WIFI_STA_PWD']='somente-teste';p.general['MDB_BAUD']='9600';p.change_slave(7)
        b=BinDocument.from_bytes(p.bin_bytes()).params;self.assertEqual(b['WIFI_STA_SSID'],'rede-de-teste');self.assertEqual(b['MDBA_ID0'],'7');self.assertEqual(b['MDB_BAUD'],'9600')

    def test_ecu_validity_scales_and_pressure_identity(self):
        d={c.role:c for c in load_profile('DSE7420_ECU').channels}
        self.assertEqual((d['ecu_fuel_pressure'].params['ADDR'],d['ecu_fuel_pressure'].divisor,d['ecu_fuel_pressure'].unit),('1282',100,'bar'))
        self.assertEqual((d['ecu_rail_pressure'].params['ADDR'],d['ecu_rail_pressure'].divisor,d['ecu_rail_pressure'].unit),('1360',100,'MPa'))
        a={c.role:c for c in load_profile('AGC150_GEN_ECU').channels}
        self.assertEqual((a['ecu_fuel_pressure'].params['ADDR'],a['ecu_fuel_pressure'].validity_role,a['ecu_fuel_pressure'].validity_bit),('26022','ecu_validity_2',9))
        self.assertEqual(a['mode_semi_auto'].params['BIT'],'2');self.assertEqual(a['mode_no_regulation'].params['BIT'],'1')
        self.assertEqual(sum(c.role.startswith('alarm_word_') for c in a.values()),1)

    def test_matched_export_metadata_and_query_fields(self):
        for model in available_models():
            p=Project.new(model)
            if not p.profile.motor_type:continue
            with zipfile.ZipFile(io.BytesIO(p.bundle_bytes('id_demo','Planta','ds'))) as z:
                b=BinDocument.from_bytes(z.read(model+'.bin')).params;d=json.loads(z.read(model+'_GRAFANA.json'));report=json.loads(z.read('COMPATIBILIDADE.json'))
                self.assertEqual(report['motor_type'],'ecu');self.assertEqual(report['base_model'],p.profile.base_model)
                self.assertEqual(d['timezone'],'America/Sao_Paulo')
                for c in p.profile.channels:self.assertEqual(b[f'MDBA_ADDR{c.index}'],c.params['ADDR'])
                self.assertIn('ORDER BY "time" DESC LIMIT 1',d['panels'][0]['targets'][0]['rawSql'])

    def test_configurable_energy_scale_stays_bound_to_queries(self):
        p=Project.new('DSE7420_ECU');p.energy_divisor='100'
        d=p.dashboard('id_demo','Planta','ds')
        self.assertEqual(next(v['query'] for v in d['templating']['list'] if v['name']=='Divisor_Energia'),'100')
        self.assertIn('${Divisor_Energia:sqlstring}',d['panels'][0]['targets'][0]['rawSql'])

@unittest.skipUnless(os.environ.get('DISPLAY'),'Tk requires a display')
class ElectronicInterfaceTests(unittest.TestCase):
    def test_switch_from_real_backup_preserves_network_and_slave(self):
        from logsis_studio.app import Studio
        app=Studio();app.update()
        try:
            p=Project.new('DSE7420');p.general.update(WIFI_STA_SSID='local-teste',WIFI_STA_PWD='nao-real',MDB_BAUD='9600');p.change_slave(7)
            p.rows[0].update(DM='Óleo personalizado',TH='1234',TL='12')
            with tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'backup.bin';path.write_bytes(p.bin_bytes());app.project=Project.open(path);app.sync_project()
                with patch('logsis_studio.app.messagebox.askyesno',return_value=True):app.switch_model('DSE7420_ECU')
                app.update();self.assertEqual(app.project.general['WIFI_STA_SSID'],'local-teste');self.assertEqual(app.project.slave,'7');self.assertEqual(app.project.general['MDB_BAUD'],'9600');self.assertIn('Eletrônico',app.model_var.get())
                self.assertFalse(app.project.validate())
                self.assertEqual(app.project.rows[0]['DM'],'Óleo personalizado')
                self.assertEqual(app.project.rows[0]['TH'],'1234')
        finally:app.destroy()
