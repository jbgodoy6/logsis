"""Remote gateway preserves D-Max authentication and never publishes OCPP."""
import asyncio
import gzip
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.main import create_app
from app.store import password_hash
from app.remote_gateway import create_gateway,backend,permitted,MAX_BODY
from app.remote_tunnel import command,ssh_command,cloudflare_session,connector_ready,valid_url,public_status,write_status,session,supervise

class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.app=create_app(':memory:',background=False,root_password_hash=password_hash('fixture-remote-root'))
        self.local=TestClient(self.app)
        self.local.post('/api/setup',json={'admin_password':'fixture-remote-admin'})
        upstream=ProxyHeadersMiddleware(self.app,trusted_hosts=['127.0.0.1'])
        self.gateway=create_gateway('http://127.0.0.1:80',transport=httpx.ASGITransport(app=upstream,client=('127.0.0.1',45000)))
        self.context=TestClient(self.gateway,base_url='https://fixture-123.trycloudflare.com',client=('127.0.0.1',41000),headers={'X-Forwarded-Proto':'https','X-Forwarded-For':'203.0.113.12'})
        self.c=self.context.__enter__()
    def tearDown(self):
        self.context.__exit__(None,None,None);self.local.close();self.app.state.store.db.close()
    def login(self):
        r=self.c.post('/api/login',json={'username':'root','password':'fixture-remote-root'},headers={'Origin':'https://fixture-123.trycloudflare.com'})
        self.assertEqual(r.status_code,200,r.text)
        self.assertIn('Secure',r.headers['set-cookie']);self.assertIn('HttpOnly',r.headers['set-cookie'])
    def test_remote_login_session_live_updates_and_logout(self):
        self.assertEqual(self.c.get('/api/state').status_code,401)
        self.login()
        self.assertEqual(self.c.get('/ui/overview').status_code,200)
        self.assertEqual(self.c.get('/ui-data/overview').json()['schema_version'],1)
        self.assertEqual(self.c.post('/api/logout',json={},headers={'Origin':'https://fixture-123.trycloudflare.com'}).status_code,200)
        self.assertEqual(self.c.get('/api/state').status_code,401)
    def test_signed_html_forms_keep_nonce_cookies_csrf_and_redirects(self):
        from test_server_ui import Forms
        self.login();self.c.post('/api/demo',json={})
        forms=Forms(self.c.get('/ui/overview').text)
        form=next(f for f in forms.forms if f.get('_action')=='load');form['other_kw']='480'
        reply=self.c.post('/ui/post',data=form,headers={'Origin':'https://fixture-123.trycloudflare.com'})
        self.assertEqual(reply.status_code,200,reply.text);self.assertIn('Alteração aplicada.',reply.text)
        self.assertEqual(self.app.state.engine.other_kw,480)
    def test_ocpp_setup_and_traversal_never_forwarded(self):
        self.login()
        for path in ('/ocpp/REAL','/api/%2e%2e/ocpp/REAL','/docs','/openapi.json'):
            self.assertEqual(self.c.get(path).status_code,404,path)
        self.assertEqual(self.c.post('/api/setup',json={'admin_password':'anything-valid'}).status_code,404)
        with self.assertRaises(WebSocketDisconnect):
            with self.c.websocket_connect('/ocpp/REAL',subprotocols=['ocpp1.6']):pass
    def test_initial_setup_cannot_be_reached_indirectly_through_html_form(self):
        from test_server_ui import Forms
        with self.app.state.store.db:
            self.app.state.store.db.execute('DELETE FROM logins');self.app.state.store.db.execute('DELETE FROM users')
        form=next(f for f in Forms(self.c.get('/').text).forms if f.get('_action')=='setup')
        form['admin_password']='fixture-forbidden-setup'
        self.assertEqual(self.c.post('/ui/post',data=form,headers={'Origin':'https://fixture-123.trycloudflare.com'}).status_code,403)
        self.assertIsNone(self.app.state.store.db.execute('SELECT 1 FROM users').fetchone())
    def test_cross_site_actions_are_still_rejected(self):
        self.login()
        self.assertEqual(self.c.post('/api/simulation',json={'other_kw':500},headers={'Origin':'https://other.tunnl.gg'}).status_code,403)
    def test_connection_header_cannot_rewrite_host_to_localhost(self):
        self.login()
        response=self.c.get('/api/state',headers={'Connection':'host','Origin':'https://fixture-123.trycloudflare.com'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.c.post('/api/logout',json={},headers={'Connection':'host','Origin':'https://fixture-123.trycloudflare.com'}).status_code,200)
    def test_only_relay_host_and_https_accepted(self):
        self.assertEqual(self.c.get('/api/setup',headers={'Host':'localhost'}).status_code,400)
        self.assertEqual(self.c.get('/api/setup',headers={'X-Forwarded-Proto':'http'}).status_code,400)
    def test_large_upload_refused_before_backend(self):
        self.assertEqual(self.c.post('/api/maintenance/update',headers={'Content-Length':str(MAX_BODY+1)}).status_code,413)
    def test_live_json_compressed_without_changing_contents(self):
        self.login()
        r=self.c.get('/ui-data/overview',headers={'Accept-Encoding':'gzip'})
        self.assertEqual(r.status_code,200);self.assertEqual(r.headers.get('content-encoding'),'gzip')
        self.assertEqual(r.json()['schema_version'],1)
        self.assertNotIn('content-encoding',self.c.get('/ui/profile').headers)
    def test_remote_status_and_grafana_settings_remain_independent(self):
        self.login();before=self.app.state.store.settings()
        r=self.c.get('/api/remote');self.assertEqual(r.status_code,200)
        page=self.c.get('/ui/remote');self.assertEqual(page.status_code,200)
        self.assertIn('Grafana',page.text)
        self.assertEqual(self.app.state.store.settings(),before)
    def test_unavailable_backend_returns_controlled_error_without_changing_controller(self):
        before=self.app.state.store.settings()
        with patch.object(self.gateway.state.client,'send',side_effect=httpx.ConnectError('fixture unavailable')):
            self.assertEqual(self.c.get('/api/setup').status_code,503)
        self.assertEqual(self.app.state.store.settings(),before)
        self.assertEqual(self.local.get('/api/setup').status_code,200)

class RuntimeTests(unittest.TestCase):
    def test_backend_respects_existing_port_and_tls(self):
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)/'rede.ini';config.write_text('[web]\nporta=9090\nhost=0.0.0.0\n')
            self.assertEqual(backend(config,{})[0],'http://127.0.0.1:9090')
            self.assertEqual(backend(config,{'DMAX_PORT':'8443','DMAX_TLS_CERT':'/fixture/cert.pem'})[0],'https://127.0.0.1:8443')
            with self.assertRaises(ValueError):backend(config,{'DMAX_HOST':'192.0.2.10'})
    def test_ssh_command_pins_host_and_reuses_identity(self):
        args=ssh_command()
        self.assertIn('StrictHostKeyChecking=yes',args);self.assertIn('BatchMode=yes',args)
        self.assertIn('GlobalKnownHostsFile=/dev/null',args);self.assertIn('UpdateHostKeys=no',args)
        self.assertIn('80:127.0.0.1:8766',args);self.assertIn('stable@proxy.tunnl.gg',args)
        self.assertNotIn('StrictHostKeyChecking=no',args)
        self.assertEqual(args,ssh_command())
    def test_url_validation_rejects_external_and_credential_urls(self):
        self.assertTrue(valid_url('https://happy-123.tunnl.gg'))
        for url in ('http://test.tunnl.gg','https://tunnl.gg.evil.test','https://evil.test','https://a:b@ok.tunnl.gg','https://ok.tunnl.gg:443','https://ok.tunnl.gg/?token=x'):
            self.assertFalse(valid_url(url),url)
    def test_stale_status_preserves_url_without_claiming_connectivity(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'status.json'
            write_status({'url':'https://test-123.tunnl.gg','connected':True},p)
            self.assertTrue(public_status(p)['connected'])
            with patch('app.remote_tunnel.time.time',return_value=time.time()+100):
                data=public_status(p)
            self.assertFalse(data['connected']);self.assertEqual(data['url'],'https://test-123.tunnl.gg')

class ReconnectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_disconnect_restart_preserves_url_and_reports_disconnected(self):
        outputs=[];stop=asyncio.Event()
        lines=[json.dumps(dict(event='tunnel',stable=True,url='https://client-1.tunnl.gg')).encode()+b'\n',b'']
        class Process:
            returncode=0
            stdout=type('Stream',(),{'readline':AsyncMock(side_effect=lines)})()
            wait=AsyncMock(return_value=0)
        spawn=AsyncMock(return_value=Process());state={'connected':False,'url':None}
        await session(state,stop,spawn,lambda data:outputs.append(dict(data)))
        self.assertTrue(outputs[0]['connected']);self.assertFalse(outputs[-1]['connected'])
        self.assertEqual(outputs[-1]['url'],'https://client-1.tunnl.gg')
        self.assertEqual(spawn.call_args.args,tuple(ssh_command()))
    async def test_supervisor_retries_without_creating_new_key(self):
        stop=asyncio.Event();calls=[];delays=[]
        async def connect(state,event):
            calls.append(command())
            if len(calls)==1:raise OSError('fixture offline')
            event.set()
        async def pause(delay):delays.append(delay)
        with patch('app.remote_tunnel.write_status'),patch('app.remote_tunnel.public_status',return_value={'url':'https://client-1.tunnl.gg'}):
            await supervise(stop,connect,pause)
        self.assertEqual(len(calls),2);self.assertEqual(calls[0],calls[1]);self.assertGreater(delays[0],5)

if __name__=='__main__':unittest.main()

class CloudflareTests(unittest.IsolatedAsyncioTestCase):
    async def run_lines(self,lines):
        outputs=[];active=set();lines=iter(lines)
        async def readline():
            line=next(lines,'')
            match=__import__('re').search(r'connIndex=(\d+)',line);index=match.group(1) if match else '0'
            if 'Registered tunnel connection' in line:active.add(index)
            elif 'Failed to serve tunnel connection' in line or 'Lost connection with the edge' in line:active.discard(index)
            return line.encode()+b'\n' if line else b''
        class Process:
            returncode=0
            stdout=type('Stream',(),{'readline':AsyncMock(side_effect=readline)})()
            wait=AsyncMock(return_value=0)
        spawn=AsyncMock(return_value=Process());state=dict(url='https://old.tunnl.gg',connected=False)
        await cloudflare_session(state,asyncio.Event(),spawn,lambda data:outputs.append(dict(data)),ready=lambda:bool(active))
        self.assertEqual(spawn.call_args.args,tuple(command()));return outputs
    async def test_url_requires_registered_connection_and_disconnect_is_visible(self):
        states=await self.run_lines(['https://new-place.trycloudflare.com','2026-11-10 INF Registered tunnel connection connIndex=0','2026-11-10 ERR Failed to serve tunnel connection connIndex=0'])
        self.assertIsNone(states[0]['url']);self.assertFalse(states[1]['connected']);self.assertTrue(states[2]['connected']);self.assertFalse(states[3]['connected'])
        self.assertEqual(states[-1]['url'],'https://new-place.trycloudflare.com')
        self.assertNotIn('--no-tls-verify',command())
    async def test_certificate_failure_is_reported_without_accepting_certificate(self):
        states=await self.run_lines(['[]','ERR x509: certificate signed by unknown authority'])
        self.assertFalse(states[-1]['connected']);self.assertIn('TLS mantida',states[-1]['message'])
    async def test_all_registered_connections_must_drop_before_offline(self):
        states=await self.run_lines(['https://new-place.trycloudflare.com','INF Registered tunnel connection connIndex=0','INF Registered tunnel connection connIndex=1','ERR Failed to serve tunnel connection connIndex=0','ERR Failed to serve tunnel connection connIndex=1'])
        self.assertTrue(states[4]['connected']);self.assertFalse(states[5]['connected'])

    async def test_api_url_in_error_is_not_a_public_tunnel(self):
        states=await self.run_lines(['ERR Post "https://api.trycloudflare.com/tunnel": context deadline exceeded'])
        self.assertTrue(all(p.get('url') is None for p in states))
        self.assertFalse(valid_url('https://api.trycloudflare.com'))
        self.assertFalse(valid_url('https://www.trycloudflare.com'))
    async def test_lost_edge_log_clears_connection(self):
        states=await self.run_lines(['https://real-site.trycloudflare.com','INF Registered tunnel connection connIndex=0','INF Lost connection with the edge connIndex=0'])
        self.assertTrue(states[2]['connected']);self.assertFalse(states[3]['connected'])
    async def test_defaults_allow_native_protocol_fallback_without_disabling_tls(self):
        args=command();self.assertEqual(args[args.index('--protocol')+1],'auto')
        self.assertEqual(args[args.index('--edge-ip-version')+1],'4')
        self.assertEqual(args[args.index('--output')+1],'json')
        with patch.dict('os.environ',{'DMAX_REMOTE_PROTOCOL':'http2'}):self.assertIn('http2',command())
        with patch.dict('os.environ',{'DMAX_REMOTE_PROTOCOL':'bad'}):
            with self.assertRaises(ValueError):command()
    async def test_registered_log_does_not_override_failed_readiness(self):
        lines=iter([b'https://ready-check.trycloudflare.com\n',b'INF Registered tunnel connection connIndex=0\n',b''])
        class Process:
            returncode=0
            stdout=type('Stream',(),{'readline':AsyncMock(side_effect=lambda:next(lines))})()
        states=[]
        await cloudflare_session({},asyncio.Event(),AsyncMock(return_value=Process()),lambda data:states.append(dict(data)),ready=lambda:False)
        self.assertTrue(all(not p['connected'] for p in states))
    async def test_readiness_is_http_status_not_merely_open_port(self):
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        import threading
        class Handler(BaseHTTPRequestHandler):
            code=503
            def do_GET(self):self.send_response(self.code);self.end_headers()
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with patch('app.remote_tunnel.READY_URL','http://127.0.0.1:'+str(server.server_port)+'/ready'):
                self.assertFalse(await asyncio.to_thread(connector_ready));Handler.code=200
                self.assertTrue(await asyncio.to_thread(connector_ready))
        finally:await asyncio.to_thread(server.shutdown);server.server_close();thread.join(timeout=2)
    async def test_silent_process_is_recycled_and_stop_does_not_wait_for_log_line(self):
        import sys
        processes=[]
        async def spawn(*args,**kwargs):
            child=await asyncio.create_subprocess_exec(sys.executable,'-u','-c','import time; time.sleep(60)',**kwargs);processes.append(child);return child
        states=[]
        await asyncio.wait_for(cloudflare_session({},asyncio.Event(),spawn,lambda x:states.append(dict(x)),ready=lambda:False,stall_s=.08,check_s=.02),3)
        self.assertIn('recriando',states[-1]['message']);self.assertIsNotNone(processes[-1].returncode)
        stop=asyncio.Event();task=asyncio.create_task(cloudflare_session({},stop,spawn,lambda x:None,ready=lambda:False,check_s=10))
        await asyncio.sleep(.05);stop.set();await asyncio.wait_for(task,3)
        self.assertIsNotNone(processes[-1].returncode)
    async def test_connectivity_errors_are_logged_without_echoing_secrets(self):
        import io
        output=io.StringIO()
        with patch('sys.stdout',output):
            await self.run_lines(['{"message":"precheck", "component":"TCP Connectivity", "target":"region2.v2.argotunnel.com", "status":"fail", "error":"fixture-private-secret"}',
                                  '{"message":"precheck complete", "hard_fail":true}',
                                  'ERR x509: fixture-private-secret'])
        text=output.getvalue();self.assertIn('region2.v2.argotunnel.com',text);self.assertIn('certificado recusado',text);self.assertNotIn('fixture-private-secret',text)
