# spider_navigation_mixin.py

# Why is there no __init__ in this class ?
#
# Mixins are meant to layer behaviour on top of an existing concrete class.
# RollMainWindow already owns initialization of shared state (self.spiderPoint, self.tbSpider, self.actionMoveLt, …).
# Adding an __init__ here would force every subclass to remember calling super().__init__() in the right order,
# which is easy to forget and can break other base classes because Python’s MRO would run multiple constructors that weren’t designed to cooperate.
# All state the mixin needs is created elsewhere: the host window instantiates the toolbar actions, numpy models, transforms, etc.
# The mixin only binds signals via setup_spider_actions() and relies on attributes that already exist.
# That keeps the mixin “passive” and avoids side effects during construction.
# If someday the mixin does need to set up its own attributes,
# the typical pattern is to expose a dedicated setup method (like setup_spider_actions()) that the concrete class calls after its own initialization.
# This is more explicit and doesn’t interfere with other base classes’ constructors.
# So skipping __init__ is deliberate: it keeps the mixin lightweight, predictable, and safe to reuse in multiple inheritance hierarchies.

# SpiderNavigationMixin.navigateSpider() calls self.getVisiblePlotWidget() around spider_navigation_mixin.py:58-83.
# At runtime self is an instance of RollMainWindow, because that class inherits from the mixin (e.g., class RollMainWindow(..., SpiderNavigationMixin)).
# Python resolves self.getVisiblePlotWidget through the method resolution order,
# so it finds the implementation already defined on RollMainWindow in roll_main_window.py:2228-2277.
# Methods don’t need to be defined “above” their call sites; they just have to exist on the object when the call happens.
# So the mixin can safely rely on RollMainWindow supplying that method.

import numpy as np
import pyqtgraph as pg
from qgis.PyQt.QtCore import QItemSelection, QItemSelectionModel, QPoint, Qt
from qgis.PyQt.QtWidgets import QApplication, QMessageBox

from .enums_and_int_flags import Direction, MsgType
from .functions_numba import numbaSpiderBin


