"""Real decoder limits and cancellation, without libsndfile or audio hardware."""
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave

import numpy as np

import ffmpeg_audio
from audio_engine import ClipBuffer


class DecoderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'audio sample.wav'
        samples = (np.sin(np.arange(8820) * 2 * np.pi * 440 / 44100) * 15000).astype('<i2')
        with wave.open(str(self.path), 'wb') as output:
            output.setparams((2, 2, 44100, 0, 'NONE', 'not compressed'))
            output.writeframes(np.column_stack((samples, samples)).tobytes())

    def test_real_resample_and_mono_downmix(self):
        stereo, rate = ffmpeg_audio.decode_pcm(self.path)
        mono, mono_rate = ffmpeg_audio.decode_pcm(self.path, channels=1)
        self.assertEqual((rate, mono_rate), (48000, 48000))
        self.assertEqual(stereo.shape, (9600, 2))
        self.assertEqual(mono.shape, (9600, 1))
        self.assertGreater(float(np.max(np.abs(stereo))), 0.1)
        self.assertTrue(np.isfinite(mono).all())

    def test_real_oversized_decode_is_rejected_not_truncated(self):
        with self.assertRaisesRegex(ValueError, 'decoded audio limit'):
            ffmpeg_audio.decode_pcm(self.path, max_bytes=1024)

    def test_corrupt_audio_is_rejected(self):
        self.path.write_bytes(b'not audio')
        with self.assertRaisesRegex(ValueError, 'Could not decode audio'):
            ffmpeg_audio.decode_pcm(self.path)

    def test_running_decode_is_killed_when_cancelled(self):
        cancel = threading.Event()
        killed = []

        def start(command, **kwargs):
            self.assertFalse(kwargs['shell'])
            self.assertEqual(command[command.index('-protocol_whitelist') + 1], 'file')
            cancel.set()
            return SimpleNamespace(poll=lambda: None, kill=lambda: killed.append(True), wait=lambda: 0)

        with patch.object(ffmpeg_audio.subprocess, 'Popen', side_effect=start):
            with self.assertRaises(ffmpeg_audio.AudioCancelled):
                ffmpeg_audio.decode_pcm(self.path, cancel=cancel)
        self.assertEqual(killed, [True])

    def test_pause_keeps_buffer_position_and_resumes(self):
        buffer = ClipBuffer(np.ones((10, 2), dtype='float32'))
        output = np.empty((4, 2), dtype='float32')
        self.assertFalse(buffer.render(output))
        buffer.paused = True
        self.assertFalse(buffer.render(output))
        self.assertEqual(buffer.position, 4)
        self.assertTrue((output == 0).all())
        buffer.paused = False
        buffer.render(output)
        self.assertEqual(buffer.position, 8)


if __name__ == '__main__':
    unittest.main()
