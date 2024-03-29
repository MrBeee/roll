from pyqtgraph.parametertree import Parameter, registerParameterType
from pyqtgraph.parametertree.parameterTypes.basetypes import WidgetParameterItem
from qgis.core import QgsCoordinateReferenceSystem
from qgis.gui import QgsProjectionSelectionWidget

# See: https://qgis.org/pyqgis/3.22/gui/QgsProjectionSelectionWidget.html
# See: https://webgeodatavore.github.io/pyqgis-samples/gui-group/QgsProjectionSelectionWidget.html
# See: https://python.hotexamples.com/examples/qgis.gui/QgsProjectionSelectionWidget/-/python-qgsprojectionselectionwidget-class-examples.html
# See: https://python.hotexamples.com/examples/qgis.gui/QgsProjectionSelectionWidget/setCrs/python-qgsprojectionselectionwidget-setcrs-method-examples.html
# See: https://www.programcreek.com/python/example/91088/qgis.core.QgsCoordinateTransform
# See: https://python.hotexamples.com/examples/qgis.core/QgsCoordinateTransform/transformBoundingBox/python-qgscoordinatetransform-transformboundingbox-method-examples.html
# See: https://python.hotexamples.com/examples/qgis.core/QgsCoordinateTransform/-/python-qgscoordinatetransform-class-examples.html


class MyCrsParameterItem(WidgetParameterItem):
    def __init__(self, param, depth):
        crs = QgsCoordinateReferenceSystem('EPSG:4326')                         # create invalid crs object
        self.crs = param.opts.get('value', crs)

        super().__init__(param, depth)

    def makeWidget(self):
        w = QgsProjectionSelectionWidget()
        w.setOptionVisible(QgsProjectionSelectionWidget.CrsNotSet, False)

        w.setCrs(self.crs)

        w.sigChanged = w.crsChanged
        w.value = w.crs
        w.setValue = self.setValue                                              # the function defined below
        self.hideWidget = False
        return w

    def setValue(self, val):
        self.widget.setCrs(val)

    def defaultClicked(self):                                                   # need to overwrite WidgetParameterItem version
        self.param.setToDefault()                                               # to ensure sigValueChanged is emitted
        self.updateDefaultBtn()
        self.param.sigValueChanged.emit(self.param, self.widget.value())


class MyCrsParameter(Parameter):

    itemClass = MyCrsParameterItem

    def __init__(self, **opts):
        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        Parameter.__init__(self, **opts)

        crs = QgsCoordinateReferenceSystem('EPSG:4326')                         # create invalid crs object
        self.crs = opts.get('value', crs)


registerParameterType('myCrs', MyCrsParameter, override=True)
