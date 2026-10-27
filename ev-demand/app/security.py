"""Small, bounded checks before expensive authentication work."""
from collections import OrderedDict, deque
import ipaddress
import re
import time
from urllib.parse import urlsplit


def valid_host(value):
    if not isinstance(value, str) or len(value) > 260:
        return False
    if not re.fullmatch(r'(?:[A-Za-z0-9.-]+|\[[0-9A-Fa-f:]+\])(?::[0-9]{1,5})?', value):
        return False
    try:
        parsed = urlsplit('http://' + value)
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            return False
        if value.startswith('['):
            ipaddress.IPv6Address(parsed.hostname)
    except ValueError:
        return False
    return True


def same_origin(origin, host, scheme):
    try:
        parsed = urlsplit(origin)
        return (valid_host(host) and parsed.scheme == scheme and parsed.netloc.lower() == host.lower()
                and not parsed.path and not parsed.query and not parsed.fragment
                and not parsed.username and not parsed.password)
    except (ValueError, TypeError):
        return False


class AttemptLimiter:
    def __init__(self, limit=8, window=300, max_keys=4096):
        self.limit, self.window, self.max_keys = limit, window, max_keys
        self.entries = OrderedDict()

    def allow(self, key):
        now = time.monotonic()
        # Reap idle entries, without allowing an address flood to evict live limits.
        while self.entries and self.entries[next(iter(self.entries))][-1] <= now - self.window:
            self.entries.popitem(last=False)
        if key not in self.entries:
            if len(self.entries) >= self.max_keys:
                return False
            self.entries[key] = deque()
        recent = self.entries[key]
        while recent and recent[0] <= now - self.window:
            recent.popleft()
        if len(recent) >= self.limit:
            return False
        recent.append(now)
        self.entries.move_to_end(key)
        return True
