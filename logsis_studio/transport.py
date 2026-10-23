"""Read-only Modbus transports. LogSis 30/40 mean two FC03/FC04 registers."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
import secrets
import socket
import struct

from .core import Channel, MODES, integer, number


class ModbusError(ValueError):
    pass


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc & 0xFFFF


def read_exact(reader, size):
    chunks = bytearray()
    while len(chunks) < size:
        chunk = reader(size - len(chunks))
        if not chunk:
            raise ModbusError('Resposta incompleta ou tempo de leitura esgotado.')
        chunks.extend(chunk)
    return bytes(chunks)


def request_parameters(slave, function, address):
    slave = integer(slave, 'Slave ID', 1, 247)
    function = integer(function, 'Função')
    if function not in [3, 4, 30, 40]:
        raise ModbusError('O teste aceita funções LogSis 3, 4, 30 e 40 (somente leitura).')
    address = integer(address, 'Endereço', 0, 65535)
    count = 2 if function in [30, 40] else 1
    if address + count > 65536:
        raise ModbusError('A leitura ultrapassa o último registrador Modbus.')
    return slave, 3 if function in [3, 30] else 4, address, count


def parse_pdu(pdu, function, count):
    if len(pdu) >= 2 and pdu[0] == function | 0x80:
        if len(pdu) != 2:
            raise ModbusError('Tamanho da exceção Modbus inválido.')
        names = {1: 'função não suportada', 2: 'endereço não disponível', 3: 'valor inválido', 4: 'falha no equipamento', 6: 'equipamento ocupado'}
        raise ModbusError(f'Exceção Modbus {pdu[1]:02d}: {names.get(pdu[1], "verifique o controlador")}.')
    if len(pdu) < 2 or pdu[0] != function:
        raise ModbusError('A resposta não corresponde à função solicitada.')
    expected = count * 2
    if pdu[1] != expected or len(pdu) != expected + 2:
        raise ModbusError('Quantidade de bytes diferente da leitura solicitada.')
    return tuple(struct.unpack('>' + 'H' * count, pdu[2:]))


def read_tcp(host, port, slave, function, address, timeout=3):
    slave, function, address, count = request_parameters(slave, function, address)
    port = integer(port, 'Porta TCP', 1, 65535)
    if not str(host).strip():
        raise ModbusError('Informe o endereço IP ou nome do equipamento.')
    transaction = secrets.randbelow(65536)
    pdu = struct.pack('>BHH', function, address, count)
    with socket.create_connection((str(host).strip(), port), timeout=timeout) as connection:
        connection.settimeout(timeout)
        connection.sendall(struct.pack('>HHHB', transaction, 0, len(pdu) + 1, slave) + pdu)
        header = read_exact(connection.recv, 7)
        tid, protocol, length, unit = struct.unpack('>HHHB', header)
        if (tid, protocol, unit) != (transaction, 0, slave):
            raise ModbusError('Cabeçalho TCP incompatível: transação, protocolo ou Slave ID.')
        if not 3 <= length <= 254:
            raise ModbusError('Tamanho da resposta TCP inválido.')
        return parse_pdu(read_exact(connection.recv, length - 1), function, count)


def read_rtu(port, baud, parity, stopbits, slave, function, address, timeout=2):
    try:
        import serial
    except ImportError as exc:
        raise ModbusError('Para RS485/USB, instale o componente opcional: python -m pip install pyserial') from exc
    slave, function, address, count = request_parameters(slave, function, address)
    baud = integer(baud, 'Baud rate', 1, 4000000)
    parity = str(parity).upper()
    if parity not in ['N', 'E', 'O'] or str(stopbits) not in ['1', '2']:
        raise ModbusError('Paridade: N, E ou O. Stop bits: 1 ou 2.')
    request = struct.pack('>BBHH', slave, function, address, count)
    request += struct.pack('<H', crc16(request))
    with serial.Serial(port=str(port).strip(), baudrate=baud, bytesize=8, parity=parity, stopbits=int(stopbits), timeout=timeout) as connection:
        connection.reset_input_buffer()
        connection.write(request)
        head = read_exact(connection.read, 2)
        if head[1] & 0x80:
            frame = head + read_exact(connection.read, 3)
            payload = frame[1:-2]
        else:
            length = read_exact(connection.read, 1)
            if length[0] > 250:
                raise ModbusError('Resposta RTU com tamanho inválido.')
            frame = head + length + read_exact(connection.read, length[0] + 2)
            payload = frame[1:-2]
        if struct.unpack('<H', frame[-2:])[0] != crc16(frame[:-2]):
            raise ModbusError('CRC da resposta RTU inválido.')
        if frame[0] != slave:
            raise ModbusError('A resposta RTU veio de outro Slave ID.')
        return parse_pdu(payload, function, count)


@dataclass(frozen=True)
class Reading:
    registers: tuple[int, ...]
    unsigned: int
    signed: int
    engineering: Decimal | None
    state: str
    bit: int | None


def decode(channel: Channel, row, registers, low_first=False, energy_divisor='10'):
    expected = 2 if str(row['FNC']) in ['30', '40'] else 1
    if len(registers) != expected or any(not 0 <= v <= 65535 for v in registers):
        raise ModbusError('Registradores incompatíveis com a função selecionada.')
    words = tuple(reversed(registers)) if low_first and expected == 2 else tuple(registers)
    unsigned = words[0] if expected == 1 else words[0] << 16 | words[1]
    width = 16 * expected
    signed = unsigned if unsigned < 1 << (width - 1) else unsigned - (1 << width)
    selected_bit = integer(row['BIT'], 'Bit', -1, width - 1)
    bit = (unsigned >> selected_bit) & 1 if selected_bit >= 0 else None
    unavailable = unsigned >= 32760 if expected == 1 else unsigned in [0x7FFFFFFF, 0x80000000, 0xFFFFFFFF]
    # Negative signed temperatures/PF are legitimate, except the sentinel band.
    if expected == 1 and channel.signed:
        unavailable = not -32759 <= signed <= 32759
    value = bit if bit is not None else signed if channel.signed else unsigned
    divisor = number(energy_divisor) if channel.number == 37 else Decimal(channel.divisor)
    if divisor <= 0:
        raise ModbusError('O divisor de engenharia deve ser positivo.')
    engineering = None if unavailable and bit is None else Decimal(value) / divisor
    state = ''
    if channel.number == 40:
        state = MODES.get(unsigned, 'MODO INVÁLIDO') if engineering is not None else 'SEM DADOS'
    elif channel.number >= 41:
        if engineering is None or value not in [0, 1]:
            state, engineering = 'ESTADO INVÁLIDO', None
        elif channel.number >= 52:
            state = 'FECHADO' if value else 'ABERTO'
        elif channel.number <= 43:
            state = 'ATIVO' if value else 'INATIVO'
        else:
            state = 'ON' if value else 'OFF'
    return Reading(tuple(registers), unsigned, signed, engineering, state, bit)
