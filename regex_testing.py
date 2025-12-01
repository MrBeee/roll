from qgis.PyQt.QtGui import (QColor, QFont, QFontMetrics, QPainter,
                             QSyntaxHighlighter, QTextCharFormat, QTextOption)
from qgis.PyQt.QtWidgets import QApplication, QFileDialog, QPlainTextEdit


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
        self.greyFormat.setFont(QFont('Courier New', 10))  # Monospaced font

        self.darkRedFormat = QTextCharFormat()
        self.darkRedFormat.setForeground(QColor('#8B0000'))  # Dark Red
        self.darkRedFormat.setFont(QFont('Courier New', 10))  # Monospaced font

        self.darkBlueFormat = QTextCharFormat()
        self.darkBlueFormat.setForeground(QColor('#00008B'))  # Dark Blue
        self.darkBlueFormat.setFont(QFont('Courier New', 10))  # Monospaced font

        self.darkGreenFormat = QTextCharFormat()
        self.darkGreenFormat.setForeground(QColor('#006400'))  # Dark Green
        self.darkGreenFormat.setFont(QFont('Courier New', 10))  # Monospaced font

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
        self.setStyleSheet('background-color: #FFFFE0; color: #000000;')  # Light yellow background, black text

    def paintEvent(self, event):
        # Call the base class paintEvent to ensure the text is drawn
        super(CustomPlainTextEdit, self).paintEvent(event)

        # Draw the vertical line
        painter = QPainter(self.viewport())
        painter.setPen(QColor('#000080'))  # dark color for the line

        # Calculate the x-coordinate for the vertical line
        char_width = self.fontMetrics().averageCharWidth()
        x_position = char_width * 10  # After the 10th character
        x_offset = int(char_width * 0.4) - self.horizontalScrollBar().value()   # Adjust the offset to center the line

        # Draw the line for the full height of the widget
        for i in range(1, 9):
            painter.drawLine(x_position * i + x_offset, 0, x_position * i + x_offset, self.viewport().height())
        painter.end()


# Example usage
if __name__ == '__main__':

    app = QApplication([])

    screen = app.primaryScreen()
    print(f'Screen: %s {screen.name()}')
    size = screen.size()
    print(f'Size: {size.width()} x {size.height()}')
    rect = screen.availableGeometry()
    print(f'Available: {rect.width()} x {rect.height()}')

    font = QFont('Courier New', 10)
    font.setStyleHint(QFont.Monospace)

    fontMetrics = QFontMetrics(font)   # Get the font metrics for the monospaced font
    print(f'Font metrics h: {fontMetrics.height()}')
    print(f'Font metrics w: {fontMetrics.averageCharWidth()}')

    editor = CustomPlainTextEdit()

    fileName, _ = QFileDialog.getOpenFileName(  # filetype variable not used
        None,  # no parent
        'Import SPS data...',  # caption
        'D:\\Roll\\',  # start directory + filename
        'SPS triplets (*.s01 *.r01 *.x01);;SPS triplets (*.sps *.rps *.xps);;Source   files (*.sps *.s01 *.sp1);;Receiver files (*.rps *.r01 *.rp1);;Relation files (*.xps *.x01 *.xp1);;All files (*.*)',
    )                                             # file extensions

    if fileName:
        with open(fileName, 'r', encoding='utf-8') as file:
            editor.setPlainText(file.read())
    else:
        # If no file is selected, set some default text
        editor.setPlainText(
            'Hello World\n'
            'how do you like my header line?\n'
            'This is a test line\n'
            'Another test line\n'
            'Source line (dark red) \n'
            'Receiver line (dark blue)\n'
            'Black line\n'
            'wwwwwwwwww----------1111111111wwwwwwwwww----------iiiiiiiiii__________WWWWWWWWWW'
        )

    w = fontMetrics.averageCharWidth() * 85  # 80 characters wide and some margin for the vertical scrollbar
    h = fontMetrics.height() * 30  # 30 lines high
    # editor.setMinimumSize(w, h)  # Set the minimum size of the editor

    editor.resize(w, h)
    editor.setWindowTitle('Custom Highlighter Example')

    # Apply the custom highlighter
    highlighter = LineHighlighter(editor.document())

    editor.show()
    app.exec()
