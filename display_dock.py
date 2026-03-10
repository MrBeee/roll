# display_dock.py
# -*- coding: utf-8 -*-

"""Builders for the RollMainWindow display dock."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QKeySequence
from qgis.PyQt.QtWidgets import (QActionGroup, QDockWidget, QGroupBox,
                                 QHBoxLayout, QPushButton, QToolButton,
                                 QVBoxLayout, QWidget)

from .aux_classes import QHLine
from .config import dockWidgetTitleStyle, exportButtonStyle, toolButtonStyle


def createDisplayDock(window):
    """Construct the geometry/analysis display dock for RollMainWindow."""
    return _DisplayDockBuilder(window).build()


class _DisplayDockBuilder:
    def __init__(self, window):
        self.w = window
        self.centralColumn = QVBoxLayout()

    def build(self):
        self._initShell()
        self._buildGeometrySection()
        self._buildAnalysisSection()
        self._buildExportSection()
        self._composeLayout()
        self._finalize()
        return self.w.dockDisplay

    def _initShell(self):
        self.w.dockDisplay = QDockWidget('Display pane', self.w)
        self.w.dockDisplay.setObjectName('dockDisplay')
        self.w.dockDisplay.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.w.dockDisplay.setStyleSheet(dockWidgetTitleStyle)

        self.w.geometryChoice = QGroupBox('Geometry to display')
        self.w.analysisChoice = QGroupBox('Analysis to display')
        self.w.analysisToQgis = QGroupBox('Export to QGIS')

        for box in (self.w.geometryChoice, self.w.analysisChoice, self.w.analysisToQgis):
            box.setMinimumWidth(140)
            box.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.w.displayLayout = QHBoxLayout()
        self.w.displayLayout.addStretch()
        self.w.displayLayout.addLayout(self.centralColumn)
        self.w.displayLayout.addStretch()

    def _buildGeometrySection(self):
        w = self.w
        w.tbTemplat = self._toggleButton(w.actionTemplates, textOnly=True)
        w.tbRecList = self._toggleButton(w.actionRecPoints)
        w.tbSrcList = self._toggleButton(w.actionSrcPoints)
        w.tbRpsList = self._toggleButton(w.actionRpsPoints)
        w.tbSpsList = self._toggleButton(w.actionSpsPoints)
        w.tbAllList = self._toggleButton(w.actionAllPoints)

        w.actionTemplates.setChecked(True)
        w.actionShowPatterns.setChecked(True)
        w.actionShowCmpArea.setChecked(True)
        w.actionShowSrcArea.setChecked(True)
        w.actionShowSrcLines.setChecked(True)
        w.actionShowSrcPoints.setChecked(True)
        w.actionShowSrcPatterns.setChecked(True)
        w.actionShowRecArea.setChecked(True)
        w.actionShowRecLines.setChecked(True)
        w.actionShowRecPoints.setChecked(True)
        w.actionShowRecPatterns.setChecked(True)

        w.setupPaintActions()
        w.paintMode = QActionGroup(w)
        for action in (w.actionShowBlocks, w.actionShowTemplates, w.actionShowLines, w.actionShowPoints, w.actionShowPatterns):
            w.paintMode.addAction(action)

        for action in (w.actionRecPoints, w.actionSrcPoints, w.actionRpsPoints, w.actionSpsPoints):
            action.setEnabled(False)
        w.actionAllPoints.setEnabled(False)
        w.actionAllPoints.setChecked(True)

        layout = QVBoxLayout()
        layout.addWidget(w.tbTemplat)
        layout.addWidget(w.tbRecList)
        layout.addWidget(w.tbSrcList)
        layout.addWidget(w.tbRpsList)
        layout.addWidget(w.tbSpsList)
        layout.addWidget(QHLine())
        layout.addWidget(w.tbAllList)

        w.geometryChoice.setLayout(layout)

    def _buildAnalysisSection(self):
        w = self.w
        w.tbNone = self._toggleButton(w.actionNone)
        w.tbArea = self._toggleButton(w.actionArea)
        w.tbFold = self._toggleButton(w.actionFold)
        w.tbMinO = self._toggleButton(w.actionMinO)
        w.tbMaxO = self._toggleButton(w.actionMaxO)
        w.tbRmsO = self._toggleButton(w.actionRmsO)

        w.actionArea.setChecked(True)

        w.tbSpider = self._toggleButton(w.actionSpider, textOnly=True)
        w.btnSpiderLt = self._navButton(w.actionMoveLt)
        w.btnSpiderRt = self._navButton(w.actionMoveRt)
        w.btnSpiderUp = self._navButton(w.actionMoveUp)
        w.btnSpiderDn = self._navButton(w.actionMoveDn)

        w.actionMoveLt.setShortcuts(['Alt+Left', 'Alt+Shift+Left', 'Alt+Ctrl+Left', 'Alt+Shift+Ctrl+Left'])
        w.actionMoveRt.setShortcuts(['Alt+Right', 'Alt+Shift+Right', 'Alt+Ctrl+Right', 'Alt+Shift+Ctrl+Right'])
        w.actionMoveUp.setShortcuts(['Alt+Up', 'Alt+Shift+Up', 'Alt+Ctrl+Up', 'Alt+Shift+Ctrl+Up'])
        w.actionMoveDn.setShortcuts(['Alt+Down', 'Alt+Shift+Down', 'Alt+Ctrl+Down', 'Alt+Shift+Ctrl+Down'])
        w.setupSpiderActions()

        w.analysisActionGroup = QActionGroup(w)
        for action in (w.actionNone, w.actionArea, w.actionFold, w.actionMinO, w.actionMaxO, w.actionRmsO):
            w.analysisActionGroup.addAction(action)

        w.actionNone.triggered.connect(w.onActionNoneTriggered)
        w.actionArea.triggered.connect(w.onActionAreaTriggered)
        w.actionFold.triggered.connect(w.onActionFoldTriggered)
        w.actionMinO.triggered.connect(w.onActionMinOTriggered)
        w.actionMaxO.triggered.connect(w.onActionMaxOTriggered)
        w.actionRmsO.triggered.connect(w.onActionRmsOTriggered)

        layout = QVBoxLayout()
        for button in (w.tbNone, w.tbArea, w.tbFold, w.tbMinO, w.tbMaxO, w.tbRmsO):
            layout.addWidget(button)
        layout.addWidget(QHLine())
        layout.addWidget(w.tbSpider)

        nav = QHBoxLayout()
        nav.addStretch()
        for btn in (w.btnSpiderLt, w.btnSpiderRt, w.btnSpiderUp, w.btnSpiderDn):
            nav.addWidget(btn)
        nav.addStretch()
        layout.addLayout(nav)

        w.analysisChoice.setLayout(layout)

    def _buildExportSection(self):
        w = self.w
        w.btnBinToQGIS = self._exportButton('Fold Map')
        w.btnMinToQGIS = self._exportButton('Min Offset')
        w.btnMaxToQGIS = self._exportButton('Max Offset')
        w.btnRmsToQGIS = self._exportButton('Rms Offset')

        layout = QVBoxLayout()
        layout.addWidget(w.btnBinToQGIS)
        layout.addWidget(w.btnMinToQGIS)
        layout.addWidget(w.btnMaxToQGIS)
        layout.addWidget(w.btnRmsToQGIS)
        w.analysisToQgis.setLayout(layout)

    def _composeLayout(self):
        column = self.centralColumn
        column.addStretch()
        column.addWidget(self.w.geometryChoice)
        column.addStretch()
        column.addWidget(self.w.analysisChoice)
        column.addStretch()
        column.addWidget(self.w.analysisToQgis)
        column.addStretch()

    def _finalize(self):
        w = self.w
        w.displayWidget = QWidget()
        w.displayWidget.setLayout(w.displayLayout)
        w.dockDisplay.setWidget(w.displayWidget)

        w.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, w.dockDisplay)
        toggle = w.dockDisplay.toggleViewAction()
        toggle.setShortcut(QKeySequence('Ctrl+Alt+d'))
        w.menuView.addAction(toggle)

    # def _toggleButton(self, action, *, textOnly=False):
    #     btn = QToolButton()
    #     btn.setMinimumWidth(110)
    #     btn.setStyleSheet(toolButtonStyle)
    #     if textOnly:
    #         btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
    #     btn.setDefaultAction(action)
    #     return btn

    def _toggleButton(self, action, *, textOnly=False):
        btn = QToolButton()
        btn.setMinimumWidth(110)
        btn.setAutoRaise(False)
        btn.setCheckable(True)
        if action is not None:
            action.setCheckable(True)
        btn.setStyleSheet(toolButtonStyle)
        if textOnly:
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        btn.setDefaultAction(action)
        return btn

    # def _navButton(self, action):
    #     btn = QToolButton()
    #     btn.setStyleSheet(toolButtonStyle)
    #     btn.setDefaultAction(action)
    #     return btn

    def _navButton(self, action):
        btn = QToolButton()
        btn.setAutoRaise(False)
        btn.setStyleSheet(toolButtonStyle)
        btn.setDefaultAction(action)
        return btn

    def _exportButton(self, label):
        btn = QPushButton(label)
        btn.setMinimumWidth(110)
        btn.setStyleSheet(exportButtonStyle)
        return btn
