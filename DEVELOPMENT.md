# Source and GitHub upload

The `qt-client/` directory contains the Qt UI, audio/import/storage code, build
script and relevant tests. This folder excludes development environments, build
caches, legacy Tk executables, personal clips, presets, SIP accounts, contacts
and call records.

## Upload to GitHub

This is a runnable Windows distribution with source. Its bundled FFmpeg binary
exceeds GitHub's normal 100 MiB per-file limit. Install [Git LFS](https://git-lfs.com/)
before the first commit; `.gitattributes` already tracks binary files with LFS.

From this directory, after creating an empty GitHub repository:

```
git lfs install
git init
git add .
git commit -m "Initial Qt soundboard release"
git branch -M main
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
```

Cloners need Git LFS and should run `git lfs pull` after cloning. Alternatively,
publish the prepared ZIP as a GitHub Release download and keep only source,
documentation and notices in the repository. GitHub's web file uploader is not
the upload route for this complete binary directory.

Reference: [GitHub large file storage](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage).

## Build from source

First download the complete repository, including Git LFS files, using the
[README setup steps](README.md#install-and-run). The build reuses the bundled
FFmpeg binary, so source alone without its LFS files is insufficient.

Install **Python 3.14.10 x64** from the [official Windows downloads](https://www.python.org/downloads/windows/).
Use the full installer with pip and the Python launcher. Open a new PowerShell
window and run `py -3.14 --version`; it must report **Python 3.14.10**, because
the release build script checks that exact version.

The virtual environment will install these pinned application dependencies:

- PySide6-Essentials 6.12.0 and shiboken6 6.12.0 (Qt Widgets).
- NumPy 2.5.4 and sounddevice 0.5.6 (audio processing and device playback).
- Their dependencies, including CFFI, are resolved by pip.
- PyInstaller 6.22.3 is required only to build the executable.

From the repository root in PowerShell:

```powershell
py -3.14 -m venv qt-client/.qt-venv
qt-client/.qt-venv/Scripts/python.exe -m pip install -r qt-client/requirements-qt.txt pyinstaller==6.22.3
qt-client/.qt-venv/Scripts/python.exe -m pip check
qt-client/.qt-venv/Scripts/python.exe qt-client/qt_app.py
qt-client/.qt-venv/Scripts/python.exe -m unittest discover -s qt-client/tests -v
qt-client/.qt-venv/Scripts/python.exe qt-client/build_qt.py
```

Internet access is needed for pip installation. Activating the environment is
optional because these commands address its Python executable directly. The
VB-CABLE installation and MicroSIP microphone configuration in
[MANUAL.md](MANUAL.md) also apply when running from source.

Use a short checkout path or enable Windows long-path support if pip reports a
long filename error while installing Qt. Builds isolate PATH so unrelated ICU
DLLs from development tools cannot break QtCore loading. Build output is under
`qt-client/dist/Offsec Call Client Qt/`. Keep its executable and `_qt_internal/`
together with the vendor folders when assembling a release.

The executable supports `--smoke-test OUTPUT_DIRECTORY` for isolated rendering
and FFmpeg decoding checks. This creates synthetic test media under that output
directory, does not use the live library, and does not place calls. Keep those
test outputs out of a distribution.
