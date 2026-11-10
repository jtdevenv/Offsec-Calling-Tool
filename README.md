# OffSec Calltool

A Windows desktop soundboard that plays prerecorded audio into MicroSIP calls.
Organize clips in a file browser, arrange sound pads, and save boards for later.
Each active pad contains its own playback controls.

[Installation](#installation) · [Usage](#usage) · [Troubleshooting](#troubleshooting) · [User manual](MANUAL.md) · [Build from source](DEVELOPMENT.md#build-from-source)

## Features

- Drag audio files or entire directories into the library, with subfolders retained.
- Drag clips onto the board to add pads, or onto an existing pad to replace it.
- Play, pause, seek and stop inside the active pad. One clip plays at a time.
- Save named soundboards and organize presets into folders.
- Route audio to MicroSIP through VB-CABLE.
- Import managed MP3 copies while keeping the original files unchanged.

## Requirements

| Requirement | What you need to do |
| --- | --- |
| Windows x64 | Use a writable folder. This build was tested on Windows 11. |
| Git and Git LFS | Install these to download the repository's executable and binary dependencies. |
| VB-CABLE driver | Install the included driver as administrator, then restart Windows. |
| SIP account | Configure MicroSIP with your provider's account details to make calls. |
| Headphones or speakers | Use these for MicroSIP's speaker and ringing output. |

**Python, Qt/PySide6, NumPy, sounddevice, FFmpeg and MicroSIP are included.**
You do not need to install them separately or run pip to use the executable.
Internet access is needed to download the tool and connect to your SIP service.

## Installation

Follow these steps in order. Building the application from source is optional.

### 1. Install Git and Git LFS

1. Download and install [Git for Windows](https://git-scm.com/downloads/win).
   Keep Git Credential Manager enabled in the installer for GitHub sign-in.
2. Open a **new PowerShell window** and check both commands:

   ```powershell
   git --version
   git lfs version
   ```

3. If `git lfs version` says that LFS is not a Git command, install
   [Git LFS for Windows](https://git-lfs.com/), then reopen PowerShell.

Both commands should print a version number before you continue.

### 2. Download the complete application

In PowerShell, navigate to the folder where you want to keep the tool, then run:

```powershell
git lfs install
git clone https://github.com/jtdevenv/Offsec-Calling-Tool.git
cd Offsec-Calling-Tool
git lfs pull
git lfs fsck
```

Sign in to GitHub if prompted. While the repository is private, your GitHub
account must have access. Wait for the binary downloads to finish;
`git lfs fsck` should report `Git LFS fsck OK`.

**Already cloned the repository?** Open PowerShell in that folder and run
`git lfs install`, `git lfs pull`, and `git lfs fsck`.

Use these clone instructions rather than GitHub's **Code > Download ZIP**:
the ordinary source ZIP may contain LFS pointer files instead of usable binaries.
If you already received a complete distribution ZIP, extract it and continue
with step 3; Git and Git LFS are not needed for that route.

### 3. Install the VB-CABLE driver

1. Open the application's `VB-CABLE` folder in File Explorer.
2. Right-click **VBCABLE_Setup_x64.exe** and choose **Run as administrator**.
3. Approve the Windows prompt, select **Install Driver**, and wait for confirmation.
4. **Restart Windows** to complete installation.

Keep every file in the `VB-CABLE` folder together; the installer needs its
companion driver files. Administrator access is needed for driver installation.
Run the soundboard normally afterward. If VB-CABLE is already installed and
its devices are available, continue to step 4.

### 4. Start the tool and configure MicroSIP

1. Open the downloaded application folder and double-click **Offsec Call Client Qt.exe**.
   MicroSIP opens alongside the soundboard.
2. Configure your SIP account in MicroSIP with the details from your provider.
3. Open MicroSIP's menu (down-arrow/menu button), then choose **Settings**.
4. Set the audio devices as shown below, and apply/save the settings:

| Application | Setting | Select |
| --- | --- | --- |
| OffSec Calltool | **Output** at the bottom of the window | **CABLE Input (VB-Audio Virtual Cable)** |
| MicroSIP | **Microphone** | **CABLE Output (VB-Audio Virtual Cable)** |
| MicroSIP | **Speaker** and **Ring device** | Your headphones or speakers |

If the tool lists several cable outputs, try the WASAPI entry first, then MME
if needed. Windows' default audio devices do not need to change.

```text
Soundboard → CABLE Input → CABLE Output → MicroSIP microphone → Call
```

**The names are different on purpose:** the soundboard sends audio into the cable;
MicroSIP receives audio from its output. This setup does not mix your physical
microphone into the soundboard signal.

### 5. Try your first sound

1. Select **Files** in the sidebar and drag in an audio file or directory.
2. Wait for the import to finish, then drag a clip from the browser onto the board.
3. Make a test call in MicroSIP and click the pad. Confirm the other end hears it.
4. Use the controls inside the pad to pause, resume or stop. **Escape** also stops playback.

Audio routed to VB-CABLE is sent to the call. Local speaker monitoring is not
included, so you may not hear the clip through your own headphones.

## Usage

| Task | Action |
| --- | --- |
| Organize audio | Use **Files > New folder**, drag files between folders, or import a directory. |
| Add a sound pad | Drag a library clip onto blank board space. |
| Replace a pad | Drop a library clip onto that pad. A clip appears once per board. |
| Remove a pad | Right-click it and select **Remove from board**. |
| Save a soundboard | Click **Save** or press **Ctrl+S**. Name the board when prompted. |
| Save another preset | Switch the sidebar to **Soundboards**, then choose **Save as…**. |
| Load a preset | Select **Soundboards** and click its name. |
| Start an empty board | Click **New board**. |

Use MicroSIP for dialing, answering and hanging up. Closing OffSec Calltool
leaves MicroSIP and any ongoing call running. See [MANUAL.md](MANUAL.md) for details.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| `git` is not recognized | Install Git for Windows and open a new PowerShell window. |
| `git lfs` is not recognized | Install Git LFS and open a new PowerShell window. |
| Repository not found or access denied | Sign in with a GitHub account that has repository access. |
| Executable will not run after downloading | Run `git lfs pull` and `git lfs fsck` inside the repository. Keep `_qt_internal` beside the executable. |
| Cable devices are missing | Finish the driver installation, restart Windows, reopen both apps, and click **Refresh** in the tool. |
| The call cannot hear clips | Check **CABLE Input** in the tool, **CABLE Output** for MicroSIP's microphone, volume, microphone mute, and Windows microphone permissions. |
| An import fails | Use a local, unprotected file with a decodable audio track. Split very large clips into shorter files. |

## Files and saved data

Keep this layout together when moving the application:

```text
Offsec-Calling-Tool/
├── Offsec Call Client Qt.exe
├── _qt_internal/             # Python, Qt, FFmpeg and other runtime dependencies
├── MicroSIP/                 # SIP client and its runtime files
├── VB-CABLE/                 # Complete vendor driver installer package
├── licenses/                 # Third-party notices and license files
├── qt-client/                # Editable source, build script and tests
└── MANUAL.md
```

The distribution starts with no personal clips, soundboards or SIP accounts.
MicroSIP's vendor ringing and notification sounds are included.

The app creates `settings.json`, `qt-layout.json`, and `media/` as you use it.
**Back up all three together** to preserve your library and boards. MicroSIP
stores its accounts, contacts and call records in its own directory.
These personal files are excluded by `.gitignore`. Avoid running multiple
instances against the same library.

## Updating

Back up your library first. Close OffSec Calltool and MicroSIP, then open
PowerShell in the repository folder:

```powershell
git pull --ff-only
git lfs pull
git lfs fsck
```

Reopen **Offsec Call Client Qt.exe**. If Git reports local changes, resolve them
before updating; do not delete your library or account files to complete an update.

## Development

Running the packaged app does not require a development environment.
For Python setup, pinned dependencies, tests and executable builds, see
[DEVELOPMENT.md](DEVELOPMENT.md#build-from-source).

## Third-party software

This build includes Python 3.14.10, Qt/PySide6 6.12.0, NumPy 2.5.4,
sounddevice 0.5.6, FFmpeg, MicroSIP and the VB-CABLE installer.
VB-CABLE is donationware from [VB-Audio](https://vb-audio.com/Cable/index.htm).
See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and `licenses/` for upstream
terms. Those notices do not grant a project-wide application license.
