import copy
from decimal import Decimal
import io
import json
from pathlib import Path
import socket
import socketserver
import struct
import tempfile
import threading
import types
import unittest
from unittest.mock import patch
import zipfile

from logsis_studio.core import BinDocument, DEFAULT_MDB, Project, RESOURCES, atomic_write, integer, load_profile, number
from logsis_studio.transport import ModbusError, crc16, decode, parse_pdu, read_exact, read_rtu, read_tcp, request_parameters


class ProfileTests(unittest.TestCase):
    def test_exact_mapping_and_zero_based_bin(self):
        common = {1: (1024, 3, -1), 8: (1031, 3, -1), 9: (1032, 30, -1), 22: (1536, 30, -1), 28: (1557, 3, -1), 36: (1798, 30, -1), 37: (1800, 30, -1), 40: (772, 3, -1), 41: (774, 3, 10), 42: (774, 3, 11), 43: (774, 3, 12), 44: (43521, 3, -1), 51: (43535, 3, -1), 52: (48659, 3, -1)}
        for model, count in [('DSE7420', 53), ('DSE8610', 52)]:
            with self.subTest(model=model):
                p = Project.new(model)
                self.assertEqual(p.validate(), [])
                self.assertEqual([c.number for c in p.profile.channels], list(range(1, count + 1)))
                params = BinDocument.from_bytes(p.bin_bytes()).params
                for n, expected in common.items():
                    self.assertEqual(tuple(int(params[f'MDBA_{k}{n-1}']) for k in ['ADDR', 'FNC', 'BIT']), expected)
                for index in range(count, 100):
                    self.assertEqual(tuple(params[f'MDBA_{k}{index}'] for k in ['ID', 'FNC', 'ADDR']), ('-1', '-1', '-1'))
                self.assertEqual(int(params['MDBA_ADDR28']), 1059 if model == 'DSE7420' else 1091)
                self.assertEqual(int(params['MDBA_ADDR29']), 1060 if model == 'DSE7420' else 1092)
                if model == 'DSE7420': self.assertEqual(params['MDBA_ADDR52'], '48660')
                self.assertNotIn('MDB_RST', params)
                self.assertNotIn('MDB_DLY', params)
                self.assertIn('MDB_RST_FAILURE', params)
                self.assertIn('MDB_R_DELAY', params)

    def test_profiles_match_independent_audited_bin(self):
        audit = json.loads((Path(__file__).resolve().parents[1] / 'DSE8610_ANALISE/DSE8610_AUDITORIA.json').read_text())
        rows = [r for r in audit['records'] if r['status'] == 'configurado']
        profile = load_profile('DSE8610')
        for channel, record in zip(profile.channels, rows):
            for field in ['ADDR', 'FNC', 'BIT']:
                self.assertEqual(int(channel.params[field]), int(record[field]))

    def test_round_trip_for_both_models(self):
        for model in ['DSE7420', 'DSE8610']:
            p = Project.new(model)
            data = p.bin_bytes()
            opened = Project.from_bytes(data)
            self.assertEqual(opened.profile.model, model)
            self.assertEqual(opened.rows, p.rows)
            self.assertEqual(opened.validate(), [])
            self.assertEqual(opened.bin_bytes(), data)

    def test_import_does_not_reorder_or_repair_silently(self):
        p = Project.new()
        p.rows[0], p.rows[1] = p.rows[1], p.rows[0]
        doc = p.document.render({f'MDBA_{k}{i}': v for i, row in enumerate(p.rows) for k, v in row.items()})
        imported = Project.from_bytes(doc)
        self.assertEqual(imported.rows[0]['ADDR'], '1025')
        self.assertTrue(imported.validate())
        with self.assertRaises(ValueError): imported.bin_bytes()
        imported.apply_profile()
        self.assertEqual(imported.validate(), [])
        self.assertEqual(imported.rows[0]['ADDR'], '1024')

    def test_reserved_slot_and_core_fields_block_export(self):
        for field, wrong in [('ADDR', '1'), ('FNC', '4'), ('BIT', '4'), ('ID', '2')]:
            p = Project.new()
            p.rows[0][field] = wrong
            self.assertTrue(p.validate())
            with self.assertRaises(ValueError): p.bundle_bytes('id_demo', 'Demo')
        p = Project.new('DSE8610')
        p.rows[52].update(ID='10', ADDR='48660', FNC='3')
        self.assertTrue(any(i.channel == 53 for i in p.validate()))

    def test_duplicate_and_out_of_range_keys_normalized_explicitly(self):
        p = Project.new()
        data = p.bin_bytes() + b'MDBA_ADDR0;900\nMDBA_ADDR100;1000\nCUSTOM;preservar\n'
        p = Project.from_bytes(data)
        self.assertTrue(any('duplicada' in i.message for i in p.validate()))
        self.assertTrue(any('100 slots' in i.message for i in p.validate()))
        p.apply_profile()
        self.assertEqual(p.validate(), [])
        self.assertIn(b'CUSTOM;preservar', p.bin_bytes())
        self.assertNotIn(b'MDBA_ADDR100;', p.bin_bytes())

    def test_unknown_settings_and_credentials_preserved_locally(self):
        p = Project.new()
        p.general.update(CUSTOM='valor original', WIFI_STA_SSID='rede de teste', WIFI_STA_PWD='senha;ficticia')
        original = p.bin_bytes()
        p = Project.from_bytes(original)
        p.rows[9]['DM'] = 'DESCRICAO NOVA'
        p.apply_profile()
        params = BinDocument.from_bytes(p.bin_bytes()).params
        for key, expected in [('CUSTOM', 'valor original'), ('WIFI_STA_SSID', 'rede de teste'), ('WIFI_STA_PWD', 'senha;ficticia')]:
            self.assertEqual(params[key], expected)

    def test_line_endings_encoding_bom_and_no_terminal_newline(self):
        for original in [b'CUSTOM;A\r\nOUTRO;B\r\n', b'CUSTOM;A\nOUTRO;B', '\ufeffCUSTOM;á\r\nOUTRO;B\r\n'.encode('utf-8'), 'CUSTOM;ação\r\nOUTRO;B'.encode('cp1252')]:
            doc = BinDocument.from_bytes(original)
            self.assertEqual(doc.render({}), original)
            output = doc.render({'OUTRO': 'C'})
            self.assertEqual(output, original.replace(b'OUTRO;B', b'OUTRO;C'))

    def test_safe_metadata_and_numeric_validation(self):
        p = Project.new()
        with self.assertRaises(ValueError): p.set_channel_metadata(0, {'ADDR': '2'})
        for value in ['NaN', 'Infinity', '-Infinity', 'x']:
            with self.assertRaises(ValueError): number(value)
            with self.assertRaises(ValueError): p.set_channel_metadata(0, {'TH': value})
        for text in ['a;b', 'a\nb', 'a\rb']:
            with self.assertRaises(ValueError): p.set_channel_metadata(0, {'DM': text})
        with self.assertRaises(ValueError): p.set_channel_metadata(0, {'TL': '100', 'TH': '10'})
        with self.assertRaises(ValueError): integer('1.5')
        p.slave = '248'
        self.assertTrue(p.validate())

    def test_limits_apply_voltage_without_changing_scales(self):
        p = Project.new()
        p.nominal.update(voltage='380', frequency='60', rpm='1800', battery='24')
        p.apply_profile()
        self.assertEqual((p.rows[7]['TL'], p.rows[7]['TH']), ('540', '660'))
        self.assertEqual((p.rows[5]['TL'], p.rows[5]['TH']), ('192', '288'))
        self.assertEqual((p.rows[6]['TL'], p.rows[6]['TH']), ('1620', '1980'))
        self.assertEqual(p.profile.channels[8].divisor, 10)
        self.assertEqual(p.profile.channels[35].divisor, 3600)

    def test_bundles_preserve_approved_dashboard_queries(self):
        for model in ['DSE7420', 'DSE8610']:
            p = Project.new(model)
            p.energy_divisor = '1'
            with zipfile.ZipFile(io.BytesIO(p.bundle_bytes('public.id_demo', 'Planta de teste', 'POSTGRES_UID'))) as archive:
                self.assertEqual(len(archive.namelist()), 5)
                self.assertIn(model + '.bin', archive.namelist())
                dashboard = json.loads(archive.read(model + '_GRAFANA.json'))
                expected = json.loads((RESOURCES / p.profile.dashboard).read_text())
                def targets(panels):
                    return [t.get('rawSql') for panel in panels for t in panel.get('targets', [])] + [v for panel in panels for v in targets(panel.get('panels', []))]
                self.assertEqual(targets(dashboard['panels']), targets(expected['panels']))
                variables = {v['name']: v['query'] for v in dashboard['templating']['list']}
                self.assertEqual(variables['Id_Logsis'], 'public.id_demo')
                self.assertEqual(variables['Divisor_Energia'], '1')
                self.assertEqual(dashboard['timezone'], 'America/Sao_Paulo')
                report = json.loads(archive.read('COMPATIBILIDADE.json'))
                self.assertEqual(report['channels'], p.profile.count)
                self.assertEqual(report['channels_map'][0]['bin_index'], 0)
                self.assertEqual(report['channels_map'][0]['sql_column'], 'mdb1')
                self.assertEqual(report['channels_map'][36]['divisor'], '1')
                self.assertNotIn('senha-ficticia', json.dumps(report))
                self.assertIn(b'MDB01;mdb1;0;', archive.read(model + '_MAPA.csv'))

    def test_unique_stable_dashboard_uids_and_explicit_update(self):
        p = Project.new()
        a = p.dashboard('id_a', 'A', 'ds')['uid']
        self.assertEqual(a, p.dashboard('id_a', 'Outra legenda', 'ds')['uid'])
        self.assertNotEqual(a, p.dashboard('id_b', 'B', 'ds')['uid'])
        self.assertNotEqual(a, Project.new('DSE8610').dashboard('id_a', 'A', 'ds')['uid'])
        self.assertEqual(p.dashboard('id_a', 'A', 'ds', 'uid-existente')['uid'], 'uid-existente')
        for bad in ['id_a;DROP TABLE x', 'id_a --', 'id a', '"id_a"']:
            with self.assertRaises(ValueError): p.dashboard(bad, 'A', 'ds')

    def test_atomic_write_keeps_original_on_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'planta.bin'
            target.write_bytes(b'original')
            with patch('logsis_studio.core.os.replace', side_effect=OSError('teste')):
                with self.assertRaises(OSError): atomic_write(target, b'novo')
            self.assertEqual(target.read_bytes(), b'original')
            self.assertEqual(list(Path(folder).iterdir()), [target])
            atomic_write(target, b'novo')
            self.assertEqual(target.read_bytes(), b'novo')


