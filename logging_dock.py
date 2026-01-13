# logging_dock.py
# -*- coding: utf-8 -*-

"""Builder for the RollMainWindow logging dock."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QKeySequence, QTextOption
from qgis.PyQt.QtWidgets import QDockWidget, QPlainTextEdit


def create_logging_dock(window):
    """Construct the logging dock for RollMainWindow."""
    return _LoggingDockBuilder(window).build()


class _LoggingDockBuilder:
    def __init__(self, window):
        self.w = window

    def build(self):
        self._init_shell()
        self._init_editor()
        self._finalize()
        return self.w.dockLogging

    def _init_shell(self):
        self.w.dockLogging = QDockWidget('Logging pane', self.w)
        areas = (
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.BottomDockWidgetArea
            | Qt.DockWidgetArea.TopDockWidgetArea
        )
        self.w.dockLogging.setAllowedAreas(areas)
        self.w.dockLogging.setStyleSheet('QDockWidget::title {background : lightblue;}')

    def _init_editor(self):
        log = QPlainTextEdit()
        log.clear()
        log.setUndoRedoEnabled(False)
        log.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        log.setWordWrapMode(QTextOption.WrapMode.NoWrap)
        log.setStyleSheet('QPlainTextEdit { font-family: Courier New; font-weight: bold; font-size: 12px;}')
        self.w.logEdit = log
        self.w.dockLogging.setWidget(log)

    def _finalize(self):
        self.w.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.w.dockLogging)
        toggle = self.w.dockLogging.toggleViewAction()
        toggle.setShortcut(QKeySequence('Ctrl+Alt+l'))
        self.w.menu_View.addAction(toggle)
