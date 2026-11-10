import json
from pathlib import Path
import tempfile
import unittest

from library_store import LibraryStore


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = Path(self.temp.name) / 'settings.json'

    def test_legacy_paths_survive_restart_until_converted(self):
        paths = ['C:/voice/a.m4a', 'C:/voice/b.wav']
        self.settings.write_text(json.dumps({'clips': paths, 'volume': 72}), encoding='utf-8')
        store = LibraryStore(self.settings)
        self.assertEqual(store.clips, [])
        self.assertEqual(store.pending_legacy, paths)
        store.pending_legacy.remove(paths[0])
        store.clips.append({'id': 'clip1', 'name': 'a.mp3', 'file': 'clip1.mp3', 'folder': ''})
        store.save('CABLE Input', 72)
        restored = LibraryStore(self.settings)
        self.assertEqual(restored.pending_legacy, [paths[1]])
        self.assertEqual(restored.clips[0]['name'], 'a.mp3')
        self.assertEqual(restored.device, 'CABLE Input')

    def test_folders_and_membership_persist(self):
        store = LibraryStore(self.settings)
        folder = store.create_folder('Greetings')
        store.clips.append({'id': 'clip1', 'name': 'hello.mp3', 'file': 'clip1.mp3', 'folder': folder['id']})
        store.save('', 85)
        restored = LibraryStore(self.settings)
        self.assertEqual(restored.folders, [folder])
        self.assertEqual(restored.clips[0]['folder'], folder['id'])
        with self.assertRaises(ValueError):
            restored.create_folder(' greetings ')
        with self.assertRaises(ValueError):
            restored.create_folder(' ')

    def test_corrupt_metadata_is_not_overwritten(self):
        original = '{broken JSON'
        self.settings.write_text(original)
        store = LibraryStore(self.settings)
        self.assertIsNotNone(store.load_error)
        with self.assertRaises(ValueError):
            store.save('', 85)
        self.assertEqual(self.settings.read_text(), original)

    def test_media_paths_cannot_escape_managed_directory(self):
        self.settings.write_text(json.dumps({'version': 2, 'clips': [
            {'id': 'bad', 'name': 'bad', 'file': '../original.mp3'}]}))
        store = LibraryStore(self.settings)
        self.assertIsNotNone(store.load_error)

    def test_missing_folder_defaults_to_unfiled(self):
        self.settings.write_text(json.dumps({'version': 2, 'clips': [
            {'id': 'clip', 'name': 'Clip', 'file': 'clip.mp3'}]}))
        store = LibraryStore(self.settings)
        self.assertIsNone(store.load_error)
        self.assertEqual(store.clips[0]['folder'], '')

    def test_invalid_soundboards_preserve_settings(self):
        original = json.dumps({'version': 2, 'soundboards': [{'name': 'Bad', 'clips': [42]}]})
        self.settings.write_text(original)
        store = LibraryStore(self.settings)
        self.assertIsNotNone(store.load_error)
        with self.assertRaises(ValueError): store.save('', 85)
        self.assertEqual(self.settings.read_text(), original)


if __name__ == '__main__':
    unittest.main()
