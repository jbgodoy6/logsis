import asyncio
import copy
import math
import os
import struct
import unittest

from pydantic import ValidationError
from app.meter import (DEFAULT_METER, Meter, crc16, decode_registers, normalize_meter,
                       read_meter, read_rtu)


def mapping(key='power_total_kw', **changes):
    return dict(measurement=key, enabled=True, address=10, function=3,
                type='float32', scale=1, word_order='big', byte_order='big') | changes


class MapTests(unittest.TestCase):
    def test_four_byte_orders(self):
        raw = struct.pack('>f', 1234.5)
        for word_order, byte_order, encoded in [
            ('big', 'big', raw), ('little', 'big', raw[2:]+raw[:2]),
            ('big', 'little', raw[1::-1]+raw[3:1:-1]), ('little', 'little', raw[::-1])]:
            self.assertEqual(decode_registers(encoded, mapping(word_order=word_order, byte_order=byte_order)), 1234.5)

    def test_types_scaling_and_64bit(self):
        self.assertEqual(decode_registers(struct.pack('>i', -12000), mapping(type='int32', scale=.001)), -12)
        self.assertEqual(decode_registers(struct.pack('>Q', 123456789), mapping('energy_import_kwh', type='uint64', scale=.001)), 123456.789)
        self.assertEqual(decode_registers(struct.pack('>d', 1000.25), mapping(type='float64')), 1000.25)

    def test_nonfinite_wrong_length_and_negative_energy_rejected(self):
        with self.assertRaises(ValueError): decode_registers(struct.pack('>f', math.nan), mapping())
        with self.assertRaises(ValueError): decode_registers(b'\x00\x01', mapping())
        with self.assertRaises(ValueError): decode_registers(struct.pack('>f', -1), mapping('energy_import_kwh'))

    def test_modbus_crc_known_frame(self):
        self.assertEqual(struct.pack('<H', crc16(bytes.fromhex('01030000000a'))).hex(), 'c5cd')

    def test_v01_configuration_migration_preserves_register(self):
        old = {'host': '192.0.2.1', 'port': 1502, 'unit': 8, 'address': 123,
               'type': 'int32', 'word_order': 'little', 'scale': .001, 'poll_s': 2}
        migrated = Meter.model_validate(normalize_meter(old))
        self.assertEqual(migrated.host, old['host'])
        self.assertEqual(migrated.registers[0].address, 123)
        self.assertEqual(migrated.registers[0].type, 'int32')
        self.assertEqual(migrated.registers[0].word_order, 'little')
        self.assertEqual(migrated.registers[0].scale, .001)

    def test_one_based_offsets_and_register_overrun(self):
        config = copy.deepcopy(DEFAULT_METER)
        config.update(address_base=1, registers=[mapping(address=1)])
        self.assertEqual(Meter.model_validate(config).address_base, 1)
        for changes in [dict(address=0), dict(address=65536, type='float32'), dict(function=6), dict(scale=0)]:
            with self.assertRaises(ValidationError):
                Meter.model_validate(config | {'registers': [mapping(**changes)]})

    def test_duplicate_measurement_rejected(self):
        with self.assertRaises(ValidationError):
            Meter.model_validate(copy.deepcopy(DEFAULT_METER) | {'registers': [mapping(), mapping(address=20)]})

    def test_tcp_unit255_supported_but_rtu_broadcast_rejected(self):
        self.assertEqual(Meter.model_validate(copy.deepcopy(DEFAULT_METER) | {'unit': 255}).unit, 255)
        for unit in (0, 255):
            with self.assertRaises(ValidationError):
                Meter.model_validate(copy.deepcopy(DEFAULT_METER) | {'transport': 'rtu', 'unit': unit})


class FakeSerial:
    def __init__(self, **kwargs):
        self.buffer = b''
        self.requests = []
        self.bad_crc = False
        self.exception = False
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def reset_input_buffer(self): self.buffer = b''
    def flush(self): pass
    def write(self, data):
        self.requests.append(data)
        if self.exception:
            payload = bytes([data[0], data[1] | 0x80, 2])
        else:
            payload = bytes([data[0], data[1], 4]) + struct.pack('>f', 321.5)
        self.buffer = payload + struct.pack('<H', crc16(payload) ^ (1 if self.bad_crc else 0))
        return len(data)
    def read(self, count):
        data, self.buffer = self.buffer[:count], self.buffer[count:]
        return data


