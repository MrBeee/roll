from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import QHeaderView, QLabel, QVBoxLayout

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
    # self.anaView.setResizeContentsPrecision(0)
    # self.anaView.resizeColumnsToContents()                                # takes WAY too much time for large tables
    self.anaView.horizontalHeader().setMinimumSectionSize(10)
    self.anaView.horizontalHeader().setDefaultSectionSize(100)

    self.anaView.verticalHeader().setDefaultSectionSize(24)
    self.anaView.verticalHeader().sectionResizeMode(QHeaderView.ResizeMode.Fixed)
    self.anaView.verticalHeader().setFont(QFont('Arial', 8, QFont.Weight.Normal))
    self.anaView.verticalHeader().setFixedWidth(95)

    self.anaView.setStyleSheet(table_style)                                 # define selection colors

    label_style = 'font-family: Arial; font-weight: bold; font-size: 16px;'
    self.anaLabel = QLabel('\nANALYSIS records')
    self.anaLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.anaLabel.setStyleSheet(label_style)

    # then create the layout
    self.tabTraces.layout = QVBoxLayout(self)
    self.tabTraces.layout.setContentsMargins(1, 1, 1, 1)
    self.tabTraces.layout.addWidget(self.anaLabel)
    self.tabTraces.layout.addWidget(self.anaView)

    # put table on traces tab
    self.tabTraces.setLayout(self.tabTraces.layout)
