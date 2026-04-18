# coding=utf-8

from qgis.PyQt.QtCore import QFileInfo, QRectF, Qt
from qgis.PyQt.QtGui import QFont, QImage, QPainter
from qgis.PyQt.QtPrintSupport import QPrinter, QPrintPreviewDialog
from qgis.PyQt.QtWidgets import QFileDialog


class PrintPresentationController:
    def __init__(self, window) -> None:
        self.window = window

    def filePrint(self):
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        preview = QPrintPreviewDialog(printer, self.window)
        preview.paintRequested.connect(self.window.printPreview)
        preview.setWindowTitle('Print Preview')
        preview.exec()

    def printPreview(self, printer):
        currentWidget = self.window.mainTabWidget.currentWidget()

        if currentWidget is self.window.textEdit:
            self.window.textEdit.print(printer)
            return

        plotWidget = self.window._grabPlotWidgetForPrint()
        if plotWidget is not None:
            self._printPlotWidget(printer, plotWidget)
            return

        self.window.textEdit.print(printer)

    def filePrintPdf(self):
        fileName, _ = QFileDialog.getSaveFileName(self.window, 'Export PDF', None, 'PDF files (*.pdf);;All Files (*)')

        if not fileName:
            return

        if not QFileInfo(fileName).suffix():
            fileName += '.pdf'

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(fileName)
        self.window.textEdit.document().print(printer)

    def _printPlotWidget(self, printer, plotWidget) -> None:
        painter = QPainter(printer)
        try:
            target = printer.pageLayout().paintRectPixels(printer.resolution())
            source = plotWidget.rect()
            if source.isEmpty() or target.isEmpty():
                return

            target = self._applyPrintMargins(target)
            if target.isEmpty():
                return

            target = self._drawHeader(painter, target)
            if target.isEmpty():
                return

            image = QImage(source.size(), QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.white)
            imagePainter = QPainter(image)
            try:
                plotWidget.render(imagePainter)
            finally:
                imagePainter.end()

            scale = min(target.width() / image.width(), target.height() / image.height())
            x = target.x() + (target.width() - image.width() * scale) / 2.0
            y = target.y() + (target.height() - image.height() * scale) / 2.0
            drawRect = QRectF(x, y, image.width() * scale, image.height() * scale)
            painter.drawImage(drawRect, image)
        finally:
            painter.end()

    @staticmethod
    def _applyPrintMargins(target: QRectF) -> QRectF:
        margin = int(min(target.width(), target.height()) * 0.10)
        return target.adjusted(margin, margin, -margin, -margin)

    def _drawHeader(self, painter, target: QRectF) -> QRectF:
        headerText = QFileInfo(self.window.fileName).fileName() if self.window.fileName else 'Untitled'
        if not headerText:
            return target

        painter.save()
        try:
            headerFont = QFont(painter.font())
            headerFont.setBold(True)
            headerFont.setPointSize(max(8, int(headerFont.pointSize() * 1.2)))
            painter.setFont(headerFont)

            headerHeight = painter.fontMetrics().height()
            headerRect = QRectF(target.x(), target.y(), target.width(), headerHeight)
            painter.drawText(headerRect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, headerText)

            gap = max(2, int(headerHeight * 0.35))
            lineY = int(headerRect.bottom() + (gap * 0.5))
            painter.drawLine(int(target.x()), lineY, int(target.x() + target.width()), lineY)
            return target.adjusted(0, headerHeight + gap, 0, 0)
        finally:
            painter.restore()