class RTUTests(unittest.TestCase):
    def test_rtu_request_crc_function04_and_base1(self):
        fake = FakeSerial()
        config = copy.deepcopy(DEFAULT_METER) | {'transport': 'rtu', 'serial_port': 'COM3', 'unit': 7, 'address_base': 1}
        readings = read_rtu(config, [mapping(address=101, function=4)], serial_factory=lambda **kwargs: fake)
        request = fake.requests[0]
        self.assertEqual(request[:6], bytes.fromhex('070400640002'))
        self.assertEqual(crc16(request[:-2]), struct.unpack('<H', request[-2:])[0])
        self.assertEqual(readings[0]['value'], 321.5)

    def test_corrupt_crc_is_rejected(self):
        fake = FakeSerial();fake.bad_crc = True
        with self.assertRaisesRegex(ValueError, 'CRC'):
            read_rtu(copy.deepcopy(DEFAULT_METER), [mapping()], serial_factory=lambda **kwargs: fake)

    def test_exception_retains_map_and_no_fabricated_value(self):
        fake = FakeSerial();fake.exception = True
        rows = read_rtu(copy.deepcopy(DEFAULT_METER), [mapping()], serial_factory=lambda **kwargs: fake)
        self.assertIsNone(rows[0]['value'])
        self.assertIn('Exceção Modbus 2', rows[0]['error'])


class TCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_multiple_manual_registers_fc03_fc04_base1(self):
        received = []
        async def reply(reader, writer):
            try:
                for value in (1234.5, 12345.0):
                    request = await reader.readexactly(12)
                    _, _, _, unit, function, address, count = struct.unpack('>HHHBBHH', request)
                    received.append((unit, function, address, count))
                    body = bytes([function, 4]) + struct.pack('>f', value)
                    writer.write(request[:2] + struct.pack('>HHB', 0, len(body) + 1, unit) + body)
                    await writer.drain()
            finally:
                writer.close();await writer.wait_closed()
        server = await asyncio.start_server(reply, '127.0.0.1', 0)
        async with server:
            config = copy.deepcopy(DEFAULT_METER) | {'host': '127.0.0.1', 'port': server.sockets[0].getsockname()[1],
                     'unit': 9, 'address_base': 1, 'registers': [mapping(address=101), mapping('energy_import_kwh', address=201, function=4)]}
            rows = await read_meter(config)
        self.assertEqual(received, [(9, 3, 100, 2), (9, 4, 200, 2)])
        self.assertEqual([r['value'] for r in rows], [1234.5, 12345.0])

    @unittest.skipUnless(os.name == 'posix', 'Pseudo-terminal de validação disponível no Linux')
    async def test_rtu_through_real_pyserial_driver(self):
        import select
        import threading
        master, slave = os.openpty()
        port = os.ttyname(slave)
        requests = []
        errors = []
        def device():
            try:
                packet = b''
                while len(packet) < 8:
                    if not select.select([master], [], [], 3)[0]:
                        raise TimeoutError('Controlador não enviou quadro RTU')
                    packet += os.read(master, 8 - len(packet))
                requests.append(packet)
                data = bytes([3, 4, 4]) + struct.pack('>f', 432.5)
                os.write(master, data + struct.pack('<H', crc16(data)))
            except Exception as exc:
                errors.append(str(exc))
        thread = threading.Thread(target=device, daemon=True)
        thread.start()
        try:
            config = copy.deepcopy(DEFAULT_METER) | {'transport': 'rtu', 'serial_port': port,
                     'unit': 3, 'timeout_s': 1, 'registers': [mapping(address=1234, function=4)]}
            rows = await read_meter(config)
            self.assertEqual(rows[0]['value'], 432.5)
            self.assertEqual(requests[0][:6], struct.pack('>BBHH', 3, 4, 1234, 2))
            self.assertFalse(errors)
        finally:
            os.close(master);os.close(slave)
            thread.join(timeout=4)


if __name__ == '__main__': unittest.main()
