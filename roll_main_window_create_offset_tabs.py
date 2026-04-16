from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (QAction, QActionGroup, QFrame, QGroupBox,
                                 QHBoxLayout, QSplitter, QToolButton,
                                 QVBoxLayout)

from .config import toolButtonStyle


def _createOffsetTab(self, tab, plotWidget, prefix, triggerHandler):
    componentChoice = QGroupBox('Offset component')
    componentChoice.setMinimumWidth(140)
    componentChoice.setAlignment(Qt.AlignmentFlag.AlignHCenter)

    tbOffset = QToolButton()
    tbInline = QToolButton()
    tbXline = QToolButton()

    for button in (tbOffset, tbInline, tbXline):
        button.setMinimumWidth(110)
        button.setStyleSheet(toolButtonStyle)

    actionOffset = QAction('|offset|', self)
    actionOffset.setCheckable(True)
    actionOffset.setData(0)

    actionInline = QAction('Inline', self)
    actionInline.setCheckable(True)
    actionInline.setData(1)

    actionXline = QAction('X-line', self)
    actionXline.setCheckable(True)
    actionXline.setData(2)

    actionGroup = QActionGroup(self)
    actionGroup.setExclusive(True)
    actionGroup.addAction(actionOffset)
    actionGroup.addAction(actionInline)
    actionGroup.addAction(actionXline)
    actionOffset.setChecked(True)

    tbOffset.setDefaultAction(actionOffset)
    tbInline.setDefaultAction(actionInline)
    tbXline.setDefaultAction(actionXline)

    actionOffset.triggered.connect(triggerHandler)
    actionInline.triggered.connect(triggerHandler)
    actionXline.triggered.connect(triggerHandler)

    setattr(self, f'{prefix}ComponentChoice', componentChoice)
    setattr(self, f'tb{prefix}ComponentOffset', tbOffset)
    setattr(self, f'tb{prefix}ComponentInline', tbInline)
    setattr(self, f'tb{prefix}ComponentXline', tbXline)
    setattr(self, f'action{prefix}ComponentOffset', actionOffset)
    setattr(self, f'action{prefix}ComponentInline', actionInline)
    setattr(self, f'action{prefix}ComponentXline', actionXline)
    setattr(self, f'{prefix}ComponentActionGroup', actionGroup)

    controlsLayout = QVBoxLayout()
    controlsLayout.addWidget(tbOffset)
    controlsLayout.addWidget(tbInline)
    controlsLayout.addWidget(tbXline)
    componentChoice.setLayout(controlsLayout)

    leftLayout = QVBoxLayout()
    leftLayout.addStretch(2)
    leftLayout.addWidget(componentChoice)
    leftLayout.addStretch(10)

    leftWrapper = QHBoxLayout()
    leftWrapper.addStretch()
    leftWrapper.addLayout(leftLayout)
    leftWrapper.addStretch()

    leftSide = QFrame()
    leftSide.setFrameShape(QFrame.Shape.StyledPanel)
    leftSide.setLayout(leftWrapper)
    leftSide.setMaximumWidth(180)

    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.addWidget(leftSide)
    splitter.addWidget(plotWidget)
    splitter.setSizes([100, 500])

    tabLayout = tab.layout()
    if tabLayout is None:
        tabLayout = QHBoxLayout(tab)
        tabLayout.setContentsMargins(0, 0, 0, 0)
    else:
        while tabLayout.count():
            item = tabLayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    tabLayout.addWidget(splitter)


def createOffsetTabs(self):
    _createOffsetTab(self, self.tabOffTrk, self.offTrkWidget, 'OffTrk', self.onOffTrkComponentChanged)
    _createOffsetTab(self, self.tabOffBin, self.offBinWidget, 'OffBin', self.onOffBinComponentChanged)
