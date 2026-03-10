from types import MethodType

import numpy as np
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                                 QPushButton, QVBoxLayout, QWidget)

from .config import labelStyle, purpleButtonStyle, purpleLabelStyle, tableStyle
from .enums_and_int_flags import MsgType
from .table_model_view import AnaTableModel, TableView


def createTraceTableTab(self):
    # analysis table; to copy data to clipboard, create a subclassed QTableView, see bottom of following article:
    # See: https://stackoverflow.com/questions/40225270/copy-paste-multiple-items-from-qtableview-in-pyqt4
    self.anaModel = AnaTableModel(self.output.an2Output)

    # to resize a table to available space, see:
    # See: https://stackoverflow.com/questions/58855704/how-to-squeeze-the-column-to-minimum-in-qtableview-in-pyqt5

    # first create the widget(s)
    self.anaView = TableView()
    self.anaView.setModel(self.anaModel)
    self.anaView.horizontalHeader().setMinimumSectionSize(10)
    self.anaView.horizontalHeader().setDefaultSectionSize(100)

    self.anaView.verticalHeader().setDefaultSectionSize(24)
    self.anaView.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
    self.anaView.verticalHeader().setFont(QFont('Arial', 8, QFont.Weight.Normal))
    self.anaView.verticalHeader().setFixedWidth(95)

    self.anaView.setStyleSheet(tableStyle)                                 # define selection colors

    self.anaLabel = QLabel('\nANALYSIS records')
    self.anaLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.anaLabel.setStyleSheet(labelStyle)

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
    self.btnFirstPage.setStyleSheet(purpleButtonStyle)
    self.btnPrevPage.setStyleSheet(purpleButtonStyle)
    self.lblPageInfo.setStyleSheet(purpleLabelStyle)
    self.btnNextPage.setStyleSheet(purpleButtonStyle)
    self.btnLastPage.setStyleSheet(purpleButtonStyle)

    self.gotoLabel.setStyleSheet(purpleLabelStyle)
    self.gotoEdit.setStyleSheet('background-color:lavender')
    self.btnGoto.setStyleSheet(purpleButtonStyle)

    hbox.addWidget(self.btnFirstPage)
    hbox.addWidget(self.btnPrevPage)
    hbox.addWidget(self.lblPageInfo)
    hbox.addWidget(self.btnNextPage)
    hbox.addWidget(self.btnLastPage)
    hbox.addStretch()
    hbox.addWidget(self.gotoLabel)
    hbox.addWidget(self.gotoEdit)
    hbox.addWidget(self.btnGoto)

    # Below are methods for navigation through the analysis table
    # these methods make use of MethodType to bind them to the RollMainWindow class
    # See: https://docs.python.org/3/library/types.html#types.MethodType
    # See: https://runebook.dev/en/docs/python/library/types/types.MethodType
    self._updatePageInfo = MethodType(_updatePageInfo, self)
    self._goToFirstPage = MethodType(_goToFirstPage, self)
    self._goToPrevPage = MethodType(_goToPrevPage, self)
    self._goToNextPage = MethodType(_goToNextPage, self)
    self._goToLastPage = MethodType(_goToLastPage, self)
    self._goToSpecificRow = MethodType(_goToSpecificRow, self)

    # Connect signals
    self.btnFirstPage.clicked.connect(self._goToFirstPage)
    self.btnPrevPage.clicked.connect(self._goToPrevPage)
    self.btnNextPage.clicked.connect(self._goToNextPage)
    self.btnLastPage.clicked.connect(self._goToLastPage)
    self.btnGoto.clicked.connect(self._goToSpecificRow)

    # then create the layout (reuse existing layout if tab is rebuilt)
    tabLayout = self.tabTraces.layout()
    if tabLayout is None:
        tabLayout = QVBoxLayout(self.tabTraces)
        tabLayout.setContentsMargins(1, 1, 1, 1)
    else:
        while tabLayout.count():
            item = tabLayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    tabLayout.addWidget(self.anaLabel)
    tabLayout.addWidget(self.anaView)

    # Add the pagination widget to the layout near the trace table
    tabLayout.addWidget(self.paginationWidget)

    # initialize page info
    self._updatePageInfo()

