# OffSec Calltool

A Windows x64 desktop soundboard for playing audio into MicroSIP calls using
VB-Audio Virtual Cable. Built with Python and PySide6 / Qt.

Extract the complete folder to a writable location, then double-click
**Offsec Call Client Qt.exe**. Python does not need to be installed. Keep
`_qt_internal`, `MicroSIP`, and `VB-CABLE` beside the executable.

See [MANUAL.md](MANUAL.md) for driver installation, MicroSIP microphone setup,
audio imports, playback and saved soundboards. See [DEVELOPMENT.md](DEVELOPMENT.md)
for building from source and uploading to GitHub.

This distribution starts with an empty library and no saved soundboards or SIP
accounts. MicroSIP's original notification/ringing sounds are retained; these are
vendor runtime assets, not user soundboard clips.

The app creates `settings.json`, `qt-layout.json`, and `media/` when used. These
contain personal library data and are excluded by `.gitignore`. Back them up
together if you want to retain your library. MicroSIP accounts and call history
are stored separately in its directory and are also excluded from Git.

The executable uses Python 3.14.10, Qt/PySide6 6.12.0, NumPy 2.5.4 and
sounddevice 0.5.6. Third-party terms are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
and `licenses/`. No project-wide license is granted by these third-party notices.
