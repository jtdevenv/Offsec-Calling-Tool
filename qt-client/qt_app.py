"""Qt desktop soundboard. Audio imports/decoding never block the GUI thread."""
import ctypes
import json
import os
from pathlib import Path
import queue
import sys
import threading
from uuid import uuid4

from PySide6.QtCore import Qt, QMimeData, QTimer
from PySide6.QtGui import QDrag, QFontDatabase, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMenu, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QSlider, QSplitter, QStackedWidget,
    QStyle, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)
from audio_engine import AudioEngine
from ffmpeg_audio import AudioCancelled, decode_pcm
from library_store import LibraryStore
from media_import import convert_media
from microsip_backend import MicroSipBackend

ROOT = (Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False)
        else Path(__file__).resolve().parent.parent)
ROLE = Qt.ItemDataRole.UserRole
CLIP_MIME = 'application/x-offsec-library-clip'
PRESET_MIME = 'application/x-offsec-preset'
MEDIA = {'.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg', '.opus', '.aif', '.aiff',
         '.wma', '.mp4', '.mov', '.mkv', '.webm', '.avi'}


def clock(seconds):
    seconds = max(0, int(seconds))
    return f'{seconds // 60}:{seconds % 60:02d}'


def button(text, callback, parent=None):
    result = QPushButton(text, parent)
    result.clicked.connect(callback)
    result.setCursor(Qt.CursorShape.PointingHandCursor)
    return result


class Browser(QTreeWidget):
    """A single native index for library folders and soundboard preset folders."""
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setHeaderHidden(True)
        self.setIndentation(18)
        self.setAnimated(True)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.context_menu)
        self.itemDoubleClicked.connect(self.open_item)

    def startDrag(self, actions):
        items = self.selectedItems()
        if not items:
            return
        kind, key = items[0].data(0, ROLE)
        if kind not in ('clip', 'preset'):
            return
        keys = [i.data(0, ROLE)[1] for i in items if i.data(0, ROLE)[0] == kind]
        mime = QMimeData()
        mime.setData(CLIP_MIME if kind == 'clip' else PRESET_MIME,
                     json.dumps(keys).encode('utf-8'))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if mime.hasUrls() or mime.hasFormat(CLIP_MIME) or mime.hasFormat(PRESET_MIME):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        kind, key = item.data(0, ROLE) if item else ('root', '')
        mime = event.mimeData()
        if self.window.mode == 'files':
            if kind == 'clip':
                key = self.window.clip(key).get('folder', '')
            elif kind != 'folder':
                key = ''
            if mime.hasUrls():
                self.window.start_import([u.toLocalFile() for u in mime.urls() if u.isLocalFile()], key)
            elif mime.hasFormat(CLIP_MIME):
                for clip_id in self.window.mime_ids(mime, CLIP_MIME):
                    clip = self.window.clip(clip_id)
                    if clip:
                        clip['folder'] = key
                self.window.persist()
                self.window.render_browser()
        elif mime.hasFormat(PRESET_MIME):
            if kind == 'preset':
                key = self.window.layout_data['preset_locations'].get(key, '')
            elif kind != 'board-folder':
                key = ''
            for name in self.window.mime_ids(mime, PRESET_MIME):
                self.window.layout_data['preset_locations'][name] = key
            self.window.persist()
            self.window.render_browser()
        event.acceptProposedAction()

    def open_item(self, item, column):
        kind, key = item.data(0, ROLE)
        if kind == 'preset':
            self.window.load_board(key)

    def context_menu(self, point):
        item = self.itemAt(point)
        if item:
            self.setCurrentItem(item)
        menu = QMenu(self)
        if self.window.mode == 'files':
            menu.addAction('New folder', self.window.new_folder)
            menu.addAction('Import audio files…', self.window.pick_files)
            menu.addAction('Import directory…', self.window.pick_directory)
        else:
            menu.addAction('New folder', self.window.new_folder)
            menu.addAction('Save board as…', self.window.save_board_as)
        if item and item.data(0, ROLE)[0] not in ('root', 'board-root'):
            menu.addSeparator()
            menu.addAction('Rename…', self.window.rename_item)
            menu.addAction('Remove from library' if self.window.mode == 'files' else 'Remove',
                           self.window.remove_item)
        menu.exec(self.viewport().mapToGlobal(point))


