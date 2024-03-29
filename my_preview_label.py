import winsound  # make a sound when an exception ocurs

from pyqtgraph.widgets.SpinBox import ErrorBox
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import QLabel, QSizePolicy


class MyPreviewLabel(QLabel):
    """helper class to set up parameter label's size policy, font size and text alignment"""

    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        font = self.font()
        font.setPointSizeF(font.pointSize() - 0.5)
        self.setFont(font)
        self.setAlignment(Qt.AlignVCenter)

        self.errorBox = ErrorBox(self)

    def setErrorCondition(self, error=False):

        myFont = QFont()
        myFont.setBold(error)
        self.setFont(myFont)
        self.errorBox.setVisible(error)

        if error and self.isVisible():
            winsound.PlaySound('SystemHand', winsound.SND_ALIAS | winsound.SND_ASYNC)
            # SystemAsterisk, SystemExclamation, SystemExit, SystemHand, SystemQuestion are common sounds; use asyync to avoid waiting on sound to finish
