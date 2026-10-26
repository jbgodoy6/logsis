"""Manual read-only Modbus maps, shared by TCP and RS485/RTU transports."""
import asyncio
import copy
import math
import secrets
import struct
import threading
import time

from pydantic import BaseModel, ConfigDict, Field, model_validator


MEASUREMENTS = {
    'power_total_kw': ('Potência ativa total', 'kW'),
    'energy_import_kwh': ('Energia ativa importada', 'kWh'),
    'current_l1_a': ('Corrente L1', 'A'), 'current_l2_a': ('Corrente L2', 'A'),
    'current_l3_a': ('Corrente L3', 'A'), 'voltage_l1_v': ('Tensão L1–N', 'V'),
    'voltage_l2_v': ('Tensão L2–N', 'V'), 'voltage_l3_v': ('Tensão L3–N', 'V'),
    'frequency_hz': ('Frequência', 'Hz'), 'power_factor': ('Fator de potência', ''),
    'power_l1_kw': ('Potência ativa L1', 'kW'), 'power_l2_kw': ('Potência ativa L2', 'kW'),
    'power_l3_kw': ('Potência ativa L3', 'kW'),
}
FORMATS = {'float32': ('f', 2), 'float64': ('d', 4), 'int16': ('h', 1),
           'uint16': ('H', 1), 'int32': ('i', 2), 'uint32': ('I', 2),
           'int64': ('q', 4), 'uint64': ('Q', 4)}
DEFAULT_METER = {
    'transport': 'tcp', 'host': '', 'port': 502, 'unit': 1, 'poll_s': 1.0,
    'timeout_s': 2.0, 'serial_port': '', 'baudrate': 9600, 'parity': 'N',
    'stopbits': 1, 'bytesize': 8, 'address_base': 0,
    'registers': [{'measurement': key, 'enabled': key == 'power_total_kw',
                   'address': 0, 'function': 3, 'type': 'float32', 'scale': 1.0,
                   'word_order': 'big', 'byte_order': 'big'} for key in MEASUREMENTS],
}


def normalize_meter(data):
    """Migrate v0.1 without changing the configured register's meaning."""
    result = copy.deepcopy(DEFAULT_METER)
    for key in result:
        if key in data:
            result[key] = copy.deepcopy(data[key])
    if 'registers' not in data:
        for key in ('address', 'type', 'scale', 'word_order'):
            if key in data:
                result['registers'][0][key] = data[key]
    return result


