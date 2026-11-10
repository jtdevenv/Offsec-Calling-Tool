"""Pinned inputs for the next Windows x64 release."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / '.release-assets'
PYTHON_VERSION = '3.14.10'
PYTHON_URL = 'https://www.python.org/ftp/python/3.14.10/python-3.14.10-amd64.zip'
PYTHON_SHA256 = 'cc28026a650970cc1570bb127312f1f9634eb67abfe157ae6ca1acbbc627d091'
FFMPEG_VERSION = '9.0.2'
FFMPEG_URL = 'https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.2-essentials_build.zip'
FFMPEG_SHA256 = '60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba'
MICROSIP_VERSION = '3.22.23'
MICROSIP_URL = 'https://www.microsip.org/download/MicroSIP-3.22.23.zip'
