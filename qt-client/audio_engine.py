"""Clip playback independent of the desktop UI; no audio starts on import."""
from pathlib import Path

import numpy as np
import sounddevice as sd
from ffmpeg_audio import decode_pcm, RATE


class ClipBuffer:
    def __init__(self, samples):
        self.samples = samples
        self.position = 0
        self.paused = False
        self.volume = 1.0

    def render(self, output):
        output.fill(0)
        if self.paused:
            return False
        count = min(len(output), len(self.samples) - self.position)
        if count:
            np.multiply(self.samples[self.position:self.position + count],
                        self.volume, out=output[:count])
            self.position += count
        return self.position >= len(self.samples)


class AudioEngine:
    def __init__(self):
        self.stream = None
        self.buffer = None
        self.rate = 1
        self.path = None
        self.warning = None
        self.volume = 1.0

    @staticmethod
    def devices():
        apis = sd.query_hostapis()
        return [(i, f"{d['name']} [{apis[d['hostapi']]['name']}]")
                for i, d in enumerate(sd.query_devices()) if d['max_output_channels'] > 0]

    def play(self, path, device):
        self.stop()
        channels = min(2, int(sd.query_devices(device)['max_output_channels']))
        if channels < 1:
            raise ValueError('The selected device has no playback channels.')
        sd.check_output_settings(device=device, channels=channels,
                                 dtype='float32', samplerate=RATE)
        samples, rate = decode_pcm(path, channels=channels)
        self.play_samples(samples, rate, path, device)

    def play_samples(self, samples, rate, path, device):
        """Start already decoded PCM on the UI thread, after background decoding."""
        self.stop()
        channels = samples.shape[1]
        self.buffer = ClipBuffer(np.ascontiguousarray(samples))
        self.buffer.volume = self.volume
        self.rate, self.path, self.warning = rate, Path(path), None
        try:
            self.stream = sd.OutputStream(device=device, samplerate=rate,
                channels=channels, dtype='float32', callback=self._callback)
            self.stream.start()
        except Exception:
            self.stop()
            raise

    def seek(self, seconds):
        if self.buffer is not None:
            self.buffer.position = max(0, min(len(self.buffer.samples) - 1,
                                               int(float(seconds) * self.rate)))

    def _callback(self, output, frames, time_info, status):
        if status:
            self.warning = str(status)
        if self.buffer.render(output):
            raise sd.CallbackStop

    def toggle_pause(self):
        if self.stream is not None and self.stream.active:
            self.buffer.paused = not self.buffer.paused

    def set_volume(self, value):
        self.volume = float(value)
        if self.buffer is not None:
            self.buffer.volume = self.volume

    def stop(self):
        if self.stream is not None:
            self.stream.abort()
            self.stream.close()
            self.stream = None
        self.buffer = None
        self.path = None

    @property
    def state(self):
        if self.stream is None:
            return 'Stopped'
        if not self.stream.active:
            return 'Finished'
        return 'Paused' if self.buffer.paused else 'Playing'

    @property
    def times(self):
        if self.buffer is None:
            return 0, 0
        return self.buffer.position / self.rate, len(self.buffer.samples) / self.rate
