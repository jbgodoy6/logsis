from __future__ import annotations

from datetime import datetime
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, font, messagebox, ttk
import traceback

from . import __version__
from .core import Project, RESOURCES, atomic_write, integer, number, safe_text, safe_value
from .transport import decode, read_rtu, read_tcp, request_parameters

BG, PANEL, SIDE, INPUT = '#0b111b', '#111c2a', '#080e17', '#172535'
INK, MUTED, CYAN, GREEN, GOLD, RED, BORDER = '#edf3fa', '#91a4ba', '#65d5e6', '#63d4ad', '#e9bd79', '#fa8d92', '#25364a'


class ScrollFrame(ttk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        scrollbar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.inner = ttk.Frame(self.canvas)
        window = self.canvas.create_window((0, 0), window=self.inner, anchor='nw')
        self.inner.bind('<Configure>', lambda _: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(window, width=e.width))
        # Only this frame handles wheel events; other scrollable areas stay independent.
        self.canvas.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(-int(e.delta / 120), 'units'))
        self.canvas.bind('<Button-4>', lambda _: self.canvas.yview_scroll(-1, 'units'))
        self.canvas.bind('<Button-5>', lambda _: self.canvas.yview_scroll(1, 'units'))


class Studio(tk.Tk):
    page_names = ['Visão geral', 'Mapa de variáveis', 'Equipamento & rede', 'Teste Modbus', 'Validar & exportar']

    def __init__(self):
        super().__init__()
        self.title('LogSis Studio 7 • DSE7420 / DSE8610')
        width, height = min(1460, self.winfo_screenwidth() - 70), min(920, self.winfo_screenheight() - 70)
        self.geometry(f'{width}x{height}')
        self.minsize(1120, 720)
        self.configure(bg=BG)
        self.project = Project.new()
        self.dirty = False
        self.current = 0
        self.syncing = False
        self.busy = False
        self.closing = False
        self.results = queue.Queue()
        families = {name.casefold() for name in font.families(self)}
        self.family = next((name for name in ['Segoe UI', 'Inter', 'DejaVu Sans', 'Noto Sans', 'Helvetica', 'Arial'] if name.casefold() in families), 'Helvetica')
        self.mono = next((name for name in ['Cascadia Mono', 'DejaVu Sans Mono', 'Courier New', 'Courier'] if name.casefold() in families), 'Courier')
        self.styles()
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.build()
        self.sync_project()
        self.show_page(0)
        self.after(100, self.poll_results)
        self.bind('<Control-o>', lambda _: self.open_bin())
        self.bind('<Control-s>', lambda _: self.save_bin())
        self.bind_all('<MouseWheel>', self.route_wheel, add='+')
        self.bind_all('<Button-4>', self.route_wheel, add='+')
        self.bind_all('<Button-5>', self.route_wheel, add='+')

    def route_wheel(self, event):
        widget = event.widget
        if isinstance(widget, (tk.Text, ttk.Treeview)):
            return None
        while widget is not None:
            if isinstance(widget, ScrollFrame):
                amount = -1 if getattr(event, 'num', None) == 4 else 1 if getattr(event, 'num', None) == 5 else -int(event.delta / 120)
                widget.canvas.yview_scroll(amount, 'units')
                return 'break'
            widget = getattr(widget, 'master', None)
        return None

    def styles(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', font=(self.family, 10), background=BG, foreground=INK)
        for name, background in [('TFrame', BG), ('Card.TFrame', PANEL), ('Side.TFrame', SIDE)]:
            style.configure(name, background=background)
        style.configure('TLabel', background=BG, foreground=INK)
        style.configure('Muted.TLabel', foreground=MUTED)
        style.configure('Card.TLabel', background=PANEL)
        style.configure('CardMuted.TLabel', background=PANEL, foreground=MUTED)
        style.configure('Title.TLabel', font=(self.family, 25, 'bold'))
        style.configure('Heading.TLabel', font=(self.family, 13, 'bold'))
        style.configure('TButton', background=INPUT, foreground=INK, borderwidth=0, padding=(14, 10), focuscolor=CYAN)
        style.map('TButton', background=[('active', '#263d54'), ('disabled', '#15202c')], foreground=[('disabled', '#63768a')])
        style.configure('Primary.TButton', background=CYAN, foreground=SIDE, font=(self.family, 10, 'bold'))
        style.map('Primary.TButton', background=[('active', '#9fe9f3'), ('disabled', '#23444c')], foreground=[('disabled', MUTED)])
        style.configure('Nav.TButton', background=SIDE, foreground=MUTED, anchor='w', padding=(18, 14), font=(self.family, 10))
        style.map('Nav.TButton', background=[('active', '#132332')])
        style.configure('Active.Nav.TButton', background='#143040', foreground=CYAN)
        style.configure('Model.TButton', padding=(14, 8), font=(self.family, 10, 'bold'))
        style.configure('Selected.Model.TButton', background='#214459', foreground=CYAN, padding=(14, 8))
        style.configure('TEntry', fieldbackground=INPUT, foreground=INK, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, insertcolor=INK, padding=8)
        style.map('TEntry', fieldbackground=[('readonly', '#14202e')], foreground=[('readonly', MUTED)])
        style.configure('TCombobox', fieldbackground=INPUT, background=INPUT, foreground=INK, arrowcolor=MUTED, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, padding=7)
        style.map('TCombobox', fieldbackground=[('readonly', INPUT)], foreground=[('readonly', INK)], selectbackground=[('readonly', INPUT)], selectforeground=[('readonly', INK)])
        self.option_add('*TCombobox*Listbox.background', INPUT)
        self.option_add('*TCombobox*Listbox.foreground', INK)
        self.option_add('*TCombobox*Listbox.selectBackground', '#225167')
        style.configure('Treeview', background=PANEL, fieldbackground=PANEL, foreground=INK, rowheight=36, borderwidth=0, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
        style.configure('Treeview.Heading', background='#1a2b3c', foreground=MUTED, borderwidth=0, font=(self.family, 9, 'bold'), padding=(8, 10))
        style.map('Treeview', background=[('selected', '#21475b')], foreground=[('selected', INK)])
        style.configure('TScrollbar', background='#30465d', troughcolor=BG, borderwidth=0, arrowcolor=MUTED)
        for scrollbar in ['Vertical.TScrollbar', 'Horizontal.TScrollbar']:
            style.configure(scrollbar, background='#30465d', troughcolor=BG, bordercolor=BG, lightcolor='#30465d', darkcolor='#30465d', arrowcolor=MUTED, gripcount=0)
            style.map(scrollbar, background=[('active', '#496c8b'), ('!active', '#30465d')])
        style.configure('TSeparator', background=BORDER)
        style.configure('TCheckbutton', background=BG, foreground=INK, indicatorbackground=INPUT)
        icon = tk.PhotoImage(width=32, height=32)
        icon.put(SIDE, to=(0, 0, 32, 32)); icon.put(CYAN, to=(7, 6, 12, 25)); icon.put(CYAN, to=(7, 20, 25, 25))
        self.iconphoto(True, icon)
        self._icon = icon

    def label(self, parent, text='', size=10, colour=INK, background=BG, bold=False, **kw):
        return tk.Label(parent, text=text, fg=colour, bg=background, font=(self.family, size, 'bold' if bold else 'normal'), anchor='w', **kw)

    def card(self, parent, **kw):
        return tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, **kw)

    def tracked(self, value=''):
        var = tk.StringVar(self, value=value)
        var.trace_add('write', self.mark_dirty)
        return var

    def mark_dirty(self, *_):
        if not self.syncing:
            self.dirty = True
            if hasattr(self, 'file_status'):
                self.file_status.set('Alterações não salvas')

    def build(self):
        sidebar = tk.Frame(self, bg=SIDE, width=218)
        sidebar.pack(side='left', fill='y'); sidebar.pack_propagate(False)
        self.label(sidebar, 'L /', 30, CYAN, SIDE, True).pack(anchor='w', padx=22, pady=(26, 2))
        self.label(sidebar, 'LOGSIS', 22, INK, SIDE, True).pack(anchor='w', padx=22)
        self.label(sidebar, 'S T U D I O   /   7', 10, MUTED, SIDE).pack(anchor='w', padx=23, pady=(3, 28))
        self.label(sidebar, 'ESPAÇO DE TRABALHO', 8, MUTED, SIDE, True).pack(anchor='w', padx=22, pady=(10, 12))
        self.nav = []
        for i, title in enumerate(self.page_names):
            button = ttk.Button(sidebar, text=f'{i + 1:02}   {title}', style='Nav.TButton', command=lambda n=i: self.show_page(n))
            button.pack(fill='x', padx=10, pady=3)
            self.nav.append(button)
        footer = tk.Frame(sidebar, bg=SIDE)
        footer.pack(side='bottom', fill='x', padx=22, pady=23)
        self.label(footer, 'BIN + GRAFANA', 10, GREEN, SIDE, True).pack(anchor='w')
        self.label(footer, 'Dois lados. O mesmo mapa.', 9, MUTED, SIDE).pack(anchor='w', pady=(6, 12))
        self.label(footer, 'DSE7420  /  DSE8610', 9, MUTED, SIDE).pack(anchor='w')
        self.label(footer, f'Versão {__version__}', 8, MUTED, SIDE).pack(anchor='w', pady=(5, 0))
        host = ttk.Frame(self, padding=(24, 18, 24, 14)); host.pack(side='left', fill='both', expand=True)
        top = ttk.Frame(host); top.pack(fill='x', pady=(0, 16))
        self.label(top, 'ENGENHARIA  /  CONFIGURAÇÃO', 9, MUTED).pack(side='left')
        self.model_buttons = {}
        for model in ['DSE8610', 'DSE7420']:
            button = ttk.Button(top, text=model, style='Model.TButton', command=lambda m=model: self.switch_model(m))
            button.pack(side='right', padx=(8, 0)); self.model_buttons[model] = button
        titlebar = ttk.Frame(host); titlebar.pack(fill='x', pady=(0, 18))
        left = ttk.Frame(titlebar); left.pack(side='left', fill='x', expand=True)
        self.page_title = tk.StringVar()
        ttk.Label(left, textvariable=self.page_title, style='Title.TLabel').pack(anchor='w')
        self.file_status = tk.StringVar(value='Novo projeto')
        ttk.Label(left, textvariable=self.file_status, style='Muted.TLabel').pack(anchor='w', pady=(6, 0))
        ttk.Button(titlebar, text='Abrir BIN', command=self.open_bin).pack(side='left', padx=5)
        ttk.Button(titlebar, text='Salvar BIN', command=self.save_bin).pack(side='left', padx=5)
        ttk.Button(titlebar, text='Exportar pacote', style='Primary.TButton', command=lambda: self.show_page(4)).pack(side='left', padx=(5, 0))
        self.body = ttk.Frame(host); self.body.pack(fill='both', expand=True)
        self.body.rowconfigure(0, weight=1); self.body.columnconfigure(0, weight=1)
        self.pages = [ttk.Frame(self.body) for _ in self.page_names]
        for page in self.pages: page.grid(row=0, column=0, sticky='nsew')
        self.build_overview(); self.build_map(); self.build_settings(); self.build_test(); self.build_export()
        bottom = ttk.Frame(host); bottom.pack(fill='x', pady=(12, 0))
        self.status = tk.StringVar(value='Pronto')
        ttk.Label(bottom, textvariable=self.status, style='Muted.TLabel').pack(side='left')
        self.compat_status = tk.StringVar()
        tk.Label(bottom, textvariable=self.compat_status, bg=BG, fg=GREEN, font=(self.family, 9)).pack(side='right')

    def build_overview(self):
        scroll = ScrollFrame(self.pages[0]); scroll.pack(fill='both', expand=True)
        page = scroll.inner
        self.overview_model = tk.StringVar()
        self.overview_subtitle = tk.StringVar()
        hero = self.card(page); hero.pack(fill='x', pady=(0, 16))
        self.label(hero, 'PERFIL DE ENGENHARIA', 9, CYAN, PANEL, True).pack(anchor='w', padx=22, pady=(22, 7))
        tk.Label(hero, textvariable=self.overview_model, font=(self.family, 31, 'bold'), bg=PANEL, fg=INK).pack(anchor='w', padx=20)
        tk.Label(hero, textvariable=self.overview_subtitle, font=(self.family, 11), bg=PANEL, fg=MUTED).pack(anchor='w', padx=22, pady=(5, 19))
        buttons = tk.Frame(hero, bg=PANEL); buttons.pack(fill='x', padx=22, pady=(0, 22))
        ttk.Button(buttons, text='Aplicar perfil completo', style='Primary.TButton', command=self.apply_profile).pack(side='left')
        ttk.Button(buttons, text='Conferir variáveis', command=lambda: self.show_page(1)).pack(side='left', padx=10)
        grid = ttk.Frame(page); grid.pack(fill='x', pady=(0, 16))
        self.metrics = []
        for i, title in enumerate(['CANAIS DO PERFIL', 'COMPATIBILIDADE', 'GRAFANA DE REFERÊNCIA', 'POSIÇÕES FIXAS']):
            grid.columnconfigure(i, weight=1)
            card = self.card(grid); card.grid(row=0, column=i, sticky='nsew', padx=(0 if i == 0 else 6, 0 if i == 3 else 6))
            self.label(card, title, 8, MUTED, PANEL, True).pack(anchor='w', padx=16, pady=(15, 9))
            value = self.label(card, '', 22, CYAN if i == 0 else INK, PANEL, True); value.pack(anchor='w', padx=16, pady=(0, 16)); self.metrics.append(value)
        flow = self.card(page); flow.pack(fill='both', expand=True)
        self.label(flow, 'A configuração acompanha a sua planta.', 14, INK, PANEL, True).pack(anchor='w', padx=22, pady=(19, 5))
        self.label(flow, 'Ordem, endereços e bits definidos pelo perfil do controlador.', 10, MUTED, PANEL).pack(anchor='w', padx=22)
        self.topology = tk.Canvas(flow, bg=PANEL, height=130, highlightthickness=0)
        self.topology.pack(fill='x', padx=20, pady=12)
        self.topology.bind('<Configure>', lambda _: self.draw_topology())
        self.flow_note = tk.StringVar()
        tk.Label(flow, textvariable=self.flow_note, bg=PANEL, fg=MUTED, font=(self.family, 9), wraplength=850, justify='left', anchor='w').pack(anchor='w', padx=22, pady=(0, 16))

    def draw_topology(self):
        canvas = self.topology
        canvas.delete('all')
        width = max(canvas.winfo_width(), 500)
        items = [('Fontes', 'Rede + Gerador'), ('Transferência', 'K1 / K2'), ('Instalação', 'Carga')]
        if self.project.profile.model == 'DSE8610': items = [('Fonte', 'Gerador'), ('Acoplamento', 'MDB52 / GCB'), ('Instalação', 'BUS + Carga')]
        gap = 36; cardw = (width - gap * 2 - 4) / 3
        for i, (caption, value) in enumerate(items):
            x = 2 + i * (cardw + gap)
            canvas.create_rectangle(x, 15, x + cardw, 109, fill=INPUT, outline=BORDER)
            canvas.create_text(x + 15, 39, text=f'0{i + 1}  /  {caption.upper()}', anchor='w', fill=MUTED, font=(self.family, 8))
            canvas.create_text(x + 15, 75, text=value, anchor='w', fill=CYAN if i == 1 else INK, font=(self.family, 13, 'bold'))
            if i < 2: canvas.create_line(x + cardw, 63, x + cardw + gap - 6, 63, fill=CYAN, width=2, arrow='last')

    def build_map(self):
        page = self.pages[1]
        toolbar = ttk.Frame(page); toolbar.pack(fill='x', pady=(0, 12))
        self.search = tk.StringVar()
        self.search.trace_add('write', lambda *_: self.refresh_map())
        ttk.Entry(toolbar, textvariable=self.search, width=29).pack(side='left')
        self.label(toolbar, '  Buscar medição, canal ou endereço', 9, MUTED).pack(side='left')
        self.group_filter = tk.StringVar(value='Todos os grupos')
        self.group_box = ttk.Combobox(toolbar, textvariable=self.group_filter, state='readonly', width=18)
        self.group_box.pack(side='right'); self.group_box.bind('<<ComboboxSelected>>', lambda _: self.refresh_map())
        content = ttk.Frame(page); content.pack(fill='both', expand=True)
        content.columnconfigure(0, weight=1); content.rowconfigure(0, weight=1)
        table = self.card(content); table.grid(row=0, column=0, sticky='nsew', padx=(0, 14))
        table.rowconfigure(0, weight=1); table.columnconfigure(0, weight=1)
        columns = ('channel', 'name', 'group', 'address', 'function', 'scale', 'state')
        self.tree = ttk.Treeview(table, columns=columns, show='headings', selectmode='browse')
        for key, title, width in zip(columns, ['CANAL', 'MEDIÇÃO', 'GRUPO', 'ENDEREÇO', 'FNC', 'GRAFANA', 'MAPA'], [76, 236, 104, 88, 58, 90, 76]):
            self.tree.heading(key, text=title, anchor='w'); self.tree.column(key, width=width, minwidth=width, stretch=key == 'name', anchor='w')
        self.tree.grid(row=0, column=0, sticky='nsew')
        y = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview); y.grid(row=0, column=1, sticky='ns')
        x = ttk.Scrollbar(table, orient='horizontal', command=self.tree.xview); x.grid(row=1, column=0, sticky='ew')
        self.tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.tree.tag_configure('odd', background='#142130'); self.tree.tag_configure('error', foreground=RED)
        self.tree.bind('<<TreeviewSelect>>', self.select_channel)
        detail = tk.Frame(content, bg=BG, width=298); detail.grid(row=0, column=1, sticky='ns'); detail.grid_propagate(False)
        scroll = ScrollFrame(detail); scroll.pack(fill='both', expand=True); inner = scroll.inner
        self.detail_title = tk.StringVar(); self.detail_info = tk.StringVar()
        tk.Label(inner, textvariable=self.detail_title, bg=BG, fg=CYAN, font=(self.family, 21, 'bold'), anchor='w').pack(fill='x', pady=(1, 5))
        tk.Label(inner, textvariable=self.detail_info, bg=BG, fg=MUTED, font=(self.family, 9), justify='left', wraplength=265, anchor='w').pack(fill='x', pady=(0, 16))
        self.editor = {}
        for key, caption in [('DM', 'Nome / descrição no Grafana'), ('DH', 'Texto acima de TH'), ('DL', 'Texto abaixo de TL'), ('TL', 'Limite inferior · contagem bruta'), ('TH', 'Limite superior · contagem bruta')]:
            self.label(inner, caption, 9, MUTED).pack(anchor='w', pady=(7, 4))
            self.editor[key] = tk.StringVar(); ttk.Entry(inner, textvariable=self.editor[key]).pack(fill='x', padx=(0, 4))
        advanced = ttk.Frame(inner); advanced.pack(fill='x', pady=(12, 0))
        for i, key in enumerate(['H', 'VR', 'SM']):
            advanced.columnconfigure(i, weight=1)
            self.label(advanced, key, 8, MUTED).grid(row=0, column=i, sticky='w', padx=(0, 6))
            self.editor[key] = tk.StringVar(); ttk.Entry(advanced, textvariable=self.editor[key], width=6).grid(row=1, column=i, sticky='ew', padx=(0, 6), pady=4)
        self.label(inner, 'H, VR e SM são parâmetros do LogSis.\nO divisor do Grafana é mostrado no mapa.', 8, MUTED, justify='left').pack(anchor='w', pady=(8, 14))
        ttk.Button(inner, text='Aplicar edição', style='Primary.TButton', command=lambda: self.commit_editor(True)).pack(fill='x', padx=(0, 4), pady=4)
        ttk.Button(inner, text='Testar leitura deste canal', command=self.test_current_channel).pack(fill='x', padx=(0, 4), pady=4)
        self.detail_problem = tk.StringVar()
        tk.Label(inner, textvariable=self.detail_problem, bg=BG, fg=RED, wraplength=263, justify='left', anchor='w', font=(self.family, 9)).pack(fill='x', pady=(10, 0))

    def build_settings(self):
        scroll = ScrollFrame(self.pages[2]); scroll.pack(fill='both', expand=True)
        page = scroll.inner
        self.general_vars = {}
        top = self.card(page); top.pack(fill='x', pady=(0, 14))
        self.label(top, 'Controlador e limites nominais', 14, INK, PANEL, True).pack(anchor='w', padx=20, pady=(18, 8))
        self.label(top, 'Os limites são calculados em contagens brutas. As escalas do Grafana permanecem fixas.', 9, MUTED, PANEL).pack(anchor='w', padx=20)
        grid = tk.Frame(top, bg=PANEL); grid.pack(fill='x', padx=20, pady=(14, 18))
        self.slave_var = self.tracked('10'); self.nominal_vars = {}
        entries = [('Slave ID', self.slave_var)]
        for key, label, value in [('voltage', 'Tensão L–L · V', '380'), ('frequency', 'Frequência · Hz', '60'), ('battery', 'Bateria · V', '24'), ('rpm', 'Rotação · rpm', '1800')]:
            self.nominal_vars[key] = self.tracked(value); entries.append((label, self.nominal_vars[key]))
        for i, (label, variable) in enumerate(entries):
            grid.columnconfigure(i, weight=1)
            self.label(grid, label, 9, MUTED, PANEL).grid(row=0, column=i, sticky='w', padx=(0, 12))
            ttk.Entry(grid, textvariable=variable, width=10).grid(row=1, column=i, sticky='ew', padx=(0, 12), pady=7)
        ttk.Button(top, text='Recalcular limites e reaplicar perfil', command=self.apply_profile).pack(anchor='w', padx=20, pady=(0, 18))
        for title, fields in [
            ('Comunicação Modbus', [('MDB_BAUD', 'Velocidade · baud'), ('MDB_TOUT', 'Timeout'), ('MDB_R_DELAY', 'Intervalo de leitura'), ('MDB_RST_FAILURE', 'Reset em falha · 0/1')]),
            ('Identificação da planta', [('SYS_ORG', 'Organização'), ('SYS_DESC', 'Descrição da instalação')]),
            ('Wi-Fi', [('SYS_USE_WIFI', 'Usar conexão Wi-Fi'), ('WIFI_STA_SSID', 'Nome da rede · SSID'), ('WIFI_STA_PWD', 'Senha da rede'), ('WIFI_AP_PWD', 'Senha do ponto de acesso')]),
            ('Integração LogSis', [('SYS_USE_GSM', 'Usar modem GSM'), ('DASH_KEY', 'Endpoint do dashboard / broker'), ('DASH_REM_PWD', 'Senha de acesso remoto')]),
        ]:
            card = self.card(page); card.pack(fill='x', pady=(0, 14))
            self.label(card, title, 13, INK, PANEL, True).pack(anchor='w', padx=20, pady=(16, 10))
            form = tk.Frame(card, bg=PANEL); form.pack(fill='x', padx=20, pady=(0, 16)); form.columnconfigure(1, weight=1)
            for r, (key, label) in enumerate(fields):
                self.label(form, label, 9, MUTED, PANEL).grid(row=r, column=0, sticky='w', padx=(0, 20), pady=7)
                self.general_vars[key] = self.tracked()
                if key in ['SYS_USE_WIFI', 'SYS_USE_GSM']:
                    ttk.Checkbutton(form, text='Ativado', variable=self.general_vars[key], onvalue='1', offvalue='0').grid(row=r, column=1, sticky='w', pady=5)
                else:
                    ttk.Entry(form, textvariable=self.general_vars[key], show='•' if 'PWD' in key else '').grid(row=r, column=1, sticky='ew', pady=5)
        self.label(page, 'Ao abrir um BIN, os demais parâmetros são preservados. O Studio não envia a configuração ao equipamento.', 9, MUTED).pack(anchor='w', pady=(0, 14))

    def build_test(self):
        scroll = ScrollFrame(self.pages[3]); scroll.pack(fill='both', expand=True)
        page = scroll.inner
        card = self.card(page); card.pack(fill='x', pady=(0, 14))
        self.label(card, 'Teste de leitura', 15, INK, PANEL, True).pack(anchor='w', padx=20, pady=(18, 5))
        self.label(card, 'Leia um canal e confira registradores, bits e a conversão usada pelo Grafana.', 10, MUTED, PANEL).pack(anchor='w', padx=20)
        form = tk.Frame(card, bg=PANEL); form.pack(fill='x', padx=20, pady=(16, 18))
        self.test_channel = tk.StringVar(); self.test_protocol = tk.StringVar(value='TCP / Ethernet')
        self.test_channel_box = ttk.Combobox(form, textvariable=self.test_channel, state='readonly', width=44)
        self.test_channel_box.grid(row=0, column=0, sticky='ew', padx=(0, 12)); form.columnconfigure(0, weight=1)
        ttk.Combobox(form, textvariable=self.test_protocol, values=['TCP / Ethernet', 'RS485 / USB'], state='readonly', width=20).grid(row=0, column=1, sticky='ew')
        self.test_host = tk.StringVar(value=''); self.test_port = tk.StringVar(value='502')
        self.serial_port = tk.StringVar(value=''); self.serial_baud = tk.StringVar(value='19200'); self.serial_parity = tk.StringVar(value='N'); self.serial_stop = tk.StringVar(value='1'); self.word_order = tk.StringVar(value='High → Low')
        grid = tk.Frame(card, bg=PANEL); grid.pack(fill='x', padx=20, pady=(0, 18))
        for i, (label, variable, width) in enumerate([('IP / hostname TCP', self.test_host, 23), ('Porta TCP', self.test_port, 7), ('Porta serial', self.serial_port, 14), ('Baud', self.serial_baud, 9), ('Paridade', self.serial_parity, 6), ('Stop', self.serial_stop, 4)]):
            self.label(grid, label, 8, MUTED, PANEL).grid(row=0, column=i, sticky='w', padx=(0, 10))
            ttk.Entry(grid, textvariable=variable, width=width).grid(row=1, column=i, sticky='ew', padx=(0, 10), pady=7)
        footer = tk.Frame(card, bg=PANEL); footer.pack(fill='x', padx=20, pady=(0, 18))
        ttk.Combobox(footer, textvariable=self.word_order, values=['High → Low', 'Low → High'], state='readonly', width=16).pack(side='left')
        self.label(footer, '  Ordem de palavras no teste local', 9, MUTED, PANEL).pack(side='left')
        self.test_button = ttk.Button(footer, text='Executar leitura', style='Primary.TButton', command=self.start_test); self.test_button.pack(side='right')
        result = self.card(page); result.pack(fill='x', pady=(0, 14))
        self.label(result, 'RESULTADO DA ÚLTIMA LEITURA', 9, MUTED, PANEL, True).pack(anchor='w', padx=20, pady=(16, 5))
        self.reading_value = tk.StringVar(value='—')
        tk.Label(result, textvariable=self.reading_value, font=(self.family, 27, 'bold'), bg=PANEL, fg=CYAN).pack(anchor='w', padx=19, pady=(0, 6))
        self.reading_detail = tk.StringVar(value='Nenhum teste executado.')
        tk.Label(result, textvariable=self.reading_detail, font=(self.family, 9), bg=PANEL, fg=MUTED, anchor='w').pack(fill='x', padx=20, pady=(0, 16))
        self.log = tk.Text(page, bg=SIDE, fg=MUTED, insertbackground=INK, borderwidth=0, highlightbackground=BORDER, highlightthickness=1, font=(self.mono, 10), padx=16, pady=14, wrap='word', height=8, state='disabled')
        self.log.pack(fill='both', expand=True)

    def build_export(self):
        footer = ttk.Frame(self.pages[4], padding=(0, 12, 0, 0)); footer.pack(side='bottom', fill='x')
        self.label(footer, 'BIN + JSON do Grafana + mapa + relatório', 9, MUTED).pack(side='left')
        self.export_button = ttk.Button(footer, text='Exportar BIN + Grafana', style='Primary.TButton', command=self.export_bundle)
        self.export_button.pack(side='right')
        scroll = ScrollFrame(self.pages[4]); scroll.pack(fill='both', expand=True)
        page = scroll.inner
        self.audit_card = self.card(page); self.audit_card.pack(fill='x', pady=(0, 14))
        self.audit_heading = tk.StringVar(); self.audit_summary = tk.StringVar()
        tk.Label(self.audit_card, textvariable=self.audit_heading, bg=PANEL, fg=GREEN, font=(self.family, 15, 'bold'), anchor='w').pack(fill='x', padx=20, pady=(17, 8))
        tk.Label(self.audit_card, textvariable=self.audit_summary, bg=PANEL, fg=MUTED, font=(self.family, 9), anchor='w').pack(fill='x', padx=20, pady=(0, 13))
        ttk.Button(self.audit_card, text='Conferir novamente', command=self.run_validation).pack(anchor='w', padx=20, pady=(0, 17))
        layout = ttk.Frame(page); layout.pack(fill='both', expand=True)
        layout.columnconfigure(0, weight=3); layout.columnconfigure(1, weight=2); layout.rowconfigure(0, weight=1)
        form = self.card(layout); form.grid(row=0, column=0, sticky='nsew', padx=(0, 14))
        self.label(form, 'Pacote da planta', 14, INK, PANEL, True).pack(anchor='w', padx=20, pady=(18, 6))
        self.label(form, 'BIN e dashboard exportados juntos.', 10, MUTED, PANEL).pack(anchor='w', padx=20, pady=(0, 13))
        self.plant_var = self.tracked('Minha planta'); self.table_var = self.tracked(); self.datasource_var = self.tracked('zKW_ld27k'); self.uid_var = self.tracked(); self.energy_var = self.tracked('10'); self.maintenance_var = self.tracked('50')
        for label, variable in [('Nome da planta', self.plant_var), ('Tabela SQL · Id_Logsis', self.table_var), ('UID do datasource PostgreSQL', self.datasource_var), ('UID do dashboard · opcional', self.uid_var), ('Divisor de energia · bruto → kWh', self.energy_var), ('Avisar manutenção a partir de · horas', self.maintenance_var)]:
            self.label(form, label, 9, MUTED, PANEL).pack(anchor='w', padx=20, pady=(7, 4))
            ttk.Entry(form, textvariable=variable).pack(fill='x', padx=20)
        self.label(form, 'Tabela: id_planta ou public.id_planta.\nUID vazio: gera um identificador por modelo e tabela.\nPara atualizar um dashboard, informe seu UID atual.', 8, MUTED, PANEL, justify='left').pack(anchor='w', padx=20, pady=(9, 9))
        ttk.Button(form, text='Usar UID do dashboard de referência', command=self.reference_uid).pack(anchor='w', padx=20, pady=(0, 9))
        results = self.card(layout); results.grid(row=0, column=1, sticky='nsew')
        self.label(results, 'CONFERÊNCIA DO MAPA', 9, CYAN, PANEL, True).pack(anchor='w', padx=16, pady=(18, 12))
        self.audit_text = tk.Text(results, bg=PANEL, fg=MUTED, borderwidth=0, wrap='word', font=(self.family, 9), padx=16, pady=4, highlightthickness=0, state='disabled', width=32)
        self.audit_text.pack(fill='both', expand=True, pady=(0, 10))

    def show_page(self, number):
        if hasattr(self, 'general_vars') and not self.flush(): return
        self.page_title.set(self.page_names[number])
        self.pages[number].tkraise()
        for i, button in enumerate(self.nav): button.configure(style='Active.Nav.TButton' if i == number else 'Nav.TButton')
        if number == 4: self.run_validation()

    def sync_project(self):
        self.syncing = True
        p = self.project
        for key, variable in self.general_vars.items(): variable.set(p.general.get(key, ''))
        self.slave_var.set(p.slave)
        for key, variable in self.nominal_vars.items(): variable.set(p.nominal[key])
        self.energy_var.set(p.energy_divisor)
        self.maintenance_var.set(p.maintenance_alert_hours)
        self.serial_baud.set(p.general.get('MDB_BAUD', '19200'))
        self.overview_model.set(p.profile.model)
        self.overview_subtitle.set('Rede, transferência e gerador' if p.profile.model == 'DSE7420' else 'Gerador, acoplamento e barramento comum')
        self.flow_note.set('K1 usa MDB52 e K2 usa MDB53. Ambos com 0 aberto e 1 fechado.' if p.profile.model == 'DSE7420' else 'Um único gerador. O BUS é medido independentemente do estado do disjuntor MDB52.')
        self.group_filter.set('Todos os grupos')
        self.group_box.configure(values=['Todos os grupos'] + list(dict.fromkeys(c.group for c in p.profile.channels)))
        self.test_channel_box.configure(values=[f'MDB{c.number:02} · {c.name}' for c in p.profile.channels])
        self.test_channel_box.current(0)
        self.current = 0
        self.load_editor(); self.refresh_map(); self.refresh_validation(); self.draw_topology()
        for model, button in self.model_buttons.items(): button.configure(style='Selected.Model.TButton' if model == p.profile.model else 'Model.TButton')
        self.file_status.set(p.source.name if p.source else 'Novo projeto · perfil completo aplicado')
        self.syncing = False

    def flush(self):
        if not self.commit_editor(): return False
        try:
            general = {key: safe_value(var.get(), key) for key, var in self.general_vars.items()}
            if self.slave_var.get().strip() != self.project.slave:
                self.project.change_slave(self.slave_var.get())
            self.project.general.update(general)
            alert = number(self.maintenance_var.get(), 'Aviso de manutenção')
            if alert < 0: raise ValueError('O aviso de manutenção não pode ser negativo.')
            self.project.maintenance_alert_hours = str(alert)
            self.project.energy_divisor = str(number(self.energy_var.get(), 'Divisor de energia'))
            if number(self.project.energy_divisor) <= 0: raise ValueError('O divisor de energia deve ser positivo.')
            return True
        except ValueError as exc:
            messagebox.showerror('Confira os parâmetros', str(exc), parent=self)
            return False

    def refresh_map(self):
        if not hasattr(self, 'tree'): return
        selected = str(self.current)
        self.tree.delete(*self.tree.get_children())
        query = self.search.get().strip().casefold()
        group = self.group_filter.get()
        for channel in self.project.profile.channels:
            row = self.project.rows[channel.index]
            text = f'MDB{channel.number:02} {channel.column} {channel.name} {row["DM"]} {row["ADDR"]}'.casefold()
            if query and query not in text: continue
            if group != 'Todos os grupos' and channel.group != group: continue
            issues = self.project.row_issues(channel)
            scale = '÷ ' + str(self.project.channel_divisor(channel)) if channel.divisor != 1 else channel.unit
            self.tree.insert('', 'end', iid=str(channel.index), values=(f'MDB{channel.number:02}', self.project.channel_name(channel), channel.group, row['ADDR'], row['FNC'], scale, 'Revisar' if issues else 'OK'), tags=(('odd',) if channel.index % 2 else ()) + (('error',) if issues else ()))
        if self.tree.exists(selected): self.tree.selection_set(selected)

    def load_editor(self):
        if self.current >= self.project.profile.count: self.current = 0
        channel = self.project.profile.channels[self.current]
        row = self.project.rows[self.current]
        self.detail_title.set(f'MDB{channel.number:02}')
        bit = row['BIT'] if row['BIT'] != '-1' else 'nenhum'
        self.detail_info.set(f'{channel.name}\n\nSQL: {channel.column}  ·  BIN: índice {channel.index}\nEndereço: {row["ADDR"]}  ·  FNC: {row["FNC"]}\nBit: {bit}  ·  Slave ID: {row["ID"]}\nGrafana: bruto ÷ {self.project.channel_divisor(channel)} {channel.unit}')
        for key, variable in self.editor.items(): variable.set(row[key])
        self.detail_problem.set('\n'.join(self.project.row_issues(channel)))

    def commit_editor(self, show=False):
        if not hasattr(self, 'editor') or not self.editor['DM'].get() and not self.detail_title.get(): return True
        changes = {key: variable.get() for key, variable in self.editor.items()}
        if all(self.project.rows[self.current].get(key) == value for key, value in changes.items()): return True
        try:
            self.project.set_channel_metadata(self.current, changes)
            self.mark_dirty(); self.refresh_map(); self.refresh_validation()
            if show: self.status.set(f'MDB{self.current + 1:02}: edição aplicada. A ordem do perfil foi preservada.')
            return True
        except ValueError as exc:
            messagebox.showerror('Edição da variável', str(exc), parent=self)
            return False

    def select_channel(self, _=None):
        selection = self.tree.selection()
        if not selection: return
        index = int(selection[0])
        if index == self.current: return
        if not self.commit_editor():
            if self.tree.exists(str(self.current)): self.tree.selection_set(str(self.current))
            return
        self.current = index
        if self.tree.exists(str(index)): self.tree.selection_set(str(index))
        self.load_editor()

    def refresh_validation(self):
        issues = self.project.validate()
        profile = self.project.profile
        self.metrics[0].configure(text=f'{profile.count:02}')
        self.metrics[1].configure(text='Alinhado' if not issues else f'{len(issues)} ajustes', fg=GREEN if not issues else GOLD)
        self.metrics[2].configure(text=profile.dashboard_version)
        self.metrics[3].configure(text=f'01 a {profile.count:02}')
        self.compat_status.set(f'{profile.count} canais · Grafana {profile.dashboard_version} · ' + ('mapa compatível' if not issues else f'{len(issues)} divergências'))
        self.audit_heading.set('Mapa compatível com o Grafana' if not issues else f'{len(issues)} divergências para corrigir')
        self.audit_summary.set(f'{profile.model} · {profile.count} canais obrigatórios · BIN e Grafana na mesma ordem')
        self.export_button.configure(state='normal' if not issues else 'disabled')
        text = '\n\n'.join((f'MDB{i.channel:02} · ' if i.channel else '') + i.message for i in issues)
        if not text:
            text = f'✓ {profile.count} canais nas posições corretas.\n\n✓ Endereços, funções e bits conferidos.\n\n✓ Slots restantes desativados.\n\n✓ MDB40: modos completos.\n\n✓ MDB41/42/43: Warning, Trip e Shutdown.\n\n✓ ' + ('MDB52/53: K1 e K2.' if profile.model == 'DSE7420' else 'MDB52: acoplamento ao BUS.') + '\n\nO pacote inclui BIN, Grafana, mapa CSV e relatório de compatibilidade.'
        self.audit_text.configure(state='normal'); self.audit_text.delete('1.0', 'end'); self.audit_text.insert('end', text); self.audit_text.configure(state='disabled')
        return issues

    def run_validation(self):
        if self.flush():
            self.refresh_map(); self.refresh_validation()
            self.status.set('Conferência concluída. Endereços e posições foram comparados ao perfil.')

    def has_pending_changes(self):
        return self.dirty or any(variable.get() != self.project.rows[self.current].get(key) for key, variable in self.editor.items())

    def reset_export_fields(self, plant='Minha planta'):
        was_syncing = self.syncing
        self.syncing = True
        self.table_var.set(''); self.uid_var.set(''); self.plant_var.set(plant)
        self.syncing = was_syncing

    def can_discard(self):
        if self.busy:
            messagebox.showinfo('Leitura em andamento', 'Aguarde o término da leitura para trocar o projeto.', parent=self)
            return False
        return not self.has_pending_changes() or messagebox.askyesno('Alterações não salvas', 'Descartar as alterações não salvas deste projeto?', parent=self)

    def switch_model(self, model):
        if model == self.project.profile.model: return
        if not self.can_discard(): return
        self.project = Project.new(model); self.dirty = False
        self.reset_export_fields()
        self.sync_project(); self.status.set(f'Novo projeto {model}. Perfil completo aplicado.')

    def apply_profile(self):
        if not self.flush(): return
        if not messagebox.askyesno('Aplicar perfil completo', f'Regerar as 100 posições para {self.project.profile.model}?\n\nO perfil usa {self.project.profile.count} canais fixos e desativa os demais. Os textos e limites MDB serão substituídos. As configurações de comunicação serão preservadas.', parent=self): return
        try:
            self.project.nominal = {key: str(number(v.get())) for key, v in self.nominal_vars.items()}
            self.project.apply_profile(); self.mark_dirty(); self.current = 0; self.load_editor(); self.refresh_map(); self.refresh_validation()
            self.status.set('Perfil completo aplicado, sem deslocar as colunas do Grafana.')
        except ValueError as exc: messagebox.showerror('Perfil do controlador', str(exc), parent=self)

    def open_bin(self):
        if not self.can_discard(): return
        filename = filedialog.askopenfilename(parent=self, title='Abrir configuração LogSis', filetypes=[('Configuração LogSis', '*.bin'), ('Todos os arquivos', '*.*')])
        if not filename: return
        try:
            self.project = Project.open(filename, self.project.profile.model)
            self.dirty = False; self.reset_export_fields(Path(filename).stem); self.sync_project()
            self.status.set('BIN carregado. Parâmetros originais preservados; confira eventuais divergências.')
        except (OSError, ValueError) as exc: messagebox.showerror('Abrir BIN', str(exc), parent=self)

    def save_bin(self):
        if not self.flush(): return
        try:
            data = self.project.bin_bytes()
            filename = filedialog.asksaveasfilename(parent=self, title='Salvar configuração LogSis', defaultextension='.bin', initialfile=f'{self.project.profile.model}.bin', filetypes=[('Configuração LogSis', '*.bin')])
            if not filename: return
            atomic_write(filename, data)
            self.project.source = Path(filename); self.dirty = False; self.file_status.set(Path(filename).name)
            self.status.set('BIN salvo com sucesso. A sequência MDB foi validada.')
        except (OSError, ValueError) as exc:
            self.show_page(4); messagebox.showerror('Salvar BIN', str(exc), parent=self)

    def reference_uid(self):
        import json
        template = json.loads((RESOURCES / self.project.profile.dashboard).read_text(encoding='utf-8'))
        self.uid_var.set(template['uid'])

    def export_bundle(self):
        if not self.flush(): return
        try:
            data = self.project.bundle_bytes(self.table_var.get().strip(), self.plant_var.get().strip(), self.datasource_var.get().strip(), self.uid_var.get().strip())
            filename = filedialog.asksaveasfilename(parent=self, title='Exportar pacote BIN + Grafana', defaultextension='.zip', initialfile=f'{self.project.profile.model}_PLANTA.zip', filetypes=[('Pacote LogSis + Grafana', '*.zip')])
            if not filename: return
            atomic_write(filename, data)
            self.status.set(f'Pacote exportado: {Path(filename).name}')
            messagebox.showinfo('Pacote exportado', 'BIN, JSON do Grafana, mapa CSV e relatório foram exportados juntos.\n\nO UID informado permite atualizar o dashboard existente; UID automático cria uma identidade por modelo e tabela.', parent=self)
        except (OSError, ValueError) as exc:
            self.refresh_validation(); messagebox.showerror('Exportar pacote', str(exc), parent=self)

    def test_current_channel(self):
        if not self.commit_editor(): return
        self.test_channel_box.current(self.current)
        self.show_page(3)

    def start_test(self):
        if self.busy or not self.flush(): return
        try:
            index = self.test_channel_box.current()
            if index < 0: raise ValueError('Selecione uma variável para testar.')
            channel = self.project.profile.channels[index]
            row = dict(self.project.rows[index])
            request_parameters(row['ID'], row['FNC'], row['ADDR'])
            serial = self.test_protocol.get() == 'RS485 / USB'
            params = dict(port=self.serial_port.get().strip(), baud=self.serial_baud.get(), parity=self.serial_parity.get(), stopbits=self.serial_stop.get()) if serial else dict(host=self.test_host.get().strip(), port=self.test_port.get())
            params.update(slave=row['ID'], function=row['FNC'], address=row['ADDR'])
            if not serial:
                integer(params['port'], 'Porta TCP', 1, 65535)
                if not params['host']: raise ValueError('Informe o IP ou hostname para leitura TCP.')
            elif not params['port']: raise ValueError('Informe a porta serial para leitura RS485.')
            snapshot = (channel, row, self.word_order.get() == 'Low → High', self.project.energy_divisor)
        except ValueError as exc:
            messagebox.showerror('Teste de leitura', str(exc), parent=self); return
        self.busy = True; self.test_button.configure(state='disabled'); self.reading_detail.set('Aguardando resposta do equipamento…')
        threading.Thread(target=self.worker, args=(serial, params, snapshot), daemon=True).start()

    def worker(self, serial, params, snapshot):
        # No Tk calls in a worker thread; all values were captured on the UI thread.
        try:
            registers = (read_rtu if serial else read_tcp)(**params)
            channel, row, low_first, energy_divisor = snapshot
            reading = decode(channel, row, registers, low_first, energy_divisor)
            self.results.put((True, channel, reading, None))
        except Exception as exc:
            self.results.put((False, snapshot[0], None, str(exc)))

    def poll_results(self):
        if self.closing: return
        try:
            while True:
                ok, channel, reading, error = self.results.get_nowait()
                self.busy = False; self.test_button.configure(state='normal')
                stamp = datetime.now().strftime('%H:%M:%S')
                if ok:
                    value = '—' if reading.engineering is None else f'{reading.engineering:.2f} {channel.unit}'
                    self.reading_value.set(reading.state or value)
                    self.reading_detail.set(f'MDB{channel.number:02} · {channel.name} · {stamp}')
                    text = f'[{stamp}] MDB{channel.number:02} / {channel.name}\nRegistradores: {list(reading.registers)}\nUnsigned: {reading.unsigned} | Signed: {reading.signed}\n'
                    if reading.bit is not None: text += f'Bit extraído: {reading.bit}\n'
                    text += f'Grafana: {reading.state or value}\n\n'
                else:
                    self.reading_value.set('Leitura não concluída')
                    self.reading_detail.set(f'MDB{channel.number:02} · {stamp}')
                    text = f'[{stamp}] MDB{channel.number:02} / ERRO: {error}\n\n'
                self.log.configure(state='normal'); self.log.insert('end', text); self.log.see('end'); self.log.configure(state='disabled')
        except queue.Empty:
            pass
        self.after(100, self.poll_results)

    def destroy(self):
        self.closing = True
        for callback in self.tk.call('after', 'info'):
            self.after_cancel(callback)
        super().destroy()

    def close(self):
        if self.has_pending_changes() and not messagebox.askyesno('Fechar Studio', 'Há alterações não salvas. Deseja fechar mesmo assim?', parent=self): return
        self.closing = True
        self.destroy()


def main():
    try:
        import sys
        if sys.platform == 'win32':
            import ctypes
            try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except (AttributeError, OSError): pass
        Studio().mainloop()
    except Exception:
        text = traceback.format_exc()
        try: messagebox.showerror('LogSis Studio', 'Não foi possível iniciar o Studio.\n\n' + text)
        except tk.TclError: print(text)
        raise
