"""Build the Qt UI without overwriting the original portable release."""
from pathlib import Path
import os
import subprocess
import sys

SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parent


def build():
    from release_policy import PYTHON_VERSION
    if '.'.join(map(str, sys.version_info[:3])) != PYTHON_VERSION:
        raise SystemExit(f'Qt release builds require Python {PYTHON_VERSION}. Use .qt-venv.')
    import PySide6
    import shiboken6
    # Do not collect foreign ICU/VC runtime DLLs from developer-tool PATHs.
    # Qt links Windows' unversioned ICU API; Poppler's same-named ICU uses
    # versioned exports and makes frozen QtCore fail with WinError 127.
    environment = os.environ.copy()
    windows = Path(os.environ.get('WINDIR', 'C:/Windows'))
    environment['PATH'] = os.pathsep.join(map(str, (
        windows / 'System32', windows, Path(sys.executable).parent,
        Path(sys.base_prefix), Path(PySide6.__file__).parent,
        Path(shiboken6.__file__).parent)))
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--windowed', '--onedir', '--name', 'Offsec Call Client Qt',
        '--contents-directory', '_qt_internal', '--distpath', str(SOURCE / 'dist'),
        '--workpath', str(SOURCE / 'build'), '--specpath', str(SOURCE),
        '--add-binary', str(ROOT / '_qt_internal' / 'ffmpeg' / 'bin' / 'ffmpeg.exe') + ';ffmpeg/bin',
        '--exclude-module', 'tkinter', '--exclude-module', 'PySide6.QtQml',
        '--exclude-module', 'PySide6.QtQuick', '--exclude-module', 'PySide6.QtNetwork',
        str(SOURCE / 'qt_app.py')], check=True, cwd=SOURCE, env=environment)


if __name__ == '__main__':
    build()
