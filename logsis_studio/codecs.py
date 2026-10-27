"""Decode integer telemetry without requiring FLOAT support in the LogSis firmware.

SQL expressions are pure PostgreSQL: no extension, database function or write.
CDAB is the two 16-bit words as read from the wire, packed high-word first
by LogSis 30/40. Both signed and unsigned representations preserve those bits.
"""
from __future__ import annotations
from decimal import Decimal
import math
import struct


def decode_value(channel, raw):
    if raw is None:
        return None
    try:
        value = Decimal(str(raw))
        width = 32 if channel.params['FNC'] in ['30', '40'] else 16
        if not value.is_finite() or value != value.to_integral_value() or not -(1 << (width-1)) <= value < (1 << width):
            return None
        bits = int(value) % (1 << width)
        if channel.codec == 'float32_cdab':
            bits = ((bits & 65535) << 16) | (bits >> 16)
            result = struct.unpack('>f', struct.pack('>I', bits))[0]
            return Decimal(str(result)) / Decimal(channel.divisor) if math.isfinite(result) else None
        if channel.codec == 'boolean':
            return Decimal(bits) if bits in (0, 1) else None
        if channel.signed and bits >= 1 << (width-1):
            bits -= 1 << width
        return Decimal(bits) / Decimal(channel.divisor)
    except (ValueError, TypeError, ArithmeticError):
        return None


def sql_value(channel, expression):
    """Expression is validated numeric or NULL; reject fractions/out-of-width values."""
    width = 32 if channel.params['FNC'] in ['30', '40'] else 16
    wrap = 1 << width
    valid = f'({expression} = trunc({expression}) AND {expression} BETWEEN {-wrap//2} AND {wrap-1})'
    bits = f'mod(({expression})::numeric+{wrap},{wrap})'
    if channel.codec == 'float32_cdab':
        ordered = f'((({bits})::bigint & 65535) << 16 | (({bits})::bigint >> 16))'
        exponent = f'(({ordered} >> 23) & 255)'
        mantissa = f'({ordered} & 8388607)'
        sign = f'(CASE WHEN ({ordered} & 2147483648)<>0 THEN -1 ELSE 1 END)'
        result = f'''CASE WHEN {exponent}=255 THEN NULL
            WHEN {exponent}=0 THEN {sign}*{mantissa}*power(2::double precision,-149)
            ELSE {sign}*(1+{mantissa}/8388608.0)*power(2::double precision,{exponent}-127) END'''
    elif channel.codec == 'boolean':
        result = f'CASE WHEN {bits} IN (0,1) THEN {bits} END'
    elif channel.signed:
        result = f'CASE WHEN {bits}>={wrap//2} THEN {bits}-{wrap} ELSE {bits} END'
    else:
        result = bits
    return f'(CASE WHEN {valid} THEN ({result}) END)/{channel.divisor}'
