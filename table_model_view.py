import io
import winsound  # make a sound when a record isn't found
from collections import deque

import numpy as np
import pyqtgraph as pg
from qgis.PyQt.QtCore import QAbstractTableModel, QEvent, Qt, QVariant
from qgis.PyQt.QtGui import QBrush, QColor, QFont, QKeySequence
from qgis.PyQt.QtWidgets import QAbstractItemView, QApplication, QMessageBox, QTableView

from .functions import myPrint

# TableModel requires a 2D array to work from
# this means flattening the 4D analysis array from 4D to 2D, before it can be used:

# self.survey.output.anaOutput = np.memmap(anaFileName, dtype=np.float32, mode='r', shape=(nx, ny, fold, 13))
# self.D2_Output = self.survey.output.anaOutput.reshape(nx * ny * fold, 13)

# When using a Treeview approach, flattening won't be required; now we will have:
# index = model.index(row, column, parent) for each record
# The main complication is that each parent has another parent:

# grandparent = line number -> parent = bin number -> record = fold index [1 ...n]
# See: https://doc.qt.io/qtforpython/overviews/model-view-programming.html

# for the time being a QAbstractTableModel is being used

# analysis table; to copy data to clipboard:
# See: https://stackoverflow.com/questions/40225270/copy-paste-multiple-items-from-qtableview-in-pyqt4

# editable table
# See: https://www.pythonguis.com/faq/editing-pyqt-tableview/


# palette not needed; use styleSheets instead
# palette = QPalette()
# FG = palette.highlightedText()
# BG = palette.highlight()


class AnaTableModel(QAbstractTableModel):
    def __init__(self, data):
        super().__init__()
        self._data = None

        # the underlying data uses a 2D numpy array without any field names. So it is reliant on the header names and format strings for export to clipboard
        # fmt: off
        self._format =  '%d',    '%d',   '%d',   '%.2f',  '%.2f',  '%.2f',  '%.2f',  '%.2f',  '%.2f',  '%.2f',     '%.2f',   '%.2f',    '%d'
        self._header = ['stake', 'line', 'fold', 'src-x', 'src-y', 'rec-x', 'rec-y', 'cmp-x', 'cmp-y', 'TWT [ms]', 'offset', 'azimuth', 'unique']
        # fmt: on

        self.setData(data)

    def data(self, index, role):
        if role == Qt.DisplayRole:
            if self._data is not None:
                if index.column() < 3:                                          # Show int values for first three columns
                    value = str(int(self._data[index.row(), index.column()]))
                elif index.column() == 12:                                      # Show True / False for unique values
                    value = 'True' if self._data[index.row(), index.column()] == -1.0 else ''
                else:                                                           # Show floats for the remainder if fold > 0 (fold = col nr 2)
                    value = f'{float(self._data[index.row(), index.column()]):,.2f}' if self._data[index.row(), 2] > 0 else ''
                    # value = str(self._data[index.row(), index.column()])
            else:
                value = '  n/a  '
            return value
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        elif role == Qt.FontRole:
            # return QFont("Courier New", 10, QFont.Bold)
            # return QFont('Courier New', 8, QFont.Normal)
            return QFont('Arial', 8, QFont.Normal)

    def setData(self, data):
        # self.beginResetModel()                                                  # https://doc.qt.io/qt-6/qabstractitemmodel.html#beginResetModel
        self._data = data
        self.layoutChanged.emit()                                               # needed to indicate that 'model' has changed

        # TL = QModelIndex(self.anaView.model().index(0, 0))
        # BR = QModelIndex(self.anaView.model().index(offset + fold - 1, 0))
        # self.dataChanged.emit(TL, BR)                                                 # needed to indicate that 'model' has changed

    def getData(self):
        return self._data

    def getHeader(self):
        return self._header

    def getFormat(self):
        return self._format

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return self._header[section]
            else:
                return f'{section + 1:,}'

        return QAbstractTableModel.headerData(self, section, orientation, role)

    def setHeaderData(self, section, orientation, data, role=Qt.EditRole):
        if orientation == Qt.Horizontal and role in (Qt.DisplayRole, Qt.EditRole):
            return self._header[section]
        return super().setHeaderData(section, orientation, data, role)

    # required 2nd parameter (index) not being used. See: https://gist.github.com/nbassler/342fc56c42df27239fa5276b79fca8e6
    def rowCount(self, _):
        if self._data is not None:
            return self._data.shape[0]
        return 20

    # required 2nd parameter (index) not being used. See: https://gist.github.com/nbassler/342fc56c42df27239fa5276b79fca8e6
    def columnCount(self, _=0):
        if self._data is not None:
            return self._data.shape[1]
        if self._header is not None:
            return len(self._header)
        return 13

    def nextDuplicate(self, _):                                                 # index not used and replaced by _
        return None

    def prevDuplicate(self, _):                                                 # index not used and replaced by _
        return None

    def nextSrcOrphan(self, _):                                                 # index not used and replaced by _
        return None

    def prevSrcOrphan(self, _):                                                 # index not used and replaced by _
        return None

    def nextRecOrphan(self, _):                                                 # index not used and replaced by _
        return None

    def prevRecOrphan(self, _):                                                 # index not used and replaced by _
        return None