def _updatePageInfo(self):
    """Update the page information label"""
    if hasattr(self.anaModel, '_chunkedData') and self.anaModel._chunkedData:
        cd = self.anaModel._chunkedData
        self.lblPageInfo.setText(
            f'Page {cd.currentChunk + 1:,} of {cd.totalChunks:,} '
            f'(Rows {cd.currentChunk * cd.chunkSize + 1:,}-'
            f'{min((cd.currentChunk + 1) * cd.chunkSize, cd.getTotalRows()):,} '
            f'of {cd.getTotalRows():,})'
        )

        # Enable/disable navigation buttons
        self.btnFirstPage.setEnabled(cd.currentChunk > 0)
        self.btnPrevPage.setEnabled(cd.currentChunk > 0)
        self.btnNextPage.setEnabled(cd.currentChunk < cd.totalChunks - 1)
        self.btnLastPage.setEnabled(cd.currentChunk < cd.totalChunks - 1)

        self.gotoLabel.setEnabled(cd.getTotalRows() > 0)
        self.gotoEdit.setEnabled(cd.getTotalRows() > 0)
        self.btnGoto.setEnabled(cd.getTotalRows() > 0)
    else:
        self.lblPageInfo.setText('No paging')

        # Enable/disable navigation buttons
        self.btnFirstPage.setEnabled(False)
        self.btnPrevPage.setEnabled(False)
        self.btnNextPage.setEnabled(False)
        self.btnLastPage.setEnabled(False)

        self.gotoLabel.setEnabled(False)
        self.gotoEdit.setEnabled(False)
        self.btnGoto.setEnabled(False)

def _goToFirstPage(self):
    """Navigate to the first chunk of data"""
    if hasattr(self.anaModel, '_chunkedData') and self.anaModel._chunkedData:
        if self.anaModel._chunkedData.gotoChunk(0):
            # Update model with new chunk data
            self.anaModel.layoutAboutToBeChanged.emit()
            currentChunk = self.anaModel._chunkedData.getCurrentChunk()
            self.anaModel._data = np.copy(currentChunk)  # Make a copy to avoid memory mapping issues
            self.anaModel.layoutChanged.emit()
            # Update page info
            self._updatePageInfo()
            # Reset selection
            self.anaView.clearSelection()

def _goToPrevPage(self):
    """Navigate to the previous chunk of analysis rows."""
    cd = getattr(self.anaModel, '_chunkedData', None)
    if not cd:
        return
    if cd.previousChunk():
        self.anaModel.layoutAboutToBeChanged.emit()
        self.anaModel._data = np.copy(cd.getCurrentChunk())
        self.anaModel.layoutChanged.emit()
        self._updatePageInfo()
        self.anaView.clearSelection()

def _goToNextPage(self):
    """Navigate to the next chunk of data"""
    if hasattr(self.anaModel, '_chunkedData') and self.anaModel._chunkedData:
        if self.anaModel._chunkedData.nextChunk():
            # Update model with new chunk data
            self.anaModel.layoutAboutToBeChanged.emit()
            currentChunk = self.anaModel._chunkedData.getCurrentChunk()
            self.anaModel._data = np.copy(currentChunk)  # Make a copy to avoid memory mapping issues
            self.anaModel.layoutChanged.emit()
            # Update page info
            self._updatePageInfo()
            # Reset selection
            self.anaView.clearSelection()

def _goToLastPage(self):
    """Navigate to the last chunk of data"""
    if hasattr(self.anaModel, '_chunkedData') and self.anaModel._chunkedData:
        lastChunk = self.anaModel._chunkedData.totalChunks - 1
        if self.anaModel._chunkedData.gotoChunk(lastChunk):
            # Update model with new chunk data
            self.anaModel.layoutAboutToBeChanged.emit()
            currentChunk = self.anaModel._chunkedData.getCurrentChunk()
            self.anaModel._data = np.copy(currentChunk)  # Make a copy to avoid memory mapping issues
            self.anaModel.layoutChanged.emit()
            # Update page info
            self._updatePageInfo()
            # Reset selection
            self.anaView.clearSelection()

def _goToSpecificRow(self):
    """Navigate to a specific row in the dataset"""
    if hasattr(self.anaModel, '_chunkedData') and self.anaModel._chunkedData:
        try:
            # Get row number from the input field
            rowNumber = int(self.gotoEdit.text()) - 1  # Convert to 0-based index
            totalRows = self.anaModel._chunkedData.getTotalRows()

            if 0 <= rowNumber < totalRows:
                # Calculate which chunk contains this row
                chunkSize = self.anaModel._chunkedData.chunkSize
                targetChunk = rowNumber // chunkSize

                # Go to that chunk
                if self.anaModel._chunkedData.gotoChunk(targetChunk):
                    # Update model with new chunk data
                    self.anaModel.layoutAboutToBeChanged.emit()
                    currentChunk = self.anaModel._chunkedData.getCurrentChunk()
                    self.anaModel._data = np.copy(currentChunk)
                    self.anaModel.layoutChanged.emit()

                    # Calculate the local row index within the chunk
                    localRow = rowNumber % chunkSize

                    # Select and scroll to the row
                    self.anaView.selectRow(localRow)
                    self.anaView.scrollTo(self.anaModel.index(localRow, 0))

                    # Update page info
                    self._updatePageInfo()
            else:
                self.appendLogMessage(f'Input&nbsp;&nbsp;: Trace number out of range (1-{totalRows})', MsgType.Error)
        except ValueError:
            self.appendLogMessage('Input&nbsp;&nbsp;: Please enter a valid trace number', MsgType.Error)






