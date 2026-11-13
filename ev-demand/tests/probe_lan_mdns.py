"""Independent DNS-SD interoperability probe for the --announce test fixture."""
from zeroconf import Zeroconf, IPVersion

with Zeroconf(ip_version=IPVersion.V4Only) as discovery:
    info = discovery.get_service_info(
        '_http._tcp.local.', 'dmax-lan-fixture._http._tcp.local.', timeout=7000
    )
    assert info is not None, 'mDNS não respondeu'
    assert info.server == 'dmax-lan-fixture.local.' and info.port == 8080
    assert info.parsed_addresses() and info.properties.get(b'path') == b'/'
    print('mDNS PASS: DNS-SD, hostname, IPv4, porta e path=/ via Zeroconf.')
