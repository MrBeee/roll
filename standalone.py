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


def _log_message(message):
    global _LOG_FILE
    if _LOG_FILE is None:
        _LOG_FILE = open(LOG_PATH, 'a', encoding='utf-8')
        faulthandler.enable(_LOG_FILE)

    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    _LOG_FILE.write(f'[{timestamp}] {message}\n')
    _LOG_FILE.flush()


def _close_log_file():
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
    qgis_site = os.path.join(sys.prefix, 'Lib', 'site-packages')
    if os.path.isdir(qgis_site):
        if qgis_site in sys.path:
            sys.path.remove(qgis_site)
        sys.path.insert(0, qgis_site)

    user_site = site.getusersitepackages()
    if user_site and user_site in sys.path:
        sys.path.remove(user_site)
        sys.path.append(user_site)


def dropUserPyqtgraphModules():
    user_site = site.getusersitepackages()
    if not user_site:
        return

    to_remove = []
    for name, module in sys.modules.items():
        module_path = getattr(module, '__file__', None)
        if not module_path:
            continue
        if name == 'pyqtgraph' or name.startswith('pyqtgraph.'):
            if os.path.normcase(module_path).startswith(os.path.normcase(user_site)):
                to_remove.append(name)

    for name in to_remove:
        sys.modules.pop(name, None)


def ensureQgisPyqtgraph():
    user_site = site.getusersitepackages()
    removed_user_site = False
    if user_site and user_site in sys.path:
        sys.path.remove(user_site)
        removed_user_site = True

    try:
        import pyqtgraph  # noqa: F401
    except ModuleNotFoundError as exc:
        if removed_user_site:
            sys.path.append(user_site)
            removed_user_site = False

        version_tag = f'Python{sys.version_info.major}{sys.version_info.minor}'
        user_site_ok = bool(user_site and version_tag.lower() in user_site.lower())
        if user_site_ok:
            import pyqtgraph  # noqa: F401
            return

        message = (
            'pyqtgraph is not available in the QGIS Python environment.\n'
            'Install it into the QGIS Python site-packages (not the user site-packages) and retry.\n'
            'Example: run "python-qgis.bat -m pip install pyqtgraph".'
        )
        raise RuntimeError(message) from exc
    finally:
        if removed_user_site:
            sys.path.append(user_site)


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
        _log_message(f"Top-level widgets: count={len(widgets)}")
        for w in widgets:
            try:
                title = w.windowTitle()
                className = w.metaObject().className() if w.metaObject() else type(w).__name__
                visible = w.isVisible()
                size = w.size()
                _log_message(f"  - {className} title='{title}' visible={visible} size={size.width()}x{size.height()}")
            except Exception as exc:
                _log_message(f"  - <error reading widget>: {exc}")
    except Exception as exc:
        _log_message(f"Failed to list top-level widgets: {exc}")

def main(argv=None):
    argv = sys.argv if argv is None else argv

    _log_message('Starting Roll standalone')
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
    exit_code = runStandalone(argv if argv is not None else sys.argv, filePath=filePath)
    logTopLevelWidgets()
    return exit_code

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SystemExit as exc:
        _log_message(f'SystemExit: {exc}')
        _close_log_file()
        raise
    except Exception:
        _log_message('Unhandled exception:\n' + traceback.format_exc())
        _close_log_file()
        raise
