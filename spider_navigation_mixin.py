# spider_navigation_mixin.py

# Why is there no __init__ in this class ?
#
# Mixins are meant to layer behaviour on top of an existing concrete class.
# RollMainWindow already owns initialization of shared state (self.spiderPoint, self.tbSpider, self.actionMoveLt, …).
# Adding an __init__ here would force every subclass to remember calling super().__init__() in the right order,
# which is easy to forget and can break other base classes because Python’s MRO would run multiple constructors that weren’t designed to cooperate.
# All state the mixin needs is created elsewhere: the host window instantiates the toolbar actions, numpy models, transforms, etc.
# The mixin only binds signals via setupSpiderActions() and relies on attributes that already exist.
# That keeps the mixin “passive” and avoids side effects during construction.
# If someday the mixin does need to set up its own attributes,
# the typical pattern is to expose a dedicated setup availableRows (like setupSpiderActions()) that the concrete class calls after its own initialization.
# This is more explicit and doesn’t interfere with other base classes’ constructors.
# So skipping __init__ is deliberate: it keeps the mixin lightweight, predictable, and safe to reuse in multiple inheritance hierarchies.

# SpiderNavigationMixin.navigateSpider() calls self.getVisiblePlotWidget() around spider_navigation_mixin.py:58-83.
# At runtime self is an instance of RollMainWindow, because that class inherits from the mixin (e.g., class RollMainWindow(..., SpiderNavigationMixin)).
# Python resolves self.getVisiblePlotWidget through the availableRows resolution order,
# so it finds the implementation already defined on RollMainWindow in roll_main_window.py:2228-2277.
# availableRowss don’t need to be defined “above” their call sites; they just have to exist on the object when the call happens.
# So the mixin can safely rely on RollMainWindow supplying that availableRows.

import numpy as np
import pyqtgraph as pg
from qgis.PyQt.QtCore import QItemSelection, QItemSelectionModel, QPoint, Qt
from qgis.PyQt.QtWidgets import QApplication, QMessageBox

from .enums_and_int_flags import Direction, MsgType
from .functions_numba import numbaSpiderBin


