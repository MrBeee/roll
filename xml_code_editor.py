"""
Licensed under the terms of the MIT License
https://github.com/luchko/QCodeEditor
@author: Ivan Luchko (luchko.ivan@gmail.com)

This module contains the light QPlainTextEdit based QCodeEditor widget which
provides the line numbers bar and the syntax and the current line highlighting.

    class XMLHighlighter(QSyntaxHighlighter):
    class QCodeEditor(QPlainTextEdit):

testing and examples:

    def run_test():

Module is only compatible pyQt5; pyQt4 compatibility has been removed

For a C++ implementation, see:
https://github.com/d1vanov/basic-xml-syntax-highlighter
https://github.com/d1vanov/basic-xml-syntax-highlighter/blob/master/basic-xml-syntax-highlighter/BasicXMLSyntaxHighlighter.h
https://github.com/d1vanov/basic-xml-syntax-highlighter/blob/master/basic-xml-syntax-highlighter/BasicXMLSyntaxHighlighter.cpp

Consider using a scintilla based text editor. See: https://qscintilla.com/#home
There's also a way to edit xml in a bit more sophisticated manner: https://github.com/dealii/parameter_gui
Here's a way to highlight python code: https://wiki.python.org/moin/PyQt/Python%20syntax%20highlighting
See also: https://carsonfarmer.com/2009/07/syntax-highlighting-with-pyqt/
For cpp: https://github.com/d1vanov/basic-xml-syntax-highlighter

To add find and replace dialog, see: https://github.com/goldsborough/Writer-Tutorial/tree/master.
And in particular: https://web.archive.org/web/20170515141231/http://www.binpress.com/tutorial/building-a-text-editor-with-pyqt-part-3/147
"""

# QRegExp is obsolete as of Qt 5.15
# See: https://doc.qt.io/qt-5/qregexp.html
# See: https://github.com/Komet/MediaElch/issues/1086
# See:https://doc.qt.io/archives/qt-5.15/qregularexpression.html#notes-for-qregexp-users
# See: https://qxmledit.org/


from qgis.PyQt.QtCore import QRect, QRegularExpression, Qt
from qgis.PyQt.QtGui import QColor, QFont, QPainter, QSyntaxHighlighter, QTextCharFormat, QTextCursor, QTextFormat, QTextOption
from qgis.PyQt.QtWidgets import QApplication, QPlainTextEdit, QTextEdit, QWidget

# classes definition


class XMLHighlighter(QSyntaxHighlighter):
    """
    Class for highlighting xml text inherited from QSyntaxHighlighter

    reference:
        http://www.yasinuludag.com/blog/?p=49

    """

    def __init__(self, parent=None):

        super(XMLHighlighter, self).__init__(parent)

        self.highlightingRules = []

        xmlElementFormat = QTextCharFormat()
        xmlElementFormat.setForeground(QColor('#0070C0'))   # blue-ish
        # xmlElementFormat.setForeground(QColor("#000070")) # blue
        self.highlightingRules.append((QRegularExpression(r'\b[A-Za-z0-9_]+(?=[\s/>])'), xmlElementFormat))

        xmlAttributeFormat = QTextCharFormat()
        xmlAttributeFormat.setFontItalic(True)
        xmlAttributeFormat.setForeground(QColor('#177317'))   # green
        self.highlightingRules.append((QRegularExpression(r'\b[A-Za-z0-9_]+(?==)'), xmlAttributeFormat))
        self.highlightingRules.append((QRegularExpression(r'='), xmlAttributeFormat))

        self.valueFormat = QTextCharFormat()
        self.valueFormat.setForeground(QColor('#e35e00'))   # orange

        # CORRECTION: the '"' caracter needs to be preceeded by a '=' character !
        # to highlight an attribute that follows an '=' sign use: (?<=\=)\"([^"]*?)\"
        self.valueStartExpression = QRegularExpression(r'(?<=\=)"')
        self.valueEndExpression = QRegularExpression(r'"(?=[\s></])')

        singleLineCommentFormat = QTextCharFormat()
        singleLineCommentFormat.setForeground(QColor('#a0a0a4'))   # grey
        self.highlightingRules.append((QRegularExpression(r'<!--[^\n]*-->'), singleLineCommentFormat))

        textFormat = QTextCharFormat()
        textFormat.setForeground(QColor('#000000'))   # black
        self.highlightingRules.append((QRegularExpression(r'>(.+)(?=</)'), textFormat))

        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor('#000070'))   # blue
        keywordFormat.setFontWeight(QFont.Weight.Bold)
        keywordPatterns = [
            r'/>',
            r'>',
            r'<',
            r'</',
            r'\b?(spatialrefsys|wkt|proj4|srsid|srid|authid|description|projectionacronym|ellipsoidacronym|geographicflag)\b',
            r'\b?(survey|type|name|surveyCrs|limits|angles|binning|offset|output|unique|well|spiral|circle)\b',
            r'\b?(grid|b?local|global|block_list|block|borders|plane|sphere|reflectors|rec_border|src_border)\b',
            r'\b?(template_list|template|roll_list|translate|seed_list|seed|grow_list|pattern_list|pattern|wellCrs|xml)\b',
        ]

        self.highlightingRules += [(QRegularExpression(pattern), keywordFormat) for pattern in keywordPatterns]

    # VIRTUAL FUNCTION WE OVERRIDE THAT DOES ALL THE COLLORING

    def highlightBlock(self, text):
        # for every pattern
        for pattern, form in self.highlightingRules:
            # pattern is now a QRegularExpression
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                index = match.capturedStart()
                length = match.capturedLength()
                self.setFormat(index, length, form)

        # HANDLE QUOTATION MARKS NOW.. WE WANT TO START WITH " AND END WITH ".. A THIRD " SHOULD NOT CAUSE THE WORDS INBETWEEN SECOND AND THIRD TO BE COLORED

        self.setCurrentBlockState(0)
        startIndex = 0
        if self.previousBlockState() != 1:
            match = self.valueStartExpression.match(text)
            startIndex = match.capturedStart() if match.hasMatch() else -1
        while startIndex >= 0:
            endMatch = self.valueEndExpression.match(text, startIndex + 1)
            endIndex = endMatch.capturedStart() if endMatch.hasMatch() else -1
            if endIndex == -1:
                self.setCurrentBlockState(1)
                commentLength = len(text) - startIndex
            else:
                commentLength = endIndex - startIndex + endMatch.capturedLength()
            self.setFormat(startIndex, commentLength, self.valueFormat)
            # Find next start
            match = self.valueStartExpression.match(text, startIndex + commentLength)
            startIndex = match.capturedStart() if match.hasMatch() else -1


