# coding=utf-8
"""Standalone runner for Roll plugin."""

import faulthandler
import os
import site
import sys
import tempfile
import time
import traceback

LOG_PATH = os.path.join(tempfile.gettempdir(), 'roll-standalone.log')
_LOG_FILE = None


def _logMessage(message):
    global _LOG_FILE
    if _LOG_FILE is None:
        _LOG_FILE = open(LOG_PATH, 'a', encoding='utf-8')
        faulthandler.enable(_LOG_FILE)

    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    _LOG_FILE.write(f'[{timestamp}] {message}\n')
    _LOG_FILE.flush()


def _closeLogFile():
    global _LOG_FILE
    if _LOG_FILE is None:
        return
    try:
        _LOG_FILE.flush()
    except Exception:
        pass
    try:
        _LOG_FILE.close()
    finally:
        _LOG_FILE = None


def ensureQgisPythonPaths():
    prefix = os.environ.get('QGIS_PREFIX_PATH') or os.environ.get('QGIS_PREFIX')
    if not prefix:
        return

    candidates = [
        os.path.join(prefix, 'python'),
        os.path.join(prefix, 'python', 'plugins'),
    ]
    for path in candidates:
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)



def preferQgisSitePackages():
    qgisSite = os.path.join(sys.prefix, 'Lib', 'site-packages')
    if os.path.isdir(qgisSite):
        if qgisSite in sys.path:
            sys.path.remove(qgisSite)
        sys.path.insert(0, qgisSite)

    userSite = site.getusersitepackages()
    if userSite and userSite in sys.path:
        sys.path.remove(userSite)
        sys.path.append(userSite)


def dropUserPyqtgraphModules():
    userSite = site.getusersitepackages()
    if not userSite:
        return

    toRemove = []
    for name, module in sys.modules.items():
        modulePath = getattr(module, '__file__', None)
        if not modulePath:
            continue
        if name == 'pyqtgraph' or name.startswith('pyqtgraph.'):
            if os.path.normcase(modulePath).startswith(os.path.normcase(userSite)):
                toRemove.append(name)

    for name in toRemove:
        sys.modules.pop(name, None)


def ensureQgisPyqtgraph():
    userSite = site.getusersitepackages()
    removedUserSite = False
    if userSite and userSite in sys.path:
        sys.path.remove(userSite)
        removedUserSite = True

    try:
        import pyqtgraph  # noqa: F401
    except ModuleNotFoundError as exc:
        if removedUserSite:
            sys.path.append(userSite)
            removedUserSite = False

        versionTag = f'Python{sys.version_info.major}{sys.version_info.minor}'
        userSiteOk = bool(userSite and versionTag.lower() in userSite.lower())
        if userSiteOk:
            import pyqtgraph  # noqa: F401
            return

        message = (
            'pyqtgraph is not available in the QGIS Python environment.\n'
            'Install it into the QGIS Python site-packages (not the user site-packages) and retry.\n'
            'Example: run "python-qgis.bat -m pip install pyqtgraph".'
        )
        raise RuntimeError(message) from exc
    finally:
        if removedUserSite:
            sys.path.append(userSite)


def configureQtBinding():
    from qgis.PyQt.QtCore import QT_VERSION_STR
    qtMajor = int((QT_VERSION_STR or '5').split('.')[0])
    if qtMajor >= 6:
        os.environ.setdefault('QT_API', 'pyqt6')
        os.environ.setdefault('PYQTGRAPH_QT_LIB', 'PyQt6')
    else:
        os.environ.setdefault('QT_API', 'pyqt5')
        os.environ.setdefault('PYQTGRAPH_QT_LIB', 'PyQt5')

def logTopLevelWidgets():
    try:
        from qgis.PyQt.QtWidgets import QApplication
        widgets = QApplication.topLevelWidgets()
        _logMessage(f"Top-level widgets: count={len(widgets)}")
        for w in widgets:
            try:
                title = w.windowTitle()
                className = w.metaObject().className() if w.metaObject() else type(w).__name__
                visible = w.isVisible()
                size = w.size()
                _logMessage(f"  - {className} title='{title}' visible={visible} size={size.width()}x{size.height()}")
            except Exception as exc:
                _logMessage(f"  - <error reading widget>: {exc}")
    except Exception as exc:
        _logMessage(f"Failed to list top-level widgets: {exc}")

def main(argv=None):
    argv = sys.argv if argv is None else argv

    _logMessage('Starting Roll standalone')
    ensureQgisPythonPaths()
    configureQtBinding()
    preferQgisSitePackages()
    dropUserPyqtgraphModules()
    ensureQgisPyqtgraph()

    filePath = None
    for arg in argv[1:]:
        if arg.lower().endswith('.roll') and os.path.isfile(arg):
            filePath = os.path.abspath(arg)
            break

    from .roll_main_window import runStandalone
    exitCode = runStandalone(argv if argv is not None else sys.argv, filePath=filePath)
    logTopLevelWidgets()
    return exitCode

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SystemExit as exc:
        _logMessage(f'SystemExit: {exc}')
        _closeLogFile()
        raise
    except Exception:
        _logMessage('Unhandled exception:\n' + traceback.format_exc())
        _closeLogFile()
        raise