class TransportTests(unittest.TestCase):
    def test_function_translation_and_bounds(self):
        for fn, wire, count in [(3, 3, 1), (4, 4, 1), (30, 3, 2), (40, 4, 2)]:
            self.assertEqual(request_parameters(10, fn, 1024), (10, wire, 1024, count))
        for args in [(0, 3, 0), (248, 3, 0), (10, 16, 0), (10, 30, 65535)]:
            with self.assertRaises(ValueError): request_parameters(*args)

    def test_tcp_fragmentation_actual_local_server(self):
        requests = []
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                header = read_exact(self.request.recv, 7)
                tid, proto, length, unit = struct.unpack('>HHHB', header)
                pdu = read_exact(self.request.recv, length - 1)
                requests.append((unit, struct.unpack('>BHH', pdu)))
                response = struct.pack('>HHHB', tid, 0, 7, unit) + b'\x03\x04\x12\x34\x56\x78'
                for byte in response: self.request.sendall(bytes([byte]))
        with socketserver.TCPServer(('127.0.0.1', 0), Handler) as server:
            thread = threading.Thread(target=server.handle_request, daemon=True); thread.start()
            result = read_tcp('127.0.0.1', server.server_address[1], 10, 30, 1032)
            thread.join(timeout=2)
        self.assertEqual(result, (0x1234, 0x5678))
        self.assertEqual(requests, [(10, (3, 1032, 2))])

    def test_tcp_header_exception_and_truncated_response(self):
        def connection(response):
            class Connection:
                def __enter__(self): return self
                def __exit__(self, *_): pass
                def settimeout(self, _): pass
                def sendall(self, request):
                    self.data = bytearray(response(request))
                def recv(self, count):
                    data = bytes(self.data[:count]); del self.data[:count]; return data
            return Connection()
        def reply(request, **kw):
            tid, _, _, unit = struct.unpack('>HHHB', request[:7])
            pdu = kw.get('pdu', b'\x03\x02\x00\x01')
            return struct.pack('>HHHB', kw.get('tid', tid), kw.get('proto', 0), len(pdu)+1, kw.get('unit', unit))+pdu
        for maker in [lambda req: reply(req, tid=-1 & 65535) if struct.unpack('>H', req[:2])[0] != 65535 else reply(req, tid=1), lambda req: reply(req, proto=2), lambda req: reply(req, unit=2), lambda req: reply(req, pdu=b'\x83\x02'), lambda req: reply(req)[:-1]]:
            with patch('logsis_studio.transport.socket.create_connection', return_value=connection(maker)):
                with self.assertRaises(ValueError): read_tcp('localhost', 502, 10, 3, 0)
        with self.assertRaises(ValueError): parse_pdu(b'\x04\x02\x00\x01', 3, 1)
        with self.assertRaises(ValueError): parse_pdu(b'\x03\x04\x00\x01', 3, 1)

    def test_rtu_crc_exception_and_partial_reads(self):
        requests = []
        def serial_module(payload, corrupt=False):
            class Serial:
                def __init__(self, **_):
                    self.data = bytearray(payload + struct.pack('<H', crc16(payload) ^ (1 if corrupt else 0)))
                def __enter__(self): return self
                def __exit__(self, *_): pass
                def reset_input_buffer(self): pass
                def write(self, value): requests.append(value)
                def read(self, count):
                    value = bytes(self.data[:min(1, count)]); del self.data[:min(1, count)]; return value
            return types.SimpleNamespace(Serial=Serial)
        with patch.dict('sys.modules', serial=serial_module(b'\x0a\x03\x02\x00\x01')):
            self.assertEqual(read_rtu('FAKE', 19200, 'N', 1, 10, 3, 1024), (1,))
        self.assertEqual(struct.unpack('<H', requests[0][-2:])[0], crc16(requests[0][:-2]))
        for payload, corrupt in [(b'\x0a\x03\x02\x00\x01', True), (b'\x0b\x03\x02\x00\x01', False), (b'\x0a\x83\x02', False)]:
            with patch.dict('sys.modules', serial=serial_module(payload, corrupt)):
                with self.assertRaises(ValueError): read_rtu('FAKE', 19200, 'N', 1, 10, 3, 1024)

    def test_decode_engineering_sentinels_bits_and_states(self):
        p = Project.new()
        def reading(n, registers, **kw): return decode(p.profile.channels[n-1], p.rows[n-1], registers, **kw)
        self.assertEqual(reading(1, (450,)).engineering, Decimal('4.5'))
        self.assertIsNone(reading(1, (65535,)).engineering)
        self.assertEqual(reading(25, (65439,)).engineering, Decimal('-.97'))
        self.assertEqual(reading(2, (65531,)).engineering, Decimal('-5'))
        self.assertEqual(reading(22, (65535, 64536)).engineering, Decimal('-1'))
        self.assertEqual(reading(36, (0, 36000)).engineering, Decimal('10'))
        self.assertEqual(reading(37, (1, 0)).engineering, Decimal('6553.6'))
        self.assertEqual(reading(37, (0, 1), low_first=True).engineering, Decimal('6553.6'))
        self.assertIsNone(reading(36, (32767, 65535)).engineering)
        for n, word in [(41, 1024), (42, 2048), (43, 4096)]:
            self.assertEqual(reading(n, (word,)).state, 'ATIVO')
            self.assertEqual(reading(n, (word,)).bit, 1)
        self.assertEqual(reading(40, (3,)).state, 'TESTE COM CARGA')
        self.assertEqual(reading(40, (7,)).state, 'OFF')
        self.assertEqual(reading(52, (1,)).state, 'FECHADO')
        self.assertEqual(reading(52, (0,)).state, 'ABERTO')
        self.assertIsNone(reading(52, (2,)).engineering)
        self.assertEqual(reading(37, (0, 188), energy_divisor='1').engineering, Decimal('188'))


if __name__ == '__main__':
    unittest.main()