class Pad(QFrame):
    def __init__(self, window, clip_id, index):
        super().__init__()
        self.window, self.clip_id, self.index = window, clip_id, index
        self.setObjectName('soundPad')
        self.setAcceptDrops(True)
        self.stack = QStackedWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)
        self.launch = button(window.clip(clip_id)['name'].removesuffix('.mp3'),
                             lambda: window.play_clip(clip_id))
        self.launch.setObjectName('padLaunch')
        self.launch.setToolTip(window.clip(clip_id)['name'])
        self.launch.setAccessibleName('Play ' + window.clip(clip_id)['name'])
        self.stack.addWidget(self.launch)
        player = QWidget()
        player.setObjectName('padPlayer')
        controls = QVBoxLayout(player)
        controls.setContentsMargins(15, 14, 15, 14)
        self.state_label = QLabel('PLAYING')
        self.state_label.setObjectName('eyebrow')
        controls.addWidget(self.state_label)
        controls.addStretch()
        self.time = QLabel('0:00 / 0:00')
        self.time.setObjectName('muted')
        controls.addWidget(self.time)
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 1000)
        self.seek.setAccessibleName('Playback position')
        self.seek.sliderReleased.connect(self.seek_to)
        controls.addWidget(self.seek)
        row = QHBoxLayout()
        self.pause = button('', window.toggle_pause)
        self.pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self.pause.setAccessibleName('Pause')
        stop = button('', window.stop)
        stop.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        stop.setAccessibleName('Stop')
        stop.setToolTip('Stop and restore sound name (Escape)')
        row.addWidget(self.pause)
        row.addWidget(stop)
        controls.addLayout(row)
        self.stack.addWidget(player)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.context_menu)
        self.update_player()

    def update_player(self):
        active = self.window.active_clip == self.clip_id
        self.stack.setCurrentIndex(1 if active else 0)
        if not active:
            return
        state = 'Loading' if self.window.decoding else self.window.engine.state
        self.state_label.setText(state.upper())
        self.pause.setEnabled(not self.window.decoding)
        paused = state == 'Paused'
        self.pause.setIcon(self.style().standardIcon(
            QStyle.StandardPixmap.SP_MediaPlay if paused else QStyle.StandardPixmap.SP_MediaPause))
        self.pause.setAccessibleName('Play' if paused else 'Pause')
        self.pause.setToolTip('Resume' if paused else 'Pause')
        elapsed, total = self.window.engine.times
        self.time.setText(f'{clock(elapsed)} / {clock(total)}')
        self.seek.setEnabled(not self.window.decoding and total > 0)
        if not self.seek.isSliderDown():
            self.seek.setValue(round(elapsed / total * 1000) if total else 0)

    def seek_to(self):
        self.window.engine.seek(self.seek.value() / 1000 * self.window.engine.times[1])

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(CLIP_MIME) or event.mimeData().hasUrls():
            event.acceptProposedAction()

    dragMoveEvent = dragEnterEvent

    def dropEvent(self, event):
        self.window.board_drop(event.mimeData(), self.index)
        event.acceptProposedAction()

    def context_menu(self, point):
        menu = QMenu(self)
        menu.addAction('Remove from board', lambda: self.window.remove_pad(self.index))
        menu.exec(self.mapToGlobal(point))


