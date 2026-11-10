"""Persistent library metadata. Folder names are labels, never filesystem paths."""
import json
from pathlib import Path
from uuid import uuid4


class LibraryStore:
    def __init__(self, settings):
        self.settings = Path(settings)
        self.media_dir = self.settings.parent / 'media'
        self.clips = []
        self.folders = []
        self.pending_legacy = []
        self.device = ''
        self.volume = 85.0
        self.soundboards = []
        self.active_soundboard = ''
        self.load_error = None
        self._load()

    def _load(self):
        if not self.settings.exists():
            return
        try:
            data = json.loads(self.settings.read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                raise ValueError('Settings must contain an object.')
            self.device = str(data.get('device', ''))
            self.volume = max(0, min(100, float(data.get('volume', 85))))
            if data.get('version') == 2:
                self.folders = data.get('folders', [])
                self.clips = data.get('clips', [])
                self.pending_legacy = data.get('pending_legacy', [])
                if not all(isinstance(items, list) for items in
                           (self.folders, self.clips, self.pending_legacy)):
                    raise ValueError('Invalid library lists.')
                if not all(isinstance(x, dict) and isinstance(x.get('id'), str)
                           and isinstance(x.get('name'), str) for x in self.folders + self.clips):
                    raise ValueError('Invalid library entries.')
                ids = [x['id'] for x in self.folders + self.clips]
                if len(ids) != len(set(ids)) or any(not i or i == 'root' for i in ids):
                    raise ValueError('Invalid library identifiers.')
                folder_ids = {f['id'] for f in self.folders}
                for clip in self.clips:
                    filename = clip['file']
                    if (not isinstance(filename, str) or Path(filename).name != filename
                            or '/' in filename or '\\' in filename or not filename.endswith('.mp3')):
                        raise ValueError('Invalid managed media filename.')
                    clip['folder'] = clip.get('folder', '')
                    if not isinstance(clip['folder'], str) or clip['folder'] not in folder_ids:
                        clip['folder'] = ''
                    if not isinstance(clip.get('source_name', ''), str):
                        raise ValueError('Invalid source filename.')
                boards = data.get('soundboards', [])
                if not isinstance(boards, list): raise ValueError('Invalid soundboards.')
                clip_ids = {c['id'] for c in self.clips}
                names = set()
                for board in boards:
                    if (not isinstance(board, dict) or not isinstance(board.get('name'), str)
                            or not board['name'].strip() or board['name'].casefold() in names
                            or not isinstance(board.get('clips'), list)
                            or not all(isinstance(k, str) for k in board['clips'])):
                        raise ValueError('Invalid soundboard preset.')
                    names.add(board['name'].casefold())
                    self.soundboards.append({'name': board['name'], 'clips': list(dict.fromkeys(k for k in board['clips'] if k in clip_ids))})
                active = data.get('active_soundboard', '')
                self.active_soundboard = active if any(b['name'] == active for b in self.soundboards) else ''
                if not all(isinstance(p, str) for p in self.pending_legacy):
                    raise ValueError('Invalid legacy paths.')
            else:
                paths = data.get('clips', [])
                if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
                    raise ValueError('Invalid legacy library.')
                self.pending_legacy = list(dict.fromkeys(paths))
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            # Preserve the original for recovery; do not silently overwrite it.
            self.clips, self.folders, self.pending_legacy = [], [], []
            self.soundboards = []
            self.active_soundboard = ''
            self.load_error = str(exc)

    def save(self, device, volume):
        if self.load_error:
            raise ValueError('The existing settings file could not be read and has been preserved. '
                             'Repair or move settings.json before saving. ' + self.load_error)
        data = {'soundboards': self.soundboards, 'active_soundboard': self.active_soundboard, 'version': 2, 'clips': self.clips, 'folders': self.folders,
                'pending_legacy': self.pending_legacy, 'device': device, 'volume': volume}
        temp = self.settings.with_suffix('.tmp')
        temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
        temp.replace(self.settings)

    def create_folder(self, name):
        name = name.strip()
        if not name:
            raise ValueError('Enter a folder name.')
        if any(f['name'].casefold() == name.casefold() for f in self.folders):
            raise ValueError('A folder with this name already exists.')
        folder = {'id': uuid4().hex, 'name': name}
        self.folders.append(folder)
        return folder
