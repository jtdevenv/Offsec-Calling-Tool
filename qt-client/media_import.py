"""Convert local media into owned MP3 files without touching the source."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
from uuid import uuid4

from ffmpeg_audio import AudioCancelled as ImportCancelled, decode_pcm, ffmpeg_executable


def convert_media(source, media_dir, cancel=None):
    source = Path(source).resolve(strict=True)
    if not source.is_file():
        raise ValueError('Drop files, not directories.')
    media_dir = Path(media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)
    clip_id = uuid4().hex
    target = media_dir / f'{clip_id}.mp3'
    partial = media_dir / f'{clip_id}.part.mp3'
    # Pass an argument list: spaces, braces, Unicode and shell characters are literal.
    command = [ffmpeg_executable(), '-hide_banner', '-loglevel', 'error',
               '-nostdin', '-y', '-protocol_whitelist', 'file', '-i', str(source), '-map', '0:a:0',
               '-vn', '-sn', '-dn', '-map_metadata', '-1', '-c:a', 'libmp3lame',
               '-b:a', '192k', '-ar', '48000', '-ac', '2', str(partial)]
    process = None
    try:
        if cancel is not None and cancel.is_set():
            raise ImportCancelled()
        # A temporary log avoids pipe deadlocks and holding unbounded stderr in memory.
        with tempfile.TemporaryFile() as log:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            deadline = time.monotonic() + 900
            while process.poll() is None:
                if cancel is not None and cancel.wait(0.1):
                    raise ImportCancelled()
                if cancel is None:
                    time.sleep(0.1)
                if time.monotonic() > deadline:
                    raise ValueError('Conversion exceeded the 15 minute time limit.')
            if process.returncode:
                log.seek(0, os.SEEK_END)
                log.seek(max(0, log.tell() - 2000))
                detail = log.read().decode('utf-8', errors='replace').strip()
                raise ValueError('Cannot decode an audio track from this file. ' + detail)
        if cancel is not None and cancel.is_set():
            raise ImportCancelled()
        # Validate actual decoded frames with the same bounded decoder used for playback.
        decode_pcm(partial, cancel=cancel)
        partial.replace(target)
        return {'id': clip_id, 'name': source.stem + '.mp3', 'file': target.name,
                'folder': '', 'source_name': source.name}
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        partial.unlink(missing_ok=True)
