"""Server-rendered D-Max console. No browser scripts or additional runtime packages.

Forms call the same authenticated API used by the controller, preserving role
checks, rate limits, audit, data validation and session revocation.
"""
import hashlib
import hmac
import html
import math
import secrets
import time
from urllib.parse import parse_qs, quote, urlencode

import httpx
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from .meter import MEASUREMENTS, FORMATS, normalize_serial_port
from .plant_view import render_plant
from .live_dom import view_tree

VERSION = '0.14.1'
PAGES = {
    'overview': 'Visão geral', 'chargers': 'Carregadores', 'vehicles': 'Veículos',
    'schedule': 'Horários', 'history': 'Histórico', 'meter': 'Multimedidor',
    'settings': 'Configurações', 'users': 'Usuários', 'directory': 'Técnicos globais',
    'profile': 'Minha senha',
    'simulation': 'Simulador',
    'maintenance': 'Manutenção',
    'audit': 'Auditoria',
    'remote': 'Acesso remoto',
    'remoteclients': 'Buscar clientes remotos',
}
ROLES = {'root': 'Raiz', 'technician': 'Técnico / instalador', 'admin': 'Administrador', 'operator': 'Operador', 'developer': 'Desenvolvedor', 'commercial': 'Comercial'}


def esc(value):
    return html.escape(str(value if value is not None else ''), quote=True)


def attrs(values):
    return ''.join(' ' + esc(k.rstrip('_').replace('_', '-')) + '="' + esc(v) + '"'
                   for k, v in values.items() if v is not None and v is not False)


def field(label, name, value='', kind='text', **options):
    return ('<label>' + esc(label) + '<input' + attrs(dict(name=name, type=kind, value=value, **options))
            + '></label>')


def select(label, name, choices, current=''):
    options = ''.join('<option value="' + esc(value) + '"' + (' selected' if str(value) == str(current) else '')
                      + '>' + esc(title) + '</option>' for value, title in choices)
    return '<label>' + esc(label) + '<select name="' + esc(name) + '">' + options + '</select></label>'


def checkbox(label, name, checked=False):
    return '<label class="checkbox-label"><input type="checkbox" name="' + esc(name) + '"' + (' checked' if checked else '') + '>' + esc(label) + '</label>'


def hidden(name, value):
    return '<input type="hidden" name="' + esc(name) + '" value="' + esc(value) + '">'


def number(value, digits=1):
    try:
        return f'{float(value):,.{digits}f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    except (ValueError, TypeError):
        return '—'


def panel(title, content):
    return '<article class="panel"><h3>' + esc(title) + '</h3>' + content + '</article>'


def table(headers, rows):
    return ('<div class="table-wrap"><table><thead><tr>' + ''.join('<th>' + esc(x) + '</th>' for x in headers)
            + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + cell + '</td>' for cell in row) + '</tr>' for row in rows)
            + '</tbody></table></div>')


def link(page, text, **query):
    path = '/ui/' + page
    if query:
        path += '?' + urlencode(query)
    return '<a class="secondary" href="' + esc(path) + '">' + esc(text) + '</a>'


def subscription_banner(state):
    subscription = state.get('subscription', {})
    result = '<div class="subscription-banner" id="subscription-banner" role="status">'
    if subscription.get('state') in ('pending', 'native') or subscription.get('offline_state') == 'warning':
        title = ('Controle de demanda desativado · funcionamento nativo solicitado' if subscription.get('native')
                 else 'Assinatura pendente · ' + str(subscription['remaining_days']) + ' dia(s) restantes')
        if subscription.get('offline_state') == 'warning' and subscription.get('state') not in ('pending', 'native'):
            title = 'Reconecte à internet · mais de 15 dias sem contato autenticado; controle ativo'
        elif subscription.get('offline_state') == 'pending' and not subscription.get('native'):
            title = 'Pendência por ausência de contato · ' + str(subscription['remaining_days']) + ' dia(s) restantes'
        result += '<div class="notice"><strong>' + esc(title) + '</strong><p>' + esc(subscription['message']) + '</p>'
        if subscription.get('deadline'):
            from datetime import datetime
            from zoneinfo import ZoneInfo
            result += '<p>Prazo: ' + esc(datetime.fromtimestamp(subscription['deadline'], ZoneInfo(state['settings']['timezone'])).strftime('%d/%m/%Y %H:%M')) + '. A contagem continua sem internet.</p>'
        if subscription.get('native'):
            result += '<p>Confira a confirmação de liberação de cada carregador. O D-Max não gerencia demanda nem horário de ponta neste modo.</p>'
        if subscription.get('clock_suspect'):
            result += '<p>Relógio retrocedeu; prazo não prorrogado. Regularize a assinatura e confira o relógio do equipamento.</p>'
        result += '</div>'
    return result + '</div>'


