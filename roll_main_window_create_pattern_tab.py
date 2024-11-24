from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QActionGroup, QComboBox, QFrame, QGroupBox, QHBoxLayout, QSplitter, QToolButton, QVBoxLayout


def createPatternTab(self):
    self.patInfChoice = QGroupBox('Pattern info')                               # create display widget(s)
    self.patNr1Choice = QGroupBox('1st pattern')                                # create display widget(s)
    self.patNr2Choice = QGroupBox('2nd pattern')                                # create display widget(s)

    self.patInfChoice.setMinimumWidth(140)
    self.patNr1Choice.setMinimumWidth(140)
    self.patNr2Choice.setMinimumWidth(140)

    self.patInfChoice.setAlignment(Qt.AlignHCenter)
    self.patNr1Choice.setAlignment(Qt.AlignHCenter)
    self.patNr2Choice.setAlignment(Qt.AlignHCenter)

    vbox0 = QVBoxLayout()
    vbox0.addStretch(2)                                                         # add some stretch to main center widget(s)
    vbox0.addWidget(self.patInfChoice)                                          # add main widget(s)
    vbox0.addStretch(1)                                                         # add some stretch to main center widget(s)
    vbox0.addWidget(self.patNr1Choice)                                          # add main widget(s)
    vbox0.addStretch(1)                                                         # add some stretch to main center widget(s)
    vbox0.addWidget(self.patNr2Choice)                                          # add main widget(s)
    vbox0.addStretch(9)                                                         # add some stretch to main center widget(s)

    self.tbPatternLayout = QToolButton()
    self.tbPattern_kx_ky = QToolButton()

    self.tbPatternLayout.setMinimumWidth(110)
    self.tbPattern_kx_ky.setMinimumWidth(110)

    self.tbPatternLayout.setStyleSheet('QToolButton { selection-background-color: blue } QToolButton:checked { background-color: lightblue } QToolButton:pressed { background-color: red }')
    self.tbPattern_kx_ky.setStyleSheet('QToolButton { selection-background-color: blue } QToolButton:checked { background-color: lightblue } QToolButton:pressed { background-color: red }')

    self.tbPatternLayout.setDefaultAction(self.actionPatternLayout)             # coupling done here
    self.tbPattern_kx_ky.setDefaultAction(self.actionPattern_kx_ky)

    self.patternActionGroup = QActionGroup(self)                                # the QActionGroup provides text label to QToolButtons
    self.patternActionGroup.addAction(self.actionPatternLayout)
    self.patternActionGroup.addAction(self.actionPattern_kx_ky)
    self.actionPatternLayout.setChecked(True)

    self.actionPatternLayout.triggered.connect(self.onActionPatternLayoutTriggered)
    self.actionPattern_kx_ky.triggered.connect(self.onActionPattern_kx_kyTriggered)

    vbox1 = QVBoxLayout()                                                       # vertical layout for analysis options
    vbox1.addWidget(self.tbPatternLayout)
    vbox1.addWidget(self.tbPattern_kx_ky)
    self.patInfChoice.setLayout(vbox1)

    self.pattern1 = QComboBox()                                                 # vertical layout for selection 1st pattern
    self.pattern1.currentIndexChanged.connect(self.onPattern1IndexChanged)

    vbox2 = QVBoxLayout()
    vbox2.addWidget(self.pattern1)
    self.patNr1Choice.setLayout(vbox2)

    self.pattern2 = QComboBox()                                                 # vertical layout for selection 2nd pattern
    self.pattern2.currentIndexChanged.connect(self.onPattern2IndexChanged)

    vbox3 = QVBoxLayout()
    vbox3.addWidget(self.pattern2)
    self.patNr2Choice.setLayout(vbox3)

    self.pattern1.clear()
    self.pattern1.addItem('<no pattern>')                                       # pattern list
    for item in self.survey.patternList:
        self.pattern1.addItem(item)

    self.pattern2.clear()
    self.pattern2.addItem('<no pattern>')                                       # pattern list
    for item in self.survey.patternList:
        self.pattern2.addItem(item)

    # create widget containers for the overall layout
    hbox0 = QHBoxLayout()                                          # Make the vertical layout centered horizontally
    hbox0.addStretch()                                             # add some stretch to main center widget(s)
    hbox0.addLayout(vbox0)                                         # add the center widget, which uses QVboxLayout
    hbox0.addStretch()                                             # add some stretch to main center widget(s)

    leftSide = QFrame()
    leftSide.setFrameShape(QFrame.StyledPanel)
    leftSide.setLayout(hbox0)
    leftSide.setMaximumWidth(180)
    rightSide = self.arraysWidget

    splitter1 = QSplitter(Qt.Horizontal)
    splitter1.addWidget(leftSide)
    splitter1.addWidget(rightSide)
    splitter1.setSizes([100, 500])

    hbox1 = QHBoxLayout(self)
    hbox1.addWidget(splitter1)

    self.tabPatterns.setLayout(hbox1)