class QCodeEditor(QPlainTextEdit):
    """
    QCodeEditor inherited from QPlainTextEdit providing:

        numberBar - set by DISPLAY_LINE_NUMBERS flag equals True
        curent line highligthing - set by HIGHLIGHT_CURRENT_LINE flag equals True
        setting up QSyntaxHighlighter

    references:
        https://john.nachtimwald.com/2009/08/19/better-qplaintextedit-with-line-numbers/
        http://doc.qt.io/qt-5/qtwidgets-widgets-codeeditor-example.html

    """

    class NumberBar(QWidget):
        """class that defines textEditor numberBar"""

        def __init__(self, editor):
            QWidget.__init__(self, editor)

            self.editor = editor
            self.editor.blockCountChanged.connect(self.updateWidth)
            self.editor.updateRequest.connect(self.updateContents)
            self.font = QFont()
            self.numberBarColor = QColor('#e8e8e8')

        def paintEvent(self, event):

            painter = QPainter(self)
            painter.fillRect(event.rect(), self.numberBarColor)

            block = self.editor.firstVisibleBlock()

            # Iterate over all visible text blocks in the document.
            while block.isValid():
                blockNumber = block.blockNumber()

                # Bart: added int(xxx), as QGIS was complaing about a float for QRect()
                block_top = int(self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top())

                # Check if the position of the block is out side of the visible area.
                if not block.isVisible() or block_top >= event.rect().bottom():
                    break

                # We want the line number for the selected line to be bold.
                if blockNumber == self.editor.textCursor().blockNumber():
                    self.font.setBold(True)
                    painter.setPen(QColor('#000000'))
                else:
                    self.font.setBold(False)
                    painter.setPen(QColor('#717171'))
                painter.setFont(self.font)

                # Draw the line number right justified at the position of the line.
                paint_rect = QRect(0, block_top, self.width(), self.editor.fontMetrics().height())
                painter.drawText(paint_rect, Qt.AlignmentFlag.AlignRight, str(blockNumber + 1))

                block = block.next()

            painter.end()

            QWidget.paintEvent(self, event)

        def getWidth(self):
            count = self.editor.blockCount()
            # width = self.fontMetrics().width(str(count)) + 10 Note: width() is deprecated !
            width = self.fontMetrics().horizontalAdvance(str(count)) + 10
            return width

        def updateWidth(self):
            width = self.getWidth()
            if self.width() != width:
                self.setFixedWidth(width)
                self.editor.setViewportMargins(width, 0, 0, 0)

        def updateContents(self, rect, scroll):
            if scroll:
                self.scroll(0, scroll)
            else:
                self.update(0, rect.y(), self.width(), rect.height())

            if rect.contains(self.editor.viewport().rect()):
                fontSize = self.editor.currentCharFormat().font().pointSize()
                self.font.setPointSize(fontSize)
                self.font.setStyle(QFont.Style.StyleNormal)
                self.updateWidth()

    def __init__(self, DISPLAY_LINE_NUMBERS=True, HIGHLIGHT_CURRENT_LINE=True, SyntaxHighlighter=None):
        """
        Parameters
        ----------
        DISPLAY_LINE_NUMBERS : bool
            switch on/off the presence of the lines number bar
        HIGHLIGHT_CURRENT_LINE : bool
            switch on/off the current line highliting
        SyntaxHighlighter : QSyntaxHighlighter
            should be inherited from QSyntaxHighlighter
        """
        super(QCodeEditor, self).__init__()

        self.setFont(QFont('Ubuntu Mono', 9))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setWordWrapMode(QTextOption.WrapMode.NoWrap)

        self.DISPLAY_LINE_NUMBERS = DISPLAY_LINE_NUMBERS

        if DISPLAY_LINE_NUMBERS:
            self.number_bar = self.NumberBar(self)

        if HIGHLIGHT_CURRENT_LINE:
            self.currentLineNumber = None
            self.currentLineColor = self.palette().alternateBase()
            # self.currentLineColor = QColor("#e8e8e8")
            self.cursorPositionChanged.connect(self.highligtCurrentLine)

        if SyntaxHighlighter is not None:   # add highlighter to textdocument
            self.highlighter = SyntaxHighlighter(self.document())

    def resizeEvent(self, *e):
        """overload resizeEvent handler"""

        if self.DISPLAY_LINE_NUMBERS:   # resize number_bar widget
            cr = self.contentsRect()
            rec = QRect(cr.left(), cr.top(), self.number_bar.getWidth(), cr.height())
            self.number_bar.setGeometry(rec)

        QPlainTextEdit.resizeEvent(self, *e)

    def highligtCurrentLine(self):
        newCurrentLineNumber = self.textCursor().blockNumber()
        if newCurrentLineNumber != self.currentLineNumber:
            self.currentLineNumber = newCurrentLineNumber
            hi_selection = QTextEdit.ExtraSelection()
            hi_selection.format.setBackground(self.currentLineColor)
            hi_selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            hi_selection.cursor = self.textCursor()
            hi_selection.cursor.clearSelection()
            self.setExtraSelections([hi_selection])

    def getTextViaClipboard(self):
        cursor = self.textCursor()                                              # Do NOT use textEdit.toPlainText() as it resets doc status
        self.selectAll()                                                        # Copies any selected text to the clipboard.
        self.copy()                                                             # reset cursor to original position
        self.setTextCursor(cursor)                                              # set cursor back at original position

        clipboard = QApplication.clipboard()                                    # self.textEdit.setPlainText() messes up the docment status
        plainText = clipboard.text()                                            # get clipboard string
        clipboard.setText('')                                                   # empty the clipboard, don't leave text hanging there !
        return plainText                                                        # return data copied via clipboard

    def setTextViaClipboard(self, plainText):
        cursor = self.textCursor()                                              # Do NOT use textEdit.toPlainText() as it resets doc status
        clipboard = QApplication.clipboard()                                    # self.textEdit.setPlainText() messes up the docment status
        clipboard.setText(plainText)                                            # use the clipboard as a backdoor to update the text !
        self.selectAll()                                                        # select all text, so it will be replaced
        self.paste()                                                            # read the data from the clipboard into the textEdit
        self.setTextCursor(cursor)                                              # set cursor back at original position

    def getTextViaCursor(self):
        cursor = self.textCursor()                                              # get a cursor
        cursor.select(QTextCursor.SelectionType.Document)                                     # select the whole document
        plainText = cursor.selectedText()                                       # the plainText contains unicode paragraph separators
        plainText = plainText.replace('\u2029', '\n')                          # here we replace the Paragraph Separator by a New Line character

        return plainText                                                        # return the selected text

    def setTextViaCursor(self, plainText):
        cursor = self.textCursor()                                              # get a cursor
        cursor.select(QTextCursor.SelectionType.Document)                                     # select the whole document
        cursor.insertText(plainText)                                            # replace selection by provided text

    # See: https://stackoverflow.com/questions/45880941/replace-all-tab-operations-with-inserting-four-spaces-in-qplaintextedit-widget
    # See: https://stackoverflow.com/questions/59404003/keypressevent-is-not-working-in-my-pyqt-application why the following might not work...


