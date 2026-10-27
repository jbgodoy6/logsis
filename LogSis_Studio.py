# -*- coding: utf-8 -*-
"""LogSis Studio — startup diagnostics also work before Tk/package import."""
import os
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REQUIRED = (
    'logsis_studio/__init__.py', 'logsis_studio/app.py',
    'logsis_studio/core.py', 'logsis_studio/transport.py',
    'logsis_studio/manual_dashboard.py', 'logsis_studio/deif_dashboard.py',
    'logsis_studio/standard_layout.py', 'logsis_studio/codecs.py',
    'logsis_studio/resources/profiles.json', 'logsis_studio/resources/template.bin',
    'logsis_studio/resources/dse7420.json', 'logsis_studio/resources/dse8610.json',
    'logsis_studio/resources/logsis_symbol.png',
    'logsis_studio/resources/sgc420_alarms.json',
    'logsis_studio/resources/agc150_alarms.json',
)


def check_runtime():
    if sys.version_info < (3, 10):
        raise RuntimeError('Use Python 3.10 ou superior, com Tcl/Tk, para abrir o Studio.')
    missing = [name for name in REQUIRED if not (ROOT / name).is_file()]
    if missing:
        raise FileNotFoundError(
            'A pasta do Studio está incompleta. Extraia TODOS os arquivos do ZIP '
            'antes de abrir LogSis_Studio.py. Não abra diretamente dentro do ZIP.\n\n'
            'Arquivos ausentes:\n' + '\n'.join(missing)
        )


def save_diagnostic(details):
    """Write locally only; do not collect environment variables or upload logs."""
    bases = [os.environ.get('LOCALAPPDATA'), tempfile.gettempdir()]
    name = 'abertura_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.txt'
    text = (
        'LogSis Studio — diagnóstico de abertura\n'
        'Horário local: ' + datetime.now().astimezone().isoformat() + '\n'
        'Python: ' + sys.version + '\n'
        'Interpretador: ' + sys.executable + '\n'
        'Pasta do Studio: ' + str(ROOT) + '\n\n' + details
    )
    for base in bases:
        if not base:
            continue
        try:
            folder = Path(base) / 'LogSisStudio' / 'logs'
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / name
            target.write_text(text, encoding='utf-8')
            return target
        except OSError:
            continue
    return None


def show_failure(text):
    # Native Windows dialog works even if tkinter or its DLLs cannot load.
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, text, 'LogSis Studio — falha ao abrir', 0x10010)
            return
        except (AttributeError, OSError):
            pass
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        try:
            messagebox.showerror('LogSis Studio — falha ao abrir', text, parent=root)
        finally:
            root.destroy()
        return
    except Exception:
        pass
    stream = sys.stderr or sys.stdout
    if stream is not None:
        try:
            stream.write(text + '\n')
            stream.flush()
        except (OSError, UnicodeError):
            pass


def main():
    try:
        check_runtime()
        # Keep this import inside the handler: missing Tk/modules previously
        # terminated the process before app.main could show its error dialog.
        from logsis_studio.app import main as run_studio
        run_studio()
        return 0
    except Exception as exc:
        details = traceback.format_exc()
        diagnostic = save_diagnostic(details)
        help_text = ''
        if isinstance(exc, ImportError) and ('tkinter' in str(exc) or '_tkinter' in str(exc)):
            help_text = '\n\nO Python instalado precisa incluir Tcl/Tk (tkinter).'
        message = 'Não foi possível abrir o Studio.\n\n' + type(exc).__name__ + ': ' + str(exc) + help_text
        if diagnostic:
            message += '\n\nDiagnóstico salvo em:\n' + str(diagnostic)
        else:
            message += '\n\nNão foi possível gravar o diagnóstico. Copie esta mensagem.'
        show_failure(message)
        return 1

if __name__ == '__main__':
    sys.exit(main())
