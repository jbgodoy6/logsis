"""systemd notifications, tied to controller progress rather than HTTP availability."""
import asyncio
import os
import socket
import time


class Notifier:
    def __init__(self, address, timeout):
        self.address = '\0' + address[1:] if address.startswith('@') else address
        self.timeout = timeout

    @classmethod
    def from_environment(cls):
        address = os.getenv('NOTIFY_SOCKET', '')
        if not address.startswith(('/', '@')) or not hasattr(socket, 'AF_UNIX'):
            return None
        try:
            pid = int(os.getenv('WATCHDOG_PID', str(os.getpid())))
            timeout = int(os.getenv('WATCHDOG_USEC', '0')) / 1_000_000
            if pid != os.getpid() or timeout < 0:
                return None
        except ValueError:
            return None
        return cls(address, timeout)

    def send(self, message):
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as channel:
                channel.setblocking(False)
                channel.sendto(message.encode(), self.address)
            return True
        except OSError:
            # Never block control waiting on the service manager. Missing heartbeats
            # will make systemd enforce its configured timeout.
            return False


def controller_healthy(engine, tasks, timeout, now=None):
    now = time.monotonic() if now is None else now
    return (not engine.fault and all(not task.done() for task in tasks)
            and 0 <= now - engine.control_progress_at <= min(90, timeout * .75))


async def supervise(engine, tasks, notifier):
    notifier.send('READY=1\nSTATUS=D-Max iniciado; controle OCPP e Modbus ativo')
    if not notifier.timeout:
        return
    while True:
        if controller_healthy(engine, tasks, notifier.timeout):
            notifier.send('WATCHDOG=1')
        else:
            notifier.send('STATUS=Controle sem progresso ou tarefa encerrada; aguardando reinício pelo watchdog')
        await asyncio.sleep(max(.05, notifier.timeout / 3))
