# Third-party notices

This local distribution retains upstream software names and license notices.
Application source, tests and build instructions are provided in `qt-client/`
and `DEVELOPMENT.md`. This file does not assign a license to the application itself.

- **Qt / PySide6-Essentials / shiboken6 6.12.0:** LGPL-3.0-only OR GPL-2.0-only
  OR GPL-3.0-only, as recorded in the wheel metadata. Libraries are dynamically
  loaded from `_qt_internal/`. Available license files and metadata are in
  `licenses/qt/`. Upstream: https://code.qt.io/ and https://www.qt.io/.
- **MicroSIP 3.22.23:** GPL v2. Its vendor license is in the MicroSIP folder.
  Upstream and source: https://www.microsip.org/ and https://www.microsip.org/source.
- **Python 3.14.10, NumPy 2.5.4, sounddevice 0.5.6 / PortAudio, CFFI,
  pycparser, FFmpeg 9.0.2 and PyInstaller:** retain their respective upstream
  terms. Available package notices and metadata are in `licenses/` and the
  bundled runtime. FFmpeg upstream: https://ffmpeg.org/; vendor build:
  https://www.gyan.dev/ffmpeg/builds/.
- **VB-CABLE Driver Pack45:** donationware by VB-Audio / Vincent Burel.
  The complete vendor package is retained in `VB-CABLE/`; see its `readme.txt`
  for terms and installation. Upstream: https://vb-audio.com/Cable/index.htm.

The included binaries are local build artifacts. Redistribution must meet the
applicable third-party terms, including supplying matching upstream sources and
build materials where required. Links and application source alone do not replace
the corresponding-source requirements for bundled Qt, MicroSIP or FFmpeg binaries.
