import pyqtgraph as pg
from qgis.PyQt.QtGui import (QColor, QFont, QFontMetricsF, QPainter,
                             QSyntaxHighlighter, QTextCharFormat, QTextOption)
from qgis.PyQt.QtWidgets import (QButtonGroup, QFrame, QPlainTextEdit, QWizard,
                                 QWizardPage)

from .roll_survey import RollSurvey


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


class CustomPlainTextEdit(QPlainTextEdit):
    """
    Custom QPlainTextEdit with some vertical lines drawn at two locations.
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


# this derived wizard class contains a survey object, that is passed to the wizard pages
class SurveyWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)

        # to access the main window and its components
        self.parent = parent

        # in the wizard constructor, first create the survey object for use in subsequent wizard pages
        self.survey = RollSurvey()


class SurveyWizardPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent                                                    # to access parent's parameters in the wizard pages (this will crash if parent is None)

    def cleanupPage(self):                                                      # is called to reset the page’s contents when the user clicks the wizard’s Back button.
        # The default implementation resets the page’s fields to their original values
        # To prevent initializePage() being called when browsing backwards,
        pass                                                                    # the default is now to do absolutely nothing !




# See: https://groups.google.com/g/pyqtgraph/c/V01QJKvrUio/m/iUBp5NePCQAJ
class LineROI(pg.LineSegmentROI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def addHandle(self, *args, **kwargs):
        # Larger handle for improved visibility
        self.handleSize = 8
        super().addHandle(*args, **kwargs)

    def checkPointMove(self, handle, pos, modifiers):
        # needed to prevent 'eternal' range-jitter preventing the plot to complete
        self.getViewBox().disableAutoRange(axis='xy')
        return True

    def generateSvg(self, nodes):
        pass                                                                    # for the time being don't do anything; just to keep PyLint happy


# See: https://gist.github.com/mistic100/dcbffbd9e9c15271dd14
class QButtonGroupEx(QButtonGroup):
    def setCheckedId(self, _id) -> int:
        for button in self.buttons():
            if self.id(button) == _id:
                button.setChecked(True)
                return _id
        return None


class QHLine(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)


class QVLine(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.VLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)


# Example usage:
# hline = QHLine()
# vline = QVLine()
