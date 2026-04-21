# coding=utf-8
import os
import sys
from pathlib import Path


def _iterCandidateRoots():
    seen = set()

    for envName in ('QGIS_PREFIX_PATH', 'QGIS_ROOT', 'OSGEO4W_ROOT'):
        value = os.environ.get(envName)
        if not value:
            continue

        path = Path(value)
        if envName == 'QGIS_PREFIX_PATH' and path.name.lower() in ('apps', 'share'):
            continue

        resolved = str(path)
        if resolved not in seen:
            seen.add(resolved)
            yield path

    programFiles = Path('C:/Program Files')
    if programFiles.exists():
        qgisDirs = sorted(
            (path for path in programFiles.iterdir() if path.is_dir() and path.name.startswith('QGIS')),
            reverse=True,
        )
        for path in qgisDirs:
            resolved = str(path)
            if resolved not in seen:
                seen.add(resolved)
                yield path

    for fallback in (Path('C:/OSGeo4W'), Path('C:/OSGeo4W64')):
        if fallback.exists():
            resolved = str(fallback)
            if resolved not in seen:
                seen.add(resolved)
                yield fallback


def _iterCandidateAppDirs(root: Path):
    if (root / 'python' / 'qgis' / '__init__.py').exists():
        yield root

    for childDirName in ('apps', 'share'):
        childDir = root / childDirName
        if not childDir.exists():
            continue

        for appDir in sorted((path for path in childDir.iterdir() if path.is_dir()), reverse=True):
            if (appDir / 'python' / 'qgis' / '__init__.py').exists():
                yield appDir


def _prependSysPath(path: Path):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)


def _prependEnvPath(path: Path):
    text = str(path)
    current = os.environ.get('PATH', '')
    entries = current.split(os.pathsep) if current else []
    if text not in entries:
        os.environ['PATH'] = text + os.pathsep + current if current else text


def ensureQgisAvailable():
    try:
        import qgis  # pylint: disable=W0611  # NOQA
        return True
    except ModuleNotFoundError:
        pass

    for root in _iterCandidateRoots():
        for appDir in _iterCandidateAppDirs(root):
            pythonDir = appDir / 'python'
            pluginDir = pythonDir / 'plugins'
            binDir = appDir / 'bin'

            _prependSysPath(pythonDir)
            if pluginDir.exists():
                _prependSysPath(pluginDir)

            if binDir.exists():
                _prependEnvPath(binDir)
                addDllDirectory = getattr(os, 'add_dll_directory', None)
                if callable(addDllDirectory):
                    try:
                        addDllDirectory(str(binDir))
                    except (FileNotFoundError, OSError):
                        pass

            os.environ.setdefault('QGIS_PREFIX_PATH', str(appDir))

            try:
                import qgis  # pylint: disable=W0611  # NOQA
                return True
            except ModuleNotFoundError:
                continue

    return False