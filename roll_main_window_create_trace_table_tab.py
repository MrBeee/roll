from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from . import config  # used to pass initial settings
from .table_model_view import AnaTableModel, TableView


def createTraceTableTab(self):
    # analysis table; to copy data to clipboard, create a subclassed QTableView, see bottom of following article:
    # See: https://stackoverflow.com/questions/40225270/copy-paste-multiple-items-from-qtableview-in-pyqt4
    self.anaModel = AnaTableModel(self.output.D2_Output)

    # to resize a table to available space, see:
    # See: https://stackoverflow.com/questions/58855704/how-to-squeeze-the-column-to-minimum-in-qtableview-in-pyqt5

    # See: https://stackoverflow.com/questions/7840325/change-the-selection-color-of-a-qtablewidget
    table_style = 'QTableView::item:selected{background-color : #add8e6;selection-color : #000000;}'

    # first create the widget(s)
    self.anaView = TableView()
    self.anaView.setModel(self.anaModel)
    self.anaView.horizontalHeader().setMinimumSectionSize(10)
    self.anaView.horizontalHeader().setDefaultSectionSize(100)

    self.anaView.verticalHeader().setDefaultSectionSize(24)
    self.anaView.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
    self.anaView.verticalHeader().setFont(QFont('Arial', 8, QFont.Weight.Normal))
    self.anaView.verticalHeader().setFixedWidth(95)

    self.anaView.setStyleSheet(table_style)                                 # define selection colors

    label_style = 'font-family: Arial; font-weight: bold; font-size: 16px;'
    self.anaLabel = QLabel('\nANALYSIS records')
    self.anaLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.anaLabel.setStyleSheet(label_style)

    # Create a widget to hold pagination controls
    self.paginationWidget = QWidget()
    hbox = QHBoxLayout(self.paginationWidget)

    # Add buttons and information label
    self.btnFirstPage = QPushButton('<<')
    self.btnPrevPage = QPushButton('<')
    self.lblPageInfo = QLabel('No paging')
    self.lblPageInfo.setMinimumWidth(150)
    self.lblPageInfo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.btnNextPage = QPushButton('>')
    self.btnLastPage = QPushButton('>>')

    # Add goto page controls
    self.gotoLabel = QLabel('Go to trace:')
    self.gotoLabel.setMinimumWidth(100)
    self.gotoLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.gotoEdit = QLineEdit('1')
    self.gotoEdit.setFixedWidth(100)
    self.gotoEdit.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.btnGoto = QPushButton('Go ->')

    # Style the pagination controls
    self.btnFirstPage.setStyleSheet('background-color:lavender; font-weight:bold;')
    self.btnPrevPage.setStyleSheet('background-color:lavender; font-weight:bold;')
    self.lblPageInfo.setStyleSheet('border: 1px solid black;background-color:lavender')
    self.btnNextPage.setStyleSheet('background-color:lavender; font-weight:bold;')
    self.btnLastPage.setStyleSheet('background-color:lavender; font-weight:bold;')

    self.gotoLabel.setStyleSheet('border: 1px solid black;background-color:lavender')
    self.gotoEdit.setStyleSheet('background-color:lavender')
    self.btnGoto.setStyleSheet('background-color:lavender; font-weight:bold;')

    hbox.addWidget(self.btnFirstPage)
    hbox.addWidget(self.btnPrevPage)
    hbox.addWidget(self.lblPageInfo)
    hbox.addWidget(self.btnNextPage)
    hbox.addWidget(self.btnLastPage)
    hbox.addStretch()
    hbox.addWidget(self.gotoLabel)
    hbox.addWidget(self.gotoEdit)
    hbox.addWidget(self.btnGoto)

    # Connect signals
    self.btnFirstPage.clicked.connect(self._goToFirstPage)
    self.btnPrevPage.clicked.connect(self._goToPrevPage)
    self.btnNextPage.clicked.connect(self._goToNextPage)
    self.btnLastPage.clicked.connect(self._goToLastPage)
    self.btnGoto.clicked.connect(self._goToSpecificRow)

    # then create the layout
    self.tabTraces.layout = QVBoxLayout(self)
    self.tabTraces.layout.setContentsMargins(1, 1, 1, 1)
    self.tabTraces.layout.addWidget(self.anaLabel)
    self.tabTraces.layout.addWidget(self.anaView)

    # Add the pagination widget to the layout near the trace table
    self.tabTraces.layout.addWidget(self.paginationWidget)

    # put table on traces tab
    self.tabTraces.setLayout(self.tabTraces.layout)

    # initialize page info
    self._updatePageInfo()
