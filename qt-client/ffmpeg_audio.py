"""Decode local audio with FFmpeg into bounded 48 kHz float32 PCM."""
import importlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import numpy as np

RATE = 48000
MAX_PCM_BYTES = 128 * 1024 * 1024


class AudioCancelled(Exception):
    pass


def ffmpeg_executable():
    if getattr(sys, 'frozen', False):
        candidate = Path(sys._MEIPASS) / 'ffmpeg' / 'bin' / 'ffmpeg.exe'
    else:
        candidate = Path(__file__).resolve().parent / '.release-assets' / 'ffmpeg' / 'bin' / 'ffmpeg.exe'
    if candidate.is_file():
        return str(candidate.resolve())
    if not getattr(sys, 'frozen', False):
        # Qt development uses the complete portable release beside its source.
        portable = Path(__file__).resolve().parent.parent / '_qt_internal' / 'ffmpeg' / 'bin' / 'ffmpeg.exe'
        if portable.is_file():
            return str(portable.resolve())
        # Compatibility for running development tests in the existing environment.
        # This wrapper and its old binary are explicitly excluded from new builds.
        try:
            return importlib.import_module('imageio_ffmpeg').get_ffmpeg_exe()
        except ImportError:
            pass
    raise FileNotFoundError('FFmpeg is missing. Run Release.cmd to prepare the complete application.')


def decode_pcm(path, channels=2, cancel=None, max_bytes=MAX_PCM_BYTES):
    if channels not in (1, 2) or max_bytes < channels * 4:
        raise ValueError('Invalid PCM output limits.')
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise ValueError('Choose an audio file, not a directory.')
    if cancel is not None and cancel.is_set():
        raise AudioCancelled()
    frame_bytes = channels * 4
    max_frames = max_bytes // frame_bytes
    # Decode slightly beyond the limit to reject oversized clips, rather than
    # silently truncating them. FFmpeg itself caps the temporary output size.
    duration_cap = max_frames / RATE + 0.01
    command = [ffmpeg_executable(), '-hide_banner', '-loglevel', 'error', '-nostdin',
               '-protocol_whitelist', 'file', '-i', str(path), '-map', '0:a:0',
               '-vn', '-sn', '-dn', '-ac', str(channels), '-ar', str(RATE),
               '-t', f'{duration_cap:.9f}', '-c:a', 'pcm_f32le', '-f', 'f32le', 'pipe:1']
    process = None
    with tempfile.TemporaryFile() as pcm, tempfile.TemporaryFile() as log:
        try:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=pcm, stderr=log,
                                       shell=False, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            deadline = time.monotonic() + 120
            while process.poll() is None:
                if cancel is not None and cancel.wait(0.05):
                    raise AudioCancelled()
                if cancel is None:
                    time.sleep(0.05)
                if time.monotonic() > deadline:
                    raise ValueError('Audio decoding exceeded the two minute time limit.')
            if cancel is not None and cancel.is_set():
                raise AudioCancelled()
            if process.returncode:
                log.seek(0, os.SEEK_END)
                log.seek(max(0, log.tell() - 2000))
                detail = log.read().decode('utf-8', errors='replace').strip()
                raise ValueError('Could not decode audio. ' + detail)
            pcm.seek(0, os.SEEK_END)
            size = pcm.tell()
            if size > max_frames * frame_bytes:
                raise ValueError('Clip exceeds the 128 MiB decoded audio limit. Split it into shorter clips.')
            if not size or size % frame_bytes:
                raise ValueError('No complete audio samples were found in this file.')
            pcm.seek(0)
            samples = np.frombuffer(pcm.read(size), dtype='<f4').reshape(-1, channels)
            return samples, RATE
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
