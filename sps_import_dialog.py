import pyqtgraph as pg
from qgis.PyQt.QtCore import QFileInfo, Qt
from qgis.PyQt.QtGui import QColor, QFont, QFontMetrics, QPainter, QSyntaxHighlighter, QTextCharFormat, QTextOption
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QHeaderView, QLabel, QMessageBox, QPlainTextEdit, QTabWidget, QVBoxLayout

from . import config  # used to pass initial settings


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
        # self.greyFormat.setFont(QFont('Courier New', 10))  # Monospaced font

        self.darkRedFormat = QTextCharFormat()
        self.darkRedFormat.setForeground(QColor('#8B0000'))  # Dark Red
        # self.darkRedFormat.setFont(QFont('Courier New', 10))  # Monospaced font

        self.darkBlueFormat = QTextCharFormat()
        self.darkBlueFormat.setForeground(QColor('#00008B'))  # Dark Blue
        # self.darkBlueFormat.setFont(QFont('Courier New', 10))  # Monospaced font

        self.darkGreenFormat = QTextCharFormat()
        self.darkGreenFormat.setForeground(QColor('#006400'))  # Dark Green
        # self.darkGreenFormat.setFont(QFont('Courier New', 10))  # Monospaced font

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


class CustomPlainTextEdit(QPlainTextEdit):
    """
    Custom QPlainTextEdit with some vertical lines drawn after every 10th character.
    """

    def __init__(self, parent=None):
        super(CustomPlainTextEdit, self).__init__(parent)
        self.setFont(QFont('Courier New', 10))  # Monospaced font for all text
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setWordWrapMode(QTextOption.WrapMode.NoWrap)
        self.setStyleSheet('background-color: #FFFFF2; color: #000000;')  # Light yellow background, black text

        self.line1 = 0
        self.line2 = 1

    def paintEvent(self, event):
        # Call the base class paintEvent to ensure the text is drawn
        super(CustomPlainTextEdit, self).paintEvent(event)

        # Draw the vertical line
        painter = QPainter(self.viewport())
        painter.setPen(QColor('#000080'))  # dark color for the line

        # Calculate the x-coordinate for the vertical line
        char_width = self.fontMetrics().averageCharWidth()
        x_offset = int(char_width * 0.38 - self.horizontalScrollBar().value())   # Apply offset to adjust the line and handle scrolling

        # Draw the line for the full height of the widget
        painter.drawLine(self.line1 * char_width + x_offset, 0, self.line1 * char_width + x_offset, self.viewport().height())
        painter.drawLine(self.line2 * char_width + x_offset, 0, self.line2 * char_width + x_offset, self.viewport().height())