class TableView(QTableView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimumSize(100, 100)
        self.installEventFilter(self)
        self.setAlternatingRowColors(True)
        # self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # Can't use these lines here; header needs to exist already
        # self.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        # self.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.horizontalHeader().setMinimumSectionSize(0)
        self.horizontalHeader().setDefaultSectionSize(20)

        # don't allow selecting columns in a large virtual table; instead, always select a complete row
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.SelectionMode(QAbstractItemView.ContiguousSelection)

    @staticmethod
    def getFormat(entry):
        # fmt: off
        formatDict = dict(                                                      # used to format data being copied to clipboard
            Code   = '%s',
            Depth  = '%.1f',
            East   = '%.1f',
            Elev   = '%.1f',
            Index  = '%d',
            InSps  = '%d',
            InRps  = '%d',
            InUse  = '%d',
            InXps  = '%d',
            Line   = '%.2f',
            LocX   = '%.1f',
            LocY   ='%.1f',
            North  = '%.1f',
            Point  = '%.2f',
            Record = '%d',                                                      # record number; ambiguous name superseded by 'RecNum'
            RecNum = '%d',                                                      # record number; different name used earlier
            RecLin = '%.2f',
            RecMin = '%.2f',
            RecMax = '%.2f',
            RecInd = '%d',
            SrcLin = '%.2f',
            SrcPnt = '%.2f',
            SrcInd = '%d',
            Uniq   = '%d',
            )
        # fmt:on
        return formatDict[entry]

    @staticmethod
    def getFormats(names):
        fmt = []
        for name in names:
            fmt.append(TableView.getFormat(name))
        return fmt

    def eventFilter(self, source, event):
        # See: https://stackoverflow.com/questions/28204043/how-to-handle-keyboard-shortcuts-using-keypressevent-and-should-it-be-used-fo
        # See: https://doc.qt.io/qtforpython-5/PySide2/QtCore/Qt.html for key definitions under  PySide2.QtCore.Qt.Key
        # See: https://www.pythonguis.com/faq/programmatically-select-multiple-rows-in-qtableview/ to select cells programmatically
        # See: https://stackoverflow.com/questions/9678138/how-to-select-next-row-in-qtableview-programmatically/9678278
        # See: https://doc.qt.io/qt-6/qtableview.html#selectRow
        # See: https://stackoverflow.com/questions/22577327/how-to-retrieve-the-selected-rows-of-a-qtableview
        # See: https://forum.qt.io/topic/10708/solved-rowcount-tableview to get the model's methods
        # See: https://doc.qt.io/qt-6/qkeysequence.html for standard key sequence definitions
        # See: https://stackoverflow.com/questions/45368148/connecting-to-events-of-another-widget to bind to a specific event from another widget
        # See: https://doc.qt.io/qt-5/qobject.html#installEventFilter
        # See: https://gist.github.com/stevenliebregt/8e4211937b671ac637b610650a11914f
        # See: https://www.xingyulei.com/post/qt-detect-click/index.html
        # See: https://pythonqwt.readthedocs.io/en/stable/examples/eventfilter.html

        if event.type() == QEvent.KeyPress and event.matches(QKeySequence.Copy):
            self.copy()
            return True

        if event.type() == QEvent.KeyPress and event.matches(QKeySequence.Paste):
            self.paste()
            return True

        # The edit control on the Xml tab captures the 'selectAll' events (Ctrl+A)
        # maybe it helps to reroute these key events to the active widget.
        # See: https://stackoverflow.com/questions/9442165/pyqt-mouse-events-for-qtabwidget
        # See: https://stackoverflow.com/questions/20420072/use-keypressevent-to-catch-enter-or-return
        if event.type() == QEvent.KeyPress and event.matches(QKeySequence.SelectAll):
            self.select_all()
            return True

        if event.type() == QEvent.KeyPress and (event.modifiers() & Qt.ControlModifier):
            myPrint('The control key is pressed')

            if event.key() == Qt.Key_1:
                myPrint('Select All')
                self.clearSelection()
                self.select_all()
                return True

            if event.key() == Qt.Key_Home:
                myPrint('Go Home')
                index = 0
                myPrint(f'Row {index} is selected')
                self.clearSelection()
                self.selectRow(index)
                return True

            if event.key() == Qt.Key_End:
                myPrint('Go to the End')
                index = self.model().rowCount(0) - 1
                myPrint(f'Row {index} is selected')
                self.clearSelection()
                self.selectRow(index)
                return True

            if event.key() == Qt.Key_PageDown:
                myPrint('Move to next duplicate')
                indexes = self.selectionModel().selectedRows()
                # for index in sorted(indexes):
                #     myPrint('Row %d is selected' % index.row())
                index = indexes[0].row()
                goTo = self.model().nextDuplicate(index)
                self.clearSelection()
                if goTo is not None:
                    self.selectRow(goTo)
                else:
                    winsound.PlaySound('SystemHand', winsound.SND_ALIAS | winsound.SND_ASYNC)
                    self.selectRow(index)
                return True

            if event.key() == Qt.Key_PageUp:
                myPrint('Move to previous duplicate')
                indexes = self.selectionModel().selectedRows()
                # for index in sorted(indexes):
                #     myPrint('Row %d is selected' % index.row())
                index = indexes[0].row()
                goTo = self.model().prevDuplicate(index)
                self.clearSelection()
                if goTo is not None:
                    self.selectRow(goTo)
                else:
                    winsound.PlaySound('SystemHand', winsound.SND_ALIAS | winsound.SND_ASYNC)
                    self.selectRow(index)
                return True

            if event.key() == Qt.Key_Down:
                myPrint('Move to next src orphan')
                indexes = self.selectionModel().selectedRows()
                # for index in sorted(indexes):
                #     myPrint('Row %d is selected' % index.row())
                index = indexes[0].row()
                goTo = self.model().nextSrcOrphan(index)
                self.clearSelection()
                if goTo is not None:
                    self.selectRow(goTo)
                else:
                    winsound.PlaySound('SystemHand', winsound.SND_ALIAS | winsound.SND_ASYNC)
                    self.selectRow(index)
                return True

            if event.key() == Qt.Key_Up:
                myPrint('Move to prev src orphan')
                indexes = self.selectionModel().selectedRows()
                # for index in sorted(indexes):
                #     myPrint('Row %d is selected' % index.row())
                index = indexes[0].row()
                goTo = self.model().prevSrcOrphan(index)
                self.clearSelection()
                if goTo is not None:
                    self.selectRow(goTo)
                else:
                    winsound.PlaySound('SystemHand', winsound.SND_ALIAS | winsound.SND_ASYNC)
                    self.selectRow(index)
                return True

            if event.key() == Qt.Key_Right:
                myPrint('Move to next rec orphan')
                indexes = self.selectionModel().selectedRows()
                # for index in sorted(indexes):
                #     myPrint('Row %d is selected' % index.row())
                index = indexes[0].row()
                goTo = self.model().nextRecOrphan(index)
                self.clearSelection()
                if goTo is not None:
                    self.selectRow(goTo)
                else:
                    winsound.PlaySound('SystemHand', winsound.SND_ALIAS | winsound.SND_ASYNC)
                    self.selectRow(index)
                return True

            if event.key() == Qt.Key_Left:
                myPrint('Move to prev rec orphan')
                indexes = self.selectionModel().selectedRows()
                # for index in sorted(indexes):
                #     myPrint('Row %d is selected' % index.row())
                index = indexes[0].row()
                goTo = self.model().prevRecOrphan(index)
                self.clearSelection()
                if goTo is not None:
                    self.selectRow(goTo)
                else:
                    winsound.PlaySound('SystemHand', winsound.SND_ALIAS | winsound.SND_ASYNC)
                    self.selectRow(index)
                return True

        return super(TableView, self).eventFilter(source, event)

    def getFormatList(self):
        data = self.model().getData()                                           # get numpy data from the underlying model

        if data is None:
            return ''                                                           # no data available; return empty string

        names = data.dtype.names                                                # get the field names from the numpy array
        if names is None:                                                       # no field names available; not a record based array
            fmt = self.model().getFormat()                                      # get the format string from the model
        else:                                                                   # the numpy array is record based
            fmt = TableView.getFormats(names)                                   # therefore use the field names instead

        return fmt

    def getNameList(self):
        data = self.model().getData()                                           # get numpy data from the underlying model

        if data is None:
            return ''                                                           # no data available; return empty string

        names = list(data.dtype.names) if data.dtype.names is not None else self.model().getHeader()
        return names

    def copy(self):
        # the implemented solution copies a contiguous range of rows to the clipboard
        # this is less flexible than using an ExtendedSelection or MultiSelection,
        # but it is by far the fasted way to copy a range of rows to the clipboard

        data = self.model().getData()                                           # get numpy data from the underlying model
        if data is None:
            winsound.PlaySound('SystemHand', winsound.SND_ALIAS | winsound.SND_ASYNC)
            return

        fmt = self.getFormatList()                                              # get the format string from the model
        names = self.getNameList()

        with pg.BusyCursor():                                                   # this operation could take some time. . .
            indices = self.selectionModel().selectedRows()                      # selection list, containing selected rows
            count = len(indices)

            if count == 0:                                                      # no selection has yet been made (at start of application)
                return

            indices.sort()                                                      # sort the list to get min/max values
            rowMin = indices[0].row()
            rowMax = indices[count - 1].row()                                   # subtract one as count is exclusive

            copied = data[rowMin : rowMax + 1]                                  # select records; add 1, as the last nr. is exclusive

            memFile = io.BytesIO()                                              # create tempory file in memory
            delimiter = '\t'                                                    # use tab separator, easier for Excel than commas

            hdr = delimiter.join(names)                                         # define header from names
            # comments='' to prevent '# ' at the start of a header line
            # delimiter ='' to prevent tabs, comma's from being inserted
            # save file as tab seperated ascii data; including header
            np.savetxt(memFile, copied, delimiter=delimiter, fmt=fmt, comments='', header=hdr)
            outStr = memFile.getvalue().decode('UTF-8')                         # convert bytes to unicode string
            QApplication.clipboard().setText(outStr)                            # copy the whole lot to the cipboard

    def paste(self):

        # not implemented yet
        winsound.PlaySound('SystemHand', winsound.SND_ALIAS | winsound.SND_ASYNC)
        return

        # use the following as a starting point
        # selection = self.selectedIndexes()
        # if selection:
        #     model = self.model()

        #     buffer = QApplication.clipboard().text()
        #     all_rows = []
        #     all_columns = []
        #     for index in selection:
        #         if not index.row() in all_rows:
        #             all_rows.append(index.row())
        #         if not index.column() in all_columns:
        #             all_columns.append(index.column())
        #     visible_rows = [row for row in all_rows if not self.isRowHidden(row)]
        #     visible_columns = [col for col in all_columns if not self.isColumnHidden(col)]

        #     reader = csv.reader(io.StringIO(buffer), delimiter='\t')
        #     arr = [[cell for cell in row] for row in reader]
        #     if len(arr) > 0:
        #         nrows = len(arr)
        #         ncols = len(arr[0])
        #         if len(visible_rows) == 1 and len(visible_columns) == 1:
        #             # Only the top-left cell is highlighted.
        #             for i in range(nrows):
        #                 insert_rows = [visible_rows[0]]
        #                 row = insert_rows[0] + 1
        #                 while len(insert_rows) < nrows:
        #                     row += 1
        #                     if not self.isRowHidden(row):
        #                         insert_rows.append(row)
        #             for j in range(ncols):
        #                 insert_columns = [visible_columns[0]]
        #                 col = insert_columns[0] + 1
        #                 while len(insert_columns) < ncols:
        #                     col += 1
        #                     if not self.isColumnHidden(col):
        #                         insert_columns.append(col)
        #             for i, insert_row in enumerate(insert_rows):
        #                 for j, insert_column in enumerate(insert_columns):
        #                     cell = arr[i][j]
        #                     model.setData(model.index(insert_row, insert_column), cell)
        #         else:
        #             # Assume the selection size matches the clipboard data size.
        #             for index in selection:
        #                 selection_row = visible_rows.index(index.row())
        #                 selection_column = visible_columns.index(index.column())
        #                 model.setData(
        #                     model.index(index.row(), index.column()),
        #                     arr[selection_row][selection_column],
        #                 )
        # return

    def select_all(self):
        data = self.model().getData()                                           # get numpy data from the underlying model
        if data is None:
            winsound.PlaySound('SystemHand', winsound.SND_ALIAS | winsound.SND_ASYNC)
            return

        if self.model().rowCount(0) > 100000:
            QMessageBox.warning(self, 'Select all', 'You want to select more than 100,000 records\nPlease use File->Export to export all records and make your selection in a text editor', QMessageBox.Close)
            return True

        # See: https://github.com/NextSaturday/myQT/blob/main/tSelection/tSelection/tSelection.cpp for alternative solution
        with pg.BusyCursor():                                                   # this could take some time. . .
            self.selectAll()

        return True


# See: https://stackoverflow.com/questions/64277646/how-do-i-find-the-position-of-the-first-0-looking-backwards-in-a-numpy-array

#  Let's say I have a really long array like this:

# arr = np.array([0,0,1,1,0,1,1,1,0,0,0,1,1,0,0,1]}
# I also have a maximum position where I can look, like 6, making a slice of the array that returns this:

# sliceLocation = 6
# returning:

# np.array([0,0,1,1,0,1,1]}

# now I want to write a piece of code that slices the array and then searches for the first 0 inside this array coming from the back,
# in this case returning 4 as a viable position in a quick and efficient time. Can anybody help me?

######################################################

# Here is your example but i dont understand what you want to do with the rest of the array arr.

# arr = np.array([0,0,1,1,0,1,1,1,0,0,0,1,1,0,0,1])
# sliceLocation = 6

# arr = arr[:sliceLocation+1]
# idx = np.where(arr==0)[0][-1]

# On dealing with very large tables
# See: http://doc.qt.io/qt-5/qtwidgets-itemviews-fetchmore-example.html
# See: https://stackoverflow.com/questions/28033633/using-large-record-set-with-qtableview-and-qabstracttablemodel-retrieve-visib
# See: https://forum.qt.io/topic/96814/how-set-height-of-all-rows-qtableview
# Note: resizeColumnsToContents() Appears to be very very slow for large datasets
#
# See: https://github.com/ajenter/qt_hugelistview/blob/tableview-experiment/src/main.cpp


class RpsTableModel(QAbstractTableModel):

    # pntType1 = np.dtype(
    #     [
    #         ('Line', 'f4'),  # F10.2
    #         ('Point', 'f4'),  # F10.2
    #         ('Index', 'i4'),  # I1
    #         ('Code', 'U2'),  # A2
    #         ('Depth', 'f4'),  # I4
    #         ('East', 'f4'),  # F9.1
    #         ('North', 'f4'),  # F10.1
    #         ('Elev', 'f4'),  # F6.1
    #         ('Uniq', 'i4'),  # check if record is unique
    #         ('InXps', 'i4'),  # check if record is orphan
    #         ('InUse', 'i4'),  # check if record is in use
    #         ('LocX', 'f4'),  # F9.1
    #         ('LocY', 'f4'),  # F10.1
    #     ]
    # )

    def __init__(self, data):
        super().__init__()
        self._data = None               # Data is a numpy array of records (structured array)
        self._names = None              # Ordered list of field names, or None if there are no fields
        self._qSort = deque(maxlen=3)   # To support sorting on max 3 values

        # todo: get rid of this hardcoded stuff; use the field names instead. See formatDict in TableView above
        # fmt: off
        self._format =  '%.2f',     '%.2f',      '%d',    '%s',   '%.1f',  '%.1f',    '%.1f',     '%.1f',      '%d',     '%d',                  '%d',   '%.1f', '%.1f'
        self._header = ['rec line', 'rec point', 'index', 'code', 'depth', 'easting', 'northing', 'elevation', 'unique', 'inXps']  # not shown: 'InUse'	'LocX'	'LocY'
        # fmt: on

        self._minMax = np.zeros(shape=(2, len(self._header)), dtype=np.float32)  # Initial min and max values for each column (field) in the data array
        self.setData(data)

    def data(self, index, role):
        if role == Qt.DisplayRole:
            if self._data is not None:
                record = self._data[index.row()]
                if index.column() == 2:                                         # format depends on column
                    value = str(int(record[index.column()]))
                elif index.column() == 3:                                       # format depends on column
                    value = str(record[index.column()])
                else:                                                           # show floats for the remainder
                    value = f'{float(record[index.column()]):.1f}'
            else:
                value = 'n/a'
            return value
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        elif role == Qt.BackgroundRole:
            if self._data is None:
                return QVariant()
            record = self._data[index.row()]
            uniq = record['Uniq']
            inXps = record['InXps']
            if uniq == 0:
                if inXps == 0:
                    return QBrush(QColor(255, 200, 200))                        # duplicate AND orphan -> red
                else:
                    return QBrush(QColor(255, 230, 130))                        # duplicate -> orange
            elif inXps == 0:
                return QBrush(QColor(155, 200, 255))                            # orphan -> blue-ish
            else:
                return QVariant()
        elif role == Qt.FontRole:
            # return QFont("Courier New", 10, QFont.Bold)
            # return QFont('Courier New', 8, QFont.Normal)
            return QFont('Arial', 8, QFont.Normal)
        elif role == Qt.ForegroundRole:
            if self._data is None:
                return QVariant()
            record = self._data[index.row()]
            inXps = record['InXps']
            if not inXps:
                return QBrush(QColor(200, 200, 200))                            # inactive -> grey
            return QVariant()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                if section == 2:
                    return self._header[section] + f'\n[{ int(self._minMax[0][section])}]:\n[{int(self._minMax[1][section])}]'
                elif section != 3:
                    return self._header[section] + f'\n[{ self._minMax[0][section]:.1f}]:\n[{self._minMax[1][section]:.1f}]'
                else:
                    return self._header[section] + '\n« min »\n« max »'
            else:
                return f'{section + 1:,}'

        if role == Qt.BackgroundRole:                                           # highlight sorting column(s)
            if orientation == Qt.Horizontal:
                if len(self._qSort) > 0 and section == self._qSort[-1]:
                    return QBrush(QColor(255, 215, 0))                          # gold
                if len(self._qSort) > 1 and section == self._qSort[-2]:
                    return QBrush(QColor(255, 255, 160))                        # lightyellow
                if len(self._qSort) > 2 and section == self._qSort[-3]:
                    return QBrush(QColor(250, 250, 210))                        # lightgoldenrodyellow
                else:
                    return QVariant()

        return QAbstractTableModel.headerData(self, section, orientation, role)

    def getData(self):
        return self._data

    def getHeader(self):
        return self._header

    def getFormat(self):
        return self._format

    def setData(self, data):
        if data is not None and data.shape[0] > 0:
            self._names = data.dtype.names                                      # get the field names from the numpy array
            self._minMax = np.zeros(shape=(2, len(self._names)), dtype=np.float32)

            for i, name in enumerate(self._names):
                if i == 3:                                                      # skip code column
                    continue
                self._minMax[0, i] = data[name].min()
                self._minMax[1, i] = data[name].max()

            self._data = data
        else:
            self._minMax = np.zeros(shape=(2, len(self._header)), dtype=np.float32)  # Initial min and max values for each column (field) in the data array
            self._data = None

        self.layoutChanged.emit()
        self.headerDataChanged.emit(Qt.Horizontal, 0, 0)                        # don't communicate length of header to the view; hence 0, 0

    def applySort(self, index):
        if self._data is None:
            return

        if index not in self._qSort:                                            # check if index is already in the list; must avoid duplicates !
            self._qSort.append(index)
        else:
            self._qSort.remove(index)
            self._qSort.append(index)
            self._qSort.popleft()                                               # remove the oldest sort value

        sortList = []
        for sort in reversed(self._qSort):                                      # Iterate over self._qSort backwards
            sortList.append(self._names[sort])

        self._data.sort(order=sortList)                                         # Sort the data using the list of sorts
        self.layoutChanged.emit()
        self.headerDataChanged.emit(Qt.Horizontal, 0, 0)                        # don't communicate length of header to the view; hence 0, 0

    def sortColumns(self):
        if self._data is None:
            return ''

        sortList = []
        for sort in reversed(self._qSort):  # Iterate over self._qSort backwards
            sortList.append(self._names[sort])

        return str(sortList)

    def rowCount(self, _):
        # required 2nd parameter (index) not being used. See: https://gist.github.com/nbassler/342fc56c42df27239fa5276b79fca8e6
        if self._data is not None:
            return self._data.shape[0]
        return 10

    def columnCount(self, _):
        # required 2nd parameter (index) not being used. See: https://gist.github.com/nbassler/342fc56c42df27239fa5276b79fca8e6
        if self._header is None or len(self._header) == 0:
            raise ValueError('Table header cannot be empty list')
        else:
            return len(self._header) - 2                                        # exclude 'unique', 'inXps'

    def nextDuplicate(self, index):
        if self._data is None:
            return None
        for i in range(index + 1, self.rowCount(0)):
            record = self._data[i]
            uniq = record['Uniq']
            if uniq == 0:
                return i
        return None

    def prevDuplicate(self, index):
        if self._data is None:
            return None
        for i in range(index - 1, -1, -1):
            record = self._data[i]
            uniq = record['Uniq']
            if uniq == 0:
                return i
        return None

    def nextSrcOrphan(self, _):                                                 # index not used and replaced by _
        return None

    def prevSrcOrphan(self, _):                                                 # index not used and replaced by _
        return None

    def nextRecOrphan(self, index):
        if self._data is None:
            return None
        for i in range(index + 1, self.rowCount(0)):
            record = self._data[i]
            inXps = record['InXps']
            if inXps == 0:
                return i
        return None

    def prevRecOrphan(self, index):
        if self._data is None:
            return None
        for i in range(index - 1, -1, -1):
            record = self._data[i]
            inXps = record['InXps']
            if inXps == 0:
                return i
        return None


class SpsTableModel(QAbstractTableModel):

    # pntType1 = np.dtype(
    #     [
    #         ('Line',  'f4'),  # F10.2
    #         ('Point', 'f4'),  # F10.2
    #         ('Index', 'i4'),  # I1
    #         ('Code',  'U2'),  # A2
    #         ('Depth', 'f4'),  # I4
    #         ('East',  'f4'),  # F9.1
    #         ('North', 'f4'),  # F10.1
    #         ('Elev',  'f4'),  # F6.1
    #         ('Uniq',  'i4'),  # check if record is unique
    #         ('InXps', 'i4'),  # check if record is orphan
    #         ('InUse', 'i4'),  # check if record is in use
    #         ('LocX',  'f4'),  # F9.1
    #         ('LocY',  'f4'),  # F10.1
    #     ]
    # )

    def __init__(self, data):
        super().__init__()
        self._data = None               # Data is a numpy array of records (structured array)
        self._names = None              # Ordered list of field names, or None if there are no fields
        self._qSort = deque(maxlen=3)   # To support sorting on max 3 values

        # todo: get rid of this hardcoded stuff; use the field names instead. See formatDict in TableView above
        # fmt: off
        self._format =  '%.2f',     '%.2f',      '%d',    '%s',   '%.1f',  '%.1f',    '%.1f',     '%.1f',      '%d',     '%d',                  '%d',   '%.1f', '%.1f'
        self._header = ['src line', 'src point', 'index', 'code', 'depth', 'easting', 'northing', 'elevation', 'unique', 'inXps']  # not shown: 'InUse'	'LocX'	'LocY'
        # fmt: on

        self._minMax = np.zeros(shape=(2, len(self._header)), dtype=np.float32)
        self.setData(data)

    def data(self, index, role):
        if role == Qt.DisplayRole:
            if self._data is not None:
                record = self._data[index.row()]
                if index.column() == 2:                                         # format depends on column
                    value = str(int(record[index.column()]))
                elif index.column() == 3:                                       # format depends on column
                    value = str(record[index.column()])
                else:                                                           # show floats for the remainder
                    value = f'{float(record[index.column()]):.1f}'
            else:
                value = 'n/a'
            return value
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        elif role == Qt.BackgroundRole:
            if self._data is None:
                return QVariant()
            record = self._data[index.row()]
            uniq = record['Uniq']
            inXps = record['InXps']
            if uniq == 0:
                if inXps == 0:
                    return QBrush(QColor(255, 200, 200))                        # duplicate AND orphan -> red
                else:
                    return QBrush(QColor(255, 230, 130))                        # duplicate -> orange
            elif inXps == 0:
                return QBrush(QColor(200, 200, 255))                            # orphan -> blue
            else:
                return QVariant()
        elif role == Qt.FontRole:
            # return QFont("Courier New", 10, QFont.Bold)
            # return QFont('Courier New', 8, QFont.Normal)
            return QFont('Arial', 8, QFont.Normal)
        elif role == Qt.ForegroundRole:
            if self._data is None:
                return QVariant()
            record = self._data[index.row()]
            inXps = record['InXps']
            if not inXps:
                return QBrush(QColor(200, 200, 200))                            # inactive -> grey
            return QVariant()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                if section == 2:
                    return self._header[section] + f'\n[{ int(self._minMax[0][section])}]:\n[{int(self._minMax[1][section])}]'
                elif section != 3:
                    return self._header[section] + f'\n[{ self._minMax[0][section]:.1f}]:\n[{self._minMax[1][section]:.1f}]'
                else:
                    return self._header[section] + '\n« min »\n« max »'
            else:
                return f'{section + 1:,}'

        if role == Qt.BackgroundRole:                                           # highlight sorting column(s)
            if orientation == Qt.Horizontal:
                if len(self._qSort) > 0 and section == self._qSort[-1]:
                    return QBrush(QColor(255, 215, 0))                          # gold
                if len(self._qSort) > 1 and section == self._qSort[-2]:
                    return QBrush(QColor(255, 255, 160))                        # lightyellow
                if len(self._qSort) > 2 and section == self._qSort[-3]:
                    return QBrush(QColor(250, 250, 210))                        # lightgoldenrodyellow
                else:
                    return QVariant()

        return QAbstractTableModel.headerData(self, section, orientation, role)

    def getData(self):
        return self._data

    def getHeader(self):
        return self._header

    def getFormat(self):
        return self._format

    def setData(self, data):
        if data is not None and data.shape[0] > 0:
            self._names = data.dtype.names                                      # get the field names from the numpy array
            self._minMax = np.zeros(shape=(2, len(self._names)), dtype=np.float32)

            for i, name in enumerate(self._names):
                if i == 3:                                                      # skip code column
                    continue
                self._minMax[0, i] = data[name].min()
                self._minMax[1, i] = data[name].max()

            self._data = data
        else:
            self._minMax = np.zeros(shape=(2, len(self._header)), dtype=np.float32)  # Initial min and max values for each column (field) in the data array
            self._data = None

        self.layoutChanged.emit()
        self.headerDataChanged.emit(Qt.Horizontal, 0, 0)                        # don't communicate length of header to the view; hence 0, 0

    def applySort(self, index):
        if self._data is None:
            return

        if index not in self._qSort:                                            # check if index is already in the list; must avoid duplicates !
            self._qSort.append(index)
        else:
            self._qSort.remove(index)
            self._qSort.append(index)
            self._qSort.popleft()                                               # remove the oldest sort value

        sortList = []
        for sort in reversed(self._qSort):                                      # Iterate over self._qSort backwards
            sortList.append(self._names[sort])

        self._data.sort(order=sortList)                                         # Sort the data using the list of sorts
        self.layoutChanged.emit()
        self.headerDataChanged.emit(Qt.Horizontal, 0, 0)                        # don't communicate length of header to the view; hence 0, 0

    def sortColumns(self):
        if self._data is None:
            return ''

        sortList = []
        for sort in reversed(self._qSort):  # Iterate over self._qSort backwards
            sortList.append(self._names[sort])

        return str(sortList)

    def rowCount(self, _):
        # required 2nd parameter (index) not being used. See: https://gist.github.com/nbassler/342fc56c42df27239fa5276b79fca8e6
        if self._data is not None:
            return self._data.shape[0]
        return 10

    def columnCount(self, _):
        # required 2nd parameter (index) not being used. See: https://gist.github.com/nbassler/342fc56c42df27239fa5276b79fca8e6
        if self._header is None or len(self._header) == 0:
            raise ValueError('Table header cannot be empty list')
        else:
            return len(self._header) - 2                                        # exclude 'unique', 'inXps'

    def nextDuplicate(self, index):
        if self._data is None:
            return None
        for i in range(index + 1, self.rowCount(0)):
            record = self._data[i]
            uniq = record['Uniq']
            if uniq == 0:
                return i
        return None

    def prevDuplicate(self, index):
        if self._data is None:
            return None
        for i in range(index - 1, -1, -1):
            record = self._data[i]
            uniq = record['Uniq']
            if uniq == 0:
                return i
        return None

    def nextSrcOrphan(self, index):
        if self._data is None:
            return None
        for i in range(index + 1, self.rowCount(0)):
            record = self._data[i]
            inXps = record['InXps']
            if inXps == 0:
                return i
        return None

    def prevSrcOrphan(self, index):
        if self._data is None:
            return None
        for i in range(index - 1, -1, -1):
            record = self._data[i]
            inXps = record['InXps']
            if inXps == 0:
                return i
        return None

    def nextRecOrphan(self, _):                                                 # index not used and replaced by _
        return None

    def prevRecOrphan(self, _):                                                 # index not used and replaced by _
        return None


class XpsTableModel(QAbstractTableModel):
    def __init__(self, data):
        # relType2= np.dtype([('SrcLin', 'f4'),   # F10.2
        #                     ('SrcPnt', 'f4'),   # F10.2
        #                     ('SrcInd', 'i4'),   # I1
        #                     ('RecNum', 'i4'),   # I8
        #                     ('RecLin', 'f4'),   # F10.2
        #                     ('RecMin', 'f4'),   # F10.2
        #                     ('RecMax', 'f4'),   # F10.2
        #                     ('RecInd', 'i4'),   # I1
        #                     ('Uniq',   'i4'),   # check if record is unique
        #                     ('InSps',  'i4'),   # check if record is orphan
        #                     ('InRps',  'i4') ]) # check if record is orphan

        super().__init__()
        self._data = None               # Data is a numpy array of records (structured array)
        self._names = None              # Ordered list of field names, or None if there are no fields
        self._qSort = deque(maxlen=3)   # To support sorting on max 3 values

        # todo: get rid of this hardcoded stuff; use the field names instead. See formatDict in TableView above
        # fmt: off
        self._format =  '%.2f',     '%.2f',      '%d',        '%d',       '%.2f',     '%.2f',    '%.2f',    '%d',        '%d',     '%d',           '%d'
        self._header = ['src line', 'src point', 'src index', 'record #', 'rec line', 'rec min', 'rec max', 'rec index', 'unique', 'in sps-table', 'in rps-table']
        # fmt: on

        self._minMax = np.zeros(shape=(2, len(self._header)), dtype=np.float32)  # Initial min and max values for each column (field) in the data array
        self.setData(data)

    def data(self, index, role):
        if role == Qt.DisplayRole:
            if self._data is not None:
                record = self._data[index.row()]
                if index.column() in [2, 3, 7]:                                 # format depends on column number
                    value = str(int(record[index.column()]))
                else:                                                           # show float for remaining columns
                    value = str(float(record[index.column()]))
            else:
                value = 'n/a'
            return value
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        elif role == Qt.BackgroundRole:
            if self._data is None:
                return QVariant()
            record = self._data[index.row()]
            uniq = record['Uniq']
            inSps = record['InSps']
            inRps = record['InRps']
            if uniq == 0:
                if inSps == 0 or inRps == 0:
                    return QBrush(QColor(255, 200, 200))                        # duplicate AND orphan -> red
                else:
                    return QBrush(QColor(255, 230, 130))                        # duplicate -> orange
            elif inSps == 0 and index.column() < 4:
                return QBrush(QColor(200, 200, 255))                            # orphan -> blue
            elif inRps == 0 and index.column() > 3:
                return QBrush(QColor(155, 200, 255))                            # orphan -> blue-ish
            else:
                return QVariant()
        elif role == Qt.FontRole:
            # return QFont("Courier New", 10, QFont.Bold)
            # return QFont('Courier New', 8, QFont.Normal)
            return QFont('Arial', 8, QFont.Normal)

    def getData(self):
        return self._data

    def getHeader(self):
        return self._header

    def getFormat(self):
        return self._format

    def setData(self, data):
        if data is not None and data.shape[0] > 0:
            self._names = data.dtype.names                                      # get the field names from the numpy array
            self._minMax = np.zeros(shape=(2, len(self._names)), dtype=np.float32)

            for i, name in enumerate(self._names):
                self._minMax[0, i] = data[name].min()
                self._minMax[1, i] = data[name].max()

            self._data = data
        else:
            self._minMax = np.zeros(shape=(2, len(self._header)), dtype=np.float32)  # Initial min and max values for each column (field) in the data array
            self._data = None

        self.layoutChanged.emit()
        self.headerDataChanged.emit(Qt.Horizontal, 0, 0)                        # don't communicate length of header to the view; hence 0, 0

    def applySort(self, index):
        if self._data is None:
            return

        if index not in self._qSort:                                            # check if index is already in the list; must avoid duplicates !
            self._qSort.append(index)
        else:
            self._qSort.remove(index)
            self._qSort.append(index)
            self._qSort.popleft()                                               # remove the oldest sort value

        sortList = []
        for sort in reversed(self._qSort):                                      # Iterate over self._qSort backwards
            sortList.append(self._names[sort])

        self._data.sort(order=sortList)                                         # Sort the data using the list of sorts
        self.layoutChanged.emit()
        self.headerDataChanged.emit(Qt.Horizontal, 0, 0)                        # don't communicate length of header to the view; hence 0, 0

    def sortColumns(self):
        if self._data is None:
            return ''

        sortList = []
        for sort in reversed(self._qSort):  # Iterate over self._qSort backwards
            sortList.append(self._names[sort])

        return str(sortList)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                if section in (0, 3, 7):                                        # format depends on column number; int here
                    return self._header[section] + f'\n[{ int(self._minMax[0][section])}]:\n[{int(self._minMax[1][section])}]'
                else:                                                           # format depends on column number; float here
                    return self._header[section] + f'\n[{ self._minMax[0][section]}]:\n[{self._minMax[1][section]}]'
            else:
                return f'{section + 1:,}'                                       # 1-based index for columns, using 1000 indicator

        if role == Qt.BackgroundRole:                                           # highlight sorting column(s)
            if orientation == Qt.Horizontal:
                if len(self._qSort) > 0 and section == self._qSort[-1]:
                    return QBrush(QColor(255, 215, 0))                          # gold
                if len(self._qSort) > 1 and section == self._qSort[-2]:
                    return QBrush(QColor(255, 255, 160))                        # lightyellow
                if len(self._qSort) > 2 and section == self._qSort[-3]:
                    return QBrush(QColor(250, 250, 210))                        # lightgoldenrodyellow
                else:
                    return QVariant()

        return QAbstractTableModel.headerData(self, section, orientation, role)

    def rowCount(self, _):
        # required 2nd parameter (index) not being used. See: https://gist.github.com/nbassler/342fc56c42df27239fa5276b79fca8e6
        if self._data is not None:
            return self._data.shape[0]
        return 10

    def columnCount(self, _):
        # required 2nd parameter (index) not being used. See: https://gist.github.com/nbassler/342fc56c42df27239fa5276b79fca8e6
        if self._header is None or len(self._header) == 0:
            raise ValueError('Table header cannot be empty list')
        else:
            return len(self._header) - 3                                        # do not display the 3 [unique, inSps, inRps] attributes

    def nextDuplicate(self, index):
        if self._data is None:
            return None
        for i in range(index + 1, self.rowCount(0)):
            record = self._data[i]
            uniq = record['Uniq']
            if uniq == 0:
                return i
        return None

    def prevDuplicate(self, index):
        if self._data is None:
            return None
        for i in range(index - 1, -1, -1):
            record = self._data[i]
            uniq = record['Uniq']
            if uniq == 0:
                return i
        return None

    def nextSrcOrphan(self, index):
        if self._data is None:
            return None
        for i in range(index + 1, self.rowCount(0)):
            record = self._data[i]
            inSps = record['InSps']
            if inSps == 0:
                return i
        return None

    def prevSrcOrphan(self, index):
        if self._data is None:
            return None
        for i in range(index - 1, -1, -1):
            record = self._data[i]
            inSps = record['InSps']
            if inSps == 0:
                return i
        return None

    def nextRecOrphan(self, index):
        if self._data is None:
            return None
        for i in range(index + 1, self.rowCount(0)):
            record = self._data[i]
            inRps = record['InRps']
            if inRps == 0:
                return i
        return None

    def prevRecOrphan(self, index):
        if self._data is None:
            return None
        for i in range(index - 1, -1, -1):
            record = self._data[i]
            inRps = record['InRps']
            if inRps == 0:
                return i
        return None


# This Table first loads the model, and from there you can play with the column width
# You could use model.columnCount() to distribute available space
class ResizeTable(QTableView):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.setMinimumSize(100, 100)
        rowHeight = self.fontMetrics().height()
        self.verticalHeader().setDefaultSectionSize(rowHeight)
        self.setModel(model)

    def resizeEvent(self, event):
        width = event.size().width()
        self.setColumnWidth(1, width * 0.25)   # 25% Width Column
        self.setColumnWidth(2, width * 0.75)   # 75% Width Column

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._header[section]
        return QAbstractTableModel.headerData(self, section, orientation, role)


# Here is an example how to change background color for selected items:
# See: https://stackoverflow.com/questions/47880568/how-to-set-each-items-selection-color-of-qtablewidget-in-pyqt5

# Here is an example of a headerData implementation (code is in C++):
# See: https://doc.qt.io/qt-6/qt.html#ItemDataRole-enum

# QVariant
# Model::headerData(int section, Qt::Orientation orientation, int role) const
# {
#     ...
#     if (role == Qt::DisplayRole)
#     {
#         return QString("Header #%1").arg(section);
#     }

#     if (role == Qt::FontRole)
#     {
#         QFont serifFont("Times", 10, QFont::Bold, true);
#         return serifFont;
#     }

#     if (role == Qt::TextAlignmentRole)
#     {
#         return Qt::AlignRight;
#     }

#     if (role == Qt::BackgroundRole)
#     {
#         return QBrush(Qt::blue);
#     }

#     if (role == Qt::ForegroundRole)
#     {
#         return QBrush(Qt::red);
#     }
#     ...
# }

# def data(self, index, role):
#         if index.isValid() or (0 <= index.row() < len(self.ListItemData)):
#             if role == Qt.DisplayRole:
#                 return QVariant(self.ListItemData[index.row()]['name'])
#             elif role == Qt.DecorationRole:
#                 return QVariant(QIcon(self.ListItemData[index.row()]['iconPath']))
#             elif role == Qt.SizeHintRole:
#                 return QVariant(QSize(70,80))
#             elif role == Qt.TextAlignmentRole:
#                 return QVariant(int(Qt.AlignHCenter|Qt.AlignVCenter))
#             elif role == Qt.FontRole:
#                 font = QFont()
#                 font.setPixelSize(20)
#                 return QVariant(font)
#         else:
#             return QVariant()
