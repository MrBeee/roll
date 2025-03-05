from pyqtgraph.parametertree import registerParameterType
from qgis.core import QgsCoordinateReferenceSystem
from qgis.PyQt.QtWidgets import QMessageBox

from .my_group import MyGroupParameter, MyGroupParameterItem

registerParameterType('myGroup', MyGroupParameter, override=True)


class MyCrs2ParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigValueChanging.connect(self.onValueChanging)
        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        crs = QgsCoordinateReferenceSystem()                                    # create invalid crs object (defaults to EPSG:4326)
        val = param.opts.get('value', crs)                                      # get crs from param and give it a default value

        t = val.description()
        e = not val.isValid() or val.isGeographic()

        if not val.isValid():
            t = 'Invalid CRS'
        if val.isGeographic():
            t = 'Geographic CRS (lat/long)'

        self.previewLabel.setErrorCondition(e)
        self.previewLabel.setText(t)
        self.previewLabel.update()


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
        self.addChild(dict(name='Description', type='str', value=self.crs.description(), default=self.crs.description(), readonly=True))
        self.addChild(dict(name='Authority ID', type='str', value=self.crs.authid(), default=self.crs.authid(), readonly=True))
        self.addChild(dict(name='Projection type', type='str', value=self.crs.projectionAcronym(), default=self.crs.projectionAcronym(), readonly=True))

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
