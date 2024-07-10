from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel


class LayerDialog(QDialog):
    def __init__(self, kind: str = '', parent=None):
        super().__init__(parent)

        # to access the main window and its components
        self.parent = parent
        self.setWindowTitle(f'Select {kind} layer')
        self.setMinimumWidth(350)
        self.setWindowModality(Qt.ApplicationModal)

        # Add combobox for layer and field
        self.lcb = QgsMapLayerComboBox()                                        # create map layer combo box
        self.lcb.setCurrentIndex(-1)                                            # none selected
        self.lcb.setFilters(QgsMapLayerProxyModel.PointLayer)                   # no rasters (no lines, or polygons, just points)

        self.fcb = QgsFieldComboBox()                                           # create field combo box
        self.btn = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)  # create standard button box
        self.btn.accepted.connect(self.accept)
        self.btn.rejected.connect(self.reject)

        self.layout = QFormLayout()                                             # Create a form layout and add the two comboboxes
        self.layout.addWidget(QLabel('Available point layers'))
        self.layout.addWidget(self.lcb)
        self.layout.addWidget(QLabel('Corresponding field codes'))
        self.layout.addWidget(self.fcb)
        self.layout.addWidget(self.btn)

        self.lcb.layerChanged.connect(self.fcb.setLayer)                        # Add signal event (setLayer is a native slot function)
        self.setLayout(self.layout)                                                  # finish dialog layout

    def accept(self):
        QDialog.accept(self)

    def reject(self):
        QDialog.reject(self)
