from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (QAction, QActionGroup, QFrame, QGroupBox,
                                 QHBoxLayout, QSplitter, QToolButton,
                                 QVBoxLayout)

from .config import toolButtonStyle


def createOffAziTab(self):
    self.offAziDisplayChoice = QGroupBox('Display method')
    self.offAziDisplayChoice.setMinimumWidth(140)
    self.offAziDisplayChoice.setAlignment(Qt.AlignmentFlag.AlignHCenter)

    self.tbOffAziRectangular = QToolButton()
    self.tbOffAziPolar = QToolButton()

    self.tbOffAziRectangular.setMinimumWidth(110)
    self.tbOffAziPolar.setMinimumWidth(110)

    self.tbOffAziRectangular.setStyleSheet(toolButtonStyle)
    self.tbOffAziPolar.setStyleSheet(toolButtonStyle)

    self.actionOffAziRectangular = QAction('Rectangular', self)
    self.actionOffAziRectangular.setCheckable(True)
    self.actionOffAziPolar = QAction('Polar', self)
    self.actionOffAziPolar.setCheckable(True)

    self.offAziActionGroup = QActionGroup(self)
    self.offAziActionGroup.setExclusive(True)
    self.offAziActionGroup.addAction(self.actionOffAziRectangular)
    self.offAziActionGroup.addAction(self.actionOffAziPolar)
    self.actionOffAziRectangular.setChecked(True)

    self.tbOffAziRectangular.setDefaultAction(self.actionOffAziRectangular)
    self.tbOffAziPolar.setDefaultAction(self.actionOffAziPolar)

    self.actionOffAziRectangular.triggered.connect(self.onOffAziDisplayMethodChanged)
    self.actionOffAziPolar.triggered.connect(self.onOffAziDisplayMethodChanged)

    controlsLayout = QVBoxLayout()
    controlsLayout.addWidget(self.tbOffAziRectangular)
    controlsLayout.addWidget(self.tbOffAziPolar)
    self.offAziDisplayChoice.setLayout(controlsLayout)

    leftLayout = QVBoxLayout()
    leftLayout.addStretch(2)
    leftLayout.addWidget(self.offAziDisplayChoice)
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
    splitter.addWidget(self.offAziWidget)
    splitter.setSizes([100, 500])

    tabLayout = self.tabOffAzi.layout()
    if tabLayout is None:
        tabLayout = QHBoxLayout(self.tabOffAzi)
        tabLayout.setContentsMargins(0, 0, 0, 0)
    else:
        while tabLayout.count():
            item = tabLayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    tabLayout.addWidget(splitter)
