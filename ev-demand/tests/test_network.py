import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from app.network import WebConfig, LAN, load_config


class NetworkTests(unittest.TestCase):
    def test_default_and_persistent_port_and_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'rede.ini'
            self.assertEqual(load_config(path).port, 8080)
            path.write_text('[web]\nhost=0.0.0.0\nporta=9090\nnome=dmax-garagem\nanunciar=true\n')
            result = load_config(path)
            self.assertEqual((result.host, result.port, result.name, result.discovery),
                             ('0.0.0.0', 9090, 'dmax-garagem', True))

    def test_configuration_rejects_bad_port_hostname_and_unknown_keys(self):
        for port in (0, 65536, True):
            with self.assertRaises(ValueError):
                WebConfig(port=port).validated()
        for name in ('dmax.local', '../dmax', 'dmax site', '-dmax', 'a' * 64):
            with self.assertRaises(ValueError):
                WebConfig(name=name).validated()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'rede.ini'
            for content in ('[web]\nunknown=1', '[other]\nporta=8080', '[web]\nporta=abc'):
                path.write_text(content)
                with self.assertRaises(ValueError):
                    load_config(path)

    def test_automatic_hostname_is_stable_and_does_not_include_secrets(self):
        first = LAN(WebConfig(), 'abcdef0123456789')
        second = LAN(WebConfig(port=9000), 'abcdef0123456789')
        self.assertEqual(first.hostname, 'dmax-abcdef01.local')
        self.assertEqual(first.hostname, second.hostname)
        self.assertEqual(second.public()['url'], 'http://dmax-abcdef01.local:9000')
        self.assertNotIn('password', str(first.public()))
        self.assertEqual(LAN(WebConfig(name='dmax-garagem'), 'id', tls=True).public()['url'],
                         'https://dmax-garagem.local:8080')

    def test_loopback_binding_is_not_advertised(self):
        lan = LAN(WebConfig(host='127.0.0.1'), 'abcdef01')
        with patch('app.network.ipv4_addresses') as addresses:
            lan.start()
            addresses.assert_not_called()
        self.assertIsNone(lan.zeroconf)

    def test_mdns_record_has_correct_host_port_and_ipv4_addresses(self):
        lan = LAN(WebConfig(port=9090, name='dmax-garagem'), 'identity')
        with patch('app.network.ipv4_addresses', return_value=['192.0.2.10']), patch('zeroconf.Zeroconf') as factory:
            lan.start()
            self.assertEqual(lan.info.server, 'dmax-garagem.local.')
            self.assertEqual(lan.info.port, 9090)
            self.assertEqual(lan.info.parsed_addresses(), ['192.0.2.10'])
            factory.return_value.register_service.assert_called_once_with(lan.info, allow_name_change=False)
            self.assertEqual(lan.public()['ip_urls'], ['http://192.0.2.10:9090'])
            lan.close()
            factory.return_value.unregister_service.assert_called_once()
            factory.return_value.close.assert_called_once()

    def test_bind_to_specific_interface_advertises_only_that_address(self):
        lan = LAN(WebConfig(host='192.0.2.10'), 'abcdef01')
        with patch('app.network.ipv4_addresses', return_value=['192.0.2.10', '198.51.100.2']), patch('zeroconf.Zeroconf'):
            lan.start()
            self.assertEqual(lan.addresses, ['192.0.2.10'])
            lan.close()

    def test_mdns_failure_does_not_prevent_ip_access(self):
        lan = LAN(WebConfig(), 'abcdef01')
        with patch('app.network.ipv4_addresses', return_value=['192.0.2.10']), patch('zeroconf.Zeroconf', side_effect=OSError):
            lan.start()
        self.assertIsNone(lan.zeroconf)
        self.assertIn('use o IP', lan.status)
        self.assertEqual(lan.public()['ip_urls'], ['http://192.0.2.10:8080'])

    def test_discovery_can_be_disabled_without_changing_os_network(self):
        lan = LAN(WebConfig(discovery=False), 'abcdef01')
        with patch('app.network.ipv4_addresses', return_value=['192.0.2.10']), patch('zeroconf.Zeroconf') as factory:
            lan.start()
            factory.assert_not_called()
        self.assertIsNone(lan.zeroconf)

    def test_name_collision_does_not_unregister_someone_elses_service(self):
        from zeroconf import NonUniqueNameException
        lan = LAN(WebConfig(name='dmax-garagem'), 'abcdef01')
        with patch('app.network.ipv4_addresses', return_value=['192.0.2.10']), patch('zeroconf.Zeroconf') as factory:
            factory.return_value.register_service.side_effect = NonUniqueNameException()
            lan.start()
            factory.return_value.unregister_service.assert_not_called()
            factory.return_value.close.assert_called_once()
            self.assertFalse(lan.public()['announced'])
            self.assertEqual(lan.public()['ip_urls'], ['http://192.0.2.10:8080'])

    def test_cleanup_errors_do_not_block_controller_shutdown(self):
        lan = LAN(WebConfig(), 'abcdef01')
        service = Mock()
        service.unregister_service.side_effect = OSError()
        lan.zeroconf, lan.info, lan.registered = service, object(), True
        lan.close()
        self.assertIsNone(lan.zeroconf)
        service.close.assert_called_once()