class SpiderNavigationMixin:
    """Reusable spider-navigation behaviour for RollMainWindow variants."""

    def setupSpiderActions(self) -> None:
        """Wire toolbar buttons to the mixin handlers; call once during init."""
        self.actionMoveLt.triggered.connect(self.spiderGoLt)
        self.actionMoveRt.triggered.connect(self.spiderGoRt)
        self.actionMoveUp.triggered.connect(self.spiderGoUp)
        self.actionMoveDn.triggered.connect(self.spiderGoDn)
        self.actionSpider.triggered.connect(self.handleSpiderPlot)

    # Public triggers -----------------------------------------------------

    # deal with the spider navigation
    # See: https://stackoverflow.com/questions/49316067/how-get-pressed-keys-in-mousepressevent-availableRows-with-qt

    def spiderGoRt(self, *_, direction: Direction = Direction.Rt) -> None:
        self.navigateSpider(direction=direction)

    def spiderGoLt(self, *_, direction: Direction = Direction.Lt) -> None:
        self.navigateSpider(direction=direction)

    def spiderGoUp(self, *_, direction: Direction = Direction.Up) -> None:
        self.navigateSpider(direction=direction)

    def spiderGoDn(self, *_, direction: Direction = Direction.Dn) -> None:
        self.navigateSpider(direction=direction)

    def handleSpiderPlot(self) -> None:
        if self.tbSpider.isChecked():
            self.navigateSpider(Direction.NA)
        else:
            self.plotLayout()

    # Core logic ----------------------------------------------------------

    def navigateSpider(self, direction: Direction) -> None:
        if self.output.anaOutput is None or self.output.binOutput is None:
            return

        step = self._spiderStepFromModifiers()
        xAna, yAna, zFold, wCols = self.output.anaOutput.shape
        xBin, yBin = self.output.binOutput.shape

        if wCols != 13 or xAna != xBin or yAna != yBin:
            QMessageBox.warning(
                self,
                'Misaligned analysis arrays',
                'Binning file and extended analysis file have dissimilar sizes. Please rerun analysis',
            )
            return

        self._updateSpiderPoint(direction, step, xAna, yAna)
        nX, nY = self.spiderPoint.x(), self.spiderPoint.y()

        try:
            fold = min(self.output.binOutput[nX, nY], zFold)
        except IndexError:
            return

        _, plotIndex = self.getVisiblePlotWidget()                             # get current plot; plot_widget not used
        if plotIndex == 0:
            self._updateLayoutSpiderOverlay(nX, nY, fold)
        else:
            self.updateVisiblePlotWidget(plotIndex)

        self._syncTraceTableSelection(nX, nY, fold)

    # Helpers -------------------------------------------------------------

    def _spiderStepFromModifiers(self) -> int:
        step = 1
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            step = 10
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            step *= 5
        return step

    def _updateSpiderPoint(self, direction: Direction, step: int, x_max: int, y_max: int) -> None:
        if self.spiderPoint == QPoint(-1, -1):
            self.spiderPoint = QPoint(x_max // 2, y_max // 2)
        elif direction == Direction.Rt:
            self.spiderPoint += QPoint(1, 0) * step
        elif direction == Direction.Lt:
            self.spiderPoint -= QPoint(1, 0) * step
        elif direction == Direction.Up:
            self.spiderPoint += QPoint(0, 1) * step
        elif direction == Direction.Dn:
            self.spiderPoint -= QPoint(0, 1) * step

        self.spiderPoint.setX(min(max(self.spiderPoint.x(), 0), x_max - 1))
        self.spiderPoint.setY(min(max(self.spiderPoint.y(), 0), y_max - 1))

    def _updateLayoutSpiderOverlay(self, nX: int, nY: int, fold: int) -> None:
        if self.survey.binTransform is None or self.survey.st2Transform is None:
            return

        if fold > 0:
            slice2d = self.output.anaOutput[nX, nY, 0:fold, :]
            legs = self._spiderLegArrays(slice2d)
            self.spiderSrcX, self.spiderSrcY, self.spiderRecX, self.spiderRecY = legs
        else:
            self.spiderSrcX = self.spiderSrcY = self.spiderRecX = self.spiderRecY = None

        # if fold > 0:
        #     legs = numbaSpiderBin(self.output.anaOutput[nX, nY, 0:fold, :])
        #     self.spiderSrcX, self.spiderSrcY, self.spiderRecX, self.spiderRecY = legs
        # else:
        #     self.spiderSrcX = self.spiderSrcY = self.spiderRecX = self.spiderRecY = None

        invBin, _ = self.survey.binTransform.inverted()
        cmpX, cmpY = invBin.map(nX, nY)
        stkX, stkY = self.survey.st2Transform.map(cmpX, cmpY)

        labelX = cmpX
        labelY = max(self.spiderRecY.max(), self.spiderSrcY.max()) if fold > 0 else cmpY
        if self.glob:
            labelX, labelY = self.survey.glbTransform.map(labelX, labelY)

        if self.spiderText is None:
            self.spiderText = pg.TextItem(
                anchor=(0.5, 1.3),
                border='b',
                color='b',
                fill=(130, 255, 255, 200),
                text='spiderLabel',
            )
            self.spiderText.setZValue(1000)

        self.spiderText.setPos(labelX, labelY)
        self.spiderText.setText(f'S({int(stkX)},{int(stkY)}), fold = {fold}')
        self.plotLayout()

    def _spiderLegArrays(self, slice2d: np.ndarray):
        try:
            return numbaSpiderBin(slice2d)
        except Exception as exc:
            module = exc.__class__.__module__
            isNumbaExc = module.startswith('numba')
            isKnownAttr = isinstance(exc, AttributeError) and 'get_call_template' in str(exc)
            if not (isNumbaExc or isKnownAttr):
                raise
            self._warnSpiderFallback(exc)
            return self._spiderLegArraysPython(slice2d)

    def _warnSpiderFallback(self, exc: Exception) -> None:
        if getattr(self, '_spiderFallbackWarned', False):
            return
        self.appendLogMessage(f'Numba&nbsp;&nbsp;: Falling back to Python spider plotting because Numba failed ({exc}).', MsgType.Warning    )
        self._spiderFallbackWarned = True

    @staticmethod
    def _spiderLegArraysPython(slice2d: np.ndarray):
        foldTimesTwo = slice2d.shape[0] * 2
        spiderSrcX = np.zeros(foldTimesTwo, dtype=np.float32)
        spiderSrcY = np.zeros_like(spiderSrcX)
        spiderRecX = np.zeros_like(spiderSrcX)
        spiderRecY = np.zeros_like(spiderSrcX)
        spiderSrcX[0::2] = slice2d[:, 3]; spiderSrcX[1::2] = slice2d[:, 7]
        spiderSrcY[0::2] = slice2d[:, 4]; spiderSrcY[1::2] = slice2d[:, 8]
        spiderRecX[0::2] = slice2d[:, 5]; spiderRecX[1::2] = slice2d[:, 7]
        spiderRecY[0::2] = slice2d[:, 6]; spiderRecY[1::2] = slice2d[:, 8]
        return spiderSrcX, spiderSrcY, spiderRecX, spiderRecY

    def _syncTraceTableSelection(self, nX: int, nY: int, fold: int) -> None:
        sizeY = self.output.anaOutput.shape[1]
        maxFold = self.output.anaOutput.shape[2]
        globalOffset = (nX * sizeY + nY) * maxFold

        isChunked = hasattr(self.anaModel, '_chunkedData') and self.anaModel._chunkedData is not None
        if isChunked:
            self._syncChunkedSelection(globalOffset, fold)
            return

        index = self.anaView.model().index(globalOffset, 0)
        self.anaView.scrollTo(index)
        self.anaView.selectRow(globalOffset)

        fold = max(fold, 1)
        top = self.anaView.model().index(globalOffset, 0)
        bottom = self.anaView.model().index(globalOffset + fold - 1, 0)
        selection = QItemSelection(top, bottom)
        self.anaView.selectionModel().select(
            selection,
            QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
        )

    def _syncChunkedSelection(self, globalOffset: int, fold: int) -> None:
        chunked = self.anaModel._chunkedData
        chunkSize = chunked.chunkSize
        targetChunk = globalOffset // chunkSize

        if chunked.currentChunk != targetChunk and chunked.gotoChunk(targetChunk):
            self.anaModel.layoutAboutToBeChanged.emit()
            self.anaModel._data = np.copy(chunked.getCurrentChunk())
            self.anaModel.layoutChanged.emit()
            self._updatePageInfo()

        localOffset = globalOffset % chunkSize
        availableRows = min(fold, chunkSize - localOffset)

        if availableRows <= 0 or localOffset >= self.anaModel.rowCount():
            return

        top = self.anaModel.index(localOffset, 0)
        bottom = self.anaModel.index(localOffset + availableRows - 1, 0)
        selection = QItemSelection(top, bottom)

        self.anaView.scrollTo(top)
        sm = self.anaView.selectionModel()
        sm.select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)

        if availableRows < fold:
            self.appendLogMessage(
                f'Note&nbsp;&nbsp;: Only {availableRows} of {fold} traces for this bin are visible in the current chunk',
                MsgType.Warning,
            )
