# coding=utf-8

import pyqtgraph as pg
from qgis.PyQt.QtGui import QImage, QPainter
from qgis.PyQt.QtWidgets import QApplication

from .enums_and_int_flags import PaintDetails


class ActionStateController:
    def __init__(self, window) -> None:
        self.window = window

    def updateMenuStatus(self, resetAnalysis=True):
        window = self.window

        if resetAnalysis:
            window.actionArea.setChecked(True)
            window.imageType = 0
            window.handleImageSelection()

        self._setActionStates(
            ('actionExportFoldMap', window.output.binOutput is not None),
            ('actionExportMinOffsets', window.output.minOffset is not None),
            ('actionExportMaxOffsets', window.output.maxOffset is not None),
            ('actionExportRmsOffsets', window.output.rmsOffset is not None),
            ('actionExportAnaAsCsv', window.output.anaOutput is not None),
            ('actionExportRecAsCsv', window.recGeom is not None),
            ('actionExportSrcAsCsv', window.srcGeom is not None),
            ('actionExportRelAsCsv', window.relGeom is not None),
            ('actionExportRecAsR01', window.recGeom is not None),
            ('actionExportSrcAsS01', window.srcGeom is not None),
            ('actionExportRelAsX01', window.relGeom is not None),
            ('actionExportSrcToQGIS', window.srcGeom is not None),
            ('actionExportRecToQGIS', window.recGeom is not None),
            ('actionExportRpsAsCsv', window.rpsImport is not None),
            ('actionExportSpsAsCsv', window.spsImport is not None),
            ('actionExportXpsAsCsv', window.xpsImport is not None),
            ('actionExportRpsAsR01', window.rpsImport is not None),
            ('actionExportSpsAsS01', window.spsImport is not None),
            ('actionExportXpsAsX01', window.xpsImport is not None),
            ('actionExportSpsToQGIS', window.spsImport is not None),
            ('actionExportRpsToQGIS', window.rpsImport is not None),
            ('btnSrcRemoveDuplicates', window.srcGeom is not None),
            ('btnSrcRemoveOrphans', window.srcGeom is not None),
            ('btnSrcExportToQGIS', window.srcGeom is not None),
            ('btnRecRemoveDuplicates', window.recGeom is not None),
            ('btnRecRemoveOrphans', window.recGeom is not None),
            ('btnRecExportToQGIS', window.recGeom is not None),
            ('btnRelRemoveSrcOrphans', window.relGeom is not None),
            ('btnRelRemoveDuplicates', window.relGeom is not None),
            ('btnRelRemoveRecOrphans', window.relGeom is not None),
            ('actionExportAreasToQGIS', len(window.fileName) > 0),
            ('btnRelExportToQGIS', len(window.fileName) > 0),
            ('btnSpsExportToQGIS', window.spsImport is not None),
            ('btnRpsExportToQGIS', window.rpsImport is not None),
            ('actionFold', window.output.binOutput is not None),
            ('actionMinO', window.output.minOffset is not None),
            ('actionMaxO', window.output.maxOffset is not None),
            ('actionRmsO', window.output.rmsOffset is not None),
            ('actionSpider', window.output.anaOutput is not None and window.output.binOutput is not None),
            ('actionMoveLt', window.output.anaOutput is not None),
            ('actionMoveRt', window.output.anaOutput is not None),
            ('actionMoveUp', window.output.anaOutput is not None),
            ('actionMoveDn', window.output.anaOutput is not None),
            ('btnBinToQGIS', window.output.binOutput is not None),
            ('btnMinToQGIS', window.output.minOffset is not None),
            ('btnMaxToQGIS', window.output.maxOffset is not None),
            ('btnRmsToQGIS', window.output.rmsOffset is not None),
            ('actionExportFoldMapToQGIS', window.output.binOutput is not None),
            ('actionExportMinOffsetsToQGIS', window.output.minOffset is not None),
            ('actionExportMaxOffsetsToQGIS', window.output.maxOffset is not None),
            ('actionExportRmsOffsetsToQGIS', window.output.rmsOffset is not None),
            ('actionRecPoints', window.recGeom is not None),
            ('actionSrcPoints', window.srcGeom is not None),
            ('actionRpsPoints', window.rpsImport is not None),
            ('actionSpsPoints', window.spsImport is not None),
            ('actionAllPoints', window.recGeom is not None or window.srcGeom is not None or window.rpsImport is not None or window.spsImport is not None),
        )

        if window.survey is None:
            return

        window.actionShowSrcPatterns.setChecked(window.survey.paintDetails & PaintDetails.srcPat != PaintDetails.none)
        window.actionShowSrcPoints.setChecked(window.survey.paintDetails & PaintDetails.srcPnt != PaintDetails.none)
        window.actionShowSrcLines.setChecked(window.survey.paintDetails & PaintDetails.srcLin != PaintDetails.none)
        window.actionShowRecPatterns.setChecked(window.survey.paintDetails & PaintDetails.recPat != PaintDetails.none)
        window.actionShowRecPoints.setChecked(window.survey.paintDetails & PaintDetails.recPnt != PaintDetails.none)
        window.actionShowRecLines.setChecked(window.survey.paintDetails & PaintDetails.recLin != PaintDetails.none)

    def enableProcessingMenuItems(self, enable=True):
        window = self.window

        nTemplates = window.survey.calcNoTemplates() if window.survey is not None else 0
        hasGeometryInputs = enable is True and window.srcGeom is not None and window.recGeom is not None
        hasSpsInputs = enable is True and window.spsImport is not None and window.rpsImport is not None

        self._setActionStates(
            ('actionBasicBinFromTemplates', enable and nTemplates > 0),
            ('actionFullBinFromTemplates', enable and nTemplates > 0),
            ('actionGeometryFromTemplates', enable and nTemplates > 0),
            ('actionBasicBinFromGeometry', hasGeometryInputs),
            ('actionFullBinFromGeometry', hasGeometryInputs),
            ('actionBasicBinFromSps', hasSpsInputs),
            ('actionFullBinFromSps', hasSpsInputs),
            ('actionStopThread', not enable),
        )

    def clipboardHasText(self):
        return len(QApplication.clipboard().text()) != 0

    def invokeFocusMethod(self, methodName: str) -> bool:
        obj = QApplication.focusWidget()
        if obj is None:
            obj = QApplication.focusObject()
        if obj is None:
            return False

        method = getattr(obj, methodName, None)
        if callable(method):
            method()
            return True
        return False

    def cut(self):
        self.invokeFocusMethod('cut')
        self.window.actionPaste.setEnabled(self.clipboardHasText())

    def copy(self):
        if not self.invokeFocusMethod('copy'):
            self.copyPlotWidgetToClipboard()
        self.window.actionPaste.setEnabled(self.clipboardHasText())

    def paste(self):
        self.invokeFocusMethod('paste')

    def selectAll(self):
        self.invokeFocusMethod('selectAll')

    def grabPlotWidgetForPrint(self):
        currentWidget = self.window.mainTabWidget.currentWidget()
        if isinstance(currentWidget, pg.PlotWidget):
            return currentWidget

        if currentWidget is self.window.analysisTabWidget:
            currentWidget = self.window.analysisTabWidget.currentWidget()

        if currentWidget is None:
            return None

        if isinstance(currentWidget, pg.PlotWidget):
            return currentWidget

        return currentWidget.findChild(pg.PlotWidget)

    def copyPlotWidgetToClipboard(self) -> bool:
        plotWidget = self.grabPlotWidgetForPrint()
        if plotWidget is None:
            return False

        source = plotWidget.rect()
        if source.isEmpty():
            return False

        image = QImage(source.size(), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(pg.mkColor('w'))

        painter = QPainter(image)
        try:
            plotWidget.render(painter)
        finally:
            painter.end()

        QApplication.clipboard().setImage(image)
        return True

    def _setActionStates(self, *entries) -> None:
        for actionName, enabled in entries:
            getattr(self.window, actionName).setEnabled(enabled)
