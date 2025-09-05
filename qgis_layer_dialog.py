from qgis.core import QgsFieldProxyModel, QgsMapLayerProxyModel
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel


class LayerDialog(QDialog):
    def __init__(self, layer=None, field=None, rollCrs=None, kind: str = '', parent=None):
        super().__init__(parent)

        # to access the main window and its components
        self.parent = parent
        self.setWindowTitle(f'Select {kind} layer')
        self.setMinimumWidth(350)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self.crs = None

        # get QGIS project information
        rollInf = 'Description: ' + rollCrs.description()
        rollAut = 'AuthorityID: ' + rollCrs.authid()

        self.layerInf = QLabel('Description')
        self.layerAut = QLabel('AuthorityID')

        self.layerTxt = QLabel("\nWhen Roll's CRS and the selected layer CRS are different, \nRoll will reproject the imported points to match Roll's CRS\n")
        self.filterTxt = QLabel("Applying this filter, will kill unselected points in Roll's analysis\nfor points where the value of this field is zero (or False)")

        # self.layerTxt.setStyleSheet('QLabel { font: italic; color: blue; }')
        # self.filterTxt.setStyleSheet('QLabel { font: italic; color: blue; }')
        self.layerTxt.setStyleSheet('QLabel { color: blue; }')
        self.filterTxt.setStyleSheet('QLabel { color: blue; }')

        # Add combobox for layer
        self.lcb = QgsMapLayerComboBox()                                        # create map layer combo box
        self.lcb.setCurrentIndex(-1)                                            # start with none selected
        self.lcb.setFilters(QgsMapLayerProxyModel.PointLayer)                   # no rasters (no lines, or polygons, just points)

        # Add combobox for field
        self.fcb = QgsFieldComboBox()                                           # create field combo box
        self.fcb.setAllowEmptyFieldName(True)                                   # don't force using field to limit point selection
        self.fcb.setFilters(QgsFieldProxyModel.Int | QgsFieldProxyModel.LongLong)   # All, Date, Double, Int, LongLong, Numeric, String, Time)

        # in case layer & field have been used before in Roll
        if layer is not None:
            self.lcb.setLayer(layer)
            self.fcb.setLayer(layer)
        if field is not None:
            self.fcb.setField(field)

        # need cancel & ok buttons
        self.btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)  # create standard button box
        self.btn.accepted.connect(self.accept)
        self.btn.rejected.connect(self.reject)

        # now put everything together in a form layout
        self.layout = QFormLayout()                                             # Create a form layout and add the two comboboxes
        self.layout.addWidget(QLabel('<b>Roll project CRS</b>'))
        self.layout.addWidget(QLabel(rollInf))
        self.layout.addWidget(QLabel(rollAut))
        self.layout.addWidget(QLabel(''))
        self.layout.addWidget(QLabel(f'<b>{kind} point layer and layer CRS details</b>'))
        self.layout.addWidget(self.lcb)
        self.layout.addWidget(self.layerInf)
        self.layout.addWidget(self.layerAut)
        self.layout.addWidget(self.layerTxt)
        self.layout.addWidget(QLabel('<b>Selection field code</b>'))
        self.layout.addWidget(self.fcb)
        self.layout.addWidget(self.filterTxt)
        self.layout.addWidget(QLabel(''))
        self.layout.addWidget(self.btn)

        self.lcb.layerChanged.connect(self.fcb.setLayer)                        # Add signal event (setLayer is a native slot function)
        self.lcb.layerChanged.connect(self.layerChanged)                        # Add signal event to show new crs

        self.setLayout(self.layout)                                             # finish dialog layout

    def layerChanged(self):
        crs = self.lcb.currentLayer().dataProvider().crs()
        self.layerInf.setText('Description: ' + crs.description())
        self.layerAut.setText('AuthorityID: ' + crs.authid())

    # def accept(self):                                                         # don't need to subclass
    #     QDialog.accept(self)

    # def reject(self):
    #     QDialog.reject(self)

    # static method to create the dialog and return (success, point layer, field code)
    @staticmethod
    def getPointLayer(layer=None, field=None, rollCrs=None, kind: str = '', parent=None):
        dialog = LayerDialog(layer, field, rollCrs, kind, parent)
        result = dialog.exec()
        success = result == QDialog.DialogCode.Accepted
        layer = dialog.lcb.currentLayer()
        field = dialog.fcb.currentField()
        return (success, layer, field)
