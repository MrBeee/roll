from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (QDialog, QDialogButtonBox, QDoubleSpinBox,
                                 QHBoxLayout, QLabel, QVBoxLayout)


class ShiftSurveyAreaDialog(QDialog):
    INFO_TEXT = (
        "This utility shifts the survey area by delta-x and delta-y amounts in local coordinates. "
        "All source and receiver seeds will be moved by that amount.\n\n"
        "An exception are the well seeds; these are 'anchored' in global space.\n"
        "To alter their local coordinates, you need to edit the global grid settings\n"
    )

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle('Shift Survey Location')
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumWidth(360)

        infoLabel = QLabel(self.INFO_TEXT)
        infoLabel.setWordWrap(True)

        self.deltaXSpin = QDoubleSpinBox()
        self.deltaXSpin.setDecimals(2)
        self.deltaXSpin.setRange(-1000000.0, 1000000.0)
        self.deltaXSpin.setSingleStep(10.0)
        self.deltaXSpin.setFixedWidth(140)

        self.deltaYSpin = QDoubleSpinBox()
        self.deltaYSpin.setDecimals(2)
        self.deltaYSpin.setRange(-1000000.0, 1000000.0)
        self.deltaYSpin.setSingleStep(10.0)
        self.deltaYSpin.setFixedWidth(140)

        shiftLayout = QHBoxLayout()
        shiftLayout.addWidget(QLabel('delta-x'))
        shiftLayout.addWidget(self.deltaXSpin)
        shiftLayout.addSpacing(16)
        shiftLayout.addWidget(QLabel('delta-y'))
        shiftLayout.addWidget(self.deltaYSpin)
        shiftLayout.addStretch()

        buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(infoLabel)
        layout.addLayout(shiftLayout)
        layout.addSpacing(10)
        layout.addWidget(buttonBox)
        self.setLayout(layout)

    @staticmethod
    def getShift(parent=None):
        dialog = ShiftSurveyAreaDialog(parent)
        result = dialog.exec()
        success = result == QDialog.DialogCode.Accepted
        return success, dialog.deltaXSpin.value(), dialog.deltaYSpin.value()
