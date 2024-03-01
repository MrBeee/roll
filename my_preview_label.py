from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QLabel, QSizePolicy


class MyPreviewLabel(QLabel):
    """helper class to set up label's size policy, font size and text alignment"""

    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        font = self.font()
        font.setPointSizeF(font.pointSize() - 0.5)
        self.setFont(font)
        self.setAlignment(Qt.AlignVCenter)
