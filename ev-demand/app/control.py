"""Pure allocation and admission rules. Power is expressed in kW, without a site ceiling."""
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def blocked_at(now: datetime, schedules: list, timezone: str) -> bool:
    local = now.astimezone(ZoneInfo(timezone))
    minute = local.hour * 60 + local.minute
    for rule in schedules:
        if not rule.get('enabled', True):
            continue
        start = sum(int(n) * factor for n, factor in zip(rule['start'].split(':'), (60, 1)))
        end = sum(int(n) * factor for n, factor in zip(rule['end'].split(':'), (60, 1)))
        days = rule['days']
        if start < end and local.weekday() in days and start <= minute < end:
            return True
        if start > end and ((local.weekday() in days and minute >= start) or
                            ((local - timedelta(days=1)).weekday() in days and minute < end)):
            return True
    return False


@dataclass
class Demand:
    key: str
    maximum: float
    minimum: float
    charger: str
    circuit: str
    priority: bool = False
    arrival: float = 0


def allocate(demands: list[Demand], budget: float, charger_limits: dict, circuit_limits: dict) -> dict:
    """Priority tiers, minimum admission, FIFO ties and max-min sharing within each tier."""
    result = {d.key: 0.0 for d in demands}
    remaining = max(0.0, budget)
    chargers = dict(charger_limits)
    circuits = dict(circuit_limits)
    for priority in (True, False):
        group = sorted((d for d in demands if d.priority == priority), key=lambda d: (d.arrival, d.key))
        admitted = []
        for d in group:
            minimum = max(0.0, d.minimum)
            available = min(remaining, chargers[d.charger], circuits[d.circuit], d.maximum)
            if available + 1e-8 < minimum or available <= 1e-8:
                continue
            result[d.key] = minimum
            remaining -= minimum
            chargers[d.charger] -= minimum
            circuits[d.circuit] -= minimum
            admitted.append(d)
        while admitted and remaining > 1e-8:
            active = [d for d in admitted if d.maximum - result[d.key] > 1e-8
                      and chargers[d.charger] > 1e-8 and circuits[d.circuit] > 1e-8]
            if not active:
                break
            cc, bc = Counter(d.charger for d in active), Counter(d.circuit for d in active)
            step = min(remaining / len(active),
                       min(d.maximum - result[d.key] for d in active),
                       min(chargers[k] / n for k, n in cc.items()),
                       min(circuits[k] / n for k, n in bc.items()))
            for d in active:
                result[d.key] += step
                chargers[d.charger] -= step
                circuits[d.circuit] -= step
                remaining -= step
    return {k: round(max(0.0, v) - 0.0000001, 4) if v > 0 else 0.0 for k, v in result.items()}


def admission_ready(ports: list[dict], targets: dict, now: float, freshness: float,
                    tolerance: float = 0.2) -> bool:
    """Accepted commands never stand in for fresh telemetry after a reduction command."""
    for p in ports:
        if not p.get('running'):
            continue
        target = targets.get(p['key'], 0.0)
        if not p.get('sample_at') or now - p['sample_at'] > freshness:
            return False
        if p.get('power_kw', 0) > target + tolerance:
            return False
        if p.get('reduction_at', 0) > p['sample_at']:
            return False
        # A rejected/missing profile leaves the old higher authorization in force.
        if p.get('limit_kw', 0) > target + 0.001:
            return False
    return True
