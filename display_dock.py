# display_dock.py
# -*- coding: utf-8 -*-

"""Builders for the RollMainWindow display dock."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QKeySequence
from qgis.PyQt.QtWidgets import (QActionGroup, QDockWidget, QGroupBox,
                                 QHBoxLayout, QPushButton, QToolButton,
                                 QVBoxLayout, QWidget)

from .aux_classes import QHLine

TOOL_STYLE = (
    'QToolButton { selection-background-color: blue } '
    'QToolButton:checked { background-color: lightblue } '
    'QToolButton:pressed { background-color: red }'
)

EXPORT_STYLE = 'background-color:lightgoldenrodyellow; font-weight:bold;'


def create_display_dock(window):
    """Construct the geometry/analysis display dock for RollMainWindow."""
    return _DisplayDockBuilder(window).build()


class _DisplayDockBuilder:
    def __init__(self, window):
        self.w = window
        self._central_column = QVBoxLayout()

    def build(self):
        self._init_shell()
        self._build_geometry_section()
        self._build_analysis_section()
        self._build_export_section()
        self._compose_layout()
        self._finalize()
        return self.w.dockDisplay

    def _init_shell(self):
        self.w.dockDisplay = QDockWidget('Display pane', self.w)
        self.w.dockDisplay.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.w.dockDisplay.setStyleSheet('QDockWidget::title {background : lightblue;}')

        self.w.geometryChoice = QGroupBox('Geometry to display')
        self.w.analysisChoice = QGroupBox('Analysis to display')
        self.w.analysisToQgis = QGroupBox('Export to QGIS')

        for box in (self.w.geometryChoice, self.w.analysisChoice, self.w.analysisToQgis):
            box.setMinimumWidth(140)
            box.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.w.displayLayout = QHBoxLayout()
        self.w.displayLayout.addStretch()
        self.w.displayLayout.addLayout(self._central_column)
        self.w.displayLayout.addStretch()

    def _build_geometry_section(self):
        w = self.w
        w.tbTemplat = self._toggle_button(w.actionTemplates, text_only=True)
        w.tbRecList = self._toggle_button(w.actionRecPoints)
        w.tbSrcList = self._toggle_button(w.actionSrcPoints)
        w.tbRpsList = self._toggle_button(w.actionRpsPoints)
        w.tbSpsList = self._toggle_button(w.actionSpsPoints)
        w.tbAllList = self._toggle_button(w.actionAllPoints)

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

        w.setup_paint_actions()
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

    def _build_analysis_section(self):
        w = self.w
        w.tbNone = self._toggle_button(w.actionNone)
        w.tbArea = self._toggle_button(w.actionArea)
        w.tbFold = self._toggle_button(w.actionFold)
        w.tbMinO = self._toggle_button(w.actionMinO)
        w.tbMaxO = self._toggle_button(w.actionMaxO)
        w.tbRmsO = self._toggle_button(w.actionRmsO)

        w.actionArea.setChecked(True)

        w.tbSpider = self._toggle_button(w.actionSpider, text_only=True)
        w.btnSpiderLt = self._nav_button(w.actionMoveLt)
        w.btnSpiderRt = self._nav_button(w.actionMoveRt)
        w.btnSpiderUp = self._nav_button(w.actionMoveUp)
        w.btnSpiderDn = self._nav_button(w.actionMoveDn)

        w.actionMoveLt.setShortcuts(['Alt+Left', 'Alt+Shift+Left', 'Alt+Ctrl+Left', 'Alt+Shift+Ctrl+Left'])
        w.actionMoveRt.setShortcuts(['Alt+Right', 'Alt+Shift+Right', 'Alt+Ctrl+Right', 'Alt+Shift+Ctrl+Right'])
        w.actionMoveUp.setShortcuts(['Alt+Up', 'Alt+Shift+Up', 'Alt+Ctrl+Up', 'Alt+Shift+Ctrl+Up'])
        w.actionMoveDn.setShortcuts(['Alt+Down', 'Alt+Shift+Down', 'Alt+Ctrl+Down', 'Alt+Shift+Ctrl+Down'])
        w.setup_spider_actions()

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

    def _build_export_section(self):
        w = self.w
        w.btnBinToQGIS = self._export_button('Fold Map')
        w.btnMinToQGIS = self._export_button('Min Offset')
        w.btnMaxToQGIS = self._export_button('Max Offset')
        w.btnRmsToQGIS = self._export_button('Rms Offset')

        layout = QVBoxLayout()
        layout.addWidget(w.btnBinToQGIS)
        layout.addWidget(w.btnMinToQGIS)
        layout.addWidget(w.btnMaxToQGIS)
        layout.addWidget(w.btnRmsToQGIS)
        w.analysisToQgis.setLayout(layout)

    def _compose_layout(self):
        column = self._central_column
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
        w.menu_View.addAction(toggle)

    def _toggle_button(self, action, *, text_only=False):
        btn = QToolButton()
        btn.setMinimumWidth(110)
        btn.setStyleSheet(TOOL_STYLE)
        if text_only:
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        btn.setDefaultAction(action)
        return btn

    def _nav_button(self, action):
        btn = QToolButton()
        btn.setStyleSheet(TOOL_STYLE)
        btn.setDefaultAction(action)
        return btn

    def _export_button(self, label):
        btn = QPushButton(label)
        btn.setMinimumWidth(110)
        btn.setStyleSheet(EXPORT_STYLE)
        return btn
