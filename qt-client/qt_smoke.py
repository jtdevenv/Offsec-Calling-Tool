"""Render and verify the real Qt application without devices, calls or user data."""
import json
from pathlib import Path
import tempfile
import wave

import numpy as np
import PySide6
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from audio_engine import ClipBuffer
from ffmpeg_audio import decode_pcm, ffmpeg_executable
from library_store import LibraryStore
from media_import import convert_media


class SilentStream:
    active = True

    def abort(self):
        self.active = False

    def close(self):
        pass


def run(application, App, output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {'qt': PySide6.__version__, 'calls_placed': False, 'device_playback_tested': False}
    window = None
    try:
        with tempfile.TemporaryDirectory(dir=output) as temp:
            root = Path(temp)
            wav = root / 'sample.wav'
            with wave.open(str(wav), 'wb') as writer:
                writer.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
                writer.writeframes((np.sin(np.arange(12000) * 2 * np.pi * 440 / 48000) * 4000).astype('<i2').tobytes())
            store = LibraryStore(root / 'settings.json')
            greetings = store.create_folder('Greetings')
            responses = store.create_folder('Responses')
            closing = store.create_folder('Closing')
            names = ['Sound 1', 'Hello there', 'Introduction', 'One moment', 'Let me check',
                     'Understood', 'Thank you', 'Goodbye']
            for index, name in enumerate(names):
                clip = convert_media(wav, store.media_dir)
                clip['name'] = name + '.mp3'
                clip['folder'] = (greetings if index < 3 else responses if index < 6 else closing)['id']
                store.clips.append(clip)
            ids = [c['id'] for c in store.clips]
            store.soundboards = [{'name': 'Default board', 'clips': ids},
                                 {'name': 'Quick responses', 'clips': ids[3:]}]
            store.active_soundboard = 'Default board'
            store.save('', 85)
            window = App(root, launch_microsip=False)
            window.show()
            application.processEvents()
            window.browser.expandAll()
            application.processEvents()
            assert window.board_ids == ids
            window.grab().save(str(output / 'qt-files.png'))
            samples, rate = decode_pcm(store.media_dir / store.clips[0]['file'])
            report['ffmpeg'] = ffmpeg_executable()
            report['decoded_frames'] = len(samples)
            window.active_clip = ids[0]
            window.engine.buffer = ClipBuffer(np.tile(samples, (96, 1)))
            window.engine.rate = rate
            window.engine.buffer.position = rate * 7
            window.engine.stream = SilentStream()
            for pad in window.pads:
                pad.update_player()
            application.processEvents()
            assert window.pads[0].stack.currentIndex() == 1
            QTest.mouseClick(window.pads[0].pause, Qt.MouseButton.LeftButton)
            assert window.engine.state == 'Paused'
            window.grab().save(str(output / 'qt-inline-player.png'))
            window.set_mode('boards')
            window.browser.expandAll()
            application.processEvents()
            assert window.browser.topLevelItem(0).text(0) == 'Saved soundboards'
            window.grab().save(str(output / 'qt-soundboards.png'))
            window.resize(760, 560)
            application.processEvents()
            window.grab().save(str(output / 'qt-small-window.png'))
            assert all(p.width() == p.height() for p in window.pads)
            window.stop()
            assert window.pads[0].stack.currentIndex() == 0
            assert window.persist()
            window.allow_close = True
            window.close()
            application.processEvents()
            window = None
            report['success'] = True
    except Exception as exc:
        import traceback
        report.update(success=False, error=str(exc), traceback=traceback.format_exc())
    finally:
        if window:
            window.allow_close = True
            window.close()
        (output / 'smoke-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return 0 if report['success'] else 1