class BoardArea(QScrollArea):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAcceptDrops(True)
        self.content = QWidget()
        self.grid = QGridLayout(self.content)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(12)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setWidget(self.content)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.arrange()
        QTimer.singleShot(0, self.arrange)

    def arrange(self):
        if not hasattr(self.window, 'pads'):
            return
        width = max(150, self.viewport().width() - 8)
        cols = max(1, min(5, (width + 12) // 182))
        size = min(240, max(150, (width - 12 * (cols - 1)) // cols))
        for index, pad in enumerate(self.window.pads):
            self.grid.addWidget(pad, index // cols, index % cols)
            pad.setFixedSize(size, size)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(CLIP_MIME) or event.mimeData().hasUrls():
            event.acceptProposedAction()

    dragMoveEvent = dragEnterEvent

    def dropEvent(self, event):
        self.window.board_drop(event.mimeData())
        event.acceptProposedAction()


class App(QMainWindow):
    def __init__(self, root=ROOT, launch_microsip=True):
        super().__init__()
        if not QFontDatabase.families() and sys.platform == 'win32':
            # The offscreen platform may not enumerate Windows fonts. Load the
            # user's installed font directly; do not redistribute Windows fonts.
            font = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'segoeui.ttf'
            if font.is_file():
                QFontDatabase.addApplicationFont(str(font))
        self.root = Path(root)
        self.store = LibraryStore(self.root / 'settings.json')
        self.saved_device = self.store.device
        self.layout_path = self.root / 'qt-layout.json'
        self.layout_error = None
        self.layout_data = self.load_layout()
        self.engine = AudioEngine()
        self.events = queue.Queue()
        self.import_cancel = threading.Event()
        self.decode_cancel = threading.Event()
        self.import_thread = None
        self.decode_threads = []
        self.decode_generation = 0
        self.decoding = False
        self.active_clip = None
        self.closing = False
        self.allow_close = False
        self.mode = self.layout_data.get('mode', 'files')
        self.mode = self.mode if self.mode in ('files', 'boards') else 'files'
        self.board_name = self.layout_data.get('board_name', self.store.active_soundboard)
        saved = next((b['clips'] for b in self.store.soundboards if b['name'] == self.board_name), [])
        self.board_ids = self.valid_ids(self.layout_data.get('board', saved))
        self.dirty = self.layout_data.get('dirty', False) is True
        self.pads = []
        self.setWindowTitle('Offsec Call Client')
        self.resize(1140, 770)
        self.setMinimumSize(720, 520)
        self.build_ui()
        self.apply_theme()
        self.refresh_devices()
        self.engine.set_volume(self.store.volume / 100)
        self.render_browser()
        self.render_board()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(70)
        QShortcut(QKeySequence('Escape'), self, activated=self.stop)
        QShortcut(QKeySequence('Ctrl+S'), self, activated=self.save_board)
        if launch_microsip:
            QTimer.singleShot(150, self.open_microsip)
        if self.store.load_error or self.layout_error:
            QTimer.singleShot(250, lambda: self.error(self.store.load_error or self.layout_error))
        elif self.store.pending_legacy:
            QTimer.singleShot(250, lambda: self.start_import(self.store.pending_legacy.copy(), legacy=True))

    def load_layout(self):
        default = {'board_folders': [], 'preset_locations': {}}
        if not self.layout_path.exists():
            return default
        try:
            value = json.loads(self.layout_path.read_text(encoding='utf-8'))
            if not isinstance(value, dict) or not isinstance(value.get('preset_locations', {}), dict):
                raise ValueError('Invalid Qt layout settings')
            folders = value.get('board_folders', [])
            if not isinstance(folders, list) or not all(isinstance(f, dict) and
                    isinstance(f.get('id'), str) and isinstance(f.get('name'), str) and
                    isinstance(f.get('parent', ''), str) for f in folders):
                raise ValueError('Invalid soundboard folders')
            value.setdefault('preset_locations', {})
            value.setdefault('board_folders', [])
            if not all(isinstance(k, str) and isinstance(v, str)
                       for k, v in value['preset_locations'].items()):
                raise ValueError('Invalid preset folder locations')
            if not isinstance(value.get('board_name', ''), str) or not isinstance(value.get('mode', ''), str):
                raise ValueError('Invalid board selection')
            ids = [f['id'] for f in folders]
            if len(set(ids)) != len(ids) or any(not key for key in ids):
                raise ValueError('Invalid soundboard folder identifiers')
            return value
        except (OSError, ValueError, TypeError) as exc:
            self.layout_error = f'qt-layout.json has been preserved: {exc}'
            return default

    def valid_ids(self, ids):
        known = {c['id'] for c in self.store.clips}
        return list(dict.fromkeys(k for k in ids if isinstance(k, str) and k in known)) if isinstance(ids, list) else []

    def clip(self, key):
        return next((c for c in self.store.clips if c['id'] == key), None)

    def error(self, message):
        QMessageBox.warning(self, 'Offsec Call Client', str(message))

    def persist(self):
        try:
            self.store.save(self.outputs.currentText() or self.saved_device, self.volume.value())
            if self.layout_error:
                raise ValueError(self.layout_error)
            self.layout_data.update(board=self.board_ids, board_name=self.board_name,
                                    dirty=self.dirty, mode=self.mode)
            temp = self.layout_path.with_suffix('.tmp')
            temp.write_text(json.dumps(self.layout_data, indent=2, ensure_ascii=False), encoding='utf-8')
            temp.replace(self.layout_path)
            return True
        except (OSError, ValueError) as exc:
            self.status.setText('Could not save: ' + str(exc))
            return False

    def build_ui(self):
        body = QWidget()
        self.setCentralWidget(body)
        outer = QVBoxLayout(body)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.split = QSplitter()
        outer.addWidget(self.split, 1)
        self.sidebar = QFrame()
        self.sidebar.setObjectName('sidebar')
        left = QVBoxLayout(self.sidebar)
        left.setContentsMargins(16, 22, 16, 16)
        left.setSpacing(14)
        switch = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        self.mode_buttons = {}
        for key, title in (('files', 'Files'), ('boards', 'Soundboards')):
            tab = button(title, lambda checked=False, k=key: self.set_mode(k))
            tab.setCheckable(True)
            tab.setObjectName('browserTab')
            self.mode_group.addButton(tab)
            self.mode_buttons[key] = tab
            switch.addWidget(tab)
        left.addLayout(switch)
        tools = QHBoxLayout()
        tools.addWidget(button('New folder', self.new_folder))
        self.save_as_button = button('Save as…', self.save_board_as)
        tools.addWidget(self.save_as_button)
        left.addLayout(tools)
        self.browser = Browser(self)
        self.browser.itemClicked.connect(self.browser_click)
        left.addWidget(self.browser, 1)
        self.directory_button = button('Browse folder…', self.pick_directory)
        left.addWidget(self.directory_button)
        self.browser_hint = QLabel()
        self.browser_hint.setWordWrap(True)
        self.browser_hint.setObjectName('muted')
        left.addWidget(self.browser_hint)
        self.sidebar.setMinimumWidth(240)
        self.split.addWidget(self.sidebar)
        main = QWidget()
        center = QVBoxLayout(main)
        center.setContentsMargins(26, 26, 26, 20)
        center.setSpacing(15)
        heading = QHBoxLayout()
        title = QVBoxLayout()
        title.addWidget(QLabel('SOUNDBOARD', objectName='eyebrow'))
        self.title_label = QLabel('Soundboard')
        self.title_label.setObjectName('boardTitle')
        title.addWidget(self.title_label)
        heading.addLayout(title, 1)
        heading.addWidget(button('New board', self.new_board))
        heading.addWidget(button('Save', self.save_board))
        center.addLayout(heading)
        self.board_area = BoardArea(self)
        center.addWidget(self.board_area, 1)
        self.empty_label = QLabel('Drag audio files from the browser onto the board')
        self.empty_label.setObjectName('muted')
        center.addWidget(self.empty_label)
        self.split.addWidget(main)
        self.split.setSizes([260, 880])
        self.split.setStretchFactor(1, 1)
        route = QFrame()
        route.setObjectName('routeBar')
        bottom = QHBoxLayout(route)
        bottom.setContentsMargins(16, 12, 16, 12)
        bottom.addWidget(QLabel('Output'))
        self.outputs = QComboBox()
        self.outputs.setMinimumWidth(180)
        self.outputs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.outputs.currentIndexChanged.connect(self.change_device)
        bottom.addWidget(self.outputs, 1)
        bottom.addWidget(button('Refresh', self.refresh_devices))
        bottom.addWidget(QLabel('Volume'))
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setAccessibleName('Output volume')
        self.volume.setRange(0, 100)
        self.volume.setValue(int(self.store.volume))
        self.volume.setFixedWidth(100)
        self.volume.valueChanged.connect(lambda value: self.engine.set_volume(value / 100))
        self.volume.sliderReleased.connect(self.persist)
        bottom.addWidget(self.volume)
        bottom.addWidget(button('MicroSIP', self.open_microsip))
        outer.addWidget(route)
        status_row = QHBoxLayout()
        status_row.setContentsMargins(16, 7, 16, 9)
        self.status = QLabel('Ready · one clip at a time')
        self.status.setWordWrap(True)
        self.status.setObjectName('muted')
        status_row.addWidget(self.status, 1)
        self.cancel_button = button('Cancel import', self.import_cancel.set)
        self.cancel_button.hide()
        status_row.addWidget(self.cancel_button)
        outer.addLayout(status_row)
        menu = self.menuBar().addMenu('Application')
        menu.addAction('Open MicroSIP', self.open_microsip)
        menu.addAction('Get VB-CABLE', self.install_vbcable)
        menu.addAction('Audio routing help', self.routing_help)
        menu.addSeparator()
        menu.addAction('Quit', self.close)

    def apply_theme(self):
        dark = QApplication.palette().window().color().lightness() < 128
        bg, side, panel, ink, muted, line, soft, accent = (
            ('#16191f', '#13161b', '#1d2129', '#edf0f6', '#a3adbc', '#343b48', '#243552', '#92b4ff')
            if dark else ('#f6f7f9', '#eceef2', '#ffffff', '#202631', '#616b7b', '#dce1e8', '#e8efff', '#315dcc'))
        self.setStyleSheet(f'''
            QWidget {{ font-family: "Segoe UI"; font-size: 13px; color: {ink}; }}
            QMainWindow, QMainWindow > QWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {bg}; }}
            #sidebar, #routeBar {{ background: {side}; }}
            QPushButton {{ background: {panel}; border: 1px solid {line}; border-radius: 6px; padding: 8px 11px; }}
            QPushButton:hover {{ background: {soft}; }}
            QPushButton:focus {{ border: 1px solid {accent}; }}
            QPushButton:disabled {{ color: {muted}; }}
            #browserTab {{ background: transparent; border: none; }}
            #browserTab:checked {{ background: {panel}; }}
            #boardTitle {{ font-size: 25px; font-weight: 500; }}
            #eyebrow {{ font-size: 11px; color: {muted}; }}
            #muted {{ color: {muted}; font-size: 12px; }}
            QTreeWidget {{ border: none; background: transparent; outline: none; }}
            QTreeWidget::item {{ padding: 7px 2px; }}
            QTreeWidget::item:selected {{ background: {soft}; color: {ink}; }}
            #soundPad {{ background: {panel}; border: 1px solid {line}; border-radius: 10px; }}
            #padLaunch {{ background: transparent; border: none; font-size: 15px; font-weight: 500; }}
            #padLaunch:hover {{ background: {soft}; }}
            #padPlayer {{ background: {soft}; border-radius: 9px; }}
            QComboBox {{ background: {panel}; border: 1px solid {line}; padding: 7px; border-radius: 5px; }}
            QSlider::groove:horizontal {{ height: 4px; background: {line}; border: none; border-radius: 2px; }}
            QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: {accent}; width: 12px; margin: -5px 0; border-radius: 6px; }}
        ''')

    def set_mode(self, mode):
        self.mode = mode
        self.render_browser()
        self.persist()

    def browser_click(self, item, column):
        kind, key = item.data(0, ROLE)
        if kind == 'preset' and key != self.board_name:
            self.load_board(key)

    def render_browser(self):
        expanded = set()
        def visit(item):
            if item.isExpanded():
                expanded.add(tuple(item.data(0, ROLE)))
            for i in range(item.childCount()):
                visit(item.child(i))
        for i in range(self.browser.topLevelItemCount()):
            visit(self.browser.topLevelItem(i))
        self.browser.clear()
        self.mode_buttons[self.mode].setChecked(True)
        self.save_as_button.setVisible(self.mode == 'boards')
        self.directory_button.setVisible(self.mode == 'files')
        self.browser_hint.setText('Drop a directory or audio files here. Drag files onto the board.'
                                  if self.mode == 'files' else 'Click a soundboard to load it. Drag presets between folders.')
        root = QTreeWidgetItem(self.browser, ['Library' if self.mode == 'files' else 'Saved soundboards'])
        root.setData(0, ROLE, ('root' if self.mode == 'files' else 'board-root', ''))
        root.setExpanded(True)
        folder_list = self.store.folders if self.mode == 'files' else self.layout_data['board_folders']
        nodes = {'': root}
        for folder in folder_list:
            if folder['id'] not in nodes:
                item = QTreeWidgetItem([folder['name']])
                item.setData(0, ROLE, ('folder' if self.mode == 'files' else 'board-folder', folder['id']))
                item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
                nodes[folder['id']] = item
        for folder in folder_list:
            item = nodes[folder['id']]
            parent = folder.get('parent', '')
            # Reject cycles and unknown parents without losing the folder's contents.
            chain, cursor = {folder['id']}, parent
            while cursor in nodes and cursor:
                if cursor in chain:
                    parent = ''
                    break
                chain.add(cursor)
                cursor = next((f.get('parent', '') for f in folder_list if f['id'] == cursor), '')
            nodes.get(parent, root).addChild(item)
            item.setExpanded(tuple(item.data(0, ROLE)) in expanded)
        if self.mode == 'files':
            for clip in self.store.clips:
                item = QTreeWidgetItem(nodes.get(clip.get('folder', ''), root), [clip['name']])
                item.setData(0, ROLE, ('clip', clip['id']))
                item.setToolTip(0, clip.get('source_name', clip['name']))
                item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume))
        else:
            for board in self.store.soundboards:
                parent = self.layout_data['preset_locations'].get(board['name'], '')
                item = QTreeWidgetItem(nodes.get(parent, root), [board['name']])
                item.setData(0, ROLE, ('preset', board['name']))
                item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
                if board['name'] == self.board_name:
                    self.browser.setCurrentItem(item)

    def current_folder(self):
        item = self.browser.currentItem()
        if not item:
            return ''
        kind, key = item.data(0, ROLE)
        if kind in ('folder', 'board-folder'):
            return key
        if kind == 'clip':
            return self.clip(key).get('folder', '')
        if kind == 'preset':
            return self.layout_data['preset_locations'].get(key, '')
        return ''

    def new_folder(self):
        name, ok = QInputDialog.getText(self, 'New folder', 'Folder name:')
        if not ok or not name.strip():
            return
        folders = self.store.folders if self.mode == 'files' else self.layout_data['board_folders']
        parent = self.current_folder()
        if any(f['name'].casefold() == name.strip().casefold() and f.get('parent', '') == parent for f in folders):
            self.error('A folder with this name already exists here.')
            return
        folder = {'id': uuid4().hex, 'name': name.strip(), 'parent': parent}
        folders.append(folder)
        self.persist()
        self.render_browser()

    def rename_item(self):
        item = self.browser.currentItem()
        if not item:
            return
        kind, key = item.data(0, ROLE)
        name, ok = QInputDialog.getText(self, 'Rename', 'Name:', text=item.text(0))
        if not ok or not name.strip():
            return
        name = name.strip()
        if kind in ('folder', 'board-folder'):
            folders = self.store.folders if kind == 'folder' else self.layout_data['board_folders']
            record = next(f for f in folders if f['id'] == key)
            if any(f['id'] != key and f['name'].casefold() == name.casefold() and
                   f.get('parent', '') == record.get('parent', '') for f in folders):
                return self.error('This folder name is already in use.')
            record['name'] = name
        elif kind == 'clip':
            self.clip(key)['name'] = name
        elif kind == 'preset':
            if any(b['name'].casefold() == name.casefold() and b['name'] != key for b in self.store.soundboards):
                return self.error('This preset name is already in use.')
            next(b for b in self.store.soundboards if b['name'] == key)['name'] = name
            location = self.layout_data['preset_locations'].pop(key, '')
            self.layout_data['preset_locations'][name] = location
            if self.board_name == key:
                self.board_name = name
                self.store.active_soundboard = name
        self.persist()
        self.render_browser()
        self.render_board()

    def remove_item(self):
        item = self.browser.currentItem()
        if not item:
            return
        kind, key = item.data(0, ROLE)
        if kind in ('folder', 'board-folder'):
            folders = self.store.folders if kind == 'folder' else self.layout_data['board_folders']
            if item.childCount():
                return self.error('Move or remove this folder’s contents first.')
            folders[:] = [f for f in folders if f['id'] != key]
        elif kind == 'clip':
            if self.active_clip == key:
                self.stop()
            self.store.clips[:] = [c for c in self.store.clips if c['id'] != key]
            self.board_ids = [c for c in self.board_ids if c != key]
            for board in self.store.soundboards:
                board['clips'] = [c for c in board['clips'] if c != key]
        elif kind == 'preset':
            self.store.soundboards[:] = [b for b in self.store.soundboards if b['name'] != key]
            self.layout_data['preset_locations'].pop(key, None)
            if self.board_name == key:
                self.board_name = ''
                self.store.active_soundboard = ''
                self.dirty = True
        self.persist()
        self.render_browser()
        self.render_board()

    def render_board(self):
        for pad in self.pads:
            self.board_area.grid.removeWidget(pad)
            pad.deleteLater()
        self.pads = []
        self.board_ids = self.valid_ids(self.board_ids)
        for index, key in enumerate(self.board_ids):
            self.pads.append(Pad(self, key, index))
        self.title_label.setText((self.board_name or 'Untitled board') + (' *' if self.dirty else ''))
        self.empty_label.setText('Drag audio files from the browser onto the board' if not self.pads
                                 else 'Drop onto the board to add · drop onto a pad to replace · Escape to stop')
        self.board_area.arrange()

    @staticmethod
    def mime_ids(mime, kind):
        try:
            result = json.loads(bytes(mime.data(kind)).decode('utf-8'))
            return [k for k in result if isinstance(k, str)] if isinstance(result, list) else []
        except (ValueError, UnicodeError):
            return []

    def board_drop(self, mime, slot=None):
        if mime.hasFormat(CLIP_MIME):
            self.add_to_board(self.mime_ids(mime, CLIP_MIME), slot)
        elif mime.hasUrls():
            self.start_import([u.toLocalFile() for u in mime.urls() if u.isLocalFile()],
                              add_to_board=True, slot=slot)

    def add_to_board(self, ids, slot=None):
        ids = self.valid_ids(ids)
        if not ids:
            return
        if slot is not None and 0 <= slot < len(self.board_ids):
            removed = self.board_ids[slot]
            if removed == self.active_clip:
                self.stop()
            # One pad per clip: dropping an existing pad moves it to this position.
            first = ids.pop(0)
            self.board_ids = [k for i, k in enumerate(self.board_ids) if i != slot and k != first]
            self.board_ids.insert(min(slot, len(self.board_ids)), first)
        self.board_ids.extend(k for k in ids if k not in self.board_ids)
        self.dirty = True
        self.persist()
        self.render_board()

    def remove_pad(self, index):
        if self.board_ids[index] == self.active_clip:
            self.stop()
        self.board_ids.pop(index)
        self.dirty = True
        self.persist()
        self.render_board()

    def confirm_switch(self):
        if not self.dirty:
            return True
        answer = QMessageBox.question(self, 'Unsaved soundboard', 'Save the current board before switching?',
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
                                      QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        return self.save_board() if answer == QMessageBox.StandardButton.Save else True

    def new_board(self):
        if not self.confirm_switch():
            return
        self.stop()
        self.board_name, self.board_ids, self.dirty = '', [], False
        self.store.active_soundboard = ''
        self.persist()
        self.render_board()

    def load_board(self, name):
        if not self.confirm_switch():
            return
        board = next((b for b in self.store.soundboards if b['name'] == name), None)
        if board:
            self.stop()
            self.board_ids = board['clips'].copy()
            self.board_name = self.store.active_soundboard = name
            self.dirty = False
            self.persist()
            self.render_board()
            self.render_browser()

    def save_board(self):
        board = next((b for b in self.store.soundboards if b['name'] == self.board_name), None)
        if board is None:
            return self.save_board_as()
        board['clips'] = self.board_ids.copy()
        self.dirty = False
        saved = self.persist()
        self.render_board()
        if not saved:
            self.dirty = True
            self.error('Could not save the board. ' + self.status.text())
        return saved

    def save_board_as(self):
        name, ok = QInputDialog.getText(self, 'Save soundboard', 'Soundboard name:')
        if not ok or not name.strip():
            return False
        name = name.strip()
        if any(b['name'].casefold() == name.casefold() for b in self.store.soundboards):
            self.error('A soundboard with this name already exists. Use Save to update it.')
            return False
        self.store.soundboards.append({'name': name, 'clips': self.board_ids.copy()})
        self.layout_data['preset_locations'][name] = self.current_folder() if self.mode == 'boards' else ''
        self.board_name = self.store.active_soundboard = name
        self.dirty = False
        saved = self.persist()
        self.render_browser()
        self.render_board()
        if not saved:
            self.dirty = True
            self.error('Could not save the board. ' + self.status.text())
        return saved

    def pick_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'Import audio files', '',
                                              'Audio and video (*.mp3 *.wav *.m4a *.flac *.ogg *.aac *.mp4 *.mov *.mkv);;All files (*)')
        self.start_import(paths, self.current_folder())

    def pick_directory(self):
        path = QFileDialog.getExistingDirectory(self, 'Import folder')
        if path:
            self.start_import([path], self.current_folder())

    def start_import(self, paths, folder='', add_to_board=False, slot=None, legacy=False):
        if not paths or self.closing:
            return
        if self.store.load_error or self.layout_error:
            return self.error(self.store.load_error or self.layout_error)
        if self.import_thread is not None:
            return self.error('An import is already running. Wait for it or cancel it first.')
        self.import_cancel = threading.Event()
        self.cancel_button.show()
        self.status.setText('Preparing import…')
        def run():
            count = 0
            errors = []
            try:
                def import_file(path, parent, explicit=False):
                    nonlocal count
                    if self.import_cancel.is_set():
                        raise AudioCancelled()
                    if not explicit and path.suffix.lower() not in MEDIA:
                        return
                    self.events.put(('import-status', str(path.name)))
                    try:
                        clip = convert_media(path, self.store.media_dir, self.import_cancel)
                        clip['folder'] = parent
                        self.events.put(('import-clip', clip, str(path), add_to_board, slot if count == 0 else None, legacy))
                        count += 1
                    except AudioCancelled:
                        raise
                    except Exception as exc:
                        errors.append(f'{path.name}: {exc}')
                for raw in paths:
                    path = Path(raw)
                    if path.is_dir():
                        folder_map = {}
                        # Avoid following junctions/symlinks out of the dropped directory.
                        for current, dirs, filenames in os.walk(path, followlinks=False):
                            if self.import_cancel.is_set():
                                raise AudioCancelled()
                            current = Path(current)
                            dirs[:] = sorted(d for d in dirs if not (current / d).is_symlink()
                                             and (current / d).resolve().is_relative_to(path.resolve()))
                            rel = current.relative_to(path)
                            parent = folder if rel == Path('.') else folder_map.get(str(rel.parent), folder)
                            ident = uuid4().hex
                            folder_map[str(rel)] = ident
                            self.events.put(('import-folder', {'id': ident, 'name': current.name, 'parent': parent}))
                            for filename in sorted(filenames):
                                candidate = current / filename
                                if candidate.resolve().is_relative_to(path.resolve()):
                                    import_file(candidate, ident)
                    else:
                        import_file(path, folder, explicit=True)
            except AudioCancelled:
                pass
            except Exception as exc:
                errors.append(str(exc))
            finally:
                self.events.put(('import-done', count, errors, self.import_cancel.is_set()))
        self.import_thread = threading.Thread(target=run, daemon=True)
        self.import_thread.start()

    def refresh_devices(self):
        preferred = self.outputs.currentText() or self.saved_device
        self.stop()
        self.outputs.blockSignals(True)
        self.outputs.clear()
        try:
            devices = self.engine.devices()
            for ident, name in devices:
                self.outputs.addItem(name, ident)
            index = self.outputs.findText(preferred)
            if index < 0 and not preferred:
                index = next((i for i, (_, n) in enumerate(devices) if 'CABLE Input' in n), -1)
            self.outputs.setCurrentIndex(index)
            if index < 0:
                self.status.setText('Select an audio output. The saved output is unavailable.' if preferred else 'Select an audio output.')
        except Exception as exc:
            self.status.setText('Could not enumerate audio outputs: ' + str(exc))
        finally:
            self.outputs.blockSignals(False)

    def change_device(self):
        self.stop()
        if self.outputs.currentIndex() >= 0:
            self.saved_device = self.outputs.currentText()
        self.persist()

    def play_clip(self, key):
        if self.outputs.currentIndex() < 0:
            return self.error('Select an audio output first.')
        clip = self.clip(key)
        if not clip:
            return
        path = (self.store.media_dir / clip['file']).resolve()
        if not path.is_relative_to(self.store.media_dir.resolve()):
            return self.error('The managed audio path is outside the media directory.')
        self.stop()
        self.active_clip = key
        self.decoding = True
        self.decode_cancel = threading.Event()
        cancel = self.decode_cancel
        generation = self.decode_generation
        device = self.outputs.currentData()
        def run():
            try:
                import sounddevice as sd
                channels = min(2, int(sd.query_devices(device)['max_output_channels']))
                samples, rate = decode_pcm(path, channels=channels, cancel=cancel)
                self.events.put(('decoded', generation, key, samples, rate, path, device))
            except AudioCancelled:
                pass
            except Exception as exc:
                self.events.put(('decode-error', generation, str(exc)))
        thread = threading.Thread(target=run, daemon=True)
        self.decode_threads.append(thread)
        thread.start()
        for pad in self.pads:
            pad.update_player()

    def toggle_pause(self):
        self.engine.toggle_pause()
        for pad in self.pads:
            pad.update_player()

    def stop(self):
        self.decode_generation += 1
        self.decode_cancel.set()
        self.decoding = False
        self.active_clip = None
        self.engine.stop()
        for pad in self.pads:
            pad.update_player()

    def tick(self):
        self.decode_threads = [t for t in self.decode_threads if t.is_alive()]
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            kind, *args = event
            if kind == 'import-status':
                self.status.setText('Importing ' + args[0])
            elif kind == 'import-folder':
                self.store.folders.append(args[0])
                self.persist()
                self.render_browser()
            elif kind == 'import-clip':
                clip, source, add, slot, legacy = args
                self.store.clips.append(clip)
                if legacy and source in self.store.pending_legacy:
                    self.store.pending_legacy.remove(source)
                if add:
                    self.add_to_board([clip['id']], slot)
                self.persist()
                self.render_browser()
            elif kind == 'import-done':
                count, errors, cancelled = args
                self.import_thread = None
                self.cancel_button.hide()
                self.status.setText(f'{count} clip(s) imported' + (' · cancelled' if cancelled else '') +
                                    (f' · {len(errors)} failed' if errors else ''))
                if errors and not self.closing:
                    self.error('\n\n'.join(errors[:5]))
            elif kind == 'decoded':
                generation, key, samples, rate, path, device = args
                if generation == self.decode_generation and not self.closing:
                    self.decoding = False
                    try:
                        self.engine.play_samples(samples, rate, path, device)
                        self.status.setText('Playing ' + self.clip(key)['name'])
                    except Exception as exc:
                        self.stop()
                        self.error(exc)
            elif kind == 'decode-error' and args[0] == self.decode_generation:
                self.stop()
                if not self.closing:
                    self.error(args[1])
        if self.active_clip and not self.decoding and self.engine.state == 'Finished':
            self.stop()
            self.status.setText('Finished · ready')
        for pad in self.pads:
            pad.update_player()
        if self.closing and self.import_thread is None and not self.decode_threads:
            if self.store.load_error or self.layout_error or self.persist():
                self.allow_close = True
                self.close()
            else:
                self.closing = False
                self.setEnabled(True)
                self.error(self.status.text())

    def closeEvent(self, event):
        if self.allow_close:
            self.timer.stop()
            event.accept()
            return
        self.stop()
        self.import_cancel.set()
        if self.store.load_error or self.layout_error:
            # Nothing was imported into an unreadable library; preserve its files.
            if not self.decode_threads and self.import_thread is None:
                self.timer.stop()
                event.accept()
                return
        self.closing = True
        self.setEnabled(False)
        self.status.setText('Saving and closing…')
        event.ignore()

    def open_microsip(self):
        try:
            MicroSipBackend(self.root).show()
        except Exception as exc:
            self.error(exc)

    def install_vbcable(self):
        installer = self.root / 'VB-CABLE' / 'VBCABLE_Setup_x64.exe'
        if not installer.is_file():
            return self.error('VB-CABLE installer missing. Keep the bundled VB-CABLE directory beside the app.')
        result = ctypes.windll.shell32.ShellExecuteW(None, 'runas', str(installer), None, str(installer.parent), 1)
        if result <= 32:
            self.error('Windows could not open the VB-CABLE installer.')

    def routing_help(self):
        QMessageBox.information(self, 'Audio routing',
            'Choose CABLE Input as this app’s output. In MicroSIP, choose CABLE Output as the microphone. '
            'Keep speakers and ringing on your headset.\n\nDrag a directory into Files, then drag audio onto '
            'the board. Click a pad to play. The pad becomes its own player; Stop or Escape restores the name. '
            'Use Soundboards to save and load presets. Source files are never changed.')


def main():
    if '--smoke-test' in sys.argv:
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    app = QApplication(sys.argv)
    app.setApplicationName('Offsec Call Client')
    if '--smoke-test' in sys.argv:
        from qt_smoke import run
        index = sys.argv.index('--smoke-test')
        output = Path(sys.argv[index + 1])
        return run(app, App, output)
    window = App(launch_microsip='--no-microsip' not in sys.argv)
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