##############################################################################

if __name__ == '__main__':

    # TESTING
    import sys

    def run_test():

        app = QApplication([])

        editor = QCodeEditor(DISPLAY_LINE_NUMBERS=True, HIGHLIGHT_CURRENT_LINE=True, SyntaxHighlighter=XMLHighlighter)

        text = """<FINITELATTICE>
          <LATTICE name="myLattice">
            <BASIS>
              <VECTOR>1.0 0.0 0.0</VECTOR>
              <VECTOR>0.0 1.0 0.0</VECTOR>
            </BASIS>
          </LATTICE>
          <PARAMETER name="L" />
          <PARAMETER default="L" name="W" />
          <EXTENT dimension="1" size="L" />
          <EXTENT dimension="2" size="W" />
          <BOUNDARY type="periodic" />
        </FINITELATTICE>
"""
        editor.setPlainText(text)
        editor.resize(400, 250)
        editor.show()

        sys.exit(app.exec_())

    run_test()


# Some help with painting lines in QPlainTextEdit
# See: https://forum.qt.io/topic/77201/custom-painted-line-on-qplaintextedit-doesn-t-disappear
# See: https://stackoverflow.com/questions/72603157/overwrite-paintevent-in-qtextedit-to-draw-rectangle-around-word
# See: https://forum.qt.io/topic/1099/qtextedit-and-custom-paint-event/4
