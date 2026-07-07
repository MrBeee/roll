import contextlib
import weakref

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QApplication

_CURSOR_DEPTH = weakref.WeakKeyDictionary()
_CURSOR_PREVIOUS = weakref.WeakKeyDictionary()


def clearBusyCursorOverrides():
    try:
        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
    except RuntimeError:
        return


def clearBusyCursorOverridesIfIdle(*widgets):
    if QApplication.overrideCursor() is None:
        return

    app = QApplication.instance()
    if app is None:
        clearBusyCursorOverrides()
        return

    candidateWidgets = [widget for widget in widgets if widget is not None]

    activeWindow = app.activeWindow()
    if activeWindow is not None:
        candidateWidgets.append(activeWindow)

    focusWidget = app.focusWidget()
    if focusWidget is not None:
        candidateWidgets.append(focusWidget)

    guiThread = app.thread()

    for widget in candidateWidgets:
        thread = getattr(widget, 'thread', None)
        if thread is None:
            continue

        try:
            threadObj = thread()
            # QObject.thread() for widgets points to the GUI thread, which is
            # always running. Only non-GUI running threads should block clear.
            if threadObj is not None and threadObj is not guiThread and threadObj.isRunning():
                return
        except RuntimeError:
            continue

    clearBusyCursorState(*candidateWidgets)


def clearBusyCursorState(*widgets):
    clearBusyCursorOverrides()

    app = QApplication.instance()
    if app is None:
        return

    candidateWidgets = []
    for widget in widgets:
        if widget is not None:
            candidateWidgets.append(widget)

    activeWindow = app.activeWindow()
    if activeWindow is not None:
        candidateWidgets.append(activeWindow)

    focusWidget = app.focusWidget()
    if focusWidget is not None:
        candidateWidgets.append(focusWidget)

    candidateWidgets.extend(app.topLevelWidgets())

    seen = set()
    for widget in candidateWidgets:
        widgetId = id(widget)
        if widgetId in seen:
            continue
        seen.add(widgetId)

        try:
            cursorShape = widget.cursor().shape()
        except RuntimeError:
            continue

        if cursorShape in (Qt.CursorShape.WaitCursor, Qt.CursorShape.BusyCursor):
            try:
                widget.unsetCursor()
            except RuntimeError:
                continue


@contextlib.contextmanager
def busyCursor(widget=None):
    if widget is None:
        app = QApplication.instance()
        widget = app.activeWindow() if app is not None else None

    if widget is None:
        yield
        return

    depth = _CURSOR_DEPTH.get(widget, 0)

    try:
        if depth == 0:
            hadCursor = widget.testAttribute(Qt.WidgetAttribute.WA_SetCursor)
            previousCursor = widget.cursor() if hadCursor else None
            _CURSOR_PREVIOUS[widget] = (hadCursor, previousCursor)
            widget.setCursor(Qt.CursorShape.WaitCursor)
    except RuntimeError:
        yield
        return

    _CURSOR_DEPTH[widget] = depth + 1
    try:
        yield
    finally:
        try:
            currentDepth = _CURSOR_DEPTH.get(widget, 1) - 1
            if currentDepth > 0:
                _CURSOR_DEPTH[widget] = currentDepth
            else:
                _CURSOR_DEPTH.pop(widget, None)
                hadCursor, previousCursor = _CURSOR_PREVIOUS.pop(widget, (False, None))
                if hadCursor and previousCursor is not None:
                    widget.setCursor(previousCursor)
                else:
                    widget.unsetCursor()
        except RuntimeError:
            _CURSOR_DEPTH.pop(widget, None)
            _CURSOR_PREVIOUS.pop(widget, None)
