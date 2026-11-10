"""Control the bundled MicroSIP process using its documented commands."""
from pathlib import Path
import subprocess

from dialing import destination, dtmf


class MicroSipBackend:
    supports_accounts = False

    def __init__(self, root):
        self.root = Path(root)
        self.status_text = 'MicroSIP not started'

    def executable(self):
        prepared = self.root / '.release-assets' / 'MicroSIP'
        folder = (prepared if prepared.is_dir() else self.root / 'MicroSIP').resolve()
        matches = sorted(folder.glob('**/MicroSIP.exe'))
        if not matches:
            raise FileNotFoundError('MicroSIP.exe was not found in the bundled MicroSIP folder.')
        path = matches[-1].resolve()
        if not path.is_relative_to(folder):
            raise ValueError('MicroSIP executable resolves outside its bundled folder.')
        return path

    def command(self, argument=None):
        exe = self.executable()
        args = [str(exe)] + ([argument] if argument else [])
        subprocess.Popen(args, cwd=str(exe.parent), shell=False,
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

    def start(self):
        self.command('/minimized')
        self.status_text = 'MicroSIP started; call status is in MicroSIP'

    def show(self):
        self.command()

    def dial(self, value):
        self.command(destination(value))
        self.status_text = 'Dial command sent to MicroSIP'

    def answer(self):
        self.command('/answer')
        self.status_text = 'Answer command sent to MicroSIP'

    def hangup(self):
        self.command('/hangupall')
        self.status_text = 'Hang-up command sent to MicroSIP'

    def send_dtmf(self, value):
        self.command('/dtmf:' + dtmf(value))
        self.status_text = 'DTMF sent to MicroSIP'

    def poll(self):
        pass

    def close(self):
        # Never terminate another MicroSIP session or an ongoing call on UI close.
        pass