def install(app):
    signing_key = secrets.token_bytes(32)

    class Console:
        def __init__(self, request):
            self.request = request
            self.nonce = request.cookies.get('dmax_ui_nonce', '')
            if len(self.nonce) != 43 or not all(c.isalnum() or c in '-_' for c in self.nonce):
                self.nonce = secrets.token_urlsafe(32)
            self.session = request.cookies.get('ev_session', '')
            self.user = app.state.access.session(self.session)
            self.demonstration=getattr(app.state,'demonstration',False)
            self.cookies = []
            self.state = None

        def token(self, action, when=None):
            when = int(time.time()) if when is None else when
            data = '\n'.join((self.session, self.nonce, action, str(when))).encode()
            return str(when) + '.' + hmac.new(signing_key, data, hashlib.sha256).hexdigest()

        def valid_token(self, action, value):
            try:
                when = int(value.split('.', 1)[0])
                return 0 <= time.time() - when <= 7*86400 and hmac.compare_digest(self.token(action, when), value)
            except (ValueError, TypeError, OverflowError):
                return False

        def form(self, action, content='', submit='Salvar', page='overview', **values):
            fields = hidden('_action', action) + hidden('_csrf', self.token(action)) + hidden('_page', page)
            fields += ''.join(hidden(k, v) for k, v in values.items())
            control = '<button class="primary" type="submit">' + esc(submit) + '</button>'
            return '<form method="post" action="/ui/post">' + fields + content + control + '</form>'

        async def api(self, method, path, data=None):
            address = self.request.client
            # Preserve the real client for initial-setup and authentication limits.
            transport = httpx.ASGITransport(app=app, client=(address.host, address.port) if address else ('unknown', 0))
            base = self.request.url.scheme + '://' + self.request.headers['host']
            async with httpx.AsyncClient(transport=transport, base_url=base, follow_redirects=False) as client:
                response = await client.request(method, path, json=data,
                                                headers={'Cookie': self.request.headers.get('cookie', '')})
            self.cookies.extend(response.headers.get_list('set-cookie'))
            body = response.json()
            if response.status_code >= 400:
                detail = body.get('detail', 'Operação recusada')
                if isinstance(detail, list):
                    detail = '; '.join(str(x.get('msg', 'Dado inválido')) for x in detail)
                raise UIError(str(detail), response.status_code)
            return body

        def finish(self, response):
            response.headers['Cache-Control'] = 'no-store'
            if self.request.cookies.get('dmax_saved'):
                response.delete_cookie('dmax_saved')
            response.set_cookie('dmax_ui_nonce', self.nonce, httponly=True,
                                secure=self.request.url.scheme == 'https', samesite='strict', max_age=28800)
            for cookie in self.cookies:
                response.headers.append('set-cookie', cookie)
            return response

        def document(self, content, title='D-Max', refresh=False, live=False):
            update = ''  # Live values are patched in place; documents never auto-reload.
            styles = ('style.css', 'energycube.css', 'server.css', 'plant.css') + (('live.css',) if live else ())
            styles = ''.join('<link rel="stylesheet" href="/static/' + name + '?v=' + VERSION + '">' for name in styles)
            return ('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
                    '<meta name="viewport" content="width=device-width,initial-scale=1">'
                    '<title>' + esc(title) + ' · EnergyCube D-Max</title>' + update
                    + '<link rel="icon" type="image/png" href="/static/energycube-logo.png">'
                    + styles
                    + ('<link rel="stylesheet" href="/ui-colors.css">' if self.user and not self.user['must_change'] else '')
                    + '</head><body>' + content
                    + ('<script src="/static/live.js?v=' + VERSION + '" defer></script>' if live else '')
                    + ('<div class="login-version">EnergyCube D-Max · <span data-dmax-version>v' + VERSION + '</span></div>' if not self.user else '')
                    + '</body></html>')

        async def render(self, page='overview', message='', diagnostic=None, status=200, recovery_data=None):
            if page == 'monitor':
                page = 'overview'
            if page not in PAGES:
                return self.finish(HTMLResponse('Página não encontrada', status_code=404))
            note = '<div class="notice' + (' flash-notice' if message == 'Alteração aplicada.' else '') + '" role="status">' + esc(message) + '</div>' if message else ''
            if not self.user:
                required = (await self.api('GET', '/api/setup'))['required']
                if required:
                    content = self.form('setup',
                        field('Senha do administrador', 'admin_password', kind='password', minlength=8, maxlength=200, required='', autocomplete='new-password'),
                        'Configurar acesso')
                    title = 'Prepare seu controlador'
                else:
                    content = self.form('login',
                        field('Usuário', 'username', 'admin', autocomplete='username', required='', maxlength=40)
                        + field('Senha / palavra-passe', 'password', kind='password', autocomplete='current-password', required='', maxlength=200),
                        'Entrar no controlador')
                    content += '<p class="hint">Para acesso raiz, use root e a palavra-passe do proprietário.</p>' if app.state.root_password_enabled else ''
                    content += '<p><a href="/?recovery=1">Recuperação alternativa por assinatura</a></p>'
                    title = 'Bem-vindo de volta'
                    if self.request.query_params.get('recovery') == '1' or recovery_data is not None:
                        info = await self.api('GET', '/api/recovery')
                        title = 'Recuperar acesso'
                        content = '<p>' + esc(info['message']) + '</p>'
                        if info['enabled']:
                            content += '<p>Equipamento: ' + esc(info['controller_id']) + '</p>'
                            content += '<p>Solicite ao responsável uma autorização. O desafio vale por 15 minutos e deve ser usado neste navegador.</p>'
                            content += '<p class="hint">Chave pública: ' + esc(info['fingerprint']) + '</p>'
                            content += self.form('recovery_challenge', submit='Gerar desafio de recuperação')
                            if recovery_data and recovery_data.get('challenge'):
                                content += '<label>Desafio para enviar ao responsável<textarea readonly rows="6" name="recovery_challenge">' + esc(recovery_data['challenge']) + '</textarea></label>'
                            content += self.form('recovery_authorize', '<label>Autorização recebida<textarea name="authorization" required rows="6" maxlength="4096" autocomplete="off"></textarea></label>', 'Entrar como raiz por 15 minutos')
                        content += '<p><a href="/">Voltar ao login</a></p>'
                auth = ('<div class="auth-screen"><div class="auth-art"><div class="brand">'
                        '<img src="/static/d-max-logo.png" class="dmax-logo" alt="D-Max by EnergyCube"></div>'
                        '<h1>Mais recarga.<br>Dentro do seu limite.</h1><p>Controle local de energia.</p></div>'
                        '<div class="auth-panel"><h2>' + title + '</h2>' + note + content
                        + '<p class="hint">Interface gerada no controlador · v' + VERSION + '</p></div></div>')
                return self.finish(HTMLResponse(self.document(auth), status_code=status))
            if self.user['must_change']:
                content = note + self.password_form() + self.form('logout', submit='Sair')
                return self.finish(HTMLResponse(self.document('<main class="initial-password">' + panel('Troque a senha inicial', content) + '</main>'), status_code=status))
            allowed = {'meter': self.technical, 'settings': self.manager, 'users': self.manager,
                       'directory': self.user['role'] in ('root','developer'), 'remoteclients': self.user['role'] in ('root','developer'), 'simulation': self.technical and app.state.store.settings()['mode'] == 'simulation', 'maintenance': self.technical and not self.demonstration, 'audit': self.manager, 'remote': self.technical and not self.demonstration}
            if not allowed.get(page, True):
                page, note, status = 'overview', '<div class="notice">Acesso não permitido para seu perfil.</div>', 403
            self.state = await self.api('GET', '/api/state')
            if page == 'overview':
                await self.load_curve()
                content = self.overview()
            elif page == 'chargers':
                content = self.chargers()
            elif page == 'vehicles':
                content = self.vehicles()
            elif page == 'schedule':
                content = self.schedules()
            elif page == 'settings':
                content = self.settings()
            elif page == 'meter':
                serial = await self.api('GET', '/api/meter/ports')
                content = self.meter(diagnostic, serial['ports'])
            elif page == 'history':
                content = await self.history()
            elif page == 'remoteclients':
                content=await self.remote_clients()
            elif page == 'remote':
                remote=await self.api('GET','/api/remote')
                content=panel('Cloudflare · acesso remoto e diretório', '<p id="remote-state">'+esc('Conectado' if remote['connected'] else 'Sem conexão confirmada')+'</p><p id="remote-message">'+esc(remote['message'])+'</p><p><a id="remote-url" href="'+esc(remote.get('url') or '#')+'" target="_blank" rel="noopener noreferrer">'+esc(remote.get('url') or 'Endereço ainda não disponível')+'</a></p><p>Identificador da instalação: <code>'+esc(remote['controller_id'])+'</code></p><p id="remote-publication">'+esc('Planilha: plataforma desativada; configure Técnicos globais para registrar o endereço' if not remote['publication']['directory_enabled'] else 'Planilha: envio pendente' if remote['publication']['pending'] else 'Planilha: consulte a última confirmação no diretório')+'</p><p>Ative no Raspberry pelo instalador de acesso remoto. Cada equipamento usa sua própria identidade. O Quick Tunnel gera um endereço automático que pode mudar. O novo endereço é enviado ao diretório da planilha quando a plataforma está configurada.</p><p>O serviço gratuito tem limites de tráfego e disponibilidade. O D-Max local e a integração Grafana permanecem independentes.</p>')+'<script src="/static/remote.js?v='+VERSION+'" defer></script>'
            elif page == 'audit':
                actor=self.request.query_params.get('actor','')
                try: offset=max(0,int(self.request.query_params.get('offset','0')))
                except ValueError: offset=0
                audit=await self.api('GET','/api/audit?'+urlencode({'actor':actor,'offset':offset}))
                content=panel('Alterações e liberações', '<form method="get">'+field('Login de quem alterou','actor',actor)+'<button>Filtrar</button></form>'+table(['Horário','Evento','Responsável e alteração'],[[esc(__import__('datetime').datetime.fromtimestamp(e['ts']).isoformat()),esc(e['kind']),esc(e['payload'])] for e in audit['events']])+link('audit','Próximos registros',actor=actor,offset=offset+100))
            elif page == 'maintenance':
                content = '<article class="panel"><h3>Backup e manutenção</h3><p>O backup contém dados privados da instalação. Guarde em local seguro.</p><a href="/api/maintenance/backup">Baixar backup SQLite</a><p>Restauração e atualização exigem raiz e carregadores físicos desconectados. O serviço reinicia durante a operação.</p>'
                if self.user['role'] in ('root','developer'):
                    content += '<label>Backup desta instalação<input id="restore-file" type="file" accept=".sqlite3"></label><button type="button" data-maintenance="restore">Restaurar backup</button><label>Pacote ARM64 assinado<input id="update-file" type="file" accept=".zip"></label><button type="button" data-maintenance="update">Validar e atualizar</button>'
                content += '<p id="maintenance-status" role="status"></p></article><script src="/static/maintenance.js?v='+VERSION+'" defer></script>'
            elif page == 'users':
                content = await self.users()
            elif page == 'directory':
                content = await self.directory()
            elif page == 'simulation':
                content = self.simulation()
            elif page == 'monitor':
                content = render_plant(self.state)
            else:
                content = panel('Minha senha', self.password_form())
            live = page in ('overview', 'monitor') and status == 200
            if live:
                content = '<div class="live-status" data-live-status role="status">Atualização automática em segundo plano</div><div class="live-content" data-curve-revision="'+str(getattr(app.state.store,'_curve_revision',0))+'" data-live-page="' + page + '">' + content + '</div><noscript><p>Ative JavaScript para atualização automática. O botão Atualizar continua disponível.</p></noscript>'
            if page == 'overview' and self.technical and self.state['settings']['mode'] == 'simulation':
                content += self.simulation()
            network = getattr(app.state, 'web_network', None)
            if network is not None and page in ('settings', 'overview'):
                details = network.public()
                urls = ([details['url']] if details['announced'] else []) + details['ip_urls']
                if not urls:
                    urls = [('https' if self.request.url.scheme == 'https' else 'http') + '://127.0.0.1:' + str(details['port'])]
                content += panel('Acesso pela rede local', '<p>' + esc(details['status']) + '</p>'
                    + ''.join('<p><a href="' + esc(url) + '">' + esc(url) + '</a></p>' for url in urls)
                    )
            nav = ''.join('<a class="nav' + (' active' if key == page else '') + '" href="/ui/' + key + '">' + esc(title) + '</a>'
                          for key, title in PAGES.items() if allowed.get(key, True))
            body = ('<div id="shell"><aside class="sidebar"><a class="brand" href="/">'
                    '<img src="/static/d-max-logo.png" alt="D-Max by EnergyCube" class="dmax-logo"></a>'
                    '<div class="sidebar-label">CONTROLADOR DE DEMANDA</div><nav>' + nav + '</nav>'
                    '<div class="sidebar-bottom"><b>' + esc(self.user['full_name'] or self.user['name']) + '</b><p>'
                    + esc('Comercial · demonstração' if self.demonstration else ROLES[self.user['role']]) + '</p>' + self.form('logout', submit='Sair') + '</div></aside>'
                    '<main><header><div><div class="eyebrow" data-live-site>' + esc(self.state['settings']['site_name']) + '</div>'
                    '<h1>' + esc(PAGES[page]) + '</h1></div><a class="secondary" href="/ui/' + page + '">Atualizar</a></header>'
                    + ('<div class="notice">Demonstração comercial descartável · dados fictícios · sair apaga esta sessão.</div>' if self.demonstration else subscription_banner(self.state)) + note + content + '<footer class="app-footer"><span>EnergyCube D-Max · Controle local</span><span>Versão instalada: <b data-dmax-version>v' + VERSION + '</b></span></footer></main></div>')
            response = self.finish(HTMLResponse(self.document(body, PAGES[page], live=live), status_code=status))
            if live:
                response.headers['X-DMax-Live'] = '1'
            if page in ('maintenance','remote'):
                response.headers['X-DMax-Live'] = '1'
            return response

        @property
        def technical(self):
            return self.user and self.user['role'] in ('root', 'developer', 'technician')

        @property
        def manager(self):
            return self.user and self.user['role'] in ('root', 'developer', 'technician', 'admin')

        def password_form(self):
            if self.user and self.user['name'] == 'root':
                return '<p>O acesso raiz é definido pelo proprietário. Sessão por senha: 4 horas sem atualização autenticada; renovada durante supervisão. Recuperação por assinatura: 15 minutos, sem renovação.</p>'
            return self.form('password',
                field('Senha atual', 'current_password', kind='password', required='', maxlength=200, autocomplete='current-password')
                + field('Nova senha', 'new_password', kind='password', minlength=8, maxlength=200, required='', autocomplete='new-password')
                + field('Confirme a nova senha', 'confirmation', kind='password', minlength=8, maxlength=200, required='', autocomplete='new-password'),
                'Alterar senha e entrar novamente', page='profile')

        async def load_curve(self):
            self.curve_params={name:self.request.query_params.get('curve_'+name,'') for name in ('start','end','mode')}
            self.curve_error=''
            try:self.curve=await self.api('GET','/api/curve?'+urlencode(self.curve_params))
            except UIError as exc:
                if exc.status!=422:raise
                self.curve_error=exc.message+' · exibindo os últimos 15 minutos.'
                self.curve_params={}
                self.curve=await self.api('GET','/api/curve')

        def curve_controls(self):
            data=self.curve_params
            fields=field('Início · horário da instalação','curve_start',data.get('start',''),'datetime-local')
            fields+=field('Fim · vazio acompanha ao vivo','curve_end',data.get('end',''),'datetime-local')
            fields+=select('Origem','curve_mode',[('physical','Real'),('simulation','Simulação')],data.get('mode') or self.state['settings']['mode'])
            content='<form method="get" action="/ui/overview" class="curve-filters">'+fields+'<button class="primary">Aplicar período</button></form>'
            query=urlencode(data)
            content+='<p><a class="secondary" href="/api/curve/report.pdf?'+esc(query)+'">Relatório PDF da curva</a> <a class="secondary" href="/api/curve/export.csv?'+esc(query)+'">CSV com todos os registros</a> '+link('overview','Voltar ao vivo')+'</p>'
            return content+'<p class="hint">Histórico local: até 30 dias · fuso '+esc(self.state['settings']['timezone'])+'. Aplique o período antes de exportar.</p>'

        def overview(self,controls=True):
            summary = self.state['summary']
            content = render_plant(self.state)
            from .curve import render as render_curve
            chart='<div data-live-key="curve-controls">'+(self.curve_controls() if controls else '')+'</div>'
            if self.curve_error:chart+='<p class="notice">'+esc(self.curve_error)+'</p>'
            chart+=render_curve(self.curve)
            chart=panel('Curva de demanda · consulta por período',chart).replace('<article class="panel">','<article class="panel" data-live-key="chart">',1)
            content=content.replace('<div class="plant-section-title">',chart+'<div class="plant-section-title">',1)
            if self.state.get('fault') or not summary.get('meter_fresh'):
                content += '<div class="notice">' + esc(self.state.get('fault') or 'Sem medição atual: novas liberações bloqueadas.') + '</div>'
            content += '<p>' + ('Horário bloqueado · novas conexões aguardam.' if summary.get('blocked') else 'Horário permitido para recarga.') + '</p>'
            return content

        def simulation(self):
            if self.state['settings']['mode'] != 'simulation':
                return panel('Simulador desativado', '<p>A instalação está em modo físico.</p>')
            return panel('Simulação', self.form('load',
                field('Outras cargas · kW', 'other_kw', self.state['summary'].get('other_kw', 0), 'number', min=0, step='any', required=''),
                'Aplicar carga', page='overview')
                + (self.form('demo', submit='Carregar demonstração', page='overview') if not self.state['chargers'] else '')
                + link('overview', 'Acompanhar distribuição de potência'))

        def vehicle_options(self):
            return [('', 'Não identificado / associação manual')] + [(v['id'], v['name']) for v in self.state['vehicles']]

        def card(self, port, controls=True):
            charger = next(c for c in self.state['chargers'] if c['id'] == port['charger'])
            vehicle = next((v for v in self.state['vehicles'] if v['id'] == port['vehicle_id']), None)
            content = '<h3>' + esc(charger['name']) + '</h3><small>' + esc(port['key']) + '</small>'
            content += '<div class="charger-vehicle">' + esc(vehicle['name'] if vehicle else 'Veículo não identificado') + (' ★ PRIORITÁRIO' if vehicle and vehicle['priority'] else '') + '</div>'
            content += '<div class="charger-power"><strong>' + number(port['power_kw']) + ' kW</strong><small>' + ('Potência definida pelo carregador' if port.get('native_mode') else 'Limite ' + number(port['limit_kw']) + ' kW') + '</small></div>'
            content += '<p>' + esc(port['status']) + '</p>'
            if controls:
                if port['connected']:
                    if not self.state.get('subscription', {}).get('native'):
                        content += self.form('port', submit='Retomar' if port['manual_pause'] else 'Pausar',
                                             page='chargers', key=port['key'], command='resume' if port['manual_pause'] else 'pause')
                    content += self.form('port', select('Veículo', 'vehicle_id', self.vehicle_options(), port['vehicle_id'] or ''),
                                         'Associar veículo', page='chargers', key=port['key'], command='assign_vehicle')
                    if (self.manager or self.user['can_emergency']) and not self.state.get('subscription', {}).get('native'):
                        if port['emergency_until'] > self.state['time']:
                            content += self.form('port', submit='Encerrar emergência', page='chargers', key=port['key'], command='cancel_emergency')
                        else:
                            content += '<details><summary>Liberar emergência</summary>' + self.form('port',
                                field('Duração · minutos', 'minutes', 30, 'number', min=1, max=1440, required='')
                                + field('Motivo', 'reason', required='', maxlength=200),
                                'Liberar emergência', page='chargers', key=port['key'], command='emergency') + '</details>'
                if charger['transport'] == 'simulator' and self.technical and self.state['settings']['mode'] == 'simulation':
                    fields = '' if port['connected'] else (
                        select('Veículo', 'vehicle_id', self.vehicle_options(), '')
                        + field('Potência aceita · kW', 'acceptance_kw', charger['connector_max_kw'], 'number', min=0.1, step='any', required=''))
                    content += self.form('port', fields, 'Desconectar' if port['connected'] else 'Conectar veículo',
                                         page='chargers', key=port['key'], command='disconnect' if port['connected'] else 'connect')
                if self.technical:
                    content += link('chargers', 'Configurar carregador', edit=charger['id'])
                    if port['running'] and not self.state.get('subscription', {}).get('native'):
                        content += '<details><summary>Aprendizado assistido</summary>' + self.form('learn',
                            field('Limite de teste · kW', 'cap_kw', port['limit_kw'] / 2, 'number', min=0, step='any', required='')
                            + field('Duração · segundos', 'seconds', 30, 'number', min=10, max=300, required=''),
                            'Testar redução', page='chargers', key=port['key']) + '</details>'
            if controls and self.technical:
                content += self.delete_charger(charger)
            return '<article class="charger-card" data-live-key="' + esc(port['key']) + '">' + content + '</article>'

        def delete_charger(self, charger):
            return '<details><summary>Excluir carregador</summary><p>Remove do cadastro ativo e preserva o histórico. Equipamentos físicos devem estar sem recarga e desconectados do OCPP.</p>' + self.form('delete_charger', checkbox('Confirmo excluir este carregador', 'confirm').replace('name="confirm"','name="confirm" value="yes"'), 'Excluir carregador', page='chargers', id=charger['id']) + '</details>'

        def chargers(self):
            content = '<div class="charger-grid" data-live-key="ports">' + ''.join(self.card(p) for p in self.state['ports']) + '</div>'
            if not self.technical:
                return content
            inactive = self.state.get('inactive_chargers', [])
            if inactive:
                content += panel('Carregadores de outro modo', table(['Carregador','Transporte','Ação'],
                    [[esc(c['name']), esc(c['transport']), self.delete_charger(c)] for c in inactive]))
            old = next((c for c in self.state['chargers'] if c['id'] == self.request.query_params.get('edit')), None)
            c = old or dict(id='', name='', model='', ip='', max_kw=320, connector_max_kw=320, min_kw=6, connectors=1,
                            transport='ocpp' if self.state['settings']['mode'] == 'physical' else 'simulator', circuit=self.state['settings']['circuits'][0]['id'], enabled=True,
                            commissioned=False, zero_supported=False, rate_unit='W', voltage=230, phases=3, input_factor=1)
            fields = field('Identificador OCPP', 'id', c['id'], required='', maxlength=40, readonly='' if old else None)
            fields += field('Nome', 'name', c['name'], required='', maxlength=100) + field('Modelo', 'model', c['model'], maxlength=100) + field('IP de referência', 'ip', c['ip'], maxlength=253)
            fields += select('Transporte', 'transport', [('simulator', 'Simulador'), ('ocpp', 'OCPP 1.6J')], c['transport'])
            for name, title in [('max_kw', 'Potência total · kW'), ('connector_max_kw', 'Potência por conector · kW'), ('min_kw', 'Mínimo validado · kW'),
                                ('connectors', 'Conectores'), ('input_factor', 'Fator de entrada / perdas'), ('voltage', 'Tensão fase-neutro · V'), ('phases', 'Fases')]:
                fields += field(title, name, c[name], 'number', step='any', required='')
            fields += select('Circuito', 'circuit', [(x['id'], x['name']) for x in self.state['settings']['circuits']], c['circuit'])
            fields += select('Unidade OCPP', 'rate_unit', [('W', 'Watts'), ('A', 'Ampères')], c['rate_unit'])
            fields += field('Senha OCPP · vazio mantém a atual', 'password', kind='password', minlength=8, maxlength=200, autocomplete='new-password')
            fields += checkbox('Habilitado', 'enabled', c['enabled']) + checkbox('Zero e retomada homologados', 'zero_supported', c['zero_supported']) + checkbox('Comissionamento concluído', 'commissioned', c['commissioned'])
            return content + panel('Editar carregador' if old else 'Novo carregador', self.form('charger', fields, page='chargers'))

        def vehicles(self):
            rows = [[esc(v['name']), esc(v.get('plate', '')), '★' if v['priority'] else 'Normal', esc(', '.join(v['identifiers'])),
                     (link('vehicles', 'Editar', edit=v['id']) + '<details><summary>Excluir da frota</summary><p>O histórico de recargas será preservado.</p>'
                      + self.form('delete_vehicle', checkbox('Confirmo a exclusão', 'confirm'), 'Excluir veículo', page='vehicles', id=v['id']) + '</details>') if self.manager else ''] for v in self.state['vehicles']]
            content = panel('Veículos', table(['Nome', 'Placa', 'Prioridade', 'Identificadores', ''], rows))
            identifiers = [[esc(x['id']), esc(x['source']), link('vehicles', 'Associar', identifier=x['id']) if self.manager else ''] for x in self.state['identifiers']]
            content += panel('Identificadores observados', table(['Identificador', 'Origem', ''], identifiers))
            if self.manager:
                v = next((v for v in self.state['vehicles'] if v['id'] == self.request.query_params.get('edit')), None)
                v = v or dict(id='', name='', plate='', priority=False, identifiers=[self.request.query_params['identifier']] if self.request.query_params.get('identifier') else [])
                fields = hidden('id', v['id']) + field('Nome do veículo', 'name', v['name'], required='', maxlength=100)
                fields += field('Placa', 'plate', v['plate'], maxlength=20) + field('Identificadores separados por vírgula', 'identifiers', ', '.join(v['identifiers']))
                fields += checkbox('Veículo prioritário', 'priority', v['priority'])
                content += panel('Cadastro de veículo', self.form('vehicle', fields, page='vehicles'))
            return content

        def schedules(self):
            settings = self.state['settings']
            rows = [[esc(', '.join(str(d + 1) for d in item['days'])), esc(item['start']), esc(item['end']),
                     self.form('schedule_delete', submit='Remover', page='schedule', index=index) if self.manager else '']
                    for index, item in enumerate(settings['schedules'])]
            content = panel('Bloqueios', table(['Dias · segunda=1', 'Início', 'Término', ''], rows))
            if self.manager:
                fields = ''.join(checkbox(day, 'days', i < 5).replace('name="days"', 'name="days" value="' + str(i) + '"') for i, day in enumerate(('Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom')))
                fields += field('Início', 'start', '18:00', 'time', required='') + field('Término', 'end', '21:00', 'time', required='')
                fields += select('Sessões durante bloqueio', 'blocked_policy', [('zero', 'Suspender com zero'), ('minimum', 'Mínimo · ainda consome energia')], settings['blocked_policy'])
                content += panel('Novo bloqueio', self.form('schedule_add', fields, page='schedule'))
            return content

        def settings(self):
            s = self.state['settings']
            fields = field('Nome da instalação', 'site_name', s['site_name'], required='', maxlength=100)
            fields += field('Demanda operacional · kW', 'limit_kw', s['limit_kw'], 'number', min=0.1, step='any', required='')
            if self.technical:
                fields += select('Modo', 'mode', [('simulation', 'Simulação'), ('physical', 'Equipamentos físicos · piloto')], s['mode'])
                for key, title in [('technical_limit_kw', 'Teto técnico · kW'), ('margin_kw', 'Margem · kW'), ('freshness_s', 'Leitura válida · segundos'), ('ramp_kw_s', 'Rampa · kW/s'), ('curve_min_delta_kw', 'Curva · tolerância mínima · kW'), ('retain_days', 'Retenção de leituras sincronizadas · dias')]:
                    fields += field(title, key, s[key], 'number', step='any', required='')
                fields += field('Fuso horário', 'timezone', s['timezone'], required='') + field('API de nuvem real · HTTPS', 'cloud_url', s['cloud_url'], 'url')
                fields += field('API de demonstração separada · HTTPS', 'demo_cloud_url', s.get('demo_cloud_url',''), 'url')
                for i, circuit in enumerate(s['circuits']):
                    fields += '<fieldset><legend>Circuito ' + esc(circuit['id']) + '</legend>'
                    fields += field('Nome', 'circuit_name_' + str(i), circuit['name'], required='')
                    fields += field('Limite · kW', 'circuit_limit_' + str(i), circuit['limit_kw'], 'number', step='any', required='') + '</fieldset>'
            content = panel('Configuração', self.form('settings', fields, page='settings'))
            colors = ''.join(field(label, 'color_' + key, s['display_colors'][key], 'color', required='')
                for key, label in [('charging', 'Carregando'), ('connected', 'Cabo conectado'), ('alarm', 'Alarme'),
                                   ('disconnected', 'Cabo desconectado / estado não confirmado'), ('communication', 'Sem comunicação')])
            content += panel('Cores da planta local', '<p>Escolha as cores nos seletores abaixo. Elas alteram a página local do D-Max; no Grafana, use os limiares do cartão.</p>'
                + self.form('appearance', colors, 'Salvar cores', page='settings'))
            if self.technical:
                content += panel('Integração com a nuvem', '<p>Identificador deste controlador: <code>' + esc(self.state['cloud']['controller_id']) + '</code></p><p>' + esc(self.state['cloud']['status']) + '</p><p>Registros pendentes: ' + str(self.state['cloud']['pending']) + '</p><p>Token por equipamento: EV_CLOUD_TOKEN no ambiente do serviço. Nunca use a senha raiz como token.</p>')
            if self.technical:
                content += panel('Adicionar circuito', self.form('circuit',
                    field('Identificador', 'id', required='', maxlength=40)
                    + field('Nome', 'name', required='', maxlength=100)
                    + field('Limite · kW', 'limit_kw', 100, 'number', step='any', min=0.1, required=''), page='settings'))
            if self.user['role'] in ('root','developer'):
                content += panel('Recuperar administrador', self.form('recover',
                    field('Nova senha do administrador', 'password', kind='password', minlength=8, maxlength=200, required='', autocomplete='new-password'),
                    'Redefinir e encerrar sessões', page='settings'))
            return content

        def meter(self, diagnostic, ports):
            m = diagnostic.get('draft', self.state['settings']['meter']) if diagnostic else self.state['settings']['meter']
            fields = select('Transporte', 'transport', [('tcp', 'Modbus TCP/IP'), ('rtu', 'RS485 · Modbus RTU')], m['transport'])
            fields += field('Host / IP', 'host', m['host'], maxlength=253) + field('Porta TCP', 'port', m['port'], 'number', min=1, max=65535)
            choices = [('', 'Selecione uma porta conectada ao servidor')]
            for port in ports:
                device = port.get('stable_path') or port['device']
                choices.append((device, port['description'] + ' · ' + device))
                if m['serial_port'] == port['device'] and device != port['device']:
                    choices.append((port['device'], port['description'] + ' · ' + port['device'] + ' (configuração atual)'))
            if m['serial_port'] and m['serial_port'] not in {key for key, label in choices}:
                choices.append((m['serial_port'], 'Configurada, não detectada: ' + m['serial_port']))
            fields += select('Porta serial do servidor', 'serial_port', choices, m['serial_port'])
            if not ports:
                fields += '<p class="hint">Nenhuma porta serial detectada no servidor.</p>'
            fields += '<p class="hint">A lista mostra as portas do Raspberry/servidor, não do computador que abriu a página. Atualize esta página após conectar o adaptador.</p>'
            for key, title in [('baudrate', 'Baud rate'), ('unit', 'Unit ID'), ('address_base', 'Base · 0 ou 1'), ('poll_s', 'Intervalo de leitura · s'), ('timeout_s', 'Timeout · s'), ('stopbits', 'Stop bits')]:
                fields += field(title, key, m[key], 'number', step='any', required='')
            fields += select('Paridade', 'parity', [('N', 'Nenhuma'), ('E', 'Par'), ('O', 'Ímpar')], m['parity'])
            rows = []
            for i, reg in enumerate(m['registers']):
                prefix = 'reg_' + str(i) + '_'
                rows.append([checkbox(MEASUREMENTS[reg['measurement']][0], prefix + 'enabled', reg['enabled']),
                    field('Offset', prefix + 'address', reg['address'], 'number', min=0, max=65536, required=''),
                    select('Função', prefix + 'function', [(3, '03'), (4, '04')], reg['function']),
                    select('Tipo', prefix + 'type', [(t, t) for t in FORMATS], reg['type']),
                    field('Escala', prefix + 'scale', reg['scale'], 'number', step='any', required=''),
                    select('Palavras', prefix + 'word_order', [('big', 'Normal'), ('little', 'Invertidas')], reg['word_order']),
                    select('Bytes', prefix + 'byte_order', [('big', 'Normal'), ('little', 'Invertidos')], reg['byte_order'])])
            fields += table(['Ler', 'Offset', 'Função', 'Tipo', 'Escala', 'Palavras', 'Bytes'], rows)
            fields += '<button class="secondary" type="submit" name="operation" value="test">Testar leitura sem salvar</button>'
            content = panel('Multimedidor e mapa manual', self.form('meter', fields, 'Salvar multimedidor', page='meter'))
            readings = diagnostic.get('readings', []) if diagnostic else self.state['meter'].get('readings', [])
            error = diagnostic.get('error', '') if diagnostic else self.state['meter'].get('error', '')
            content += panel('Diagnóstico', '<p>' + esc(error) + '</p>' + table(['Grandeza', 'Valor', 'Erro'],
                [[esc(r['label']), esc(r.get('value')) + ' ' + esc(r.get('unit')), esc(r.get('error'))] for r in readings]))
            return content

        async def history(self):
            history = await self.api('GET', '/api/history')
            from datetime import datetime
            from zoneinfo import ZoneInfo
            zone = ZoneInfo(self.state['settings']['timezone'])
            def stamp(value):
                return esc(datetime.fromtimestamp(value, zone).strftime('%d/%m/%Y %H:%M:%S')) if value else 'Em andamento'
            names = {v['id']: v['name'] for v in app.state.store.entities('vehicle')}
            sessions = [[stamp(s['started_at']), stamp(s.get('ended_at')), esc(s['port']),
                         esc(names.get(s.get('vehicle_id'), 'Não identificado')), number(s['energy_kwh'], 3) + ' kWh',
                         number(s.get('peak_kw', 0)) + ' kW', esc(s.get('mode','Origem desconhecida')), esc(s.get('reason', ''))] for s in history['sessions']]
            events = [[stamp(e['ts']), esc(e['kind']), esc(e['payload'])] for e in history['events']]
            vehicles = [('', 'Todos os veículos')] + [(v['id'], v['name'] + (' · excluído' if v.get('archived') else '')) for v in app.state.store.entities('vehicle')]
            chargers = [('', 'Todos os carregadores')] + [(c['id'], c['name'] + (' · excluído' if c.get('archived') else '')) for c in app.state.store.entities('charger')]
            filters = (field('Início do período · horário da instalação', 'start', kind='datetime-local')
                       + field('Fim do período · horário da instalação', 'end', kind='datetime-local')
                       + select('Veículo', 'vehicle_id', vehicles) + select('Carregador', 'charger_id', chargers))
            filters += select('Relatório', 'report_type', [('detailed','Detalhado por sessão'), ('vehicles','Geral por veículo')])
            filters += select('Origem da energia', 'energy_scope', [('all','Todas · totais separados'),('physical','Real'),('simulation','Simulação')])
            filters += '<fieldset><legend>Veículos do relatório geral · vazio seleciona todos</legend>' + ''.join('<label><input type="checkbox" name="vehicle_selection" value="'+esc(v['id'])+'">'+esc(v['name'])+'</label>' for v in app.state.store.entities('vehicle')) + '<label><input type="checkbox" name="vehicle_selection" value="unassigned">Sem veículo associado</label></fieldset>'
            export = '<form method="get" action="/api/reports/sessions.pdf">' + filters + '<button class="primary" type="submit">Baixar relatório PDF</button></form>'
            guidance = '<p class="hint">Fuso: ' + esc(str(zone)) + '. Seleção pelo início da sessão, com término do filtro exclusivo. O PDF inclui todas as sessões encontradas, inclusive veículos e carregadores excluídos. Sessões abertas têm valores parciais.</p>'
            from .reports import report_data
            summary=report_data(app.state.store,report_type='vehicles')['vehicle_summary']
            fleet=table(['Veículo','Origem','kWh históricos','Recargas','Último início'],[[esc(r['vehicle_name']),esc({'physical':'Real','simulation':'Simulação','unknown':'Desconhecida'}[r['scope']]),number(r['total_kwh'],3),str(r['count']),stamp(r['last_at']) if r['last_at'] else 'Sem recarga'] for r in summary])
            return panel('Relatório de recargas em PDF', export + guidance) + panel('Resumo acumulado por veículo · origens separadas',fleet) + panel('Últimas sessões', table(['Início', 'Término', 'Conector', 'Veículo', 'Energia', 'Pico', 'Origem', 'Estado'], sessions)) + panel('Eventos', table(['Horário', 'Evento', 'Detalhes'], events))

        async def users(self):
            users = (await self.api('GET', '/api/users'))['users']
            rows = [[esc(u['full_name']), esc(u['name']), esc(ROLES[u['role']]), 'Excluído' if u['deleted'] else 'Ativo' if u['active'] else 'Bloqueado',
                     'Pendente de envio' if u['source'] == 'local_pending' else 'Global' if u['source'] == 'directory' else 'Local',
                     link('users', 'Editar', edit=u['id']) + self.form('reset_user', submit='Redefinir senha inicial', page='users', id=u['id']) if u['role'] not in ('root','developer','commercial') else ('Recuperação' if u['role']=='root' else 'Gerenciada na plataforma')]
                    for u in users]
            content = panel('Contas gerenciáveis', table(['Nome', 'Login', 'Perfil', 'Situação', 'Sincronização', ''], rows))
            old = next((u for u in users if u['id'] == self.request.query_params.get('edit') and u['role'] not in ('root','developer','commercial')), None)
            u = old or dict(name='', full_name='', role='operator', active=True, deleted=False, expires_at=None, can_emergency=False)
            choices = ['technician'] if u['role'] == 'technician' else ['operator', 'admin', 'technician'] if self.user['role'] in ('root','developer') else ['operator', 'admin'] if self.technical else ['operator']
            fields = hidden('id', old['id'] if old else '') + field('Nome completo', 'full_name', u['full_name'], required='', maxlength=100)
            fields += field('Login permanente', 'name', u['name'], required='', minlength=3, maxlength=40, readonly='' if old else None)
            fields += select('Perfil', 'role', [(r, ROLES[r]) for r in choices], u['role'])
            fields += field('Validade ISO com fuso · vazio não expira', 'expires_at', iso_expiry(u['expires_at']), placeholder='2027-12-31T23:59:59-03:00')
            fields += checkbox('Operador pode liberar emergência', 'can_emergency', u['can_emergency'])
            if old:
                fields += checkbox('Conta ativa', 'active', u['active']) + checkbox('Excluir acesso e preservar auditoria', 'deleted', u['deleted'])
            guidance = '<p class="hint">Novas contas cadastradas aqui entram com a senha inicial 12345678 e devem trocá-la antes de operar. Não há código de primeiro acesso.</p>'
            return content + panel('Editar conta' if old else 'Adicionar usuário', guidance + self.form('user', fields, page='users'))

        async def remote_clients(self):
            from datetime import datetime
            from zoneinfo import ZoneInfo
            intro='<p>Os endereços são consultados na plataforma somente ao abrir esta aba ou clicar em Atualizar. Escolha o cliente para abrir o D-Max em outra aba e faça login nele.</p>'
            try:data=await self.api('GET','/api/remote-clients')
            except UIError as exc:return panel('Clientes remotos',intro+'<p class="notice">'+esc(exc.message)+'</p>')
            zone=ZoneInfo(self.state['settings']['timezone']);query=self.request.query_params.get('q','')[:100]
            intro+='<form method="get" class="remote-search">'+field('Nome do cliente ou identificador','q',query)+'<button class="primary">Buscar</button></form>'
            intro+='<p class="hint">Consulta: '+esc(datetime.fromtimestamp(data['fetched_at'],zone).strftime('%d/%m/%Y %H:%M:%S'))+' · '+esc(str(zone))+'. O estado é o último informado pelo equipamento; confira a data da comunicação.</p>'
            cards=''
            for row in data['clients']:
                if query.casefold() not in (row['site_name']+' '+row['controller_id']).casefold():continue
                age=time.time()-row['updated_at'];recent=age<=900
                label='Último informe: conectado' if row['connected'] else 'Último informe: desconectado'
                if not recent:label='Sem comunicação recente · '+label.lower()
                cards+='<article class="remote-client"><h3>'+esc(row['site_name'])+'</h3><p class="hint">'+esc(row['controller_id'])+'</p><p>'+esc(label)+'</p><p>Comunicação: '+esc(datetime.fromtimestamp(row['updated_at'],zone).strftime('%d/%m/%Y %H:%M:%S'))+'</p><a class="primary" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer" href="'+esc(row['url'])+'">Abrir D-Max</a><p class="hint remote-address">'+esc(row['url'])+'</p></article>'
            return panel('Clientes remotos',intro+('<div class="remote-clients">'+cards+'</div>' if cards else '<p>Nenhum cliente encontrado. Confira os nomes em Configurações de cada D-Max e o envio à aba DMax_Remoto.</p>'))

        async def directory(self):
            data = await self.api('GET', '/api/directory')
            config = data['config']
            fields = field('URL publicada do Apps Script', 'url', config['url'], 'url', maxlength=1000)
            fields += field('Chave deste equipamento · vazio mantém', 'device_token', kind='password', minlength=32, maxlength=512, autocomplete='new-password')
            fields += field('Intervalo · segundos', 'interval_s', config['interval_s'], 'number', min=30, max=86400, required='')
            fields += checkbox('Ativar consulta', 'enabled', config['enabled'])
            status = table(['Informação', 'Valor'], [[esc('Identificador do D-Max'), esc(data['controller_id'])],
                [esc('Situação'), esc(data['status']['message'])], [esc('Chave'), 'Configurada' if data['token_present'] else 'Pendente'],
                [esc('Alterações locais pendentes'), esc(data['pending'])]])
            subscription = self.state.get('subscription', {})
            billing = panel('Assinatura deste equipamento', '<p>Estado: <b>' + esc(subscription.get('state')) + '</b> · Revisão ' + esc(subscription.get('revision')) + '</p><p>O controle comercial usa a aba Assinaturas da mesma planilha. Configure uma linha com o identificador acima e situação regular ou pendente. O aviso recebido continua válido sem internet; apagar a linha não cancela a pendência.</p><p class="hint">Exige o Apps Script atualizado fornecido com a v0.9.0. Para medir tempo desligado sem internet, use RTC com bateria. Administradores do sistema operacional podem alterar o banco: este mecanismo não é proteção contra acesso root ao Linux.</p>')
            return (billing + panel('Google Planilhas e Apps Script', self.form('directory', fields, page='directory'))
                    + panel('Sincronização', status + self.form('sync', submit='Sincronizar agora', page='directory'))
                    + '<p class="hint">Sem internet, permanece exatamente a validade recebida na última consulta.</p>')

    class UIError(Exception):
        def __init__(self, message, status=422):
            self.message, self.status = message, status

    async def live_data(request: Request, page):
        console = Console(request)
        if page not in ('overview', 'monitor'):
            return JSONResponse({'detail': 'Página não encontrada'}, status_code=404)
        if not console.user or console.user['must_change']:
            return JSONResponse({'detail': 'Faça login e conclua a troca de senha'}, status_code=401,
                                headers={'Cache-Control': 'no-store'})
        try:
            console.state = await console.api('GET', '/api/state')
            await console.load_curve()
            content = console.overview(controls=False)
            return console.finish(JSONResponse({'schema_version': 1, 'version': VERSION,
                'curve_push': not app.state.demonstration,
                'curve_revision': getattr(app.state.store,'_curve_revision',0),
                'observed_at': console.state['time'], 'site_name': console.state['settings']['site_name'],
                'subscription_nodes': view_tree(subscription_banner(console.state)),
                'colors': console.state['settings']['display_colors'], 'nodes': view_tree(content)}))
        except UIError as exc:
            return JSONResponse({'detail': exc.message}, status_code=exc.status, headers={'Cache-Control': 'no-store'})

    async def get_page(request: Request, page='overview'):
        console = Console(request)
        message = 'Alteração aplicada.' if request.cookies.get('dmax_saved') == '1' else ''
        try:
            return await console.render(page, message)
        except UIError as exc:
            if exc.status == 401:
                console.user = None
            return await console.render('overview', exc.message, status=exc.status)

    async def post(request: Request):
        console = Console(request)
        form = {}
        value = lambda key, default='': form.get(key, [default])[0]
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 131072:
                return console.finish(HTMLResponse('Formulário excedeu o tamanho permitido', status_code=413))
        try:
            if request.headers.get('content-type', '').split(';', 1)[0] != 'application/x-www-form-urlencoded':
                raise UIError('Formato de formulário inválido', 415)
            form = parse_qs(body.decode('utf-8'), keep_blank_values=True, max_num_fields=1024, errors='strict')
            if any(len(values) != 1 and key != 'days' for key, values in form.items()):
                raise UIError('Campos duplicados', 422)
            action, page = value('_action'), value('_page', 'overview')
            if page not in PAGES or not console.valid_token(action, value('_csrf')):
                raise UIError('Formulário expirado ou inválido. Atualize a página e tente novamente.', 403)
            api = console.api
            diagnostic = None
            if action == 'setup':
                await api('POST', '/api/setup', {'admin_password': value('admin_password')})
                return await console.render('overview', 'Instalação configurada. Entre com admin e a senha cadastrada.')
            elif action == 'recovery_challenge':
                result = await api('POST', '/api/recovery/challenge', {})
                return await console.render('overview', 'Envie o desafio ao responsável pela chave de recuperação.', recovery_data=result)
            elif action == 'recovery_authorize':
                await api('POST', '/api/recovery/authorize', {'authorization': value('authorization')})
            elif action == 'login':
                await api('POST', '/api/login', {k: value(k) for k in ('username', 'password')})
            elif action == 'logout':
                await api('POST', '/api/logout', {})
            elif action == 'password':
                if value('new_password') != value('confirmation'):
                    raise UIError('As novas senhas não coincidem')
                await api('POST', '/api/change-password', {k: value(k) for k in ('current_password', 'new_password')})
            else:
                if not console.user or console.user['must_change']:
                    raise UIError('Faça login e conclua a troca de senha antes de operar.', 401)
                state = await api('GET', '/api/state')
                settings = state['settings']
                if action == 'appearance':
                    await api('PUT', '/api/appearance', {key: value('color_' + key) for key in
                        ('charging', 'connected', 'alarm', 'disconnected', 'communication')})
                elif action in ('demo', 'load'):
                    await api('POST', '/api/demo' if action == 'demo' else '/api/simulation',
                              {} if action == 'demo' else {'other_kw': float(value('other_kw'))})
                elif action in ('port', 'learn'):
                    key = quote(value('key'), safe='')
                    if action == 'learn':
                        await api('POST', '/api/ports/' + key + '/learn', {'cap_kw': float(value('cap_kw')), 'seconds': int(value('seconds'))})
                    else:
                        command = value('command')
                        data = {'action': command}
                        if command in ('assign_vehicle', 'connect'):
                            data['vehicle_id'] = value('vehicle_id') or None
                        if command == 'connect':
                            data['acceptance_kw'] = float(value('acceptance_kw'))
                        if command == 'emergency':
                            data.update(reason=value('reason'), minutes=int(value('minutes')))
                        await api('POST', '/api/ports/' + key + '/action', data)
                elif action == 'charger':
                    data = {k: value(k) for k in ('id', 'name', 'model', 'ip', 'transport', 'circuit', 'rate_unit')}
                    data.update({k: float(value(k)) for k in ('max_kw', 'connector_max_kw', 'min_kw', 'input_factor', 'voltage')})
                    data.update({k: int(value(k)) for k in ('connectors', 'phases')})
                    data.update({k: k in form for k in ('enabled', 'zero_supported', 'commissioned')})
                    if value('password'):
                        data['password'] = value('password')
                    await api('POST', '/api/chargers', data)
                elif action == 'delete_charger':
                    if value('confirm') != 'yes':
                        raise UIError('Confirme a exclusão do carregador.')
                    await api('DELETE', '/api/chargers/' + quote(value('id'), safe=''))
                elif action == 'delete_vehicle':
                    if 'confirm' not in form:
                        raise UIError('Confirme a exclusão do veículo.')
                    await api('DELETE', '/api/vehicles/' + quote(value('id'), safe=''))
                elif action == 'vehicle':
                    data = dict(name=value('name'), plate=value('plate'), identifiers=[x.strip() for x in value('identifiers').split(',') if x.strip()], priority='priority' in form)
                    if value('id'):
                        data['id'] = value('id')
                    await api('POST', '/api/vehicles', data)
                elif action in ('settings', 'circuit', 'schedule_add', 'schedule_delete', 'meter'):
                    if action == 'settings':
                        for key in ('site_name', 'timezone', 'mode', 'cloud_url', 'demo_cloud_url'):
                            if key in form:
                                settings[key] = value(key)
                        for key in ('limit_kw', 'technical_limit_kw', 'margin_kw', 'freshness_s', 'ramp_kw_s', 'curve_min_delta_kw'):
                            if key in form:
                                settings[key] = float(value(key))
                        if 'retain_days' in form:
                            settings['retain_days'] = int(value('retain_days'))
                        for i, circuit in enumerate(settings['circuits']):
                            if 'circuit_name_' + str(i) in form:
                                circuit['name'] = value('circuit_name_' + str(i))
                                circuit['limit_kw'] = float(value('circuit_limit_' + str(i)))
                    elif action == 'circuit':
                        settings['circuits'].append(dict(id=value('id'), name=value('name'), limit_kw=float(value('limit_kw'))))
                    elif action == 'schedule_add':
                        settings['schedules'].append(dict(days=[int(x) for x in form.get('days', [])], start=value('start'), end=value('end'), enabled=True))
                        settings['blocked_policy'] = value('blocked_policy')
                    elif action == 'schedule_delete':
                        index = int(value('index'))
                        if not 0 <= index < len(settings['schedules']):
                            raise UIError('Horário não encontrado')
                        settings['schedules'].pop(index)
                    else:
                        meter = settings['meter']
                        for key in ('transport', 'host', 'serial_port', 'parity'):
                            meter[key] = normalize_serial_port(value(key)) if key == 'serial_port' else value(key)
                        for key in ('port', 'unit', 'baudrate', 'address_base', 'stopbits'):
                            meter[key] = int(value(key))
                        for key in ('poll_s', 'timeout_s'):
                            meter[key] = float(value(key))
                        for i, reg in enumerate(meter['registers']):
                            prefix = 'reg_' + str(i) + '_'
                            reg['enabled'] = prefix + 'enabled' in form
                            for key in ('address', 'function'):
                                reg[key] = int(value(prefix + key))
                            reg['scale'] = float(value(prefix + 'scale'))
                            for key in ('type', 'word_order', 'byte_order'):
                                reg[key] = value(prefix + key)
                        if value('operation') == 'test':
                            diagnostic = await api('POST', '/api/meter/test', meter)
                            diagnostic['draft'] = meter
                    if diagnostic is None:
                        await api('PUT', '/api/settings', settings)
                elif action in ('user', 'reset_user'):
                    if action == 'reset_user':
                        result = await api('POST', '/api/users/' + quote(value('id'), safe='') + '/reset', {})
                    else:
                        data = dict(full_name=value('full_name'), role=value('role'), expires_at=value('expires_at') or None, can_emergency='can_emergency' in form)
                        if value('id'):
                            data.update(active='active' in form, deleted='deleted' in form)
                            result = await api('PUT', '/api/users/' + quote(value('id'), safe=''), data)
                        else:
                            data['name'] = value('name')
                            result = await api('POST', '/api/users', data)
                elif action == 'recover':
                    await api('POST', '/api/recover-admin', dict(username='admin', password=value('password')))
                elif action == 'directory':
                    data = dict(url=value('url'), interval_s=int(value('interval_s')), enabled='enabled' in form)
                    if value('device_token'):
                        data['device_token'] = value('device_token')
                    await api('PUT', '/api/directory', data)
                elif action == 'sync':
                    result = await api('POST', '/api/directory/sync', {})
                    if not result['ok']:
                        raise UIError('Sincronização não concluída. ' + result['status']['message'], 502)
                else:
                    raise UIError('Operação desconhecida')
            if diagnostic is not None:
                return await console.render(page, 'Operação concluída.', diagnostic=diagnostic)
            response = console.finish(RedirectResponse('/ui/' + page, status_code=303))
            response.set_cookie('dmax_saved', '1', httponly=True, secure=request.url.scheme == 'https', samesite='strict', max_age=60)
            return response
        except UIError as exc:
            if exc.status == 401:
                console.user = None
            page = value('_page', 'overview')
            return await console.render(page if page in PAGES else 'overview', exc.message, status=exc.status,
                                        recovery_data={} if value('_action').startswith('recovery_') else None)
        except (ValueError, UnicodeDecodeError, OverflowError):
            return await console.render('overview', 'Confira os valores do formulário.', status=422)

    app.add_api_route('/ui-data/{page}', live_data, methods=['GET'])
    app.add_api_route('/', get_page, methods=['GET'], response_class=HTMLResponse)
    app.add_api_route('/ui/{page}', get_page, methods=['GET'], response_class=HTMLResponse)
    app.add_api_route('/ui/post', post, methods=['POST'], response_class=HTMLResponse)


def iso_expiry(value):
    if value is None:
        return ''
    from datetime import datetime, timezone
    return datetime.fromtimestamp(value, timezone.utc).isoformat()
