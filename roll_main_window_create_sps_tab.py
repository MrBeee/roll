from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget

from .table_model_view import RpsTableModel, SpsTableModel, TableView, XpsTableModel


def createSpsTab(self):
    table_style = 'QTableView::item:selected{background-color : #add8e6;selection-color : #000000;}'
    label_style = 'font-family: Arial; font-weight: bold; font-size: 16px;'

    # first create the main widgets
    self.spsView = TableView()                                                  # create sps view
    self.spsModel = SpsTableModel(self.spsImport)                               # create sps model
    self.spsView.setModel(self.spsModel)                                        # add the model to the view
    self.spsHdrView = self.spsView.horizontalHeader()                           # to detect button clicks here
    self.spsHdrView.sectionClicked.connect(self.sortSpsData)                    # handle the section-clicked signal
    self.spsView.setStyleSheet(table_style)                                     # define selection colors
    self.spsView.resizeColumnsToContents()
    self.spsView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    self.xpsView = TableView()                                                  # create xps view
    self.xpsModel = XpsTableModel(self.xpsImport)                               # create xps model
    self.xpsView.setModel(self.xpsModel)                                        # add the model to the view
    self.xpsHdrView = self.xpsView.horizontalHeader()                           # to detect button clicks here
    self.xpsHdrView.sectionClicked.connect(self.sortXpsData)                    # handle the section-clicked signal
    self.xpsView.setStyleSheet(table_style)                                     # define selection colors
    self.xpsView.resizeColumnsToContents()
    self.xpsView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    self.rpsView = TableView()                                                  # create rps view
    self.rpsModel = RpsTableModel(self.rpsImport)                               # create xps model
    self.rpsView.setModel(self.rpsModel)                                        # add the model to the view
    self.rpsHdrView = self.rpsView.horizontalHeader()                           # to detect button clicks here
    self.rpsHdrView.sectionClicked.connect(self.sortRpsData)                    # handle the section-clicked signal
    self.rpsView.setStyleSheet(table_style)                                     # define selection colors
    self.rpsView.resizeColumnsToContents()
    self.rpsView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    # add the top labels
    self.spsLabel = QLabel('SPS records')
    self.spsLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.spsLabel.setStyleSheet(label_style)

    self.xpsLabel = QLabel('XPS records')
    self.xpsLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.xpsLabel.setStyleSheet(label_style)

    self.rpsLabel = QLabel('RPS records')
    self.rpsLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.rpsLabel.setStyleSheet(label_style)

    # then create widget containers for the sps, xps and rps layout
    self.spsPane = QWidget()
    self.xpsPane = QWidget()
    self.rpsPane = QWidget()

    # then create the buttons for the layout; start with source buttons
    self.btnSpsRemoveDuplicates = QPushButton('Remove Duplicates')
    label1 = QLabel('«-Cleanup table-»')

    self.btnSpsRemoveOrphans = QPushButton('Remove &XPS-orphins')
    # next line
    self.btnSpsExportToQGIS = QPushButton('Export to QGIS')
    label3 = QLabel('«- QGIS I/O -»')
    self.btnSpsReadFromQGIS = QPushButton('Read from QGIS')
    self.btnSpsReadFromQGIS.pressed.connect(self.importSpsFromQgis)

    # continue with relation buttons
    self.btnXpsRemoveSpsOrphans = QPushButton('Remove SPS-orphins')
    self.btnXpsRemoveDuplicates = QPushButton('Remove Duplicates')
    self.btnXpsRemoveRpsOrphans = QPushButton('Remove RPS-orphins')
    # next line
    self.btnXpsExportToQGIS = QPushButton('Export concave Sps, and Rps &Boundaries to QGIS')
    self.btnXpsExportToQGIS.pressed.connect(self.exportSpsBoundariesToQgis)           # button; export SPS outlines to QGIS

    # lastly create the receiver buttons
    self.btnRpsRemoveOrphans = QPushButton('Remove &XPS-orphins')
    label2 = QLabel('«-Cleanup table-»')
    self.btnRpsRemoveDuplicates = QPushButton('Remove &Duplicates')
    # next line
    self.btnRpsExportToQGIS = QPushButton('Export to QGIS')
    label4 = QLabel('«- QGIS I/O -»')
    self.btnRpsReadFromQGIS = QPushButton('Read from QGIS')
    self.btnRpsReadFromQGIS.pressed.connect(self.importRpsFromQgis)

    # make the buttons stand out a bit. See: https://www.webucator.com/article/python-color-constants-module/
    self.btnSpsRemoveDuplicates.setStyleSheet('background-color:lavender; font-weight:bold;')
    self.btnSpsRemoveOrphans.setStyleSheet('background-color:lavender; font-weight:bold;')

    self.btnXpsRemoveSpsOrphans.setStyleSheet('background-color:lavender; font-weight:bold;')
    self.btnXpsRemoveDuplicates.setStyleSheet('background-color:lavender; font-weight:bold;')
    self.btnXpsRemoveRpsOrphans.setStyleSheet('background-color:lavender; font-weight:bold;')

    self.btnRpsRemoveDuplicates.setStyleSheet('background-color:lavender; font-weight:bold;')
    self.btnRpsRemoveOrphans.setStyleSheet('background-color:lavender; font-weight:bold;')

    # style for the QGIS buttons
    self.btnSpsExportToQGIS.setStyleSheet('background-color:lightgoldenrodyellow; font-weight:bold;')
    self.btnSpsReadFromQGIS.setStyleSheet('background-color:lightgoldenrodyellow; font-weight:bold;')
    self.btnRpsExportToQGIS.setStyleSheet('background-color:lightgoldenrodyellow; font-weight:bold;')
    self.btnRpsReadFromQGIS.setStyleSheet('background-color:lightgoldenrodyellow; font-weight:bold;')
    self.btnXpsExportToQGIS.setStyleSheet('background-color:lightgoldenrodyellow; font-weight:bold;')

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

    label1.setStyleSheet('border: 1px solid black;background-color:lavender')
    label1.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label2.setStyleSheet('border: 1px solid black;background-color:lavender')
    label2.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label3.setStyleSheet('border: 1px solid black;background-color:lavender')
    label3.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label4.setStyleSheet('border: 1px solid black;background-color:lavender')
    label4.setAlignment(Qt.AlignmentFlag.AlignCenter)

    # create the three button layouts
    grid1 = QGridLayout()                                                       # top row
    grid1.addWidget(self.btnSpsRemoveDuplicates, 0, 0)
    grid1.addWidget(label1, 0, 1)
    grid1.addWidget(self.btnSpsRemoveOrphans, 0, 2)

    grid1.addWidget(self.btnSpsExportToQGIS, 1, 0)                              # second row
    grid1.addWidget(label3, 1, 1)
    grid1.addWidget(self.btnSpsReadFromQGIS, 1, 2)

    grid2 = QGridLayout()                                                       # top row
    grid2.addWidget(self.btnXpsRemoveSpsOrphans, 0, 0)
    grid2.addWidget(self.btnXpsRemoveDuplicates, 0, 1)
    grid2.addWidget(self.btnXpsRemoveRpsOrphans, 0, 2)

    grid2.addWidget(self.btnXpsExportToQGIS, 1, 0, 1, 3)                        # second row

    grid3 = QGridLayout()                                                       # top row
    grid3.addWidget(self.btnRpsRemoveOrphans, 0, 0)
    grid3.addWidget(label2, 0, 1)
    grid3.addWidget(self.btnRpsRemoveDuplicates, 0, 2)

    grid3.addWidget(self.btnRpsExportToQGIS, 1, 0)                              # second row
    grid3.addWidget(label4, 1, 1)
    grid3.addWidget(self.btnRpsReadFromQGIS, 1, 2)

    # create the three vertical layouts
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

    self.spsBottom.setFrameShape(QFrame.Shape.StyledPanel)
    self.spsBottom.setStyleSheet('background-color:lightgoldenrodyellow')   # See: https://www.w3.org/TR/SVG11/types.html#ColorKeywords

    # use splitters to be able to rearrange the layout
    splitter1 = QSplitter(Qt.Orientation.Horizontal)
    splitter1.addWidget(self.spsPane)
    splitter1.addWidget(self.xpsPane)
    splitter1.addWidget(self.rpsPane)
    splitter1.setSizes([200, 200, 200])

    splitter2 = QSplitter(Qt.Orientation.Vertical)
    splitter2.addWidget(splitter1)
    splitter2.addWidget(self.spsBottom)
    splitter2.setSizes([900, 100])

    # ceate the main layout for the SPS tab
    hbox = QHBoxLayout()
    hbox.addWidget(splitter2)

    self.tabSps.setLayout(hbox)
