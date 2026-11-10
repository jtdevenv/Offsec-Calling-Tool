"""Exercise importer rollback with a simulated converter; real codecs when installed."""
from pathlib import Path
import subprocess
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

import numpy as np
import media_import
from ffmpeg_audio import decode_pcm, ffmpeg_executable

try:
    ffmpeg_executable()
    HAS_FFMPEG = True
except FileNotFoundError:
    HAS_FFMPEG = False


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.media = self.root / 'media'
        self.source = self.root / 'a space {brace} café.m4a'
        self.source.write_bytes(b'original file content')

    def converter(self, command, **kwargs):
        self.assertEqual(Path(command[command.index('-i') + 1]), self.source)
        self.assertEqual(command[command.index('-protocol_whitelist') + 1], 'file')
        Path(command[-1]).write_bytes(b'simulated MP3')
        return types.SimpleNamespace(returncode=0, poll=lambda: 0)

    def test_import_preserves_original_and_separates_duplicate_names(self):
        original = self.source.read_bytes()
        with patch.object(media_import, 'ffmpeg_executable', return_value='ffmpeg'), \
                patch.object(media_import.subprocess, 'Popen', self.converter), \
                patch.object(media_import, 'decode_pcm', return_value=(np.zeros((4800, 2)), 48000)):
            first = media_import.convert_media(self.source, self.media)
            second = media_import.convert_media(self.source, self.media)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertNotEqual(first['file'], second['file'])
        self.assertEqual(first['name'], self.source.stem + '.mp3')
        self.assertEqual(len(list(self.media.iterdir())), 2)
        self.assertEqual((self.media / first['file']).read_bytes(), b'simulated MP3')

    def test_failed_conversion_cleans_partial_output(self):
        def fail(command, **kwargs):
            Path(command[-1]).write_bytes(b'incomplete')
            kwargs['stderr'].write(b'no audio stream')
            return types.SimpleNamespace(returncode=1, poll=lambda: 1)
        with patch.object(media_import, 'ffmpeg_executable', return_value='ffmpeg'), \
                patch.object(media_import.subprocess, 'Popen', fail):
            with self.assertRaisesRegex(ValueError, 'no audio stream'):
                media_import.convert_media(self.source, self.media)
        self.assertEqual(list(self.media.iterdir()), [])
        self.assertTrue(self.source.exists())

    def test_cancel_kills_converter_and_cleans_partial_output(self):
        cancel = threading.Event()
        killed = []
        def running(command, **kwargs):
            Path(command[-1]).write_bytes(b'partial')
            cancel.set()
            return types.SimpleNamespace(poll=lambda: None, kill=lambda: killed.append(True), wait=lambda: 0)
        with patch.object(media_import, 'ffmpeg_executable', return_value='ffmpeg'), \
                patch.object(media_import.subprocess, 'Popen', running):
            with self.assertRaises(media_import.ImportCancelled):
                media_import.convert_media(self.source, self.media, cancel)
        self.assertEqual(killed, [True])
        self.assertEqual(list(self.media.iterdir()), [])

    def test_invalid_file_or_directory_does_not_create_media(self):
        with self.assertRaises(FileNotFoundError):
            media_import.convert_media(self.root / 'missing.wav', self.media)
        with self.assertRaises(ValueError):
            media_import.convert_media(self.root, self.media)
        self.assertFalse(self.media.exists())

    @unittest.skipUnless(HAS_FFMPEG, 'No development FFmpeg is available')
    def test_real_m4a_video_and_mp3_import(self):
        exe = ffmpeg_executable()
        for ext, options in [('m4a', ['-c:a', 'aac']),
                             ('mp4', ['-f', 'lavfi', '-i', 'color=size=32x32:rate=10',
                                      '-c:v', 'mpeg4', '-c:a', 'aac', '-shortest']),
                             ('mp3', ['-c:a', 'libmp3lame'])]:
            source = self.root / f'voice sample.{ext}'
            subprocess.run([exe, '-v', 'error', '-nostdin', '-y', '-f', 'lavfi', '-i',
                            'sine=frequency=440:duration=0.3', *options, '-t', '0.3', str(source)],
                           check=True, capture_output=True,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            original = source.read_bytes()
            clip = media_import.convert_media(source, self.media)
            samples, rate = decode_pcm(self.media / clip['file'])
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual((rate, samples.shape[1]), (48000, 2))
            self.assertGreater(float(np.max(np.abs(samples))), 0.01)


if __name__ == '__main__':
    unittest.main()
