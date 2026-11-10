"""Native Qt workflows with temporary libraries; no external calls or audio output."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import wave

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt, QMimeData, QUrl
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox
import numpy as np

import qt_app
from audio_engine import AudioEngine
from library_store import LibraryStore


class FakeEngine:
    def __init__(self):
        self.state = 'Stopped'
        self.times = (0, 0)
        self.warning = None
        self.volume = 1
        self.path = None

    @staticmethod
    def devices():
        return [(7, 'Test CABLE Input [WASAPI]')]

    def stop(self):
        self.state, self.times, self.path = 'Stopped', (0, 0), None

    def set_volume(self, value):
        self.volume = value

    def play_samples(self, samples, rate, path, device):
        self.state, self.times, self.path = 'Playing', (0, len(samples) / rate), path

    def toggle_pause(self):
        self.state = 'Playing' if self.state == 'Paused' else 'Paused'

    def seek(self, seconds):
        self.times = seconds, self.times[1]


class QtWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.patchers = [patch.object(qt_app, 'AudioEngine', FakeEngine),
                         patch.object(qt_app.App, 'error'),
                         patch.object(qt_app.MicroSipBackend, 'show')]
        for p in self.patchers:
            p.start()
            self.addCleanup(p.stop)
        store = LibraryStore(self.root / 'settings.json')
        folder = store.create_folder('Greetings')
        store.clips = [{'id': 'one', 'name': 'Hello.mp3', 'file': 'one.mp3', 'folder': folder['id']},
                       {'id': 'two', 'name': 'Goodbye.mp3', 'file': 'two.mp3', 'folder': ''}]
        store.save('Test CABLE Input [WASAPI]', 85)
        self.ui = qt_app.App(self.root, launch_microsip=False)
        self.ui.show()
        self.qt.processEvents()
        self.addCleanup(self.cleanup_window)

    def cleanup_window(self):
        self.ui.stop()
        self.ui.import_cancel.set()
        if self.ui.import_thread:
            self.ui.import_thread.join(10)
        for t in self.ui.decode_threads:
            t.join(10)
        self.ui.tick()
        self.ui.allow_close = True
        self.ui.close()
        self.qt.processEvents()

    def wait_until(self, predicate, timeout=12):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            self.qt.processEvents()
            self.ui.tick()
            time.sleep(.01)
        self.assertTrue(predicate(), 'Timed out waiting for worker')

    def mime(self, ids):
        mime = QMimeData()
        mime.setData(qt_app.CLIP_MIME, json.dumps(ids).encode())
        return mime

    def test_toggle_reuses_tree_and_has_no_add_audio_action(self):
        tree = self.ui.browser
        QTest.mouseClick(self.ui.mode_buttons['boards'], Qt.MouseButton.LeftButton)
        self.assertIs(self.ui.browser, tree)
        self.assertEqual(self.ui.browser.topLevelItem(0).text(0), 'Saved soundboards')
        self.assertTrue(self.ui.save_as_button.isVisible())
        self.assertFalse(self.ui.directory_button.isVisible())
        QTest.mouseClick(self.ui.mode_buttons['files'], Qt.MouseButton.LeftButton)
        self.assertFalse(self.ui.save_as_button.isVisible())
        self.assertEqual(self.ui.browser.topLevelItem(0).text(0), 'Library')
        buttons = self.ui.sidebar.findChildren(qt_app.QPushButton)
        self.assertNotIn('Add audio', [b.text() for b in buttons])
        self.assertNotIn('Add selected to board', [b.text() for b in buttons])

    def test_board_drop_appends_and_pad_drop_replaces_without_duplicates(self):
        self.ui.board_drop(self.mime(['one', 'two']))
        self.assertEqual(self.ui.board_ids, ['one', 'two'])
        self.ui.board_drop(self.mime(['two']), 0)
        self.assertEqual(self.ui.board_ids, ['two'])
        self.assertEqual(len(self.ui.pads), 1)
        self.ui.board_drop(self.mime(['one', 'one', 'unknown']))
        self.assertEqual(self.ui.board_ids, ['two', 'one'])
        self.ui.remove_pad(0)
        self.assertEqual(self.ui.board_ids, ['one'])

    def test_pad_becomes_player_pauses_seeks_stops_and_finishes(self):
        self.ui.add_to_board(['one', 'two'])
        with patch('sounddevice.query_devices', return_value={'max_output_channels': 2}), \
             patch.object(qt_app, 'decode_pcm', return_value=(np.zeros((48000, 2), dtype='float32'), 48000)):
            QTest.mouseClick(self.ui.pads[0].launch, Qt.MouseButton.LeftButton)
            self.wait_until(lambda: not self.ui.decoding)
            pad = self.ui.pads[0]
            self.assertEqual(pad.stack.currentIndex(), 1)
            self.assertEqual(self.ui.pads[1].stack.currentIndex(), 0)
            QTest.mouseClick(pad.pause, Qt.MouseButton.LeftButton)
            self.assertEqual(self.ui.engine.state, 'Paused')
            pad.seek.setValue(500)
            pad.seek_to()
            self.assertAlmostEqual(self.ui.engine.times[0], .5)
            QTest.mouseClick(pad.pause, Qt.MouseButton.LeftButton)
            self.assertEqual(self.ui.engine.state, 'Playing')
            self.ui.play_clip('two')
            self.wait_until(lambda: not self.ui.decoding)
            self.assertEqual(self.ui.pads[0].stack.currentIndex(), 0)
            self.assertEqual(self.ui.pads[1].stack.currentIndex(), 1)
            self.ui.engine.state = 'Finished'
            self.ui.tick()
            self.assertEqual(self.ui.pads[1].stack.currentIndex(), 0)
            self.assertIsNone(self.ui.active_clip)

    def test_stop_invalidates_late_decoder_results(self):
        self.ui.add_to_board(['one'])
        self.ui.active_clip = 'one'
        generation = self.ui.decode_generation
        self.ui.stop()
        self.ui.events.put(('decoded', generation, 'one', np.zeros((10, 2)), 48000,
                            self.root / 'media' / 'one.mp3', 7))
        self.ui.tick()
        self.assertEqual(self.ui.engine.state, 'Stopped')

    def test_presets_folder_membership_and_unsaved_board_survive_restart(self):
        self.ui.add_to_board(['two', 'one'])
        self.ui.set_mode('boards')
        with patch.object(QInputDialog, 'getText', return_value=('Calls', True)):
            self.ui.new_folder()
        folder = self.ui.layout_data['board_folders'][0]
        folder_item = self.ui.browser.topLevelItem(0).child(0)
        self.ui.browser.setCurrentItem(folder_item)
        with patch.object(QInputDialog, 'getText', return_value=('Daily calls', True)):
            self.assertTrue(self.ui.save_board_as())
        self.assertEqual(self.ui.layout_data['preset_locations']['Daily calls'], folder['id'])
        self.ui.remove_pad(1)
        layout = json.loads((self.root / 'qt-layout.json').read_text())
        self.assertEqual(layout['board'], ['two'])
        self.assertTrue(layout['dirty'])
        store = LibraryStore(self.root / 'settings.json')
        self.assertEqual(store.soundboards[0]['clips'], ['two', 'one'])
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Discard):
            self.ui.load_board('Daily calls')
        self.assertEqual(self.ui.board_ids, ['two', 'one'])
        self.assertFalse(self.ui.dirty)
        restored = qt_app.App(self.root, launch_microsip=False)
        self.assertEqual(restored.board_ids, ['two', 'one'])
        self.assertEqual(restored.layout_data['preset_locations']['Daily calls'], folder['id'])
        restored.allow_close = True
        restored.close()

    def test_real_directory_import_keeps_subfolders_and_originals(self):
        source = self.root / 'source clips'
        nested = source / 'Nested'
        nested.mkdir(parents=True)
        path = nested / 'hello world.wav'
        with wave.open(str(path), 'wb') as out:
            out.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
            out.writeframes(np.zeros(4800, dtype='<i2').tobytes())
        before = path.read_bytes()
        (source / 'ignore.txt').write_text('not audio')
        self.ui.start_import([str(source)], add_to_board=True)
        self.wait_until(lambda: self.ui.import_thread is None)
        imported = self.ui.store.clips[-1]
        folder = next(f for f in self.ui.store.folders if f['id'] == imported['folder'])
        parent = next(f for f in self.ui.store.folders if f['id'] == folder['parent'])
        self.assertEqual((parent['name'], folder['name']), ('source clips', 'Nested'))
        self.assertEqual(self.ui.board_ids, [imported['id']])
        self.assertTrue((self.ui.store.media_dir / imported['file']).is_file())
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(len(self.ui.store.clips), 3)

    def test_missing_saved_output_is_not_silently_replaced_or_erased(self):
        self.ui.saved_device = 'Unavailable cable'
        self.ui.outputs.setCurrentIndex(-1)
        self.ui.persist()
        self.assertEqual(LibraryStore(self.root / 'settings.json').device, 'Unavailable cable')
        self.ui.play_clip('one')
        self.assertIsNone(self.ui.active_clip)

    def test_malformed_layout_is_preserved(self):
        original = '{invalid'
        self.ui.layout_path.write_text(original)
        self.ui.layout_data = self.ui.load_layout()
        self.assertIsNotNone(self.ui.layout_error)
        self.assertFalse(self.ui.persist())
        self.assertEqual(self.ui.layout_path.read_text(), original)


class AudioTransportTests(unittest.TestCase):
    def test_seek_clamps_and_preserves_paused_state(self):
        engine = AudioEngine()
        engine.buffer = __import__('audio_engine').ClipBuffer(np.zeros((48000, 2), dtype='float32'))
        engine.rate = 48000
        engine.buffer.paused = True
        engine.seek(.5)
        self.assertEqual(engine.buffer.position, 24000)
        self.assertTrue(engine.buffer.paused)
        engine.seek(-1)
        self.assertEqual(engine.buffer.position, 0)
        engine.seek(100)
        self.assertEqual(engine.buffer.position, 47999)


if __name__ == '__main__':
    unittest.main()
