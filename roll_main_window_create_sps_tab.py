from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget

from .table_model_view import RpsTableModel, SpsTableModel, TableView, XpsTableModel


def createSpsTab(self):
    table_style = 'QTableView::item:selected{background-color : #add8e6;selection-color : #000000;}'
    label_style = 'font-family: Arial; font-weight: bold; font-size: 16px;'

    # first create the main widgets
    self.spsView = TableView()                                              # create sps view
    self.spsModel = SpsTableModel(self.spsImport)                          # create sps model
    self.spsView.setModel(self.spsModel)                                    # add the model to the view
    self.spsView.setStyleSheet(table_style)                                 # define selection colors
    self.spsView.resizeColumnsToContents()
    self.spsView.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    self.xpsView = TableView()                                              # create xps view
    self.xpsModel = XpsTableModel(self.xpsImport)                           # create xps model
    self.xpsView.setModel(self.xpsModel)                                    # add the model to the view
    self.xpsHdrView = self.xpsView.horizontalHeader()                       # to detect button clicks here
    self.xpsHdrView.sectionClicked.connect(self.sortXpsData)                # handle the section-clicked signal
    self.xpsView.setStyleSheet(table_style)                                 # define selection colors
    self.xpsView.resizeColumnsToContents()
    self.xpsView.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    self.rpsView = TableView()                                              # create rps view
    self.rpsModel = RpsTableModel(self.rpsImport)                           # create xps model
    self.rpsView.setModel(self.rpsModel)                                    # add the model to the view
    self.rpsView.setStyleSheet(table_style)                                 # define selection colors
    self.rpsView.resizeColumnsToContents()
    self.rpsView.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    self.spsLabel = QLabel('SPS records')
    self.spsLabel.setAlignment(Qt.AlignCenter)
    self.spsLabel.setStyleSheet(label_style)

    self.xpsLabel = QLabel('XPS records')
    self.xpsLabel.setAlignment(Qt.AlignCenter)
    self.xpsLabel.setStyleSheet(label_style)

    self.rpsLabel = QLabel('RPS records')
    self.rpsLabel.setAlignment(Qt.AlignCenter)
    self.rpsLabel.setStyleSheet(label_style)

    # then create widget containers for the layout
    self.spsPane = QWidget()
    self.xpsPane = QWidget()
    self.rpsPane = QWidget()

    # then create button layout
    self.btnSpsRemoveDuplicates = QPushButton('Remove Duplicates')
    self.btnSpsExportToQGIS = QPushButton('Export to QGIS')
    self.btnSpsRemoveOrphans = QPushButton('Remove &XPS-orphins')

    self.btnXpsRemoveSpsOrphans = QPushButton('Remove SPS-orphins')
    self.btnXpsRemoveDuplicates = QPushButton('Remove Duplicates')
    self.btnXpsRemoveRpsOrphans = QPushButton('Remove RPS-orphins')

    self.btnRpsRemoveDuplicates = QPushButton('Remove &Duplicates')
    self.btnRpsExportToQGIS = QPushButton('Export to QGIS')
    self.btnRpsRemoveOrphans = QPushButton('Remove &XPS-orphins')

    # make the export buttons stand out a bit
    self.btnSpsExportToQGIS.setStyleSheet('background-color:lightgoldenrodyellow; font-weight:bold;')
    self.btnRpsExportToQGIS.setStyleSheet('background-color:lightgoldenrodyellow; font-weight:bold;')

    # these buttons have signals
    self.btnSpsRemoveDuplicates.pressed.connect(self.removeSpsDuplicates)

    self.actionExportSpsToQGIS.triggered.connect(self.exportSpsToQgis)      # export sps records to QGIS
    self.btnSpsExportToQGIS.pressed.connect(self.exportSpsToQgis)           # export sps records to QGIS
    self.btnSpsRemoveOrphans.pressed.connect(self.removeSpsOrphans)

    self.btnXpsRemoveSpsOrphans.pressed.connect(self.removeXpsSpsOrphans)
    self.btnXpsRemoveDuplicates.pressed.connect(self.removeXpsDuplicates)
    self.btnXpsRemoveRpsOrphans.pressed.connect(self.removeXpsRpsOrphans)

    self.btnRpsRemoveDuplicates.pressed.connect(self.removeRpsDuplicates)
    self.actionExportRpsToQGIS.triggered.connect(self.exportRpsToQgis)      # export rps records to QGIS
    self.btnRpsExportToQGIS.pressed.connect(self.exportRpsToQgis)           # export rps records to QGIS
    self.btnRpsRemoveOrphans.pressed.connect(self.removeRpsOrphans)

    grid1 = QGridLayout()
    grid1.addWidget(self.btnSpsRemoveDuplicates, 0, 0)
    grid1.addWidget(self.btnSpsExportToQGIS, 0, 1)
    grid1.addWidget(self.btnSpsRemoveOrphans, 0, 2)

    grid2 = QGridLayout()
    grid2.addWidget(self.btnXpsRemoveSpsOrphans, 0, 0)
    grid2.addWidget(self.btnXpsRemoveDuplicates, 0, 1)
    grid2.addWidget(self.btnXpsRemoveRpsOrphans, 0, 2)

    grid3 = QGridLayout()
    grid3.addWidget(self.btnRpsRemoveOrphans, 0, 0)
    grid3.addWidget(self.btnRpsExportToQGIS, 0, 1)
    grid3.addWidget(self.btnRpsRemoveDuplicates, 0, 2)

    # then create the three vertical layouts
    vbox1 = QVBoxLayout()
    vbox1.addWidget(self.spsLabel)
    vbox1.addWidget(self.spsView)
    vbox1.addLayout(grid1)

    vbox2 = QVBoxLayout()
    vbox2.addWidget(self.xpsLabel)
    vbox2.addWidget(self.xpsView)
    vbox2.addLayout(grid2)

    vbox3 = QVBoxLayout()
    vbox3.addWidget(self.rpsLabel)
    vbox3.addWidget(self.rpsView)
    vbox3.addLayout(grid3)

    # set the layout for the three panes
    self.spsPane.setLayout(vbox1)
    self.xpsPane.setLayout(vbox2)
    self.rpsPane.setLayout(vbox3)

    # Create the widgets for the bottom pane
    self.spsBottom = QPlainTextEdit()
    self.spsBottom.appendHtml('<b>Navigation:</b>')
    self.spsBottom.appendHtml('Use <b>Ctrl + Page-Up / Page-Down</b> to find next duplicate record.')
    self.spsBottom.appendHtml('Use <b>Ctrl + Up-arrow / Down-arrow</b> to find next source orphan.')
    self.spsBottom.appendHtml('Use <b>Ctrl + Left-arrow / Right-arrow</b> to find next receiver orphan.')
    self.spsBottom.appendHtml('The <b>XPS records</b> are only tested for valid rec-station values in the <b>rec min</b> and <b>rec max</b> columns (and not for any stations in between).')
    self.spsBottom.setReadOnly(True)                                        # if we set this 'True' the context menu no longer allows 'delete', just 'select all' and 'copy'

    self.spsBottom.setFrameShape(QFrame.StyledPanel)
    self.spsBottom.setStyleSheet('background-color:lightgoldenrodyellow')   # See: https://www.w3.org/TR/SVG11/types.html#ColorKeywords

    # use splitters to be able to rearrange the layout
    splitter1 = QSplitter(Qt.Horizontal)
    splitter1.addWidget(self.spsPane)
    splitter1.addWidget(self.xpsPane)
    splitter1.addWidget(self.rpsPane)
    splitter1.setSizes([200, 200, 200])

    splitter2 = QSplitter(Qt.Vertical)
    splitter2.addWidget(splitter1)
    splitter2.addWidget(self.spsBottom)
    splitter2.setSizes([900, 100])

    # ceate the main layout for the SPS tab
    hbox = QHBoxLayout()
    hbox.addWidget(splitter2)

    self.tabSps.setLayout(hbox)
