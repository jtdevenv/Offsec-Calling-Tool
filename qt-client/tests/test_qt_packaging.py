"""Prevent unrelated developer-tool ICU DLLs entering a Qt release."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import build_qt


class QtPackagingTests(unittest.TestCase):
    def test_build_does_not_inherit_foreign_dll_search_paths(self):
        with patch.dict(os.environ, {'PATH': r'C:\foreign\poppler;C:\unrelated\tool'}), \
             patch.object(build_qt.sys, 'version_info', (3, 14, 10)), \
             patch.object(build_qt.subprocess, 'run') as run:
            build_qt.build()
        env = run.call_args.kwargs['env']
        self.assertNotIn('poppler', env['PATH'])
        self.assertNotIn('unrelated', env['PATH'])
        self.assertIn(str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'System32'), env['PATH'])

    def test_old_system_python_cannot_build_qt_release(self):
        with patch.object(build_qt.sys, 'version_info', (3, 10, 11)):
            with self.assertRaisesRegex(SystemExit, '3.14.10'):
                build_qt.build()
