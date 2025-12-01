import copy
import json
import os
import re
import shlex
from enum import IntEnum

import pyqtgraph as pg
from qgis.gui import QgsFileWidget, QgsProjectionSelectionWidget
from qgis.PyQt.QtCore import QFileInfo, QSettings, Qt
from qgis.PyQt.QtGui import (QColor, QFont, QFontMetricsF, QIcon, QPainter,
                             QSyntaxHighlighter, QTextCharFormat, QTextOption)
from qgis.PyQt.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFrame,
                                 QHBoxLayout, QLabel, QLineEdit, QListWidget,
                                 QListWidgetItem, QMessageBox, QPlainTextEdit,
                                 QPushButton, QSizePolicy, QSpinBox,
                                 QTabWidget, QVBoxLayout, QWidget)

from . import config  # used to pass initial settings

current_dir = os.path.dirname(os.path.abspath(__file__))
resource_dir = os.path.join(current_dir, 'resources')

class BlackLine(QFrame):
    def __init__(self, width: int = 1, parent=None):
        # See: https://doc.qt.io/qtforpython-5/PySide2/QtGui/QColorConstants.html for color constants
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setStyleSheet("background-color: black;")
        self.setFixedHeight(width)  # 1px thick

class LineHighlighter(QSyntaxHighlighter):
    """
    Custom highlighter to color lines based on their starting character:
    - Lines starting with 'h' or 'H': Grey
    - Lines starting with 's' or 'S': Dark Red
    - Lines starting with 'r' or 'R': Dark Blue
    """

    def __init__(self, parent=None):
        super(LineHighlighter, self).__init__(parent)

        # Define formats for each line type
        self.greyFormat = QTextCharFormat()
        self.greyFormat.setForeground(QColor('#7a7a7a'))  # Dark Grey
        # self.greyFormat.setFont(QFont('Cascadia Mono', 10))  # Monospaced font

        self.darkRedFormat = QTextCharFormat()
        self.darkRedFormat.setForeground(QColor('#8B0000'))  # Dark Red
        # self.darkRedFormat.setFont(QFont('Cascadia Mono', 10))  # Monospaced font

        self.darkBlueFormat = QTextCharFormat()
        self.darkBlueFormat.setForeground(QColor('#00008B'))  # Dark Blue
        # self.darkBlueFormat.setFont(QFont('Cascadia Mono', 10))  # Monospaced font

        self.darkGreenFormat = QTextCharFormat()
        self.darkGreenFormat.setForeground(QColor('#006400'))  # Dark Green
        # self.darkGreenFormat.setFont(QFont('Cascadia Mono', 10))  # Monospaced font

    def highlightBlock(self, text):
        # Check the starting character of the line and apply the corresponding format
        if text.startswith('h') or text.startswith('H'):
            self.setFormat(0, len(text), self.greyFormat)
        elif text.startswith('s') or text.startswith('S'):
            self.setFormat(0, len(text), self.darkRedFormat)
        elif text.startswith('r') or text.startswith('R'):
            self.setFormat(0, len(text), self.darkBlueFormat)
        elif text.startswith('x') or text.startswith('X'):
            self.setFormat(0, len(text), self.darkGreenFormat)

class ColumnBound(IntEnum):
    FROM = 0
    TO = 1

class CustomPlainTextEdit(QPlainTextEdit):
    """
    Custom QPlainTextEdit with some vertical lines drawn after every 10th character.
    """

    def __init__(self, parent=None):
        super(CustomPlainTextEdit, self).__init__(parent)
        # font = QFont("Monospace")
        # font.setStyleHint(QFont.TypeWriter)
        # font.setWeight(18)
        # self.setFont(font)  # Monospaced font for all text
        self.setFont(QFont('Cascadia Mono', 10))  # Monospaced font
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setWordWrapMode(QTextOption.WrapMode.NoWrap)
        self.setStyleSheet('background-color: #FFFFF2; color: #000000;')        # Light yellow background, black text

        self.line1 = 0
        self.line2 = 1

    def paintEvent(self, event):
        # Call the base class paintEvent to ensure the text is drawn as usual
        super(CustomPlainTextEdit, self).paintEvent(event)

        # Start preparing for the vertical lines
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)          # Disable anti-aliasing for pixel-perfect lines

        # Set cosmetic pen with width 0 for consistent 1px lines
        pen = painter.pen()
        pen.setColor(QColor('#000080'))  # dark color for the line
        pen.setCosmetic(True)
        pen.setWidthF(2)                                                        # Force exact 2-pixel width
        painter.setPen(pen)

        # Use QFontMetricsF for floating point precision to prevent drift
        font_metrics = QFontMetricsF(self.font())
        char_width = font_metrics.horizontalAdvance(' ')

        # Get the document margin to align correctly with the text start
        margin = self.document().documentMargin()
        x_offset = margin - self.horizontalScrollBar().value()

        # Draw the lines for the full height of the widget
        # Calculate positions using float math, then round to int for drawing
        x1 = round(self.line1 * char_width + x_offset)
        x2 = round(self.line2 * char_width + x_offset)

        height = self.viewport().height()
        painter.drawLine(x1, 0, x1, height)
        painter.drawLine(x2, 0, x2, height)

        # for n in range(0, 80):
        #     x = round(n  * char_width + x_offset)                             # QC the line positions
        #     painter.drawLine(x, 0, x, height)

        painter.end()

