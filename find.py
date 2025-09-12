import re

from qgis.PyQt.QtGui import QTextCursor
from qgis.PyQt.QtWidgets import QDialog, QGridLayout, QLineEdit, QPushButton, QRadioButton

# To add find and replace dialog, see: https://github.com/goldsborough/Writer-Tutorial/tree/master.
# And in particular: https://web.archive.org/web/20170515141231/http://www.binpress.com/tutorial/building-a-text-editor-with-pyqt-part-3/147


class Find(QDialog):
    def __init__(self, parent=None):

        QDialog.__init__(self, parent)
        self.parent = parent
        self.lastStart = 0
        self.initUI()

    def initUI(self):

        # Button to search the document for something
        findButton = QPushButton('Find', self)
        findButton.clicked.connect(self.find)

        # Button to replace the last finding
        replaceButton = QPushButton('Replace', self)
        replaceButton.clicked.connect(self.replace)

        # Button to remove all findings
        allButton = QPushButton('Replace all', self)
        allButton.clicked.connect(self.replaceAll)

        # Normal mode - radio button
        self.normalRadio = QRadioButton('Normal', self)

        # Regular Expression Mode - radio button
        regexRadio = QRadioButton('RegEx', self)

        # The field into which to type the query
        self.findField = QLineEdit(self)
        # self.findField = QTextEdit(self)
        self.findField.resize(250, 30)

        # The field into which to type the text to replace the queried text
        self.replaceField = QLineEdit(self)
        # self.replaceField = QTextEdit(self)
        self.replaceField.resize(250, 30)

        layout = QGridLayout()
        layout.addWidget(self.findField, 1, 0, 1, 4)
        layout.addWidget(self.normalRadio, 2, 2)
        layout.addWidget(regexRadio, 2, 3)
        layout.addWidget(findButton, 2, 0, 1, 2)

        layout.addWidget(self.replaceField, 3, 0, 1, 4)
        layout.addWidget(replaceButton, 4, 0, 1, 2)
        layout.addWidget(allButton, 4, 2, 1, 2)

        # self.setGeometry(300, 300, 360, 250)
        nWidth = 360
        nHeight = 100
        if self.parent is not None:                                             # center dialog on main window !
            xPos = self.parent.x() + (self.parent.width() - nWidth) // 2
            yPos = self.parent.y() + (self.parent.height() - nHeight) // 2
            self.setGeometry(xPos, yPos, nWidth, nHeight)
        else:
            self.resize(nWidth, nHeight)

        self.setWindowTitle('Find and Replace')
        self.setLayout(layout)

        # By default the normal mode is activated
        self.normalRadio.setChecked(True)

    def find(self):
        # Grab the parent's text
        text = self.parent.textEdit.toPlainText()

        # And the text to find
        # query = self.findField.toPlainText()
        query = self.findField.text()

        if self.normalRadio.isChecked():
            # Use normal string search to find the query from the last starting position
            self.lastStart = text.find(query, self.lastStart + 1)

            # If the find() method didn't return -1 (not found)
            if self.lastStart >= 0:
                end = self.lastStart + len(query)
                self.moveCursor(self.lastStart, end)

            else:
                # Make the next search start from the begining again
                self.lastStart = 0
                self.parent.textEdit.moveCursor(QTextCursor.MoveOperation.End)

        else:
            # Compile the pattern
            pattern = re.compile(query)

            # The actual search
            match = pattern.search(text, self.lastStart + 1)

            if match:
                self.lastStart = match.start()
                self.moveCursor(self.lastStart, match.end())
            else:
                self.lastStart = 0

                # We set the cursor to the end if the search was unsuccessful
                self.parent.textEdit.moveCursor(QTextCursor.MoveOperation.End)

    def replace(self):
        # Grab the text cursor
        cursor = self.parent.textEdit.textCursor()

        # Security
        if cursor.hasSelection():
            # We insert the new text, which will override the selected text
            # cursor.insertText(self.replaceField.toPlainText())
            cursor.insertText(self.replaceField.text())

            # And set the new cursor
            self.parent.textEdit.setTextCursor(cursor)

    def replaceAll(self):
        self.lastStart = 0
        self.find()

        # Replace and find until self.lastStart is 0 again
        while self.lastStart:
            self.replace()
            self.find()

    def moveCursor(self, start, end):
        # We retrieve the QTextCursor object from the parent's QTextEdit
        cursor = self.parent.textEdit.textCursor()

        # Then we set the position to the beginning of the last match
        cursor.setPosition(start)

        # Next we move the Cursor by over the match and pass the KeepAnchor parameter
        # which will make the cursor select the the match's text
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, end - start)

        # And finally we set this new cursor as the parent's
        self.parent.textEdit.setTextCursor(cursor)
