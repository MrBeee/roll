from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget

from .table_model_view import RpsTableModel, SpsTableModel, TableView, XpsTableModel


def createGeomTab(self):
    table_style = 'QTableView::item:selected{background-color : #add8e6;selection-color : #000000;}'
    label_style = 'font-family: Arial; font-weight: bold; font-size: 16px;'

    # first create the main widgets
    self.srcView = TableView()                                              # create src view
    self.srcModel = SpsTableModel(self.srcGeom)                             # create src model
    self.srcView.setModel(self.srcModel)                                    # add the model to the view
    self.srcView.setStyleSheet(table_style)                                 # define selection colors
    self.srcView.resizeColumnsToContents()
    self.srcView.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    self.relView = TableView()                                              # create rel view
    self.relModel = XpsTableModel(self.relGeom)                             # create rel model
    self.relView.setModel(self.relModel)                                    # add the model to the view
    self.relHdrView = self.relView.horizontalHeader()                       # to detect button clicks here
    self.relHdrView.sectionClicked.connect(self.sortRelData)                # handle the section-clicked signal
    self.relView.setStyleSheet(table_style)                                 # define selection colors
    self.relView.resizeColumnsToContents()
    self.relView.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    self.recView = TableView()                                              # create rec view
    self.recModel = RpsTableModel(self.recGeom)                             # create rec model
    self.recView.setModel(self.recModel)                                    # add the model to the view
    self.recView.setStyleSheet(table_style)                                 # define selection colors
    self.recView.resizeColumnsToContents()
    self.recView.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    self.srcLabel = QLabel('SRC records')
    self.srcLabel.setAlignment(Qt.AlignCenter)
    self.srcLabel.setStyleSheet(label_style)

    self.relLabel = QLabel('REL records')
    self.relLabel.setAlignment(Qt.AlignCenter)
    self.relLabel.setStyleSheet(label_style)

    self.recLabel = QLabel('REC records')
    self.recLabel.setAlignment(Qt.AlignCenter)
    self.recLabel.setStyleSheet(label_style)

    # then create widget containers for the layout
    self.srcPane = QWidget()
    self.relPane = QWidget()
    self.recPane = QWidget()

    # then create button layout
    self.btnSrcRemoveDuplicates = QPushButton('Remove &Duplicates')
    self.btnSrcRemoveOrphans = QPushButton('Remove &REL-orphins')

    self.btnSrcExportToQGIS = QPushButton('Export to QGIS')
    self.btnSrcReadFromQGIS = QPushButton('Read from QGIS')

    self.btnRelRemoveSrcOrphans = QPushButton('Remove &SRC-orphins')
    self.btnRelRemoveDuplicates = QPushButton('Remove &Duplicates')
    self.btnRelRemoveRecOrphans = QPushButton('Remove &REC-orphins')

    self.btnRecRemoveDuplicates = QPushButton('Remove &Duplicates')
    self.btnRecRemoveOrphans = QPushButton('Remove &REL-orphins')

    self.btnRecExportToQGIS = QPushButton('Export to QGIS')
    self.btnRecReadFromQGIS = QPushButton('Read from QGIS')

    self.btnRelExportToQGIS = QPushButton('Export Src, Cmp, Rec && Binning &Boundaries to QGIS')
    self.btnRelExportToQGIS.setToolTip('This button is enabled once you have saved the project')

    # make the buttons stand out a bit
    # See: https://www.webucator.com/article/python-color-constants-module/
    self.btnSrcRemoveDuplicates.setStyleSheet('background-color:lavender; font-weight:bold;')
    self.btnSrcRemoveOrphans.setStyleSheet('background-color:lavender; font-weight:bold;')

    self.btnRelRemoveSrcOrphans.setStyleSheet('background-color:lavender; font-weight:bold;')
    self.btnRelRemoveDuplicates.setStyleSheet('background-color:lavender; font-weight:bold;')
    self.btnRelRemoveRecOrphans.setStyleSheet('background-color:lavender; font-weight:bold;')

    self.btnRecRemoveDuplicates.setStyleSheet('background-color:lavender; font-weight:bold;')
    self.btnRecRemoveOrphans.setStyleSheet('background-color:lavender; font-weight:bold;')

    self.btnSrcExportToQGIS.setStyleSheet('background-color:lightgoldenrodyellow; font-weight:bold;')
    self.btnSrcReadFromQGIS.setStyleSheet('background-color:lightgoldenrodyellow; font-weight:bold;')

    self.btnRecExportToQGIS.setStyleSheet('background-color:lightgoldenrodyellow; font-weight:bold;')
    self.btnRecReadFromQGIS.setStyleSheet('background-color:lightgoldenrodyellow; font-weight:bold;')

    self.btnRelExportToQGIS.setStyleSheet('background-color:lightgoldenrodyellow; font-weight:bold;')

    # these buttons have signals
    self.btnSrcRemoveDuplicates.pressed.connect(self.removeSrcDuplicates)   # src buttons & actions
    self.btnSrcRemoveOrphans.pressed.connect(self.removeSrcOrphans)
    self.actionExportSrcToQGIS.triggered.connect(self.exportSrcToQgis)      # export src records to QGIS
    self.btnSrcExportToQGIS.pressed.connect(self.exportSrcToQgis)           # export src records to QGIS
    self.btnSrcReadFromQGIS.pressed.connect(self.importSrcFromQgis)

    self.btnRelRemoveDuplicates.pressed.connect(self.removeRelDuplicates)   # rel buttons & actions
    self.btnRelRemoveSrcOrphans.pressed.connect(self.removeRelSrcOrphans)
    self.btnRelRemoveRecOrphans.pressed.connect(self.removeRelRecOrphans)
    self.actionExportAreasToQGIS.triggered.connect(self.exportOutToQgis)    # export survey outline to QGIS
    self.btnRelExportToQGIS.pressed.connect(self.exportOutToQgis)           # export survey outline to QGIS

    self.btnRecRemoveDuplicates.pressed.connect(self.removeRecDuplicates)   # rec buttons & actions
    self.btnRecRemoveOrphans.pressed.connect(self.removeRecOrphans)
    self.actionExportRecToQGIS.triggered.connect(self.exportRecToQgis)      # export rec records to QGIS
    self.btnRecExportToQGIS.pressed.connect(self.exportRecToQgis)           # export rec records to QGIS
    self.btnRecReadFromQGIS.pressed.connect(self.importRecFromQgis)

    self.btnBinToQGIS.pressed.connect(self.exportBinToQGIS)                 # figures
    self.btnMinToQGIS.pressed.connect(self.exportMinToQGIS)
    self.btnMaxToQGIS.pressed.connect(self.exportMaxToQGIS)
    self.btnRmsToQGIS.pressed.connect(self.exportRmsToQGIS)

    label1 = QLabel('«-Cleanup table-»')
    label1.setStyleSheet('border: 1px solid black;background-color:lavender')
    label1.setAlignment(Qt.AlignCenter)

    label2 = QLabel('«-Cleanup table-»')
    label2.setStyleSheet('border: 1px solid black;background-color:lavender')
    label2.setAlignment(Qt.AlignCenter)

    label3 = QLabel('«- QGIS I/O -»')
    label3.setStyleSheet('border: 1px solid black;background-color:lavender')
    label3.setAlignment(Qt.AlignCenter)

    label4 = QLabel('«- QGIS I/O -»')
    label4.setStyleSheet('border: 1px solid black;background-color:lavender')
    label4.setAlignment(Qt.AlignCenter)

    grid1 = QGridLayout()
    grid1.addWidget(self.btnSrcRemoveDuplicates, 0, 0)
    grid1.addWidget(label1, 0, 1)
    grid1.addWidget(self.btnSrcRemoveOrphans, 0, 2)

    grid1.addWidget(self.btnSrcExportToQGIS, 1, 0)
    grid1.addWidget(label3, 1, 1)
    grid1.addWidget(self.btnSrcReadFromQGIS, 1, 2)

    grid2 = QGridLayout()
    grid2.addWidget(self.btnRelRemoveSrcOrphans, 0, 0)
    grid2.addWidget(self.btnRelRemoveDuplicates, 0, 1)
    grid2.addWidget(self.btnRelRemoveRecOrphans, 0, 2)
    grid2.addWidget(self.btnRelExportToQGIS, 1, 0, 1, 3)

    grid3 = QGridLayout()
    grid3.addWidget(self.btnRecRemoveOrphans, 0, 0)
    grid3.addWidget(label2, 0, 1)
    grid3.addWidget(self.btnRecRemoveDuplicates, 0, 2)

    grid3.addWidget(self.btnRecExportToQGIS, 1, 0)
    grid3.addWidget(label4, 1, 1)
    grid3.addWidget(self.btnRecReadFromQGIS, 1, 2)

    # then create the three vertical layouts
    vbox1 = QVBoxLayout()
    vbox1.addWidget(self.srcLabel)
    vbox1.addWidget(self.srcView)
    vbox1.addLayout(grid1)

    vbox2 = QVBoxLayout()
    vbox2.addWidget(self.relLabel)
    vbox2.addWidget(self.relView)
    vbox2.addLayout(grid2)

    vbox3 = QVBoxLayout()
    vbox3.addWidget(self.recLabel)
    vbox3.addWidget(self.recView)
    vbox3.addLayout(grid3)

    # set the layout for the three panes
    self.srcPane.setLayout(vbox1)
    self.relPane.setLayout(vbox2)
    self.recPane.setLayout(vbox3)

    # Create the widgets for the bottom pane
    self.geomBottom = QPlainTextEdit()
    self.geomBottom.appendHtml('<b>Navigation:</b>')
    self.geomBottom.appendHtml('Use <b>Ctrl + Page-Up / Page-Down</b> to find next duplicate record.')
    self.geomBottom.appendHtml('Use <b>Ctrl + Up-arrow / Down-arrow</b> to find next source orphan.')
    self.geomBottom.appendHtml('Use <b>Ctrl + Left-arrow / Right-arrow</b> to find next receiver orphan.')
    self.geomBottom.appendHtml('The <b>XPS records</b> are only tested for valid rec-station values in the <b>rec min</b> and <b>rec max</b> columns (and not for any stations in between).')
    self.geomBottom.setReadOnly(True)                                        # if we set this 'True' the context menu no longer allows 'delete', just 'select all' and 'copy'

    self.geomBottom.setFrameShape(QFrame.StyledPanel)
    self.geomBottom.setStyleSheet('background-color:lavender')   # See: https://www.w3.org/TR/SVG11/types.html#ColorKeywords

    # use splitters to be able to rearrange the layout
    splitter1 = QSplitter(Qt.Horizontal)
    splitter1.addWidget(self.srcPane)
    splitter1.addWidget(self.relPane)
    splitter1.addWidget(self.recPane)
    splitter1.setSizes([200, 200, 200])

    splitter2 = QSplitter(Qt.Vertical)
    splitter2.addWidget(splitter1)
    splitter2.addWidget(self.geomBottom)
    splitter2.setSizes([900, 100])

    # ceate the main layout for the SPS tab
    hbox = QHBoxLayout()
    hbox.addWidget(splitter2)

    self.tabGeom.setLayout(hbox)
