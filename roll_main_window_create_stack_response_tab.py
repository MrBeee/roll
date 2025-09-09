from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QActionGroup, QComboBox, QFrame, QGroupBox, QHBoxLayout, QSplitter, QToolButton, QVBoxLayout


def createStackResponseTab(self):
    self.stackInfChoice = QGroupBox('Stack response')                             # create display widget(s)
    self.stackNr1Choice = QGroupBox('1st pattern')                                 # create display widget(s)
    self.stackNr2Choice = QGroupBox('2nd pattern')                            # create display widget(s)

    self.stackInfChoice.setMinimumWidth(140)
    self.stackNr1Choice.setMinimumWidth(140)
    self.stackNr2Choice.setMinimumWidth(140)

    self.stackInfChoice.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    self.stackNr1Choice.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    self.stackNr2Choice.setAlignment(Qt.AlignmentFlag.AlignHCenter)

    vbox0 = QVBoxLayout()
    vbox0.addStretch(2)                                                         # add some stretch to main center widget(s)
    vbox0.addWidget(self.stackInfChoice)                                          # add main widget(s)
    vbox0.addStretch(1)                                                         # add some stretch to main center widget(s)
    vbox0.addWidget(self.stackNr1Choice)                                          # add main widget(s)
    vbox0.addStretch(1)                                                         # add some stretch to main center widget(s)
    vbox0.addWidget(self.stackNr2Choice)                                          # add main widget(s)
    vbox0.addStretch(9)                                                         # add some stretch to main center widget(s)

    self.tbStackResponse = QToolButton()
    self.tbStackPatterns = QToolButton()

    self.tbStackResponse.setMinimumWidth(110)
    self.tbStackPatterns.setMinimumWidth(110)

    self.tbStackResponse.setStyleSheet('QToolButton { selection-background-color: blue } QToolButton:checked { background-color: lightblue } QToolButton:pressed { background-color: red }')
    self.tbStackPatterns.setStyleSheet('QToolButton { selection-background-color: blue } QToolButton:checked { background-color: lightblue } QToolButton:pressed { background-color: red }')

    self.tbStackResponse.setDefaultAction(self.actionStackResponse)             # coupling done here
    self.tbStackPatterns.setDefaultAction(self.actionStackPatterns)

    self.stackActionGroup = QActionGroup(self)                                # the QActionGroup provides text label to QToolButtons
    self.stackActionGroup.addAction(self.actionStackResponse)
    self.stackActionGroup.addAction(self.actionStackPatterns)
    self.actionStackResponse.setChecked(True)

    self.actionStackResponse.triggered.connect(self.onStackPatternIndexChanged)
    self.actionStackPatterns.triggered.connect(self.onStackPatternIndexChanged)

    vbox1 = QVBoxLayout()                                                       # vertical layout for analysis options
    vbox1.addWidget(self.tbStackResponse)
    vbox1.addWidget(self.tbStackPatterns)
    self.stackInfChoice.setLayout(vbox1)

    # note: self refers to the RollMainWindow object;
    # self.pattern1 and self.pattern2 have already been used in the Patterns tab

    self.pattern3 = QComboBox()                                                 # vertical layout for selection 1st pattern
    self.pattern3.currentIndexChanged.connect(self.onStackPatternIndexChanged)

    vbox2 = QVBoxLayout()
    vbox2.addWidget(self.pattern3)
    self.stackNr1Choice.setLayout(vbox2)

    self.pattern4 = QComboBox()                                                 # vertical layout for selection 2nd pattern
    self.pattern4.currentIndexChanged.connect(self.onStackPatternIndexChanged)

    vbox3 = QVBoxLayout()
    vbox3.addWidget(self.pattern4)
    self.stackNr2Choice.setLayout(vbox3)

    self.pattern3.clear()
    self.pattern3.addItem('<no pattern>')                                       # pattern list
    for item in self.survey.patternList:
        self.pattern3.addItem(item)

    self.pattern4.clear()
    self.pattern4.addItem('<no pattern>')                                       # pattern list
    for item in self.survey.patternList:
        self.pattern4.addItem(item)

    # create widget containers for the overall layout
    hbox0 = QHBoxLayout()                                          # Make the vertical layout centered horizontally
    hbox0.addStretch()                                             # add some stretch to main center widget(s)
    hbox0.addLayout(vbox0)                                         # add the center widget, which uses QVboxLayout
    hbox0.addStretch()                                             # add some stretch to main center widget(s)

    leftSide = QFrame()
    leftSide.setFrameShape(QFrame.StyledPanel)
    leftSide.setLayout(hbox0)
    leftSide.setMaximumWidth(180)
    rightSide = self.stkCelWidget

    splitter1 = QSplitter(Qt.Horizontal)
    splitter1.addWidget(leftSide)
    splitter1.addWidget(rightSide)
    splitter1.setSizes([100, 500])

    hbox1 = QHBoxLayout(self)
    hbox1.addWidget(splitter1)

    self.tabKxKyStack.setLayout(hbox1)
