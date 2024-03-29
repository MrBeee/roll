from pyqtgraph.parametertree import registerParameterType
from pyqtgraph.parametertree.parameterTypes.basetypes import ParameterItem
from qgis.core import QgsCoordinateReferenceSystem
from qgis.PyQt.QtWidgets import (QHBoxLayout, QMessageBox, QSizePolicy,
                                 QSpacerItem, QWidget)

from .my_group import MyGroupParameter, MyGroupParameterItem
from .my_preview_label import MyPreviewLabel

registerParameterType('myGroup', MyGroupParameter, override=True)


class CrsPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()
        param.sigValueChanging.connect(self.onCrsChanging)                      # connect signal to slot

        self.crs = QgsCoordinateReferenceSystem()                               # create invalid crs object (defaults to EPSG:4326)
        val = param.opts.get('value', self.crs)                                 # get crs from param and give it a default value
        self.onCrsChanging(None, val)                                           # initialize the label in __init__()

    def onCrsChanging(self, _, val):
        t = val.description()
        e = not val.isValid() or val.isGeographic()
        if not val.isValid():
            t = 'Invalid CRS'
        if val.isGeographic():
            t = 'Geographic CRS (lat/long)'

        self.setText(t)
        self.setErrorCondition(e)
        self.update()


class MyCrs2ParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.itemWidget = QWidget()

        spacerItem = QSpacerItem(5, 5, QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.crsLabel = CrsPreviewLabel(param)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)                                                    # spacing between elements
        layout.addSpacerItem(spacerItem)
        layout.addWidget(self.crsLabel)
        self.itemWidget.setLayout(layout)

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


class MyCrs2Parameter(MyGroupParameter):

    itemClass = MyCrs2ParameterItem

    def __init__(self, **opts):
        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True
        opts['tip'] = 'Expand item to modify CRS'

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyCrs2 Parameter opts')

        self.crs = QgsCoordinateReferenceSystem()   # create invalid crs object
        self.crs = opts.get('value', self.crs)

        self.addChild(dict(name='CRS', type='myCrs', value=self.crs, default=self.crs))
        self.addChild(dict(name='Description', type='str', value=self.crs.description(), readonly=True))
        self.addChild(dict(name='Authority ID', type='str', value=self.crs.authid(), readonly=True))
        self.addChild(dict(name='Projection type', type='str', value=self.crs.projectionAcronym(), readonly=True))

        self.parC = self.child('CRS')
        self.parD = self.child('Description')
        self.parI = self.child('Authority ID')
        self.parP = self.child('Projection type')

        self.parC.sigValueChanged.connect(self.changed)

    # update the values of the three children
    def changed(self):
        crs = self.parC.value()

        if not crs.isValid():
            QMessageBox.warning(None, 'Invalid CRS', 'An invalid coordinate system has been selected', QMessageBox.Ok)

        if crs.isGeographic():
            QMessageBox.warning(None, 'Invalid CRS', 'An invalid coordinate system has been selected\nGeographic (using lat/lon coordinates)', QMessageBox.Ok)

        self.crs = crs

        self.parD.setValue(self.crs.description())
        self.parI.setValue(self.crs.authid())
        self.parP.setValue(value=self.crs.projectionAcronym())

        self.sigValueChanging.emit(self, self.crs)

    def value(self):
        return self.crs


registerParameterType('myCrs2', MyCrs2Parameter, override=True)
