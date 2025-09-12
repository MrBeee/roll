import winsound  # make a sound when an exception ocurs

from pyqtgraph.widgets.SpinBox import ErrorBox
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import QLabel, QSizePolicy


class MyPreviewLabel(QLabel):
    """helper class to set up parameter label's size policy, font size and text alignment"""

    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        font = self.font()
        font.setPointSizeF(font.pointSize() - 0.5)
        self.setFont(font)
        self.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.errorBox = ErrorBox(self)

    def setErrorCondition(self, error=False):

        myFont = QFont()
        myFont.setBold(error)                                                   # sets and resets "bold", depending on error condition
        self.setFont(myFont)

        self.errorBox.setVisible(error)                                         # hows and hides the errorBoox, depending on error condition
        if error and self.isVisible():                                          # play a sound when in focus
            winsound.PlaySound('SystemHand', winsound.SND_ALIAS | winsound.SND_ASYNC)
            # > SystemAsterisk;
            # > SystemExclamation;
            # > SystemExit;
            # > SystemHand;
            # > SystemQuestion;
            # are common sounds; use asyync to avoid waiting on sound to finish
