"""Real Tk workflows. Use DISPLAY pointing to a local test X server."""
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from logsis_studio.core import Project


@unittest.skipUnless(os.environ.get('DISPLAY'), 'Interface requer DISPLAY local')
class InterfaceTests(unittest.TestCase):
    def setUp(self):
        from logsis_studio.app import Studio
        self.app = Studio()
        self.app.update()
        self.errors = []
        self.error_patch = patch('logsis_studio.app.messagebox.showerror', side_effect=lambda *args, **kwargs: self.errors.append(args))
        self.error_patch.start()
        self.yes_patch = patch('logsis_studio.app.messagebox.askyesno', return_value=True)
        self.yes_patch.start()
        self.info_patch = patch('logsis_studio.app.messagebox.showinfo', return_value=True)
        self.info_patch.start()

    def tearDown(self):
        self.app.destroy()
        self.error_patch.stop(); self.yes_patch.stop(); self.info_patch.stop()

    def test_models_and_hidden_channels_do_not_change_serialization(self):
        app = self.app
        self.assertEqual(len(app.tree.get_children()), 56)
        app.search.set('mdb53'); app.update()
        self.assertEqual(len(app.tree.get_children()), 1)
        self.assertEqual(app.project.validate(), [])
        self.assertEqual(len([r for r in app.project.rows if r['ADDR'] != '-1']), 56)
        app.table_var.set('id_primeira'); app.uid_var.set('uid-primeira')
        app.switch_model('DSE8610'); app.search.set(''); app.update()
        self.assertEqual(len(app.tree.get_children()), 55)
        self.assertEqual(app.table_var.get(), '')
        self.assertEqual(app.uid_var.get(), '')
        self.assertEqual(app.project.rows[55]['ADDR'], '-1')
        self.assertEqual(self.errors, [])

    def test_custom_input_name_and_maintenance_threshold_reach_export(self):
        app=self.app
        app.show_page(1)
        app.tree.selection_set('43');app.tree.event_generate('<<TreeviewSelect>>');app.update()
        app.editor['DM'].set('Porta da sala')
        app.maintenance_var.set('12.5')
        self.assertTrue(app.flush())
        self.assertEqual(app.tree.item('43','values')[1],'Porta da sala')
        d=app.project.dashboard('id_demo','Demo','ds')
        variables={v['name']:v['query'] for v in d['templating']['list']}
        self.assertEqual(variables['Nome_Entrada_A'],'Porta da sala')
        self.assertEqual(variables['Manutencao_Alerta_h'],'12.5')
        self.assertIn('NOME_ENTRADA_A',d['panels'][0]['targets'][0]['rawSql'])
        app.maintenance_var.set('-1')
        self.assertFalse(app.flush())

    def test_edit_and_row_selection_keep_changes_and_selection(self):
        app = self.app
        app.show_page(1); app.update()
        app.editor['DM'].set('PRESSAO AJUSTADA')
        self.assertTrue(app.has_pending_changes())
        app.tree.selection_set('1'); app.tree.event_generate('<<TreeviewSelect>>'); app.update()
        self.assertEqual(app.project.rows[0]['DM'], 'PRESSAO AJUSTADA')
        self.assertEqual(app.current, 1)
        self.assertEqual(app.tree.selection(), ('1',))
        self.assertEqual(self.errors, [])

    def test_invalid_editor_does_not_mutate_configuration(self):
        app = self.app
        original = dict(app.project.rows[0])
        app.editor['TL'].set('NaN')
        self.assertFalse(app.commit_editor())
        self.assertEqual(app.project.rows[0], original)
        self.assertTrue(self.errors)

    def test_import_keeps_mixed_slave_ids_until_explicit_repair(self):
        app = self.app
        imported = Project.new()
        imported.rows[2]['ID'] = '11'
        data = imported.document.render({f'MDBA_{field}{i}': value for i, row in enumerate(imported.rows) for field, value in row.items()})
        app.project = Project.from_bytes(data); app.sync_project()
        app.run_validation()
        self.assertEqual(app.project.rows[2]['ID'], '11')
        self.assertTrue(app.project.validate())
        app.slave_var.set('12'); self.assertTrue(app.flush())
        self.assertTrue(all(r['ID'] == '12' for r in app.project.rows[:56]))
        self.assertEqual(app.project.validate(), [])
        self.assertEqual(self.errors, [])

    def test_save_and_export_use_current_values(self):
        app = self.app
        app.plant_var.set('Planta de teste'); app.table_var.set('id_teste')
        app.energy_var.set('1'); app.show_page(4); app.update()
        self.assertEqual(app.project.energy_divisor, '1')
        with tempfile.TemporaryDirectory() as folder:
            binary = Path(folder) / 'config.bin'; bundle = Path(folder) / 'planta.zip'
            with patch('logsis_studio.app.filedialog.asksaveasfilename', return_value=str(binary)):
                app.save_bin()
            self.assertEqual(Project.open(binary).validate(), [])
            with patch('logsis_studio.app.filedialog.asksaveasfilename', return_value=str(bundle)):
                app.export_bundle()
            with zipfile.ZipFile(bundle) as archive:
                self.assertIn('DSE7420_GRAFANA.json', archive.namelist())
                self.assertIn(b'"query": "id_teste"', archive.read('DSE7420_GRAFANA.json'))
        self.assertEqual(self.errors, [])

    def test_open_bin_detects_controller_and_resets_export_destination(self):
        app = self.app
        app.table_var.set('id_antiga'); app.uid_var.set('uid-antigo')
        with tempfile.TemporaryDirectory() as folder:
            filename = Path(folder) / 'gerador8610.bin'; filename.write_bytes(Project.new('DSE8610').bin_bytes())
            with patch('logsis_studio.app.filedialog.askopenfilename', return_value=str(filename)):
                app.open_bin()
            app.update()
            self.assertEqual(app.project.profile.model, 'DSE8610')
            self.assertEqual(app.table_var.get(), '')
            self.assertEqual(app.uid_var.get(), '')
            self.assertEqual(app.plant_var.get(), 'gerador8610')
        self.assertEqual(self.errors, [])

    def test_actual_local_tcp_read_updates_gui_from_queue(self):
        import socketserver
        import struct
        import threading
        import time
        from logsis_studio.transport import read_exact
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                header = read_exact(self.request.recv, 7)
                tid, _, length, unit = struct.unpack('>HHHB', header)
                self.request.recv(length - 1)
                pdu = b'\x03\x02\x01\xc2'  # 450 raw = 4.50 bar
                self.request.sendall(struct.pack('>HHHB', tid, 0, len(pdu)+1, unit)+pdu)
        app = self.app
        with socketserver.TCPServer(('127.0.0.1', 0), Handler) as server:
            thread = threading.Thread(target=server.handle_request, daemon=True); thread.start()
            app.test_host.set('127.0.0.1'); app.test_port.set(str(server.server_address[1]))
            app.show_page(3); app.start_test()
            deadline = time.monotonic() + 4
            while app.busy and time.monotonic() < deadline:
                app.update(); time.sleep(.01)
            thread.join(timeout=1)
        self.assertFalse(app.busy)
        self.assertEqual(app.reading_value.get(), '4.50 bar')
        self.assertIn('Unsigned: 450', app.log.get('1.0', 'end'))
        self.assertEqual(self.errors, [])

    def test_all_pages_and_small_window_remain_accessible(self):
        app = self.app
        for width, height in [(1460, 920), (1120, 740)]:
            app.geometry(f'{width}x{height}'); app.update()
            for index in range(5):
                app.show_page(index); app.update()
                self.assertTrue(app.pages[index].winfo_ismapped())
                self.assertGreater(app.pages[index].winfo_width(), 0)
                self.assertLessEqual(app.pages[index].winfo_rootx() + app.pages[index].winfo_width(), app.winfo_rootx() + app.winfo_width())
        self.assertEqual(self.errors, [])


if __name__ == '__main__': unittest.main()