class SpsImportDialog(QDialog):
    def __init__(self, parent=None, crs=None, directory=None):
        super().__init__(parent)

        # to access the main window and its components
        self.parent = parent
        self.setWindowTitle('SPS Import Dialog')
        self.setMinimumWidth(900)
        self.setMinimumHeight(500)

        buttons = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        self.buttonBox = QDialogButtonBox(buttons)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setText('Import')  # Change "OK" to "Import"
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        # We create the ParameterTree for the settings dialog
        # See: https://www.programcreek.com/python/example/114819/pyqtgraph.parametertree.ParameterTree
        # See: https://www.programcreek.com/python/?code=CadQuery%2FCQ-editor%2FCQ-editor-master%2Fcq_editor%2Fpreferences.py

        # We need to find the right sps entry in a list of dictionaries
        # See: https://stackoverflow.com/questions/8653516/search-a-list-of-dictionaries-in-python
        # See: https://stackoverflow.com/questions/4391697/find-the-index-of-a-dict-within-a-list-by-matching-the-dicts-value
        # See: https://python.hotexamples.com/examples/pyqtgraph.parametertree/ParameterTree/-/python-parametertree-class-examples.html?utm_content=cmp-true
        # See: https://github.com/DerThorsten/ivigraph/blob/master/layerviewer/viewer.py
        # See: https://programtalk.com/python-examples/pyqtgraph.parametertree.Parameter.create/?utm_content=cmp-true
        # See: http://radjkarl.github.io/fancyWidgets/_modules/fancywidgets/pyqtgraphBased/parametertree/parameterTypes.html
        # See: https://stackoverflow.com/questions/50795993/data-entered-by-the-user-are-not-taken-into-account-by-the-parameter-tree
        # See: http://pymodaq.cnrs.fr/en/latest/_modules/pymodaq/utils/parameter/ioxml.html
        # See: https://www.reddit.com/r/Python/comments/8qqznc/python_gui_and_parameter_tree_data_entered_by_the/
        # See: https://gist.github.com/blink1073/1b2f7ae3214742574d51
        # See: https://github.com/cbrunet/fibermodes/blob/master/fibermodesgui/fieldvisualizer/colormapwidget.py

        # Try this nice example
        # See: https://searchcode.com/file/50487139/gui/pyqtgraph/examples/parametertree.py/
        # See: https://github.com/campagnola/relativipy/blob/master/relativity.py how to register three paramater types (Clock, Grid and AccelerationGroup)

        # See: https://doc.qt.io/qtforpython-5/PySide2/QtGui/QColorConstants.html for color constants

        self.fileNames = []                                                     # list of all files to be imported
        self.spsFiles = []                                                      # list of SPS files to be imported
        self.rpsFiles = []
        self.xpsFiles = []

        spsNames = []                                                           # create list of sps names from config.spsFormatList
        for n in config.spsFormatList:
            spsNames.append(n['name'])

        spsItems = []                                                           # create list of sps items from config.spsFormatDict
        for value in config.spsFormatDict.values():
            spsItems.append(value)

        xpsItems = []                                                           # create list of sps items from config.spsFormatDict
        for value in config.xpsFormatDict.values():
            xpsItems.append(value)

        nameFilter = (
            'SPS triplets (*.s01 *.r01 *.x01);;'
            'SPS triplets (*.sps *.rps *.xps);;'
            'Source   files (*.sps *.s01 *.sp1);;'
            'Receiver files (*.rps *.r01 *.rp1);;'
            'Relation files (*.xps *.x01 *.xp1);;'
            'All files (*.*)'
        )  # file extensions

        fileName = None  # no file(s) selected yet
        # replaceSps = True  # replace current SPS data

        spsParams = [
            dict(
                name='SPS Import Settings',
                type='myGroup',
                brush='#add8e6',
                children=[
                    dict(name='CRS of SPS data', type='myCrs2', value=crs, default=crs, expanded=False, flat=True),
                    dict(
                        name='SPS data file(s)',
                        type='file',
                        value=fileName,
                        default=fileName,
                        selectFile=fileName,
                        acceptMode='AcceptOpen',
                        fileMode='ExistingFiles',
                        viewMode='Detail',
                        directory=directory,
                        nameFilter=nameFilter,
                    ),
                    dict(name='Local SPS dialect', type='list', limits=spsNames, value=config.spsDialect, default=config.spsDialect),  # SPS 'flavor'
                    dict(name='SPS item highlight', type='list', limits=spsItems, value=spsItems[0], default=spsItems[0], expanded=False, flat=True),
                    dict(name='XPS item highlight', type='list', limits=xpsItems, value=xpsItems[0], default=xpsItems[0], expanded=False, flat=True),
                    dict(name='RPS item highlight', type='list', limits=spsItems, value=spsItems[0], default=spsItems[0], expanded=False, flat=True),
                    # dict(name='Replace current SPS data', type='bool', value=replaceSps, default=replaceSps),
                ],
            ),
        ]

        self.parameters = pg.parametertree.Parameter.create(name='SPS Settings', type='group', children=spsParams)
        # self.parameters.addChildren(spsParams)

        self.paramTree = pg.parametertree.ParameterTree(showHeader=True)
        self.paramTree.setParameters(self.parameters, showTop=False)
        self.paramTree.header().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.paramTree.header().resizeSection(0, 275)
        # self.paramTree.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        font_metrics = QFontMetrics(self.paramTree.font())                      # Get font metrics for the current font
        line_height = font_metrics.height()                                     # Height of a single line
        self.paramTree.setFixedHeight(line_height * 12)                         # Set the height to 12 lines

        for item in self.paramTree.listAllItems():                              # Bug. See: https://github.com/pyqtgraph/pyqtgraph/issues/2744
            p = item.param                                                      # get parameter belonging to parameterItem
            p.setToDefault()                                                    # set all parameters to their default value
            if hasattr(item, 'updateDefaultBtn'):                               # note: not all parameterItems have this method
                item.updateDefaultBtn()                                         # reset the default-buttons to their grey value
            if 'tip' in p.opts:                                                 # this solves the above mentioned bug
                item.setToolTip(0, p.opts['tip'])                               # the widgets now get their tooltips

        self.spsCrs = self.parameters.child('SPS Import Settings', 'CRS of SPS data')

        self.spsDialect = self.parameters.child('SPS Import Settings', 'Local SPS dialect')
        self.spsDialect.sigTreeStateChanged.connect(self.SpsDialectHasChanged)

        self.spsFiles = self.parameters.child('SPS Import Settings', 'SPS data file(s)')
        self.spsFiles.sigTreeStateChanged.connect(self.SpsFilesHaveChanged)

        self.showSps = self.parameters.child('SPS Import Settings', 'SPS item highlight')
        self.showSps.sigTreeStateChanged.connect(self.SpsHighlightHasChanged)

        self.showXps = self.parameters.child('SPS Import Settings', 'XPS item highlight')
        self.showXps.sigTreeStateChanged.connect(self.XpsHighlightHasChanged)

        self.showRps = self.parameters.child('SPS Import Settings', 'RPS item highlight')
        self.showRps.sigTreeStateChanged.connect(self.RpsHighlightHasChanged)

        self.layout = QVBoxLayout()

        label_style = 'font-family: Arial; font-weight: bold; font-size: 16px;'
        title = QLabel('SPS Import Settings')
        title.setStyleSheet(label_style)    # Set the style for the title label
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Align center

        imported = QLabel('SPS - XPS - RPS data')
        imported.setStyleSheet(label_style)    # Set the style for the title label
        imported.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Align center

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

        self.layout.addWidget(title)
        self.layout.addWidget(QLabel('Please select the CRS, the local SPS dialect and the SPS data file(s).'), 0, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.paramTree)
        self.layout.addWidget(imported)
        self.layout.addWidget(self.tabWidget)

        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

    def accept(self):
        self.accepted()
        QDialog.accept(self)

    def accepted(self):
        # categories
        SPS = self.parameters.child('SPS Import Settings')

        # sps settings
        config.spsDialect = SPS.child('Local SPS dialect').value()

    def SpsDialectHasChanged(self, _, __):
        """
        Called when the SPS dialect has changed.
        """
        self.SpsHighlightHasChanged(self.showSps, None)  # update the SPS highlight
        self.XpsHighlightHasChanged(self.showXps, None)  # update the XPS highlight
        self.RpsHighlightHasChanged(self.showRps, None)  # update the SPS highlight

    def SpsFilesHaveChanged(self, param, _):
        """
        Called when the SPS files have changed.
        """
        self.fileNames = param.value()

        self.spsFiles = []
        self.rpsFiles = []
        self.xpsFiles = []

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

    def SpsHighlightHasChanged(self, param, _):
        """
        Called when the SPS highlight has changed.
        """

        spsKey = next((key for key, value in config.spsFormatDict.items() if value == param.value()), None)
        assert spsKey is not None, f'No valid key with value {param.value()}'

        spsFormat = next((item for item in config.spsFormatList if item['name'] == self.spsDialect.value()), None)
        assert spsFormat is not None, f'No valid SPS entry with name {self.spsDialect.value()}'

        # print(spsFormat[spsKey][0], spsFormat[spsKey][1])
        self.spsTab.line1 = spsFormat[spsKey][0]
        self.spsTab.line2 = spsFormat[spsKey][1]

        self.tabWidget.setCurrentIndex(0)
        self.spsTab.update()

    def XpsHighlightHasChanged(self, param, _):
        """
        Called when the XPS highlight has changed.
        """

        xpsKey = next((key for key, value in config.xpsFormatDict.items() if value == param.value()), None)
        assert xpsKey is not None, f'No valid key with value {param.value()}'

        xpsFormat = next((item for item in config.xpsFormatList if item['name'] == self.spsDialect.value()), None)
        assert xpsFormat is not None, f'No valid XPS entry with name {self.spsDialect.value()}'

        self.xpsTab.line1 = xpsFormat[xpsKey][0]
        self.xpsTab.line2 = xpsFormat[xpsKey][1]

        self.tabWidget.setCurrentIndex(1)
        self.xpsTab.update()

    def RpsHighlightHasChanged(self, param, _):
        """
        Called when the RPS highlight has changed.
        """

        spsKey = next((key for key, value in config.spsFormatDict.items() if value == param.value()), None)
        assert spsKey is not None, f'No valid key with value {param.value()}'

        spsFormat = next((item for item in config.spsFormatList if item['name'] == self.spsDialect.value()), None)
        assert spsFormat is not None, f'No valid SPS entry with name {self.spsDialect.value()}'

        # print(spsFormat[spsKey][0], spsFormat[spsKey][1])
        self.rpsTab.line1 = spsFormat[spsKey][0]
        self.rpsTab.line2 = spsFormat[spsKey][1]

        self.tabWidget.setCurrentIndex(2)
        self.rpsTab.update()

    # def eventFilter(self, obj, event):
    #     if event.type() == QEvent.FocusIn:
    #         if obj == self.spsTab:
    #             self.tabWidget.setCurrentIndex(0)
    #             self.tabWidget.update()
    #         elif obj == self.xpsTab:
    #             self.tabWidget.setCurrentIndex(1)
    #             self.tabWidget.update()
    #         elif obj == self.rpsTab:
    #             self.tabWidget.setCurrentIndex(2)
    #             self.tabWidget.update()
    #     return super().eventFilter(obj, event)
