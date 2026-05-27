import numpy as np
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (QAction, QActionGroup, QFrame, QGroupBox,
                                 QHBoxLayout, QSplitter, QToolButton,
                                 QVBoxLayout)

from .config import toolButtonStyle


def createCfpTab(self):
    self.cfpSliceChoice = QGroupBox('XY slices')
    self.cfpSliceChoice.setMinimumWidth(140)
    self.cfpSliceChoice.setAlignment(Qt.AlignmentFlag.AlignHCenter)

    self.cfpRadonChoice = QGroupBox('Radon transforms')
    self.cfpRadonChoice.setMinimumWidth(140)
    self.cfpRadonChoice.setAlignment(Qt.AlignmentFlag.AlignHCenter)

    self.tbCfpSliceSourceBeam = QToolButton()
    self.tbCfpSliceReceiverBeam = QToolButton()
    self.tbCfpSliceResolution = QToolButton()
    self.tbCfpRadonSrcBeam = QToolButton()
    self.tbCfpRadonRecBeam = QToolButton()
    self.tbCfpRadonAvpFunction = QToolButton()

    for button in (
        self.tbCfpSliceSourceBeam,
        self.tbCfpSliceReceiverBeam,
        self.tbCfpSliceResolution,
        self.tbCfpRadonSrcBeam,
        self.tbCfpRadonRecBeam,
        self.tbCfpRadonAvpFunction,
    ):
        button.setMinimumWidth(110)
        button.setStyleSheet(toolButtonStyle)

    self.actionCfpSliceSourceBeam = QAction('Source beam', self)
    self.actionCfpSliceSourceBeam.setCheckable(True)
    self.actionCfpSliceSourceBeam.setData(0)

    self.actionCfpSliceReceiverBeam = QAction('Receiver beam', self)
    self.actionCfpSliceReceiverBeam.setCheckable(True)
    self.actionCfpSliceReceiverBeam.setData(1)

    self.actionCfpSliceResolution = QAction('Resolution', self)
    self.actionCfpSliceResolution.setCheckable(True)
    self.actionCfpSliceResolution.setData(2)

    self.actionCfpRadonSrcBeam = QAction('Src beam', self)
    self.actionCfpRadonSrcBeam.setCheckable(True)
    self.actionCfpRadonSrcBeam.setData(3)

    self.actionCfpRadonRecBeam = QAction('Rec beam', self)
    self.actionCfpRadonRecBeam.setCheckable(True)
    self.actionCfpRadonRecBeam.setData(4)

    self.actionCfpRadonAvpFunction = QAction('AVP function', self)
    self.actionCfpRadonAvpFunction.setCheckable(True)
    self.actionCfpRadonAvpFunction.setData(5)

    self.cfpViewActionGroup = QActionGroup(self)
    self.cfpViewActionGroup.setExclusive(True)
    self.cfpViewActionGroup.addAction(self.actionCfpSliceSourceBeam)
    self.cfpViewActionGroup.addAction(self.actionCfpSliceReceiverBeam)
    self.cfpViewActionGroup.addAction(self.actionCfpSliceResolution)
    self.cfpViewActionGroup.addAction(self.actionCfpRadonSrcBeam)
    self.cfpViewActionGroup.addAction(self.actionCfpRadonRecBeam)
    self.cfpViewActionGroup.addAction(self.actionCfpRadonAvpFunction)
    self.actionCfpSliceSourceBeam.setChecked(True)

    self.tbCfpSliceSourceBeam.setDefaultAction(self.actionCfpSliceSourceBeam)
    self.tbCfpSliceReceiverBeam.setDefaultAction(self.actionCfpSliceReceiverBeam)
    self.tbCfpSliceResolution.setDefaultAction(self.actionCfpSliceResolution)
    self.tbCfpRadonSrcBeam.setDefaultAction(self.actionCfpRadonSrcBeam)
    self.tbCfpRadonRecBeam.setDefaultAction(self.actionCfpRadonRecBeam)
    self.tbCfpRadonAvpFunction.setDefaultAction(self.actionCfpRadonAvpFunction)

    self.actionCfpSliceSourceBeam.triggered.connect(self.onCfpSliceChanged)
    self.actionCfpSliceReceiverBeam.triggered.connect(self.onCfpSliceChanged)
    self.actionCfpSliceResolution.triggered.connect(self.onCfpSliceChanged)
    self.actionCfpRadonSrcBeam.triggered.connect(self.onCfpRadonTransformChanged)
    self.actionCfpRadonRecBeam.triggered.connect(self.onCfpRadonTransformChanged)
    self.actionCfpRadonAvpFunction.triggered.connect(self.onCfpRadonTransformChanged)

    controlsLayout = QVBoxLayout()
    controlsLayout.addWidget(self.tbCfpSliceSourceBeam)
    controlsLayout.addWidget(self.tbCfpSliceReceiverBeam)
    controlsLayout.addWidget(self.tbCfpSliceResolution)
    self.cfpSliceChoice.setLayout(controlsLayout)

    radonLayout = QVBoxLayout()
    radonLayout.addWidget(self.tbCfpRadonSrcBeam)
    radonLayout.addWidget(self.tbCfpRadonRecBeam)
    radonLayout.addWidget(self.tbCfpRadonAvpFunction)
    self.cfpRadonChoice.setLayout(radonLayout)

    leftLayout = QVBoxLayout()
    leftLayout.addStretch(2)
    leftLayout.addWidget(self.cfpSliceChoice)
    leftLayout.addSpacing(20)
    leftLayout.addWidget(self.cfpRadonChoice)
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
    splitter.addWidget(self.cfpWidget)
    splitter.setSizes([100, 500])

    tabLayout = self.tabCfp.layout()
    if tabLayout is None:
        tabLayout = QHBoxLayout(self.tabCfp)
        tabLayout.setContentsMargins(0, 0, 0, 0)
    else:
        while tabLayout.count():
            item = tabLayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    tabLayout.addWidget(splitter)

    self.prepareAnalysisImageAndColorBar(
        self.cfpWidget,
        np.zeros((1, 1), dtype=np.float32),
        0.0,
        0.0,
        1.0,
        1.0,
        'cfpImItem',
        'cfpColorBar',
        levels=(-60.0, 0.0),
        label='dB',
        limits=(-60.0, 0.0),
        rounding=10.0,
    )
