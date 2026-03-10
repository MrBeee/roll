# property_dock.py
# -*- coding: utf-8 -*-

"""Builder for the RollMainWindow property dock."""

import pyqtgraph as pg
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QKeySequence
from qgis.PyQt.QtWidgets import (QDialogButtonBox, QDockWidget, QHeaderView,
                                 QVBoxLayout, QWidget)

from .config import dockWidgetTitleStyle


def createPropertyDock(window):
    """Construct the property dock for RollMainWindow."""
    return _PropertyDockBuilder(window).build()


class _PropertyDockBuilder:
    def __init__(self, window):
        self.w = window

    def build(self):
        self._initShell()
        self._initParameterTree()
        self._initButtons()
        self._finalize()
        return self.w.dockProperty

    def _initShell(self):
        w = self.w
        w.dockProperty = QDockWidget('Property pane', w)
        w.dockProperty.setObjectName('dockProperty')
        allowed = Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        w.dockProperty.setAllowedAreas(allowed)
        w.dockProperty.setStyleSheet(dockWidgetTitleStyle)
        w.propertyWidget = QWidget()
        w.propertyLayout = QVBoxLayout()
        w.propertyWidget.setLayout(w.propertyLayout)
        w.dockProperty.setWidget(w.propertyWidget)

    def _initParameterTree(self):
        w = self.w
        w.paramTree = pg.parametertree.ParameterTree(showHeader=True)
        header = w.paramTree.header()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.resizeSection(0, 280)
        w.propertyLayout.addWidget(w.paramTree)
        w.registerParameters()
        w.resetSurveyProperties()

    def _initButtons(self):
        w = self.w
        w.propertyLayout.addStretch()
        buttons = (
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        w.propertyButtonBox = QDialogButtonBox(buttons)
        w.propertyButtonBox.accepted.connect(w.applyPropertyChangesAndHide)
        w.propertyButtonBox.rejected.connect(w.resetSurveyProperties)
        w.propertyButtonBox.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(w.applyPropertyChanges)
        w.propertyLayout.addWidget(w.propertyButtonBox)

    def _finalize(self):
        w = self.w
        w.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, w.dockProperty)
        toggle = w.dockProperty.toggleViewAction()
        toggle.setShortcut(QKeySequence('Ctrl+Alt+p'))
        w.menuView.addAction(toggle)