class SpsImportDialog(QDialog):
    def __init__(self, parent=None, crs=None, directory=None):
        super().__init__(parent)

        # to access the main window and its components
        self.parent = parent
        self.crs = crs
        self.oldCrs = crs
        self.setWindowTitle('SPS Import')
        self.setMinimumWidth(750)
        self.setMinimumHeight(500)

        self.fileNames = []
        self.spsFiles = []
        self.rpsFiles = []
        self.xpsFiles = []

        # Main layout
        # --- SPS Implementation selector at the top ---
        selectorLayout = QVBoxLayout()
        selectorLayout.setAlignment(Qt.AlignmentFlag.AlignTop)                  # Top-align all children
        selectorLayout.setSpacing(4)                                            # tighten vertical gaps, including label→list

        label_style = 'font-family: Arial; font-weight: bold; font-size: 15px;'

        filesLabel = QLabel('Select SPS files to import:')
        filesLabel.setStyleSheet(label_style)
        selectorLayout.addWidget(filesLabel)

        nameFilter = (
            'SPS triplets (*.s01 *.r01 *.x01);;'
            'SPS triplets (*.sps *.rps *.xps);;'
            'Source   files (*.sps *.s01 *.sp1);;'
            'Receiver files (*.rps *.r01 *.rp1);;'
            'Relation files (*.xps *.x01 *.xp1);;'
            'All files (*.*)'
        )  # file extensions

        spsFilesWidget = QgsFileWidget()
        if directory and os.path.isdir(directory):
            spsFilesWidget.setDefaultRoot(directory)
        spsFilesWidget.setStorageMode(QgsFileWidget.GetMultipleFiles)
        spsFilesWidget.setFilter(nameFilter)
        spsFilesWidget.fileChanged.connect(self.onSpsFilesChanged)

        selectorLayout.addWidget(spsFilesWidget)

        # SPS file input fields
        spsLabel = QLabel('SPS files')
        spsLabel.setMaximumWidth(80)  # Fixed width for label
        self.spsEdit = QLineEdit()
        self.spsEdit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)  # Take remaining horizontal space

        spsLayout = QHBoxLayout()
        spsLayout.addWidget(spsLabel)
        spsLayout.addWidget(self.spsEdit)
        selectorLayout.addLayout(spsLayout)

        # XPS file input fields
        xpsLabel = QLabel('XPS files')
        xpsLabel.setMaximumWidth(80)  # Fixed width for label
        self.xpsEdit = QLineEdit()
        self.xpsEdit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)  # Take remaining horizontal space

        xpsLayout = QHBoxLayout()
        xpsLayout.addWidget(xpsLabel)
        xpsLayout.addWidget(self.xpsEdit)
        selectorLayout.addLayout(xpsLayout)

        # RPS file input fields
        rpsLabel = QLabel('RPS files')
        rpsLabel.setMaximumWidth(80)  # Fixed width for label
        self.rpsEdit = QLineEdit()
        self.rpsEdit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)  # Take remaining horizontal space

        rpsLayout = QHBoxLayout()
        rpsLayout.addWidget(rpsLabel)
        rpsLayout.addWidget(self.rpsEdit)
        selectorLayout.addLayout(rpsLayout)

        line1 = BlackLine()
        selectorLayout.addWidget(line1)
        selectorLayout.addWidget(QLabel(''))                                    # spacer

        crsLabel = QLabel('Select SPS CRS projection:')
        crsLabel.setStyleSheet(label_style)
        selectorLayout.addWidget(crsLabel)

        self.crsWidget = QgsProjectionSelectionWidget()
        self.crsWidget.setCrs(self.crs)
        self.crsWidget.crsChanged.connect(self.onCrsChanged)

        selectorLayout.addWidget(self.crsWidget)

        line2 = BlackLine()
        selectorLayout.addWidget(line2)
        selectorLayout.addWidget(QLabel(''))                                    # spacer

        selectorLabel = QLabel('Select SPS Format Implementation:')
        selectorLabel.setStyleSheet(label_style)
        selectorLayout.addWidget(selectorLabel)

        # List widget (editable, min 4 rows visible)
        # Alternatively an editable QComboBox can be used. See: https://www.pythonguis.com/docs/qcombobox/
        self.enforceUniqueName = True

        self.spsFormatListInitializing = True
        self.spsFormatList = QListWidget()
        self.spsFormatList.itemChanged.connect(self.ensureUniqueSpsName)
        self.spsFormatList.currentRowChanged.connect(self.onSpsFormatChanged)

        self.spsFormatList.setFrameShape(QFrame.Shape.Panel)
        self.spsFormatList.setFrameShadow(QFrame.Shadow.Sunken)
        self.spsFormatList.setLineWidth(1)
        self.spsFormatList.setMidLineWidth(0)
        self.spsFormatList.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Calculate height for exactly 4 visible rows based on font metrics
        font_metrics = QFontMetricsF(self.spsFormatList.font())
        item_height = font_metrics.height() + 4                                 # Add padding per item
        visible_rows = 4
        list_height = int(item_height * visible_rows) + 4                       # Add 4 for widget borders
        self.spsFormatList.setFixedHeight(list_height)

        # Populate from spsNames
        spsNames = []                                                           # create list of sps names from config.spsFormatList
        for n in config.spsFormatList:
            spsNames.append(n['name'])

        for i, name in enumerate(spsNames):
            self.spsFormatList.addItem(name)                                    # Add each name as an item
            item = self.spsFormatList.item(i)                                   # Make items editable
            item.setFlags(item.flags() | Qt.ItemIsEditable)

        items = self.spsFormatList.findItems(config.spsDialect, Qt.MatchExactly)   # select default SPS formatitem
        if items:
            item = items[0]
            self.spsFormatList.setCurrentItem(item)
            self.spsFormatList.scrollToItem(item)
        else:
            self.spsFormatList.setCurrentRow(0)                                 # select first item by default
        self.spsFormatListInitializing = False                                  # finished initializing list widget

        formatLayout = QHBoxLayout()
        formatLayout.setAlignment(Qt.AlignmentFlag.AlignTop)                    # Force top alignment

        # Add list widget and buttonLayout
        formatWidget = QWidget()
        formatWidget.setLayout(formatLayout)
        formatWidget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # formatWidget.setFixedHeight(list_height)                                # or list_height + button margins

        selectorLayout.addWidget(formatWidget, 0, Qt.AlignmentFlag.AlignTop)

        # Buttons for add/remove
        buttonLayout = QVBoxLayout()
        # buttonLayout.addSpacing(20)  # spacer before the buttons

        self.addButton = QPushButton()
        self.addButton.setIcon(QIcon(os.path.join(resource_dir,'symbologyAdd.svg')))
        self.addButton.setMaximumWidth(30)
        self.addButton.setToolTip("Add a new SPS implementation to the list, based on the current selection")

        self.addButton.clicked.connect(self.onAddSpsName)
        buttonLayout.addWidget(self.addButton)

        self.removeButton = QPushButton()
        self.removeButton.setIcon(QIcon(os.path.join(resource_dir,'symbologyRemove.svg')))
        self.removeButton.setMaximumWidth(30)
        self.removeButton.setToolTip("Remove the selected SPS implementation from the list")
        self.removeButton.clicked.connect(self.onRemoveSpsName)
        buttonLayout.addWidget(self.removeButton)
        buttonLayout.addStretch()

        formatLayout.addWidget(self.spsFormatList)
        formatLayout.addLayout(buttonLayout)
        formatLayout.addStretch()

        self.databaseButton = QPushButton('  Update SPS database  ')
        self.databaseButton.setToolTip("Update the SPS implementation database stored in user's registry")
        self.databaseButton.setEnabled(False)                                   # nothing has changed yet
        # self.databaseButton.setStyleSheet('font-weight: bold; background-color: #3663FF; color: white; padding: 6px 16px;')
        self.databaseButton.setStyleSheet(label_style)
        self.databaseButton.setMinimumHeight(28)
        self.databaseButton.setMaximumWidth(220)

        # self.databaseButton.setStyleSheet(label_style)
        self.databaseButton.clicked.connect(self.onUpdateSpsDatabase)

        dbButtonLayout = QVBoxLayout()
        dbButtonLayout.addStretch()                     # push the button to the bottom
        dbButtonLayout.addWidget(self.databaseButton)

        formatLayout.addLayout(dbButtonLayout)
        # formatLayout.addWidget(self.databaseButton)
        formatLayout.addStretch()

        selectorLayout.addLayout(formatLayout)
        # selectorLayout.addWidget(QLabel(''))                                    # spacer

        line3 = BlackLine()
        selectorLayout.addWidget(line3)
        selectorLayout.addWidget(QLabel(''))                                    # spacer

        spsFieldLabel = QLabel('Select SPS field to highlight:')
        spsFieldLabel.setStyleSheet(label_style)
        selectorLayout.addWidget(spsFieldLabel)
        selectorLayout.addSpacing(6)                                            # small spacer
        # selectorLayout.addWidget(QLabel(''))                                  # spacer

        spsItems = []                                                           # create list of sps items from config.spsPointFormatDict
        for value in config.spsPointFormatDict.values():
            spsItems.append(value)

        xpsItems = []                                                           # create list of xps items from config.spsRelationFormatDict
        for value in config.spsRelationFormatDict.values():
            xpsItems.append(value)

        # SPS highlight fields
        spsLabel2 = QLabel('SPS field')
        spsLabel2.setMaximumWidth(80)  # Fixed width for label

        self.spsCombo = QComboBox()
        self.spsCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)  # Take remaining horizontal space
        self.spsCombo.addItems(spsItems)
        self.spsCombo.highlighted.connect(self.onSpsComboHighlighted)
        self.spsCombo.currentIndexChanged.connect(self.onSpsComboHighlighted)
        self.spsCombo.activated.connect(self.onSpsComboHighlighted)

        spsLabel3 = QLabel('From column:')
        spsLabel3.setMaximumWidth(100)                                          # Fixed width for label

        self.spsFromSpin = QSpinBox()
        self.spsFromSpin.setMinimum(1)                                          # minimum value is 1
        self.spsFromSpin.setMaximumWidth(90)                                    # Fixed width for label
        self.spsFromSpin.valueChanged.connect(self.onSpsSpinboxFromValueChanged)

        spsLabel4 = QLabel('To column:')
        spsLabel4.setMaximumWidth(100)                                          # Fixed width for label

        self.spsToSpin = QSpinBox()
        self.spsToSpin.setMinimum(1)                                            # minimum value is 1
        self.spsToSpin.setMaximumWidth(90)                                      # Fixed width for label
        self.spsToSpin.valueChanged.connect(self.onSpsSpinboxToValueChanged)

        spsLayout2 = QHBoxLayout()
        spsLayout2.addWidget(spsLabel2)
        spsLayout2.addWidget(self.spsCombo)
        spsLayout2.addWidget(spsLabel3)
        spsLayout2.addWidget(self.spsFromSpin)
        spsLayout2.addWidget(spsLabel4)
        spsLayout2.addWidget(self.spsToSpin)
        selectorLayout.addLayout(spsLayout2)

        # XPS highlight fields
        xpsLabel2 = QLabel('XPS field')
        xpsLabel2.setMaximumWidth(80)  # Fixed width for label

        self.xpsCombo = QComboBox()
        self.xpsCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)  # Take remaining horizontal space
        self.xpsCombo.addItems(xpsItems)
        self.xpsCombo.highlighted.connect(self.onXpsComboHighlighted)
        self.xpsCombo.currentIndexChanged.connect(self.onXpsComboHighlighted)
        self.xpsCombo.activated.connect(self.onXpsComboHighlighted)

        xpsLabel3 = QLabel('From column:')
        xpsLabel3.setMaximumWidth(100)  # Fixed width for label

        self.xpsFromSpin = QSpinBox()
        self.xpsFromSpin.setMinimum(1)                                          # minimum value is 1
        self.xpsFromSpin.setMaximumWidth(90)                                    # Fixed width for label
        self.xpsFromSpin.valueChanged.connect(self.onXpsSpinboxFromValueChanged)

        xpsLabel4 = QLabel('To column:')
        xpsLabel4.setMaximumWidth(100)                                          # Fixed width for label

        self.xpsToSpin = QSpinBox()
        self.xpsToSpin.setMinimum(1)                                            # minimum value is 1
        self.xpsToSpin.setMaximumWidth(90)                                      # Fixed width for label
        self.xpsToSpin.valueChanged.connect(self.onXpsSpinboxToValueChanged)

        xpsLayout2 = QHBoxLayout()
        xpsLayout2.addWidget(xpsLabel2)
        xpsLayout2.addWidget(self.xpsCombo)
        xpsLayout2.addWidget(xpsLabel3)
        xpsLayout2.addWidget(self.xpsFromSpin)
        xpsLayout2.addWidget(xpsLabel4)
        xpsLayout2.addWidget(self.xpsToSpin)
        selectorLayout.addLayout(xpsLayout2)

        # RPS highlight fields
        rpsLabel2 = QLabel('RPS field')
        rpsLabel2.setMaximumWidth(80)                                           # Fixed width for label

        self.rpsCombo = QComboBox()
        self.rpsCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.rpsCombo.addItems(spsItems)
        self.rpsCombo.highlighted.connect(self.onRpsComboHighlighted)
        self.rpsCombo.currentIndexChanged.connect(self.onRpsComboHighlighted)
        self.rpsCombo.activated.connect(self.onRpsComboHighlighted)

        rpsLabel3 = QLabel('From column:')
        rpsLabel3.setMaximumWidth(100)                                          # Fixed width for label

        self.rpsFromSpin = QSpinBox()
        self.rpsFromSpin.setMinimum(1)                                          # minimum value is 1
        self.rpsFromSpin.setMaximumWidth(90)                                    # Fixed width for label
        self.rpsFromSpin.valueChanged.connect(self.onRpsSpinboxFromValueChanged)

        rpsLabel4 = QLabel('To column:')
        rpsLabel4.setMaximumWidth(100)                                          # Fixed width for label

        self.rpsToSpin = QSpinBox()
        self.rpsToSpin.setMinimum(1)                                            # minimum value is 1
        self.rpsToSpin.setMaximumWidth(90)                                      # Fixed width for label
        self.rpsToSpin.valueChanged.connect(self.onRpsSpinboxToValueChanged)

        rpsLayout2 = QHBoxLayout()
        rpsLayout2.addWidget(rpsLabel2)
        rpsLayout2.addWidget(self.rpsCombo)
        rpsLayout2.addWidget(rpsLabel3)
        rpsLayout2.addWidget(self.rpsFromSpin)
        rpsLayout2.addWidget(rpsLabel4)
        rpsLayout2.addWidget(self.rpsToSpin)
        selectorLayout.addLayout(rpsLayout2)

        # Tab widget for SPS, XPS, RPS content display
        self.tabWidget = QTabWidget()
        self.tabWidget.setTabPosition(QTabWidget.TabPosition.South)
        self.tabWidget.setTabShape(QTabWidget.TabShape.Rounded)
        self.tabWidget.setDocumentMode(False)                               # has only effect on OSX ?!
        self.tabWidget.resize(300, 300)

        self.spsTab = CustomPlainTextEdit()
        self.xpsTab = CustomPlainTextEdit()
        self.rpsTab = CustomPlainTextEdit()

        self.spsHighlighter = LineHighlighter(self.spsTab.document())
        self.xpsHighlighter = LineHighlighter(self.xpsTab.document())
        self.rpsHighlighter = LineHighlighter(self.rpsTab.document())

        self.tabWidget.addTab(self.spsTab, 'SPS')
        self.tabWidget.addTab(self.xpsTab, 'XPS')
        self.tabWidget.addTab(self.rpsTab, 'RPS')
        selectorLayout.addWidget(self.tabWidget)

        buttons = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        self.buttonBox = QDialogButtonBox(buttons)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setText('Import')  # Change "OK" to "Import"
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        selectorLayout.addWidget(self.buttonBox)

        self.setLayout(selectorLayout)

    def onUpdateSpsDatabase(self):
        settings = QSettings(config.organization, config.application)
        settings.setValue('settings/sps/spsDialect', config.spsDialect)         # save current SPS dialect

        settings.beginGroup('settings/sps/spsFormatList')
        settings.remove('')                                                     # clear existing entries
        for entry in config.spsFormatList:
            name = entry.get('name', 'Unnamed')
            settings.setValue(name, json.dumps(entry))
        settings.endGroup()

        settings.beginGroup('settings/sps/xpsFormatList')
        settings.remove('')                                                     # clear existing entries
        for entry in config.xpsFormatList:
            name = entry.get('name', 'Unnamed')
            settings.setValue(name, json.dumps(entry))
        settings.endGroup()

        settings.beginGroup('settings/sps/rpsFormatList')
        settings.remove('')                                                     # clear existing entries
        for entry in config.rpsFormatList:
            name = entry.get('name', 'Unnamed')
            settings.setValue(name, json.dumps(entry))
        settings.endGroup()

        settings.sync()

    def onSpsComboHighlighted(self, index):
        print("SPS item highlighted:", index)

        keys = list(config.spsPointFormatDict.keys())
        if 0 <= index < len(keys):
            spsKey = keys[index]
        else:
            raise IndexError(f"SPS index {index} is out of range for spsPointFormatDict ({len(keys)} entries)")

        spsFormatIndex = self.spsFormatList.currentRow()
        # print("SPS format number:", spsFormatIndex)

        spsFormat = config.spsFormatList[spsFormatIndex]
        # print("SPS spsFormat:", spsFormat)

        self._setSpinValue(self.spsFromSpin, spsFormat[spsKey][0] + 1)          # +1 to convert from 0-based to 1-based indexing
        self._setSpinValue(self.spsToSpin, spsFormat[spsKey][1])                # this column is exclusive, so no +1 needed
        # print("SPS from/to:", spsFormat[spsKey][0] + 1, spsFormat[spsKey][1])

        self.spsTab.line1 = spsFormat[spsKey][0]
        self.spsTab.line2 = spsFormat[spsKey][1]

        self.tabWidget.setCurrentIndex(0)  # select SPS Tab
        self.spsTab.update()

    def onXpsComboHighlighted(self, index):
        # print("XPS item highlighted:", index)

        keys = list(config.spsRelationFormatDict.keys())
        if 0 <= index < len(keys):
            xpsKey = keys[index]
        else:
            raise IndexError(f"XPS index {index} is out of range for spsRelationFormatDict ({len(keys)} entries)")

        spsFormatIndex = self.spsFormatList.currentRow()
        # print("SPS format number:", spsFormatIndex)

        xpsFormat = config.xpsFormatList[spsFormatIndex]
        # print("SPS spsFormat:", spsFormat)

        self._setSpinValue(self.xpsFromSpin, xpsFormat[xpsKey][0] + 1)          # +1 to convert from 0-based to 1-based indexing
        self._setSpinValue(self.xpsToSpin, xpsFormat[xpsKey][1])                # this column is exclusive, so no +1 needed

        self.xpsTab.line1 = xpsFormat[xpsKey][0]
        self.xpsTab.line2 = xpsFormat[xpsKey][1]

        self.tabWidget.setCurrentIndex(1)  # select XPS Tab
        self.xpsTab.update()

    def onRpsComboHighlighted(self, index):
        # print("RPS item highlighted:", index)

        keys = list(config.spsPointFormatDict.keys())
        if 0 <= index < len(keys):
            rpsKey = keys[index]
        else:
            raise IndexError(f"SPS index {index} is out of range for spsPointFormatDict ({len(keys)} entries)")

        rpsFormatIndex = self.spsFormatList.currentRow()
        # print("SPS format number:", rpsFormatIndex)

        rpsFormat = config.rpsFormatList[rpsFormatIndex]
        # print("RPS rpsFormat:", rpsFormat)

        self._setSpinValue(self.rpsFromSpin, rpsFormat[rpsKey][0] + 1)     # +1 to convert from 0-based to 1-based indexing
        self._setSpinValue(self.rpsToSpin, rpsFormat[rpsKey][1])           # this column is exclusive, so no +1 needed
        print("RPS from/to:", rpsFormat[rpsKey][0] + 1, rpsFormat[rpsKey][1])

        self.rpsTab.line1 = rpsFormat[rpsKey][0]
        self.rpsTab.line2 = rpsFormat[rpsKey][1]

        self.tabWidget.setCurrentIndex(2)  # select RPS Tab
        self.rpsTab.update()

    def accept(self):
        self.accepted()
        QDialog.accept(self)

    def accepted(self):
        # sps settings
        config.spsDialect =  self.spsFormatList.currentItem().text()

    def onSpsFormatChanged(self, row: int):
        if self.spsFormatListInitializing or row < 0:
            return

        index  = self.tabWidget.currentIndex()                     # get current tab
        if index == 0:
            self.onSpsComboHighlighted(self.spsCombo.currentIndex())
        elif index == 1:
            self.onXpsComboHighlighted(self.xpsCombo.currentIndex())
        elif index == 2:
            self.onRpsComboHighlighted(self.rpsCombo.currentIndex())

    def onCrsChanged(self, crs):
        """Handle changes in the selected CRS."""

        if not crs.isValid():
            QMessageBox.warning(None, 'Invalid CRS', 'An invalid coordinate system has been selected', QMessageBox.Ok)
            self.crsWidget.setCrs(self.oldCrs)
            return

        if crs.isGeographic():
            QMessageBox.warning(None, 'Invalid CRS', 'An invalid coordinate system has been selected\nGeographic (using lat/lon coordinates)', QMessageBox.Ok)
            self.crsWidget.setCrs(self.oldCrs)
            return

        self.crs = crs; self.oldCrs = crs

    def onSpsFilesChanged(self, fileNames):
        """Handle changes in selected SPS files."""

        self.fileNames = []                                                  # clear previous filenames and other lists
        self.spsFiles = []
        self.rpsFiles = []
        self.xpsFiles = []

        # Parse space-separated quoted filenames into a list. Example input: '"C:/path/file1.sps" "C:/path/file2.rps"'
        # Parse the input based on whether it contains quotes (multiple files) or not (single file)
        if isinstance(fileNames, str):
            if '"' in fileNames:
                # Multiple files: space-separated quoted strings like '"file1.sps" "file2.rps"'
                try:
                    self.fileNames = shlex.split(fileNames)
                except ValueError:
                    # Fallback if shlex fails (malformed quotes)
                    self.fileNames = fileNames.strip().replace('"', '').split()
            else:
                # Single file: plain path without quotes like 'C:/path/file.sps'
                self.fileNames = [fileNames.strip()] if fileNames.strip() else []
        else:
            # Already a list (edge case for some Qt versions)
            self.fileNames = fileNames

        for fileName in self.fileNames:
            suffix = QFileInfo(fileName).suffix().lower()
            if suffix.startswith('s'):
                self.spsFiles.append(fileName)
            elif suffix.startswith('r'):
                self.rpsFiles.append(fileName)
            elif suffix.startswith('x'):
                self.xpsFiles.append(fileName)
            else:
                baseName = QFileInfo(fileName).completeBaseName()
                QMessageBox.information(None, 'Import error', f"Unsupported file extension in selected file(s):\n\n'{baseName}.{suffix}'\n")
                return False

        # Populate the line edits with space-separated filenames (basename + extension only)
        self.spsEdit.setText(' '.join(f'"{QFileInfo(f).fileName()}"' for f in self.spsFiles))
        self.rpsEdit.setText(' '.join(f'"{QFileInfo(f).fileName()}"' for f in self.rpsFiles))
        self.xpsEdit.setText(' '.join(f'"{QFileInfo(f).fileName()}"' for f in self.xpsFiles))

        spsText = ''
        xpsText = ''
        rpsText = ''

        with pg.BusyCursor():                                               # this may take a while; start wait cursor
            for spsFile in self.spsFiles:
                with open(spsFile, 'r', encoding='utf-8') as file:
                    spsText += file.read()

            for xpsFile in self.xpsFiles:
                with open(xpsFile, 'r', encoding='utf-8') as file:
                    xpsText += file.read()

            for rpsFile in self.rpsFiles:
                with open(rpsFile, 'r', encoding='utf-8') as file:
                    rpsText += file.read()

            self.spsTab.setPlainText(spsText)  # for some reason unknown, the text is not colored properly, when setPlainText is used
            self.xpsTab.setPlainText(xpsText)  # see: https://doc.qt.io/qtforpython-6.5/examples/example_widgets_richtext_syntaxhighlighter.html
            self.rpsTab.setPlainText(rpsText)

    def _setSpinValue(self, spinBox: QSpinBox, value: int):
        prev = spinBox.blockSignals(True)
        try:
            spinBox.setValue(value)
        finally:
            spinBox.blockSignals(prev)

    def onSpsSpinboxFromValueChanged(self, _):
        self.onSpsSpinboxValueChanged(ColumnBound.FROM)

    def onSpsSpinboxToValueChanged(self, _):
        self.onSpsSpinboxValueChanged(ColumnBound.TO)

    def onXpsSpinboxFromValueChanged(self, _):
        self.onXpsSpinboxValueChanged(ColumnBound.FROM)

    def onXpsSpinboxToValueChanged(self, _):
        self.onXpsSpinboxValueChanged(ColumnBound.TO)

    def onRpsSpinboxFromValueChanged(self, _):
        self.onRpsSpinboxValueChanged(ColumnBound.FROM)

    def onRpsSpinboxToValueChanged(self, _):
        self.onRpsSpinboxValueChanged(ColumnBound.TO)

    def onSpsSpinboxValueChanged(self, bound: ColumnBound):
        bound = ColumnBound(bound)

        minCol = self.spsFromSpin.value() - 1                                   # -1 to convert from 1-based to 0-based indexing
        maxCol = self.spsToSpin.value()                                         # this column is exclusive, so no -1 needed

        # make sure from is always less than to
        minCol2 = min(minCol, maxCol)
        maxCol2 = max(maxCol, minCol)

        if minCol2 == maxCol2:                                                  # prevent equal values
            if bound is ColumnBound.FROM:
                maxCol2 = minCol2 + 1
            else:
                minCol2 = maxCol2 - 1

        self._setSpinValue(self.spsFromSpin, minCol2 + 1)
        self._setSpinValue(self.spsToSpin, maxCol2)

        spsFormatIndex = self.spsFormatList.currentRow()
        spsKey = list(config.spsPointFormatDict.keys())[self.spsCombo.currentIndex()]

        config.spsFormatList[spsFormatIndex][spsKey][0] = minCol2
        config.spsFormatList[spsFormatIndex][spsKey][1] = maxCol2

        self.spsTab.line1 = config.spsFormatList[spsFormatIndex][spsKey][0]
        self.spsTab.line2 = config.spsFormatList[spsFormatIndex][spsKey][1]

        self.tabWidget.setCurrentIndex(0)                                       # select SPS Tab
        self.databaseButton.setEnabled(True)                                    # enable "Update SPS database" button
        self.spsTab.update()

    def onXpsSpinboxValueChanged(self, bound: ColumnBound):
        bound = ColumnBound(bound)

        minCol = self.xpsFromSpin.value() - 1                                   # -1 to convert from 1-based to 0-based indexing
        maxCol = self.xpsToSpin.value()                                         # this column is exclusive, so no -1 needed

        # make sure from is always less than to
        minCol2 = min(minCol, maxCol)
        maxCol2 = max(maxCol, minCol)

        if minCol2 == maxCol2:                                                  # prevent equal values
            if bound is ColumnBound.FROM:
                maxCol2 = minCol2 + 1
            else:
                minCol2 = maxCol2 - 1

        self._setSpinValue(self.xpsFromSpin, minCol2 + 1)
        self._setSpinValue(self.xpsToSpin, maxCol2)

        spsFormatIndex = self.spsFormatList.currentRow()
        spsKey = list(config.spsRelationFormatDict.keys())[self.xpsCombo.currentIndex()]

        config.xpsFormatList[spsFormatIndex][spsKey][0] = minCol2
        config.xpsFormatList[spsFormatIndex][spsKey][1] = maxCol2

        self.spsTab.line1 = config.xpsFormatList[spsFormatIndex][spsKey][0]
        self.spsTab.line2 = config.xpsFormatList[spsFormatIndex][spsKey][1]

        self.tabWidget.setCurrentIndex(1)                                       # select XPS Tab
        self.databaseButton.setEnabled(True)                                    # enable "Update SPS database" button
        self.xpsTab.update()

    def onRpsSpinboxValueChanged(self, bound: ColumnBound):
        bound = ColumnBound(bound)

        minCol = self.rpsFromSpin.value() - 1                                   # -1 to convert from 1-based to 0-based indexing
        maxCol = self.rpsToSpin.value()                                         # this column is exclusive, so no -1 needed

        # make sure from is always less than to
        minCol2 = min(minCol, maxCol)
        maxCol2 = max(maxCol, minCol)

        if minCol2 == maxCol2:                                                  # prevent equal values
            if bound is ColumnBound.FROM:
                maxCol2 = minCol2 + 1
            else:
                minCol2 = maxCol2 - 1

        self._setSpinValue(self.rpsFromSpin, minCol2 + 1)
        self._setSpinValue(self.rpsToSpin, maxCol2)

        spsFormatIndex = self.spsFormatList.currentRow()
        rpsKey = list(config.spsPointFormatDict.keys())[self.rpsCombo.currentIndex()]

        config.rpsFormatList[spsFormatIndex][rpsKey][0] = minCol2
        config.rpsFormatList[spsFormatIndex][rpsKey][1] = maxCol2

        self.rpsTab.line1 = config.rpsFormatList[spsFormatIndex][rpsKey][0]
        self.rpsTab.line2 = config.rpsFormatList[spsFormatIndex][rpsKey][1]

        self.tabWidget.setCurrentIndex(2)                                       # select RPS Tab
        self.databaseButton.setEnabled(True)                                    # enable "Update SPS database" button
        self.rpsTab.update()

    def onAddSpsName(self):
        """Add a new editable entry to the SPS implementations list."""
        newName = 'New Implementation'
        currentItem = self.spsFormatList.currentItem()
        if currentItem is not None:
            # newName = f'{currentItem.text()} copy'
            newName = currentItem.text()

        currentRow = self.spsFormatList.currentRow()
        insertRow = currentRow + 1 if currentRow >= 0 else self.spsFormatList.count()

        newItem = QListWidgetItem(newName)
        newItem.setFlags(newItem.flags() | Qt.ItemIsEditable)

        existingNames = [self.spsFormatList.item(i).text() for i in range(self.spsFormatList.count())]
        if newName in existingNames:
            match = re.match(r'^(.*?)(?:\s*\((\d+)\))?$', newName)
            base = match.group(1).strip()
            counter = int(match.group(2)) + 1 if match.group(2) else 2
            uniqueName = f'{base} ({counter})'
            while uniqueName in existingNames:
                counter += 1
                uniqueName = f'{base} ({counter})'
            newName = uniqueName

        newItem.setText(newName)

        if not config.spsFormatList or not config.xpsFormatList:
            QMessageBox.warning(self, 'Add SPS format', 'No reference SPS/XPS format is available to duplicate.')
            return

        referenceRow = currentRow if currentRow >= 0 else 0
        referenceRow = min(referenceRow, len(config.spsFormatList) - 1)

        newSpsFormat = copy.deepcopy(config.spsFormatList[referenceRow])
        newXpsFormat = copy.deepcopy(config.xpsFormatList[referenceRow])
        newRpsFormat = copy.deepcopy(config.rpsFormatList[referenceRow])
        newSpsFormat['name'] = newName
        newXpsFormat['name'] = newName
        newRpsFormat['name'] = newName

        self.spsFormatList.insertItem(insertRow, newItem)

        config.spsFormatList.insert(insertRow, newSpsFormat)
        config.xpsFormatList.insert(insertRow, newXpsFormat)
        config.rpsFormatList.insert(insertRow, newRpsFormat)

        prevBlocked = self.spsFormatList.blockSignals(True)
        self.spsFormatList.setCurrentRow(insertRow)
        self.spsFormatList.blockSignals(prevBlocked)

        self.onSpsFormatChanged(insertRow)
        self.databaseButton.setEnabled(True)                                    # maybe update database now

    def onRemoveSpsName(self):
        """Remove the currently selected entry from the list."""
        currentRow = self.spsFormatList.currentRow()
        if currentRow >= 0:
            self.spsFormatList.takeItem(currentRow)                             # remove from the list widget
            if 0 <= currentRow < len(config.spsFormatList):                     # remove from the config list
                del config.spsFormatList[currentRow]

            if 0 <= currentRow < len(config.xpsFormatList):                     # remove from the config list
                del config.xpsFormatList[currentRow]

            self.databaseButton.setEnabled(True)                                # maybe update database now
        else:
            QMessageBox.information(self, 'Remove', 'Please select an item to remove.')

    def ensureUniqueSpsName(self, item: QListWidgetItem):
        if not self.enforceUniqueName or item is None:
            return

        name = item.text().strip()
        if not name:
            name = 'Unnamed'

        names = []
        for i in range(self.spsFormatList.count()):
            other = self.spsFormatList.item(i)
            if other is item:
                continue
            names.append(other.text())

        if name not in names:                           # name is unique; done
            item.setText(name)

            index = self.spsFormatList.row(item)                                # make sure the config entries are also updated
            if 0 <= index < len(config.spsFormatList):
                config.spsFormatList[index]['name'] = name
                config.xpsFormatList[index]['name'] = name
                config.rpsFormatList[index]['name'] = name
            return

        match = re.match(r'^(.*?)(?:\s*\((\d+)\))?$', name)
        base = match.group(1).strip()
        counter = int(match.group(2)) + 1 if match.group(2) else 2

        unique = f'{base} ({counter})'
        while unique in names:
            counter += 1
            unique = f'{base} ({counter})'

        self.enforceUniqueName = False
        try:
            item.setText(unique)
        finally:
            self.enforceUniqueName = True

        index = self.spsFormatList.row(item)
        if 0 <= index < len(config.spsFormatList):
            config.spsFormatList[index]['name'] = unique
            config.xpsFormatList[index]['name'] = unique
            config.rpsFormatList[index]['name'] = unique
