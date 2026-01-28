from types import MethodType

import numpy as np
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                                 QPushButton, QVBoxLayout, QWidget)

from .enums_and_int_flags import MsgType
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

    # Below are methods for navigation through the analysis table
    # these methods make use of MethodType to bind them to the RollMainWindow class
    # See: https://docs.python.org/3/library/types.html#types.MethodType
    # See: https://runebook.dev/en/docs/python/library/types/types.MethodType
    self._updatePageInfo = MethodType(_update_page_info, self)
    self._goToFirstPage = MethodType(_go_to_first_page, self)
    self._goToPrevPage = MethodType(_go_to_prev_page, self)
    self._goToNextPage = MethodType(_go_to_next_page, self)
    self._goToLastPage = MethodType(_go_to_last_page, self)
    self._goToSpecificRow = MethodType(_go_to_specific_row, self)

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

def _update_page_info(self):
    """Update the page information label"""
    if hasattr(self.anaModel, '_chunked_data') and self.anaModel._chunked_data:
        cd = self.anaModel._chunked_data
        self.lblPageInfo.setText(
            f'Page {cd.current_chunk + 1:,} of {cd.total_chunks:,} '
            f'(Rows {cd.current_chunk * cd.chunk_size + 1:,}-'
            f'{min((cd.current_chunk + 1) * cd.chunk_size, cd.get_total_rows()):,} '
            f'of {cd.get_total_rows():,})'
        )

        # Enable/disable navigation buttons
        self.btnFirstPage.setEnabled(cd.current_chunk > 0)
        self.btnPrevPage.setEnabled(cd.current_chunk > 0)
        self.btnNextPage.setEnabled(cd.current_chunk < cd.total_chunks - 1)
        self.btnLastPage.setEnabled(cd.current_chunk < cd.total_chunks - 1)

        self.gotoLabel.setEnabled(cd.get_total_rows() > 0)
        self.gotoEdit.setEnabled(cd.get_total_rows() > 0)
        self.btnGoto.setEnabled(cd.get_total_rows() > 0)
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

def _go_to_first_page(self):
    """Navigate to the first chunk of data"""
    if hasattr(self.anaModel, '_chunked_data') and self.anaModel._chunked_data:
        if self.anaModel._chunked_data.goto_chunk(0):
            # Update model with new chunk data
            self.anaModel.layoutAboutToBeChanged.emit()
            current_chunk = self.anaModel._chunked_data.get_current_chunk()
            self.anaModel._data = np.copy(current_chunk)  # Make a copy to avoid memory mapping issues
            self.anaModel.layoutChanged.emit()
            # Update page info
            self._updatePageInfo()
            # Reset selection
            self.anaView.clearSelection()

def _go_to_prev_page(self):
    """Navigate to the previous chunk of analysis rows."""
    cd = getattr(self.anaModel, '_chunked_data', None)
    if not cd:
        return
    if cd.previous_chunk():
        self.anaModel.layoutAboutToBeChanged.emit()
        self.anaModel._data = np.copy(cd.get_current_chunk())
        self.anaModel.layoutChanged.emit()
        self._updatePageInfo()
        self.anaView.clearSelection()

def _go_to_next_page(self):
    """Navigate to the next chunk of data"""
    if hasattr(self.anaModel, '_chunked_data') and self.anaModel._chunked_data:
        if self.anaModel._chunked_data.next_chunk():
            # Update model with new chunk data
            self.anaModel.layoutAboutToBeChanged.emit()
            current_chunk = self.anaModel._chunked_data.get_current_chunk()
            self.anaModel._data = np.copy(current_chunk)  # Make a copy to avoid memory mapping issues
            self.anaModel.layoutChanged.emit()
            # Update page info
            self._updatePageInfo()
            # Reset selection
            self.anaView.clearSelection()

def _go_to_last_page(self):
    """Navigate to the last chunk of data"""
    if hasattr(self.anaModel, '_chunked_data') and self.anaModel._chunked_data:
        last_chunk = self.anaModel._chunked_data.total_chunks - 1
        if self.anaModel._chunked_data.goto_chunk(last_chunk):
            # Update model with new chunk data
            self.anaModel.layoutAboutToBeChanged.emit()
            current_chunk = self.anaModel._chunked_data.get_current_chunk()
            self.anaModel._data = np.copy(current_chunk)  # Make a copy to avoid memory mapping issues
            self.anaModel.layoutChanged.emit()
            # Update page info
            self._updatePageInfo()
            # Reset selection
            self.anaView.clearSelection()

def _go_to_specific_row(self):
    """Navigate to a specific row in the dataset"""
    if hasattr(self.anaModel, '_chunked_data') and self.anaModel._chunked_data:
        try:
            # Get row number from the input field
            row_number = int(self.gotoEdit.text()) - 1  # Convert to 0-based index
            total_rows = self.anaModel._chunked_data.get_total_rows()

            if 0 <= row_number < total_rows:
                # Calculate which chunk contains this row
                chunk_size = self.anaModel._chunked_data.chunk_size
                target_chunk = row_number // chunk_size

                # Go to that chunk
                if self.anaModel._chunked_data.goto_chunk(target_chunk):
                    # Update model with new chunk data
                    self.anaModel.layoutAboutToBeChanged.emit()
                    current_chunk = self.anaModel._chunked_data.get_current_chunk()
                    self.anaModel._data = np.copy(current_chunk)
                    self.anaModel.layoutChanged.emit()

                    # Calculate the local row index within the chunk
                    local_row = row_number % chunk_size

                    # Select and scroll to the row
                    self.anaView.selectRow(local_row)
                    self.anaView.scrollTo(self.anaModel.index(local_row, 0))

                    # Update page info
                    self._updatePageInfo()
            else:
                self.appendLogMessage(f'Input&nbsp;&nbsp;: Trace number out of range (1-{total_rows})', MsgType.Error)
        except ValueError:
            self.appendLogMessage('Input&nbsp;&nbsp;: Please enter a valid trace number', MsgType.Error)
