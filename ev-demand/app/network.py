"""LAN binding and mDNS publication; never changes firewall, DNS or the OS name."""
from configparser import ConfigParser, Error as ConfigError
from contextlib import suppress
from dataclasses import dataclass
import ipaddress
from pathlib import Path
import re
import socket


@dataclass(frozen=True)
class WebConfig:
    host: str = '0.0.0.0'
    port: int = 8080
    name: str = 'auto'
    discovery: bool = True

    def validated(self):
        if self.host != 'localhost':
            ipaddress.ip_address(self.host)
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError('Porta deve ficar entre 1 e 65535')
        if self.name != 'auto' and not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', self.name):
            raise ValueError('Nome: use até 63 letras minúsculas, números e hífen, sem .local')
        return self


def load_config(path):
    """Only typed network settings are read; no commands or arbitrary file writes."""
    path = Path(path)
    if not path.exists():
        return WebConfig()
    parser = ConfigParser(interpolation=None)
    try:
        parser.read_string(path.read_text(encoding='utf-8-sig'))
        if set(parser.sections()) != {'web'} or parser.defaults():
            raise ValueError('rede.ini deve conter somente a seção [web]')
        section = parser['web']
        if set(section) - {'host', 'porta', 'nome', 'anunciar'}:
            raise ValueError('Chave desconhecida em rede.ini')
        return WebConfig(
            host=section.get('host', '0.0.0.0').strip(),
            port=section.getint('porta', 8080),
            name=section.get('nome', 'auto').strip().lower(),
            discovery=section.getboolean('anunciar', True),
        ).validated()
    except (ConfigError, ValueError) as exc:
        raise ValueError('Configuração de rede inválida: ' + str(exc)) from exc


def ipv4_addresses():
    import ifaddr
    result = set()
    for adapter in ifaddr.get_adapters():
        for item in adapter.ips:
            if not isinstance(item.ip, str):
                continue
            try:
                address = ipaddress.IPv4Address(item.ip)
            except ipaddress.AddressValueError:
                continue
            if not address.is_loopback and not address.is_unspecified and not address.is_multicast:
                result.add(str(address))
    return sorted(result)


class LAN:
    def __init__(self, config, controller_id, tls=False):
        self.config = config.validated()
        suffix = re.sub('[^a-z0-9]', '', controller_id.lower())[:8]
        self.label = 'dmax-' + suffix if config.name == 'auto' else config.name
        self.hostname = self.label + '.local'
        self.scheme = 'https' if tls else 'http'
        self.addresses = []
        self.status = 'Aguardando inicialização'
        self.zeroconf = None
        self.info = None
        self.registered = False

    def public(self):
        return {
            'host': self.config.host, 'port': self.config.port, 'hostname': self.hostname,
            'url': self.scheme + '://' + self.hostname + ':' + str(self.config.port),
            'ip_urls': [self.scheme + '://' + ip + ':' + str(self.config.port) for ip in self.addresses],
            'status': self.status, 'discovery': self.config.discovery,
            'announced': self.zeroconf is not None and self.registered,
        }

    def start(self):
        """Called outside the controller's event loop. IP access survives mDNS failure."""
        host = self.config.host
        if host == 'localhost' or ipaddress.ip_address(host).is_loopback:
            self.status = 'Acesso restrito ao próprio computador'
            return
        try:
            self.addresses = ipv4_addresses()
            if host != '0.0.0.0':
                self.addresses = [ip for ip in self.addresses if ip == host]
            if not self.config.discovery:
                self.status = 'Nome automático desativado; use IP ou DNS da rede'
                return
            if not self.addresses:
                self.status = 'Nenhum endereço IPv4 disponível para anunciar o nome'
                return
            from zeroconf import IPVersion, ServiceInfo, Zeroconf
            service = '_https._tcp.local.' if self.scheme == 'https' else '_http._tcp.local.'
            self.zeroconf = Zeroconf(interfaces=self.addresses, ip_version=IPVersion.V4Only)
            self.info = ServiceInfo(
                service, self.label + '.' + service,
                addresses=[socket.inet_aton(ip) for ip in self.addresses],
                port=self.config.port, server=self.hostname + '.',
                properties={'path': '/', 'product': 'EnergyCube D-Max'},
            )
            # Refuse a colliding service name rather than announcing another identity.
            self.zeroconf.register_service(self.info, allow_name_change=False)
            self.registered = True
            self.status = 'Nome anunciado na rede local'
        except Exception:
            self.status = 'Nome não anunciado; use o IP e confira multicast/firewall da rede'
            self.close()

    def close(self):
        if self.zeroconf is not None:
            with suppress(Exception):
                if self.info is not None and self.registered:
                    self.zeroconf.unregister_service(self.info)
            with suppress(Exception):
                self.zeroconf.close()
            self.zeroconf = None
        self.registered = False
