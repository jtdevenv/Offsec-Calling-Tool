# Quick user manual

## Before you start: prerequisites and download

- A Windows x64 computer (tested on Windows 11), headphones or speakers, and a
  writable application folder.
- Internet access for downloading and your SIP service, plus your own SIP
  provider's account credentials to configure MicroSIP.
- Administrator approval and a restart to install the VB-CABLE driver.
- For downloading from GitHub: [Git for Windows](https://git-scm.com/downloads/win)
  and [Git LFS](https://git-lfs.com/). After installing them, reopen PowerShell,
  check `git --version` and `git lfs version`, then run:

  ```powershell
  git lfs install
  git clone https://github.com/jtdevenv/Offsec-Calling-Tool.git
  cd Offsec-Calling-Tool
  git lfs pull
  git lfs fsck
  ```

  Sign in when prompted. A private repository requires access on your GitHub
  account. If the repository is already cloned, run `git lfs pull` and
  `git lfs fsck` from that folder. If Git reports that `lfs` is not a command,
  install Git LFS and open a new PowerShell window.

Python, Qt/PySide6, NumPy, sounddevice, FFmpeg and MicroSIP are already bundled
for executable users; no Python or pip installation is necessary. The VB-CABLE
driver still needs the separate installation below. Source developers should
follow [DEVELOPMENT.md](DEVELOPMENT.md#build-from-source) for Python dependencies.

For a complete distribution ZIP, extract the whole folder and proceed below;
Git and Git LFS are not needed for that route. Avoid using GitHub's ordinary
source ZIP as a replacement for `git lfs pull`: it may contain pointer files
instead of the executable and DLLs.

## 1. Install VB-CABLE

1. Extract the entire application folder. Keep all files inside `VB-CABLE/`
   together; the installer needs the companion driver files.
2. Open `VB-CABLE`, right-click **VBCABLE_Setup_x64.exe**, and choose **Run as
   administrator**. Alternatively, launch the tool and choose **Application >
   Get VB-CABLE**, then approve the Windows administrator prompt.
3. In the vendor installer, choose **Install Driver** and wait for confirmation.
4. **Restart Windows** to finish installation. Then reopen the tool.

VB-CABLE is donationware from [VB-Audio](https://vb-audio.com/Cable/index.htm).
The vendor requires administrator installation and a restart.

## 2. Configure MicroSIP and audio output

1. Double-click **Offsec Call Client Qt.exe**. MicroSIP opens alongside the soundboard. Configure your
   own SIP account in MicroSIP using the details supplied by your SIP provider.
2. In MicroSIP, open its menu (the down-arrow/menu button) and choose **Settings**.
3. Find the audio device settings. Set **Microphone** to **CABLE Output
   (VB-Audio Virtual Cable)**. This is the recording end of VB-CABLE; do not
   select your physical microphone for soundboard playback.
4. Keep **Speaker** and **Ring device** assigned to your headphones or speakers.
   Apply/save the settings.
5. In OffSec Calltool's bottom **Output** selector, choose **CABLE Input
   (VB-Audio Virtual Cable)**. Prefer a WASAPI entry if available; try MME if needed.

Audio flows as follows:

`Soundboard -> CABLE Input -> CABLE Output -> MicroSIP microphone -> call`

Windows default audio devices do not need to change. With this setup, the call
receives the soundboard output; the tool does not mix your physical microphone
into that signal. Test routing on a test call before relying on it.

Reference: [MicroSIP user guide](https://www.microsip.org/help).

## 3. Add files and play sounds

1. Select **Files** at the top of the sidebar.
2. Drag an audio directory into the file index, or choose **Browse folder…**.
   Subfolders are retained in the index. Use **New folder** to organize clips.
3. Drag audio files into the index or onto a folder. You can also right-click the
   index and choose **Import audio files…**. Imports make managed MP3 copies;
   originals are not modified. Cancel a running import with **Cancel import**.
4. Drag files from the index onto blank soundboard space to add pads. Drop onto
   an existing pad to replace it. A clip appears once per board.
5. Click a pad to play. The pad becomes a player with position, seek bar,
   **Play/Pause**, and **Stop**. Starting another pad replaces the current clip.
6. Stop or press **Escape** to restore the clip name. Finishing playback also
   restores the name. Right-click a pad to remove it from that board.

Use the bottom volume slider to adjust the soundboard output. Manage dialing,
answering and hanging up in MicroSIP. Closing OffSec Calltool leaves MicroSIP
and any ongoing call running.

## 4. Save and load soundboards

1. Arrange your pads, then click **Save** (or press **Ctrl+S**). Give a new board a name.
2. Toggle the sidebar to **Soundboards** to see your saved presets.
3. Use **New folder** to organize presets, and drag presets between folders.
4. Click a preset to load it. Use **Save** to update it, or **Save as…** in the
   Soundboards browser to create a separate preset.
5. **New board** starts an empty board. Switching with unsaved edits offers
   Save, Discard or Cancel.

## Troubleshooting

- **Cable devices missing:** finish driver installation, restart Windows, then
  reopen both apps and click **Refresh** beside the output selector.
- **The call cannot hear clips:** check both ends: OffSec Calltool must output to
  **CABLE Input**, and MicroSIP's microphone must be **CABLE Output**. Check
  soundboard volume, MicroSIP microphone mute, and Windows microphone permissions.
- **You cannot hear the clip locally:** routing to VB-CABLE sends audio to the
  call rather than your speakers. Local monitoring is not included.
- **Import fails:** try an unprotected audio file. Files with no decodable audio
  are rejected; very large decoded clips must be split into shorter files.
- **Startup fails:** extract the whole folder, including `_qt_internal`. Do not
  copy only the executable. Avoid running two copies against the same library.
- **Executable is tiny, is text, or will not run after cloning:** run `git lfs pull`
  followed by `git lfs fsck` in the repository. Check that you are signed in to a
  GitHub account with repository access and that the download completed.