class SpiderNavigationMixin:
    """Reusable spider-navigation behaviour for RollMainWindow variants."""

    def setup_spider_actions(self) -> None:
        """Wire toolbar buttons to the mixin handlers; call once during init."""
        self.actionMoveLt.triggered.connect(self.spiderGoLt)
        self.actionMoveRt.triggered.connect(self.spiderGoRt)
        self.actionMoveUp.triggered.connect(self.spiderGoUp)
        self.actionMoveDn.triggered.connect(self.spiderGoDn)
        self.actionSpider.triggered.connect(self.handleSpiderPlot)

    # Public triggers -----------------------------------------------------

    # deal with the spider navigation
    # See: https://stackoverflow.com/questions/49316067/how-get-pressed-keys-in-mousepressevent-method-with-qt

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
        x_ana, y_ana, z_fold, w_cols = self.output.anaOutput.shape
        x_bin, y_bin = self.output.binOutput.shape

        if w_cols != 13 or x_ana != x_bin or y_ana != y_bin:
            QMessageBox.warning(
                self,
                'Misaligned analysis arrays',
                'Binning file and extended analysis file have dissimilar sizes. Please rerun analysis',
            )
            return

        self._updateSpiderPoint(direction, step, x_ana, y_ana)
        n_x, n_y = self.spiderPoint.x(), self.spiderPoint.y()

        try:
            fold = min(self.output.binOutput[n_x, n_y], z_fold)
        except IndexError:
            return

        _, plot_index = self.getVisiblePlotWidget()                             # get current plot; plot_widget not used
        if plot_index == 0:
            self._updateLayoutSpiderOverlay(n_x, n_y, fold)
        else:
            self.updateVisiblePlotWidget(plot_index)

        self._syncTraceTableSelection(n_x, n_y, fold)

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

    def _updateLayoutSpiderOverlay(self, n_x: int, n_y: int, fold: int) -> None:

        if fold > 0:
            slice2d = self.output.anaOutput[n_x, n_y, 0:fold, :]
            legs = self._spider_leg_arrays(slice2d)
            self.spiderSrcX, self.spiderSrcY, self.spiderRecX, self.spiderRecY = legs
        else:
            self.spiderSrcX = self.spiderSrcY = self.spiderRecX = self.spiderRecY = None

        # if fold > 0:
        #     legs = numbaSpiderBin(self.output.anaOutput[n_x, n_y, 0:fold, :])
        #     self.spiderSrcX, self.spiderSrcY, self.spiderRecX, self.spiderRecY = legs
        # else:
        #     self.spiderSrcX = self.spiderSrcY = self.spiderRecX = self.spiderRecY = None

        inv_bin, _ = self.survey.binTransform.inverted()
        cmp_x, cmp_y = inv_bin.map(n_x, n_y)
        stk_x, stk_y = self.survey.st2Transform.map(cmp_x, cmp_y)

        label_x = cmp_x
        label_y = max(self.spiderRecY.max(), self.spiderSrcY.max()) if fold > 0 else cmp_y
        if self.glob:
            label_x, label_y = self.survey.glbTransform.map(label_x, label_y)

        if self.spiderText is None:
            self.spiderText = pg.TextItem(
                anchor=(0.5, 1.3),
                border='b',
                color='b',
                fill=(130, 255, 255, 200),
                text='spiderLabel',
            )
            self.spiderText.setZValue(1000)

        self.spiderText.setPos(label_x, label_y)
        self.spiderText.setText(f'S({int(stk_x)},{int(stk_y)}), fold = {fold}')
        self.plotLayout()

    def _spider_leg_arrays(self, slice2d: np.ndarray):
        try:
            return numbaSpiderBin(slice2d)
        except Exception as exc:
            module = exc.__class__.__module__
            is_numba_exc = module.startswith('numba')
            is_known_attr = isinstance(exc, AttributeError) and 'get_call_template' in str(exc)
            if not (is_numba_exc or is_known_attr):
                raise
            self._warn_spider_fallback(exc)
            return self._spider_leg_arrays_python(slice2d)

    def _warn_spider_fallback(self, exc: Exception) -> None:
        if getattr(self, '_spider_fallback_warned', False):
            return
        self.appendLogMessage(f'Numba&nbsp;&nbsp;: Falling back to Python spider plotting because Numba failed ({exc}).', MsgType.Warning    )
        self._spider_fallback_warned = True

    @staticmethod
    def _spider_leg_arrays_python(slice2d: np.ndarray):
        fold_x2 = slice2d.shape[0] * 2
        spiderSrcX = np.zeros(fold_x2, dtype=np.float32)
        spiderSrcY = np.zeros_like(spiderSrcX)
        spiderRecX = np.zeros_like(spiderSrcX)
        spiderRecY = np.zeros_like(spiderSrcX)
        spiderSrcX[0::2] = slice2d[:, 3]; spiderSrcX[1::2] = slice2d[:, 7]
        spiderSrcY[0::2] = slice2d[:, 4]; spiderSrcY[1::2] = slice2d[:, 8]
        spiderRecX[0::2] = slice2d[:, 5]; spiderRecX[1::2] = slice2d[:, 7]
        spiderRecY[0::2] = slice2d[:, 6]; spiderRecY[1::2] = slice2d[:, 8]
        return spiderSrcX, spiderSrcY, spiderRecX, spiderRecY


    def _syncTraceTableSelection(self, n_x: int, n_y: int, fold: int) -> None:
        size_y = self.output.anaOutput.shape[1]
        max_fold = self.output.anaOutput.shape[2]
        global_offset = (n_x * size_y + n_y) * max_fold

        is_chunked = hasattr(self.anaModel, '_chunked_data') and self.anaModel._chunked_data is not None
        if is_chunked:
            self._syncChunkedSelection(global_offset, fold)
            return

        index = self.anaView.model().index(global_offset, 0)
        self.anaView.scrollTo(index)
        self.anaView.selectRow(global_offset)

        fold = max(fold, 1)
        top = self.anaView.model().index(global_offset, 0)
        bottom = self.anaView.model().index(global_offset + fold - 1, 0)
        selection = QItemSelection(top, bottom)
        self.anaView.selectionModel().select(
            selection,
            QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
        )

    def _syncChunkedSelection(self, global_offset: int, fold: int) -> None:
        chunked = self.anaModel._chunked_data
        chunk_size = chunked.chunk_size
        target_chunk = global_offset // chunk_size

        if chunked.current_chunk != target_chunk and chunked.goto_chunk(target_chunk):
            self.anaModel.layoutAboutToBeChanged.emit()
            self.anaModel._data = np.copy(chunked.get_current_chunk())
            self.anaModel.layoutChanged.emit()
            self._updatePageInfo()

        local_offset = global_offset % chunk_size
        available_rows = min(fold, chunk_size - local_offset)

        if available_rows <= 0 or local_offset >= self.anaModel.rowCount():
            return

        top = self.anaModel.index(local_offset, 0)
        bottom = self.anaModel.index(local_offset + available_rows - 1, 0)
        selection = QItemSelection(top, bottom)

        self.anaView.scrollTo(top)
        sm = self.anaView.selectionModel()
        sm.select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)

        if available_rows < fold:
            self.appendLogMessage(
                f'Note&nbsp;&nbsp;: Only {available_rows} of {fold} traces for this bin are visible in the current chunk',
                MsgType.Warning,
            )