class Register(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    measurement: str
    enabled: bool = True
    address: int = Field(ge=0, le=65536)
    function: int = 3
    type: str = 'float32'
    scale: float = 1.0
    word_order: str = 'big'
    byte_order: str = 'big'

    @model_validator(mode='after')
    def valid(self):
        if self.measurement not in MEASUREMENTS or self.type not in FORMATS:
            raise ValueError('Grandeza ou tipo de registrador desconhecido')
        if self.function not in (3, 4):
            raise ValueError('Use função 03 (holding) ou 04 (input)')
        if self.word_order not in ('big', 'little') or self.byte_order not in ('big', 'little'):
            raise ValueError('Ordem de bytes/palavras inválida')
        if self.scale == 0:
            raise ValueError('O fator de escala não pode ser zero')
        return self


class Meter(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    transport: str = 'tcp'
    host: str = Field(default='', max_length=253)
    port: int = Field(default=502, ge=1, le=65535)
    unit: int = Field(default=1, ge=0, le=255)
    poll_s: float = Field(default=1, ge=0.5, le=60)
    timeout_s: float = Field(default=2, ge=0.1, le=10)
    serial_port: str = Field(default='', max_length=200)
    baudrate: int = Field(default=9600, ge=300, le=921600)
    parity: str = 'N'
    stopbits: int = 1
    bytesize: int = 8
    address_base: int = 0
    registers: list[Register] = Field(min_length=1, max_length=len(MEASUREMENTS))

    @model_validator(mode='after')
    def valid(self):
        if self.transport not in ('tcp', 'rtu') or self.address_base not in (0, 1):
            raise ValueError('Transporte ou base de endereço inválidos')
        if self.transport == 'rtu' and not 1 <= self.unit <= 247:
            raise ValueError('Modbus RTU exige endereço do escravo entre 1 e 247')
        if self.parity not in ('N', 'E', 'O') or self.stopbits not in (1, 2) or self.bytesize != 8:
            raise ValueError('Parâmetros seriais inválidos para Modbus RTU')
        keys = [r.measurement for r in self.registers]
        if len(keys) != len(set(keys)):
            raise ValueError('Uma grandeza não pode ter dois endereços ativos ou cadastrados')
        for reg in self.registers:
            if reg.enabled:
                address = reg.address - self.address_base
                if address < 0 or address + FORMATS[reg.type][1] > 65536:
                    raise ValueError('Endereço fora do intervalo considerando base e tamanho do dado')
        return self


def crc16(data):
    value = 0xFFFF
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ 0xA001 if value & 1 else value >> 1
    return value


def decode_registers(raw, mapping):
    fmt, count = FORMATS[mapping['type']]
    if len(raw) != count * 2:
        raise ValueError('Quantidade de registradores diferente da configuração')
    words = [raw[i:i+2] for i in range(0, len(raw), 2)]
    if mapping.get('byte_order', 'big') == 'little':
        words = [w[::-1] for w in words]
    if mapping.get('word_order', 'big') == 'little':
        words.reverse()
    value = struct.unpack('>' + fmt, b''.join(words))[0] * mapping['scale']
    if not math.isfinite(value):
        raise ValueError('Leitura NaN/infinita; confira tipo e endianness')
    if mapping['measurement'].startswith(('energy_', 'current_', 'voltage_', 'frequency_')) and value < 0:
        raise ValueError('Valor negativo inválido para esta grandeza')
    return value


def result(mapping, raw=None, error=None):
    label, unit = MEASUREMENTS[mapping['measurement']]
    item = {'measurement': mapping['measurement'], 'label': label, 'unit': unit,
            'address': mapping['address'], 'function': mapping['function'], 'at': time.time()}
    if error:
        return item | {'value': None, 'error': error}
    try:
        return item | {'value': decode_registers(raw, mapping), 'error': None}
    except ValueError as exc:
        return item | {'value': None, 'error': str(exc)}


async def read_tcp(config, mappings):
    reader, writer = await asyncio.wait_for(asyncio.open_connection(config['host'], config['port']), config['timeout_s'])
    readings = []
    try:
        for mapping in mappings:
            transaction = secrets.randbelow(65536)
            count = FORMATS[mapping['type']][1]
            address = mapping['address'] - config['address_base']
            writer.write(struct.pack('>HHHBBHH', transaction, 0, 6, config['unit'], mapping['function'], address, count))
            await writer.drain()
            header = await asyncio.wait_for(reader.readexactly(7), config['timeout_s'])
            tid, protocol, length, unit = struct.unpack('>HHHB', header)
            if tid != transaction or protocol != 0 or unit != config['unit'] or not 3 <= length <= 254:
                raise ValueError('Cabeçalho Modbus TCP inválido')
            payload = await asyncio.wait_for(reader.readexactly(length - 1), config['timeout_s'])
            if payload[0] == mapping['function'] | 0x80:
                readings.append(result(mapping, error=f'Exceção Modbus {payload[1]}'))
            elif payload[0] != mapping['function'] or payload[1] != count * 2 or len(payload) != count * 2 + 2:
                raise ValueError('Função ou quantidade de bytes inesperada')
            else:
                readings.append(result(mapping, payload[2:]))
    finally:
        writer.close()
        await writer.wait_closed()
    return readings


_SERIAL_LOCK = threading.Lock()


def read_rtu(config, mappings, serial_factory=None):
    import serial
    factory = serial_factory or serial.Serial
    with _SERIAL_LOCK:
        with factory(port=config['serial_port'], baudrate=config['baudrate'], parity=config['parity'],
                     stopbits=config['stopbits'], bytesize=8, timeout=config['timeout_s'],
                     write_timeout=config['timeout_s']) as connection:
            readings = []
            for mapping in mappings:
                # RTU inter-frame silent interval (3.5 characters, minimum 1.75 ms).
                bits = 1 + 8 + (config['parity'] != 'N') + config['stopbits']
                time.sleep(max(.00175, 3.5 * bits / config['baudrate']))
                connection.reset_input_buffer()
                count = FORMATS[mapping['type']][1]
                request = struct.pack('>BBHH', config['unit'], mapping['function'],
                                      mapping['address'] - config['address_base'], count)
                frame = request + struct.pack('<H', crc16(request))
                if connection.write(frame) != len(frame):
                    raise ValueError('Escrita serial incompleta')
                connection.flush()
                header = connection.read(3)
                if len(header) != 3:
                    raise TimeoutError('Sem resposta RS485: confira porta, baudrate, ID, fiação e terminação')
                exception = header[1] == mapping['function'] | 0x80
                expected = 2 if exception else count * 2 + 2
                tail = connection.read(expected)
                response = header + tail
                if len(tail) != expected:
                    raise TimeoutError('Resposta RTU incompleta')
                if crc16(response[:-2]) != struct.unpack('<H', response[-2:])[0]:
                    raise ValueError('CRC Modbus RTU inválido')
                if header[0] != config['unit'] or header[1] != (mapping['function'] | (0x80 if exception else 0)):
                    raise ValueError('Resposta RTU de outro endereço/função')
                if exception:
                    readings.append(result(mapping, error=f'Exceção Modbus {header[2]}'))
                elif header[2] != count * 2:
                    raise ValueError('Quantidade de bytes RTU inesperada')
                else:
                    readings.append(result(mapping, tail[:-2]))
            return readings


async def read_meter(config):
    config = Meter.model_validate(normalize_meter(config)).model_dump()
    mappings = [r for r in config['registers'] if r['enabled']]
    if not mappings:
        raise ValueError('Habilite ao menos uma leitura no mapa')
    if config['transport'] == 'tcp':
        if not config['host']:
            raise ValueError('Informe o IP/endereço do multimedidor')
        return await read_tcp(config, mappings)
    if not config['serial_port']:
        raise ValueError('Informe a porta serial RS485')
    return await asyncio.to_thread(read_rtu, config, mappings)


async def read_modbus_power(config):
    """Compatibility helper; only the manually configured total-power register is read."""
    config = normalize_meter(config)
    config['registers'] = [r | {'enabled': True} for r in config['registers'] if r['measurement'] == 'power_total_kw']
    readings = await read_meter(config)
    if not readings or readings[0]['error']:
        raise ValueError(readings[0]['error'] if readings else 'Potência total não configurada')
    return readings[0]['value']
