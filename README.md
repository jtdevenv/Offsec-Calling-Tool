# OffSec Calltool

A Windows x64 desktop soundboard for playing audio into MicroSIP calls using
VB-Audio Virtual Cable. Built with Python and PySide6 / Qt.

## Install and run

1. Use a Windows x64 computer (tested on Windows 11), with a writable folder,
   internet access for downloading, and a SIP account for MicroSIP calls.
2. Install [Git for Windows](https://git-scm.com/downloads/win). Open a new
   PowerShell window and run `git --version` and `git lfs version`. If Git LFS
   is missing, install [Git LFS for Windows](https://git-lfs.com/) and reopen PowerShell.
3. Download the repository and its binary dependencies:

   ```powershell
   git lfs install
   git clone https://github.com/jtdevenv/Offsec-Calling-Tool.git
   cd Offsec-Calling-Tool
   git lfs pull
   git lfs fsck
   ```

   Sign in to GitHub when prompted. While this repository is private, your GitHub
   account needs access. If you already cloned it, run the last two commands
   inside your existing checkout. `git lfs fsck` should report that the files are OK.
4. Install the bundled VB-CABLE driver as administrator and restart Windows.
   Follow [the driver instructions](MANUAL.md#1-install-vb-cable).
5. Double-click **Offsec Call Client Qt.exe**. Set the app's **Output** to
   **CABLE Input**, then set MicroSIP's **Microphone** to **CABLE Output**.
   Keep MicroSIP's speaker and ring device on your headphones or speakers.

The executable includes Python, Qt, NumPy, audio libraries, FFmpeg and MicroSIP.
Running it does **not** require installing Python or running pip. Keep
`_qt_internal`, `MicroSIP`, and `VB-CABLE` beside the executable. Administrator
access is needed for the driver installer; run the app normally afterward.

If you already have a complete distribution ZIP, extract it to a writable folder
and start at step 4. Git and Git LFS are needed for cloning this repository,
not for using a complete extracted distribution. GitHub's **Code > Download ZIP**
may contain LFS pointer files; use the clone instructions to obtain the actual binaries.

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
