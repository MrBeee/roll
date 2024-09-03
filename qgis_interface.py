import uuid

# See: https://www.qgistutorials.com/en/docs/points_in_polygon.html to restict points to polygons
# import matplotlib.pyplot as plt  # to create a png file
import numpy as np
import rasterio as rio
from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsColorRampShader,
    QgsFeature,
    QgsField,
    QgsFillSymbol,
    QgsGeometry,
    QgsMarkerSymbol,
    QgsPalLayerSettings,
    QgsPointXY,
    QgsProject,
    QgsRasterLayer,
    QgsRasterShader,
    QgsRendererCategory,
    QgsSingleBandPseudoColorRenderer,
    QgsStyle,
    QgsTextFormat,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
)
from qgis.PyQt.QtCore import QFileInfo, QRectF, QVariant
from qgis.PyQt.QtGui import QPolygonF, QTransform
from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox

from .functions import isFileInUse
from .qgis_layer_dialog import LayerDialog
from .sps_io_and_qc import pntType1

# See: https://anitagraser.com/pyqgis-101-introduction-to-qgis-python-programming-for-non-programmers/pyqgis101-creating-editing-a-new-vector-layer/
# See: https://docs.qgis.org/3.28/en/docs/pyqgis_developer_cookbook/vector.html
# See: https://docs.qgis.org/3.28/en/docs/pyqgis_developer_cookbook/vector.html#modifying-vector-layers
# See: https://docs.qgis.org/3.28/en/docs/pyqgis_developer_cookbook/vector.html#modifying-vector-layers-with-an-editing-buffer
# See: https://webgeodatavore.github.io/pyqgis-samples/gui-group/QgsMapLayerComboBox.html


def identifyQgisPointLayer(iface, layer, field, kind):
    # See: https://gis.stackexchange.com/questions/412684/retrieving-qgsmaplayercomboboxs-currently-selected-layer-to-get-its-name-for-ed

    # to create a modal dialog, see here:
    # See: https://stackoverflow.com/questions/18196799/how-can-i-show-a-pyqt-modal-dialog-and-get-data-out-of-its-controls-once-its-clo
    success, layer, field = LayerDialog.getPointLayer(layer, field, kind)

    if not success or layer is None:
        QMessageBox.information(None, 'No layer selected', 'No point layer has been selected in QGIS', QMessageBox.Cancel)
        return (None, None)

    vlMeta = layer.metadata()                                                   # get meta data
    parentId = vlMeta.parentIdentifier()                                        # for easy layer verification from plugin

    if isinstance(layer, QgsVectorLayer) and parentId.startswith('Roll'):       # we have the right one
        return (layer, field)
    else:
        QMessageBox.information(None, 'Please update metadata', "Please ensure the Parent Identifier in the metadata of the selected layer starts with 'Roll'", QMessageBox.Cancel)
        return (None, None)


# def updateQgisPointLayer(layerId, spsRecords, crs=None, source=True) -> bool:

#     if crs is None:
#         return False

#     vl = QgsProject.instance().mapLayer(layerId)

#     caps = vl.dataProvider().capabilities()                                     # get layer capabilities
#     if caps & QgsVectorDataProvider.FastTruncate or caps & QgsVectorDataProvider.DeleteFeatures:
#         success = vl.dataProvider().truncate()
#         if success is False:                                                    # something went wrong
#             return False
#     else:
#         return False                                                            # can't delete stuff

#     pr = vl.dataProvider()
#     pr.addAttributes(
#         [
#             # length and precision of fields have been tuned towards shapefile properties
#             QgsField('line', QVariant.Double, len=23, prec=1),
#             QgsField('stake', QVariant.Double, len=23, prec=1),
#             QgsField('index', QVariant.Int, len=10),
#             QgsField('code', QVariant.String, len=4),
#             QgsField('depth', QVariant.Double, len=10, prec=1),
#             QgsField('elev', QVariant.Double, len=23, prec=1),
#         ]
#     )
#     vl.updateFields()
#     vl.setCrs(crs)

#     featureList = []

#     for record in spsRecords:
#         # account for numpy float32 format, and the unicode string format
#         l = float(record['Line'])
#         p = float(record['Point'])
#         i = int(record['Index'])
#         c = str(record['Code'])
#         x = float(record['East'])
#         y = float(record['North'])
#         d = float(record['Depth'])
#         z = float(record['Elev'])

#         f = QgsFeature()
#         f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
#         f.setAttributes([l, p, i, c, d, z])
#         featureList.append(f)

#     pr.addFeatures(featureList)
#     vl.updateExtents()

#     # select src/rec symbol
#     if source:
#         symbol = QgsMarkerSymbol.createSimple(
#             {
#                 'name': 'circle',
#                 'color': '255,0,0,255',
#                 'outline_color': '35,35,35,255',
#                 'outline_width': '0.5',
#                 'outline_width_unit': 'RenderMetersInMapUnits',
#                 'size': '20',
#                 'size_unit': 'RenderMetersInMapUnits',
#             }
#         )
#     else:
#         symbol = QgsMarkerSymbol.createSimple(
#             {
#                 'name': 'circle',
#                 'color': '0,0,255,255',
#                 'outline_color': '35,35,35,255',
#                 'outline_width': '0.5',
#                 'outline_width_unit': 'RenderMetersInMapUnits',
#                 'size': '20',
#                 'size_unit': 'RenderMetersInMapUnits',
#             }
#         )

#     symbol.setOpacity(0.45)                                                     # opacity not allowed in constructor properties ?!
#     vl.renderer().setSymbol(symbol)

#     # update meta data through metadata() object
#     metaId = uuid.uuid4()                                                       # create a UUID object
#     vlMeta = vl.metadata()                                                      # derive object from layer
#     vlMeta.setIdentifier(str(metaId))                                           # turn UUID into string, to make it our ID string
#     if source:
#         vlMeta.setParentIdentifier('Roll Src')                                  # for easy layer verification from plugin
#     else:
#         vlMeta.setParentIdentifier('Roll Rec')                                  # for easy layer verification from plugin
#     vlMeta.setTitle(vl.name())                                                  # in case layer is renamed
#     vlMeta.setType('dataset')                                                   # this is the default value, if you don't update the metadata
#     vlMeta.setLanguage('Python')                                                # not very relevant
#     vlMeta.setAbstract("Point vector-layer created by the 'Roll' plugin in QGIS")
#     vl.setMetadata(vlMeta)                                                      # insert object into layer

#     # Configure label settings; start with the label expression
#     settings = QgsPalLayerSettings()                                            # See: https://qgis.org/pyqgis/3.22/core/QgsPalLayerSettings.html#qgis.core.QgsPalLayerSettings.minimumScale
#     settings.fieldName = """("line" || '\n' || "stake")"""
#     settings.isExpression = True

#     # define minimum/maximum scale for labels
#     settings.minimumScale = 5000
#     settings.maximumScale = 50
#     settings.scaleVisibility = True

#     # configure label placement
#     # See:https://api.qgis.org/api/3.14/classQgsPalLayerSettings.html#a893793dc9760fd026d22e9d83f96c109a676921ebac6f80a2d7805e7c04876993
#     settings.placement = QgsPalLayerSettings.Placement.OrderedPositionsAroundPoint
#     settings.offsetType = QgsPalLayerSettings.FromSymbolBounds
#     settings.dist = -1
#     # settings.quadOffset = QgsPalLayerSettings.QuadrantPosition.QuadrantAboveRight             # Quadrant position: QuadrantAboveLeft = 0; QuadrantAbove = 1,...
#     # settings.xOffset = 1.0                                                                    # Offset X
#     # settings.yOffset = 0.0                                                                    # Offset Y

#     # create a new text format
#     textFormat = QgsTextFormat()
#     textFormat.setSize(10)
#     settings.setFormat(textFormat)

#     # create a SimpleLabeling layer, and add labels to vector layer
#     labels = QgsVectorLayerSimpleLabeling(settings)
#     vl.setLabelsEnabled(True)
#     vl.setLabeling(labels)

#     vl.triggerRepaint()

#     return True


# For categorized QgsMarkerSymbols, please see:
# See: https://gis.stackexchange.com/questions/388010/assigning-qgscategorizedsymbolrenderer-spectral-ramp-to-multipolygon
# See: https://stackoverflow.com/questions/59314446/how-do-i-create-a-categorized-symbology-in-qgis-with-pyqt-programmatically


def exportPointLayerToQgis(layerName, spsRecords, crs=None, source=True) -> QgsVectorLayer:

    if crs is None:
        return None

    vl = QgsVectorLayer('Point', layerName, 'memory')
    pr = vl.dataProvider()
    pr.addAttributes(
        [
            # length and precision of fields have been tuned towards shapefile properties
            QgsField('line', QVariant.Double, len=23, prec=1),
            QgsField('stake', QVariant.Double, len=23, prec=1),
            QgsField('index', QVariant.Int, len=10),
            QgsField('code', QVariant.String, len=4),
            QgsField('depth', QVariant.Double, len=10, prec=1),
            QgsField('elev', QVariant.Double, len=23, prec=1),
            QgsField('inuse', QVariant.Int, len=10),
        ]
    )
    vl.updateFields()
    vl.setCrs(crs)

    featureList = []

    try:
        record = spsRecords[0]
        u = int(record['InUse'])                                                # this will throw an excption if InUse isn't available

        for record in spsRecords:                                               # no exception, so do this
            # account for numpy float32 format, and the unicode string format
            l = float(record['Line'])
            p = float(record['Point'])
            i = int(record['Index'])
            c = str(record['Code'])
            x = float(record['East'])
            y = float(record['North'])
            d = float(record['Depth'])
            z = float(record['Elev'])
            u = int(record['InUse'])

            f = QgsFeature()
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            f.setAttributes([l, p, i, c, d, z, u])
            featureList.append(f)
    except ValueError:                                                          # exception; set inuse = 1 for all features
        for record in spsRecords:
            # account for numpy float32 format, and the unicode string format
            l = float(record['Line'])
            p = float(record['Point'])
            i = int(record['Index'])
            c = str(record['Code'])
            x = float(record['East'])
            y = float(record['North'])
            d = float(record['Depth'])
            z = float(record['Elev'])
            u = 1                                                               # if it wasn't there before; put it at 1 (True)

            f = QgsFeature()
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            f.setAttributes([l, p, i, c, d, z, u])
            featureList.append(f)

    pr.addFeatures(featureList)
    vl.updateExtents()

    # select src/rec symbol
    if source:
        liveSymbol = QgsMarkerSymbol.createSimple(
            {
                'name': 'circle',
                'color': '255,0,0,255',
                'outline_color': '35,35,35,255',
                'outline_width': '0.5',
                'outline_width_unit': 'RenderMetersInMapUnits',
                'size': '20',
                'size_unit': 'RenderMetersInMapUnits',
            }
        )
        liveSymbol.setOpacity(0.45)                                             # opacity apparently not allowed in constructor properties ?!?

        deadSymbol = QgsMarkerSymbol.createSimple(
            {
                'name': 'circle',
                'color': '255,237,237,255',
                'outline_color': '35,35,35,255',
                'outline_width': '0.5',
                'outline_width_unit': 'RenderMetersInMapUnits',
                'size': '20',
                'size_unit': 'RenderMetersInMapUnits',
            }
        )
        deadSymbol.setOpacity(0.45)                                             # opacity apparently not allowed in constructor properties ?!?
    else:
        liveSymbol = QgsMarkerSymbol.createSimple(
            {
                'name': 'circle',
                'color': '0,0,255,255',
                'outline_color': '35,35,35,255',
                'outline_width': '0.5',
                'outline_width_unit': 'RenderMetersInMapUnits',
                'size': '20',
                'size_unit': 'RenderMetersInMapUnits',
            }
        )
        liveSymbol.setOpacity(0.45)                                             # opacity apparently not allowed in constructor properties ?!?

        deadSymbol = QgsMarkerSymbol.createSimple(
            {
                'name': 'circle',
                'color': '237,237,255,255',
                'outline_color': '35,35,35,255',
                'outline_width': '0.5',
                'outline_width_unit': 'RenderMetersInMapUnits',
                'size': '20',
                'size_unit': 'RenderMetersInMapUnits',
            }
        )
        deadSymbol.setOpacity(0.45)                                             # opacity apparently not allowed in constructor properties ?!?

    cDead = QgsRendererCategory(0, deadSymbol, 'idle', True)
    cLive = QgsRendererCategory(1, liveSymbol, 'inuse', True)
    renderer = QgsCategorizedSymbolRenderer('inuse', [cDead, cLive])

    vl.setRenderer(renderer)

    # update meta data through metadata() object
    metaId = uuid.uuid4()                                                       # create a UUID object
    vlMeta = vl.metadata()                                                      # derive object from layer
    vlMeta.setIdentifier(str(metaId))                                           # turn UUID into string, to make it our ID string
    if source:
        vlMeta.setParentIdentifier('Roll Src')                                  # for easy layer verification from plugin
    else:
        vlMeta.setParentIdentifier('Roll Rec')                                  # for easy layer verification from plugin
    vlMeta.setTitle(layerName)                                                  # in case layer is renamed
    vlMeta.setType('dataset')                                                   # this is the default value, if you don't update the metadata
    vlMeta.setLanguage('Python')                                                # not very relevant
    vlMeta.setAbstract("Point vector-layer created by the 'Roll' plugin in QGIS")
    vl.setMetadata(vlMeta)                                                      # insert object into layer

    # Configure label settings; start with the label expression
    settings = QgsPalLayerSettings()                                            # See: https://qgis.org/pyqgis/3.22/core/QgsPalLayerSettings.html#qgis.core.QgsPalLayerSettings.minimumScale
    settings.fieldName = """("line" || '\n' || "stake")"""
    settings.isExpression = True

    # define minimum/maximum scale for labels
    settings.minimumScale = 5000
    settings.maximumScale = 50
    settings.scaleVisibility = True

    # configure label placement
    # See:https://api.qgis.org/api/3.14/classQgsPalLayerSettings.html#a893793dc9760fd026d22e9d83f96c109a676921ebac6f80a2d7805e7c04876993
    settings.placement = QgsPalLayerSettings.Placement.OrderedPositionsAroundPoint
    settings.offsetType = QgsPalLayerSettings.FromSymbolBounds
    settings.dist = -1
    # settings.quadOffset = QgsPalLayerSettings.QuadrantPosition.QuadrantAboveRight             # Quadrant position: QuadrantAboveLeft = 0; QuadrantAbove = 1,...
    # settings.xOffset = 1.0                                                                    # Offset X
    # settings.yOffset = 0.0                                                                    # Offset Y

    # create a new text format
    textFormat = QgsTextFormat()
    textFormat.setSize(10)
    settings.setFormat(textFormat)

    # create a SimpleLabeling layer, and add labels to vector layer
    labels = QgsVectorLayerSimpleLabeling(settings)
    vl.setLabelsEnabled(True)
    vl.setLabeling(labels)

    vl.triggerRepaint()
    QgsProject.instance().addMapLayer(vl)

    return vl

    ################################### using rules to display labels

    # settings = QgsPalLayerSettings()
    # format = QgsTextFormat()
    # format.setFont(QFont('Arial', 8))
    # format.setColor(QColor('Black'))

    # buffer = QgsTextBufferSettings()
    # buffer.setEnabled(True)
    # buffer.setSize(0.50)
    # buffer.setColor(QColor('grey'))
    # # format.setBuffer(buffer)

    # settings.setFormat(format)
    # settings.fieldName = """concat("line", '\n', "stake")"""
    # settings.fieldName ="""("line" ||  '\n'  ||   "stake")"""
    # settings.isExpression = True

    # #create and append a new rule
    # root = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    # # See: https://qgis.org/pyqgis/master/core/QgsRuleBasedLabeling.html
    # # rule = QgsRuleBasedLabeling.Rule(settings)
    # rule = QgsRuleBasedLabeling.Rule(settings, maximumScale = 50, minimumScale = 5000, filterExp = '', description = '', elseRule = False)
    # rule.setDescription('scale based labeling')
    # # rule.setFilterExpression('myExpression')
    # root.appendChild(rule)

    # Apply label configuration
    # rules = QgsRuleBasedLabeling(root)
    # vl.setLabeling(rules)

    # show the changes
    # vl.triggerRepaint()


def exportSurveyOutlineToQgis(layerName, survey) -> bool:
    # See: https://gis.stackexchange.com/questions/373393/creating-polygon-and-adding-it-as-new-layer-with-pyqgis
    # See: https://gis.stackexchange.com/questions/396505/creating-rectangles-from-csv-coordinates-via-python-console-in-qgis

    if survey.crs is None:
        return False

    if not layerName:
        QMessageBox.warning(None, "Can't export polygons to QGIS", 'Please save survey first, to get a valid name for vector layers')
        return False

    transform = QTransform()                                                    # empty (unit) transform
    transform = survey.glbTransform                                             # get global coordinate conversion transform

    # Configure label settings; start with the label expression
    settings = QgsPalLayerSettings()                                            # See: https://qgis.org/pyqgis/3.22/core/QgsPalLayerSettings.html#qgis.core.QgsPalLayerSettings.minimumScale
    settings.fieldName = """("name" || '\n' || "block")"""
    settings.isExpression = True

    # define minimum/maximum scale for labels
    settings.minimumScale = 200000
    settings.maximumScale = 50
    settings.scaleVisibility = True

    # configure label placement
    # See:https://api.qgis.org/api/3.14/classQgsPalLayerSettings.html#a893793dc9760fd026d22e9d83f96c109a676921ebac6f80a2d7805e7c04876993
    settings.placement = QgsPalLayerSettings.Placement.Free

    # create a new text format
    textFormat = QgsTextFormat()
    textFormat.setSize(10)
    settings.setFormat(textFormat)

    for nBlock, block in enumerate(survey.blockList):                           # iterate over all blocks
        strBlock = f'block-{nBlock + 1}'
        for index in range(3):                                                  # range is used to iterate over rec, cmp and src
            name = ''
            props = {}
            attrib = []
            rect = QRectF()

            if index == 0:
                name = f'{layerName}-rec-edge-b{nBlock+1}'
                props = {'color': 'cyan', 'outline_color': 'black'}
                attrib = ['Rec boundary', strBlock]
                rect = block.recBoundingRect
            elif index == 1:
                name = f'{layerName}-cmp-edge-b{nBlock+1}'
                props = {'color': 'green', 'outline_color': 'black'}
                attrib = ['Cmp boundary', strBlock]
                rect = block.cmpBoundingRect
            elif index == 2:
                name = f'{layerName}-src-edge-b{nBlock+1}'
                props = {'color': 'red', 'outline_color': 'black'}
                attrib = ['Src boundary', strBlock]
                rect = block.srcBoundingRect

            vl = QgsVectorLayer('Polygon', name, 'memory')
            pr = vl.dataProvider()
            pr.addAttributes(
                [
                    QgsField('name', QVariant.String, len=32),
                    QgsField('block', QVariant.String, len=32),
                ]
            )
            vl.updateFields()
            vl.setCrs(survey.crs)

            symbol = QgsFillSymbol.createSimple(props)
            symbol.setOpacity(0.35)                                             # opacity not allowed in constructor properties ?!
            vl.renderer().setSymbol(symbol)

            polygon = QPolygonF(rect)
            polygon = transform.map(polygon)
            polyQgs = QgsGeometry.fromQPolygonF(polygon)

            feature = QgsFeature()
            feature.setGeometry(polyQgs)
            feature.setAttributes(attrib)

            pr.addFeature(feature)

            # update meta data through metadata() object
            metaId = uuid.uuid4()                                               # create a UUID object
            vlMeta = vl.metadata()                                              # derive object from layer
            vlMeta.setIdentifier(str(metaId))                                   # turn UUID into string, to make it our ID string
            vlMeta.setParentIdentifier('Roll')                                  # for easy layer verification from plugin
            vlMeta.setTitle(layerName)                                          # in case layer is renamed
            vlMeta.setType('edge of dataset')                                   # this is the default value, if you don't update the metadata
            vlMeta.setLanguage('Python')                                        # not very relevant
            vlMeta.setAbstract("Polygon vector-layer created by the 'Roll' plugin in QGIS")
            vl.setMetadata(vlMeta)                                              # insert object into layer

            labels = QgsVectorLayerSimpleLabeling(settings)                     # add labels to vector layer
            vl.setLabelsEnabled(True)
            vl.setLabeling(labels)
            vl.updateExtents()
            vl.triggerRepaint()
            QgsProject.instance().addMapLayer(vl)

    if survey.output.rctOutput.isValid():                                       # do the bin extent last
        name = f'{layerName}-bin-edge-all'
        props = {'color': 'grey', 'outline_color': 'black'}
        attrib = ['Binning boundary', 'all blocks']
        rect = survey.output.rctOutput

        vl = QgsVectorLayer('Polygon', name, 'memory')
        pr = vl.dataProvider()
        pr.addAttributes(
            [
                QgsField('name', QVariant.String, len=32),
                QgsField('block', QVariant.String, len=32),
            ]
        )
        vl.updateFields()
        vl.setCrs(survey.crs)

        symbol = QgsFillSymbol.createSimple({'color': 'grey', 'outline_color': 'black'})
        symbol.setOpacity(0.35)                                                 # opacity not allowed in constructor properties ?!
        vl.renderer().setSymbol(symbol)

        polygon = QPolygonF(rect)
        polygon = transform.map(polygon)
        polyQgs = QgsGeometry.fromQPolygonF(polygon)

        feature = QgsFeature()
        feature.setGeometry(polyQgs)
        feature.setAttributes(['Binning boundary', 'all blocks'])

        pr.addFeature(feature)

        # update meta data through metadata() object
        metaId = uuid.uuid4()                                                   # create a UUID object
        vlMeta = vl.metadata()                                                  # derive object from layer
        vlMeta.setIdentifier(str(metaId))                                       # turn UUID into string, to make it our ID string
        vlMeta.setParentIdentifier('Roll')                                      # for easy layer verification from plugin
        vlMeta.setTitle(layerName)                                              # in case layer is renamed
        vlMeta.setType('edge of dataset')                                       # this is the default value, if you don't update the metadata
        vlMeta.setLanguage('Python')                                            # not very relevant
        vlMeta.setAbstract("Polygon vector-layer created by the 'Roll' plugin in QGIS")
        vl.setMetadata(vlMeta)                                                  # insert object into layer

        labelsBin = QgsVectorLayerSimpleLabeling(settings)                      # add labels to vector layer
        vl.setLabelsEnabled(True)
        vl.setLabeling(labelsBin)
        vl.updateExtents()
        vl.triggerRepaint()
        QgsProject.instance().addMapLayer(vl)

    return True


def CreateQgisRasterLayer(fileName, data, survey) -> str:

    # See: https://gis.stackexchange.com/questions/418517/rotation-of-a-spatial-grid-by-an-angle-around-a-pivot-with-python-gdal-or-raster
    # See: https://gis.stackexchange.com/questions/408386/rotating-raster-using-python/408396#408396 to rotate a raster in GDAL

    # See: https://www.gislounge.com/symbolizing-vector-and-raster-layers-qgis-python-programming-cookbook/
    # See: https://github.com/qgis/QGIS-Documentation/blob/master/docs/pyqgis_developer_cookbook/raster.rst
    # See: https://opensourceoptions.com/blog/loading-and-symbolizing-raster-layers/?utm_content=cmp-true
    # See: https://python.hotexamples.com/examples/qgis.core/QgsSingleBandPseudoColorRenderer/-/python-qgssinglebandpseudocolorrenderer-class-examples.html
    # See: https://gis.stackexchange.com/questions/118775/assigning-color-ramp-using-pyqgis
    # See: https://gis.stackexchange.com/questions/356851/setting-the-visual-style-of-a-raster-from-python-console-in-qgis
    # See: https://docs.qgis.org/3.28/en/docs/pyqgis_developer_cookbook/raster.html?highlight=qgssinglebandpseudocolorrenderer

    fn, _ = QFileDialog.getSaveFileName(
        # the main window  # caption  # start directory + filename + extension  # file extensions  # (options -> not used)
        None,
        'Save georeferenced-TIFF file as...',
        fileName,
        'GeoTIFF file format (*.tif);;All files (*.*)',
    )

    if not fn:
        return None

    extension = '.tif'                                                          # default extension value
    if not fn.lower().endswith(extension):                                      # make sure file extension is okay
        fn += extension                                                         # just add the file extension

    if isFileInUse(fn):
        QMessageBox.warning(None, 'Cannot create file', f"File '{fn}' is in use by another process")
        return None

    tl = survey.glbTransform.map(survey.output.rctOutput.topLeft())             # we need global positions

    dx = survey.grid.binSize.x() * survey.grid.scale.x()                        # allow for scaling in global coords
    dy = survey.grid.binSize.y() * survey.grid.scale.y()                        # allow also for non-square bin sizes
    azi = survey.grid.angle
    crs = survey.crs.toWkt()
    # crs = survey.crs.toProj()                                                 # tested during debugging; has no impact !
    # crs = survey.crs.authid()

    data = np.transpose(data)                                                   # put data in right order for rasterio
    height = data.shape[0]                                                      # shape[0] contains width of array
    width = data.shape[1]                                                       # shape[1] contains height of array

    # See: https://github.com/rasterio/affine for affine matrix operations

    rioTransform = rio.Affine.translation(tl.x(), tl.y()) * rio.Affine.rotation(azi) * rio.Affine.scale(dx, dy)

    with rio.open(
        fn,
        mode='w',
        driver='GTiff',
        height=height,
        width=width,
        count=1,
        # nodata=-9999,
        nodata=0,
        dtype=data.dtype,
        crs=crs,
        transform=rioTransform,
    ) as new_dataset:
        new_dataset.write(data, 1)

    return fn


def ExportRasterLayerToQgis(fileName, data, survey) -> str:
    fileName = CreateQgisRasterLayer(fileName, data, survey)                        # create the raster file first

    if fileName:
        fileInfo = QFileInfo(fileName)
        path = fileInfo.filePath()
        baseName = fileInfo.completeBaseName()

        rl = QgsRasterLayer(path, baseName)

        # update meta data through metadata() object
        metaId = uuid.uuid4()                                                       # create a UUID object
        rlMeta = rl.metadata()                                                      # derive object from layer
        rlMeta.setIdentifier(str(metaId))                                           # turn UUID into string, to make it our ID string
        rlMeta.setParentIdentifier('Roll')                                          # for easy layer verification from plugin
        rlMeta.setTitle(baseName)                                                   # in case layer is renamed
        rlMeta.setType('dataset')                                                   # this is the default value, if you don't update the metadata
        rlMeta.setLanguage('Python')                                                # not very relevant
        rlMeta.setAbstract("Raster-layer created by the 'Roll' plugin in QGIS")
        rl.setMetadata(rlMeta)                                                      # insert object into layer

        myStyle = QgsStyle().defaultStyle()                                         # extract list of default styles in QGIS
        defaultColorRampNames = myStyle.colorRampNames()                            # extract list of olor ramp names
        colorRamp = myStyle.colorRamp(defaultColorRampNames[8])                     # create a colour ramp based on style nr. 8

        fcn = QgsColorRampShader()
        fcn.setColorRampType(QgsColorRampShader.Interpolated)

        shader = QgsRasterShader()
        shader.setRasterShaderFunction(fcn)

        renderer = QgsSingleBandPseudoColorRenderer(rl.dataProvider(), 1, shader)
        minData = max(data.min(), 0)                                                # protect against min == -inf
        maxData = data.max()
        if minData == data.max():                                                   # protect against min == max
            minData = 0
            data.fill(5)
            maxData = 10.0

        renderer.setClassificationMin(minData)                                      # minimum from numpy array
        renderer.setClassificationMax(maxData)                                      # maximum from numpy array
        renderer.setOpacity(0.6)                                                    # apply transparency to renderer

        # Create the shader with the parameters
        # See: https://api.qgis.org/api/classQgsSingleBandPseudoColorRenderer.html#a1778d3596d8d46451fe466bf2b657c60
        renderer.createShader(colorRamp, QgsColorRampShader.Interpolated, QgsColorRampShader.Continuous)

        rl.setRenderer(renderer)
        rl.triggerRepaint()
        QgsProject.instance().addMapLayer(rl)

    return fileName


def readQgisPointLayer(layerId, selectionField=''):

    layer = QgsProject.instance().mapLayer(layerId)

    nFeatures = layer.featureCount()
    print('Nr features: ', nFeatures)

    if nFeatures == 0:
        return None

    pointArray = np.zeros(shape=(nFeatures), dtype=pntType1)

    vlMeta = layer.metadata()                                               # get meta data
    parentId = vlMeta.parentIdentifier()                                    # for easy layer verification from plugin
    print('Parent ID: ', parentId)

    nRecord = 0
    nErrors = 0
    features = layer.getFeatures()
    for feature in features:
        # retrieve every feature with its geometry and attributes

        try:
            geom = feature.geometry()
            point = geom.asPoint()

            line = feature['line']
            stake = feature['stake']
            index = feature['index']
            code = feature['code']
            depth = feature['depth']
            east = point.x()
            north = point.y()
            elev = feature['elev']

            try:
                inuse = feature['inuse']
            except KeyError:                                                    # inuse field does not exist; make it True by default
                inuse = True

            # dtype=pntType1
            # ('Line', 'f4'),  # F10.2
            # ('Point', 'f4'),  # F10.2
            # ('Index', 'i4'),  # I1
            # ('Code', 'U2'),  # A2
            # ('Depth', 'f4'),  # I4
            # ('East', 'f4'),  # F9.1
            # ('North', 'f4'),  # F10.1
            # ('Elev', 'f4'),  # F6.1
            # ('Uniq', 'i4'),  # check if record is unique
            # ('InXps', 'i4'),  # check if record is orphan
            # ('InUse', 'i4'),  # check if record is in use
            # ('LocX', 'f4'),  # F9.1
            # ('LocY', 'f4'),  # F10.1

            if selectionField == '':
                used = inuse
            else:
                used = feature[selectionField]

            record = (line, stake, index, code, depth, east, north, elev, 1, 1, inuse, 0.0, 0.0)

            pointArray[nRecord] = record
            nRecord += 1

        except ValueError:
            print('Bad Feature ID: ', feature.id())
            nErrors += 1

        except KeyError:
            print('Required fields are missing from layer')
            return None

    if nErrors > 0:
        pointArray.resize(nFeatures - nErrors, refcheck=False)

    return pointArray


# One way to create a spatial index for a layer is to use the "Create spatial index" tool in the "Vector general" section of the processing toolbox.
# vector --> general --> Create spatial index
# processing.run
#     (
#         "native:createspatialindex",
#         {
#             'INPUT':'D:/Roll/Orthogonal_002-rec-data.shp|layername=Orthogonal_002-rec-data'
#         }
#     )

# once the spatial index is made; the following routine is supposed to run faster.

# Vector --> Research Tools --> Select by Location
# processing.run
# 	(
# 		"native:selectbylocation",
# 		{
# 			'INPUT':'D:/Roll/EBN/Orthogonal_002-rec-data.shp|layername=Orthogonal_002-rec-data',
# 			'PREDICATE':[0],
# 			'INTERSECT':'D:/Roll/EBN/Core_area_with_1500m_rim_outline.shp|layername=Core_area_with_1500m_rim_outline',
# 			'METHOD':0
# 		}
# 	)


# From: https://gdal.org/tutorials/geotransforms_tut.html
# GT(0) x-coordinate of the upper-left corner of the upper-left pixel.
# GT(1) w-e pixel resolution / pixel width.
# GT(2) row rotation (typically zero).
# GT(3) y-coordinate of the upper-left corner of the upper-left pixel.
# GT(4) column rotation (typically zero).
# GT(5) n-s pixel resolution / pixel height (negative value for a north-up image).

# Transformation from image coordinate space to georeferenced coordinate space:

# X_geo = GT(0) + X_pixel * GT(1) + Y_line * GT(2)
# Y_geo = GT(3) + X_pixel * GT(4) + Y_line * GT(5)

# Note that the pixel/line coordinates in the above are from (0.0, 0.0) at the top left corner of the top left pixel
# to (width_in_pixels, height_in_pixels) at the bottom right corner of the bottom right pixel.
# The pixel/line location of the center of the top left pixel would therefore be (0.5, 0.5).

# In case of north up images:
# GT(2), GT(4) coefficients are zero.
# GT(1), GT(5) is the pixel size.
# GT(0), GT(3) position is the top left corner of the top left pixel of the raster.

# From: https://rasterio.readthedocs.io/en/stable/topics/georeferencing.html

# Georeferencing

# There are two parts to the georeferencing of raster datasets:
# the definition of the local, regional, or global system in which a raster’s pixels are located;
# and the parameters by which pixel coordinates are transformed into coordinates in that system.

# Coordinate Reference System

# The coordinate reference system of a dataset is accessed from its crs attribute.

# import rasterio
# src = rasterio.open('tests/data/RGB.byte.tif')
# src.crs
# CRS({'init': 'epsg:32618'})

# Rasterio follows pyproj and uses PROJ.4 syntax in dict form as its native CRS syntax. If you want a WKT representation of the CRS, see the CRS class’s wkt attribute.

# src.crs.wkt
# 'PROJCS["WGS 84 / UTM zone 18N",GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],
# AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],
# AUTHORITY["EPSG","4326"]],PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",-75],
# PARAMETER["scale_factor",0.9996],PARAMETER["false_easting",500000],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],
# AXIS["Easting",EAST],AXIS["Northing",NORTH],AUTHORITY["EPSG","32618"]]'

# When opening a new file for writing, you may also use a CRS string as an argument.

# profile = {'driver': 'GTiff', 'height': 100, 'width': 100, 'count': 1, 'dtype': rasterio.uint8}
# with rasterio.open('/tmp/foo.tif', 'w', crs='EPSG:3857', **profile) as dst:
#     pass # write data to this Web Mercator projection dataset.

# Coordinate Transformation

# This section describes the three primary kinds of georefencing metadata supported by rasterio.

# Affine

# A dataset’s pixel coordinate system has its origin at the “upper left” (imagine it displayed on your screen).
# Column index increases to the right, and row index increases downward.
# The mapping of these coordinates to “world” coordinates in the dataset’s reference system is typically done with an affine transformation matrix.

# src.transform
# Affine(300.0379266750948, 0.0, 101985.0,
#        0.0, -300.041782729805, 2826915.0)

# The Affine object is a named tuple with elements a, b, c, d, e, f corresponding to the elements in the matrix equation below,
# in which a pixel’s image coordinates are x, y and its world coordinates are x', y'.:

# | x' |   | a b c | | x |
# | y' | = | d e f | | y |
# | 1  |   | 0 0 1 | | 1 |

# The Affine class has some useful properties and methods described at https://github.com/sgillies/affine.

# Some more useful stuff here:
# See: https://www.e-education.psu.edu/geog489/node/2296
# See: https://docs.qgis.org/3.28/en/docs/pyqgis_developer_cookbook/vector.html#id2
# See: https://docs.qgis.org/3.28/en/docs/pyqgis_developer_cookbook/vector.html#from-an-instance-of-qgsvectorlayer
# See: https://gis.stackexchange.com/questions/382702/changing-layer-id-in-qgis
# See: https://www.mkrgeo-blog.com/liaison/qgis-tutorials/identify-results/
# See: https://gis.stackexchange.com/questions/138180/calculating-unique-id-value-for-a-field-in-qgis-using-python
# See: https://gis.stackexchange.com/questions/436391/python-editing-of-qgis-layer-metadata on how to edit meta data
# See: https://stackoverflow.com/questions/1210458/how-can-i-generate-a-unique-id-in-python to create a unique ID
# See: https://docs.python.org/3/library/uuid.html

# print("properties", vl.renderer().symbol().symbolLayers()[0].properties())
# See: https://docs.qgis.org/3.28/en/docs/pyqgis_developer_cookbook/vector.html#id19
# print(symbol.symbolLayers()[0].properties())
# {	'angle': '0',
# 	'cap_style': 'square',
# 	'color': '255,0,0,255',
# 	'horizontal_anchor_point': '1',
# 	'joinstyle': 'bevel',
# 	'name': 'circle',
# 	'offset': '0,0',
# 	'offset_map_unit_scale': '3x:0,0,0,0,0,0',
# 	'offset_unit': 'RenderMetersInMapUnits',
# 	'outline_color': '35,35,35,255',
# 	'outline_style': 'solid',
# 	'outline_width': '0.4',
# 	'outline_width_map_unit_scale': '3x:0,0,0,0,0,0',
# 	'outline_width_unit': 'RenderMetersInMapUnits',
# 	'scale_method': 'diameter',
# 	'size': '20',
# 	'size_map_unit_scale': '3x:0,0,0,0,0,0',
# 	'size_unit': 'RenderMetersInMapUnits',
# 	'vertical_anchor_point': '1'}

# #set labels
# palyr = QgsPalLayerSettings()
# palyr.fieldName = "Text"
# palyr.placement = QgsPalLayerSettings.OverPoint
# palyr.scaleVisibility = True
# palyr.minimumScale = 750
# labels = QgsVectorLayerSimpleLabeling(palyr)
# vlayer.setLabelsEnabled(True)
# vlayer.setLabeling(labels)
# vlayer.triggerRepaint()

# # Define layer object
# layer = QgsProject().instance().mapLayersByName('Name_of_your_layer')[0]

# buffer = QgsTextBufferSettings()
# buffer.setEnabled(True)
# buffer.setSize(0.50)
# buffer.setColor(QColor('grey'))

# format = QgsTextFormat()
# format.setFont(QFont('Arial', 8))
# format.setColor(QColor('Black'))
# format.setBuffer(buffer)

# settings = QgsPalLayerSettings()
# settings.setFormat(format)
# settings.fieldName = """concat("field_1", ' ', "Field_2")"""
# settings.isExpression = True

# labels = QgsVectorLayerSimpleLabeling(settings)
# layer.setLabelsEnabled(True)
# layer.setLabeling(labels)
# layer.triggerRepaint()

############################################## ways to get help when you get lost

# From the console get help by using
#   print (type(variable))
#   print(dir(variable))
#   print (help(variable))

# See for instance information below on the vector layer and its members

# Python Console
# Use iface to access QGIS API interface or type help(iface) for more info
# Security warning: typing commands from an untrusted source can harm your computer

# layer = iface.activeLayer()
# print (layer.renderer().symbol().symbolLayers()[0].properties())

# for the point layers
# {'angle': '0', 'cap_style': 'square', 'color': '0,0,255,255', 'horizontal_anchor_point': '1', 'joinstyle': 'bevel', 'name': 'circle', 'offset': '0,0',
# 'offset_map_unit_scale': '3x:0,0,0,0,0,0', 'offset_unit': 'RenderMetersInMapUnits', 'outline_color': '35,35,35,255', 'outline_style': 'solid', 'outline_width': '0',
# 'outline_width_map_unit_scale': '3x:0,0,0,0,0,0', 'outline_width_unit': 'RenderMetersInMapUnits', 'scale_method': 'diameter', 'size': '20',
# 'size_map_unit_scale': '3x:0,0,0,0,0,0', 'size_unit': 'RenderMetersInMapUnits', 'vertical_anchor_point': '1'}

# for the polygon layers
# {'angle': '0', 'cap_style': 'square', 'color': '0,0,255,255', 'horizontal_anchor_point': '1', 'joinstyle': 'bevel', 'name': 'circle', 'offset': '0,0',
# 'offset_map_unit_scale': '3x:0,0,0,0,0,0', 'offset_unit': 'MM',                     'outline_color': '35,35,35,255', 'outline_style': 'solid', 'outline_width': '0.5',
# 'outline_width_map_unit_scale': '3x:0,0,0,0,0,0', 'outline_width_unit': 'RenderMetersInMapUnits', 'scale_method': 'diameter', 'size': '20',
# 'size_map_unit_scale': '3x:0,0,0,0,0,0', 'size_unit': 'RenderMetersInMapUnits', 'vertical_anchor_point': '1'}

# print (type(layer))
# <class 'qgis._core.QgsVectorLayer'>

# print (dir(layer))
# ['Actions',
# 'AddToSelection',
# 'AllStyleCategories',
# 'AnnotationLayer',
# 'AttributeTable',
# 'Cross',
# 'CustomProperties',
# 'DeleteContext',
# 'Diagrams',
# 'EditFailed',
# 'EditResult',
# 'Elevation',
# 'EmptyGeometry',
# 'FastInsert',
# 'FeatureAvailability',
# 'FeaturesAvailable',
# 'FeaturesMaybeAvailable',
# 'FetchFeatureFailed',
# 'Fields',
# 'Flag',
# 'FlagDontResolveLayers',
# 'FlagForceReadOnly',
# 'FlagReadExtentFromXml',
# 'FlagTrustLayerMetadata',
# 'Flags',
# 'Forms',
# 'GeometryOptions',
# 'GroupLayer',
# 'Identifiable',
# 'IntersectSelection',
# 'InvalidLayer',
# 'Labeling',
# 'LayerConfiguration',
# 'LayerFlag',
# 'LayerFlags',
# 'LayerOptions',
# 'LayerType',
# 'Legend',
# 'MapTips',
# 'MeshLayer',
# 'Metadata',
# 'NoFeaturesAvailable',
# 'NoMarker',
# 'Notes',
# 'PluginLayer',
# 'PointCloudLayer',
# 'Private',
# 'PropertyType',
# 'RasterLayer',
# 'ReadFlag',
# 'ReadFlags',
# 'RegeneratePrimaryKey',
# 'Relations',
# 'Removable',
# 'RemoveFromSelection',
# 'Rendering',
# 'RollBackOnErrors',
# 'Searchable',
# 'SelectBehavior',
# 'SemiTransparentCircle',
# 'SetSelection',
# 'SinkFlag',
# 'SinkFlags',
# 'SpatialIndexNotPresent',
# 'SpatialIndexPresence',
# 'SpatialIndexPresent',
# 'SpatialIndexUnknown',
# 'Style',
# 'StyleCategories',
# 'StyleCategory',
# 'Success',
# 'Symbology',
# 'Symbology3D',
# 'Temporal',
# 'VectorLayer',
# 'VectorTileLayer',
# 'VertexMarkerType',
# '__bool__',
# '__class__',
# '__delattr__',
# '__dict__',
# '__dir__',
# '__doc__',
# '__eq__',
# '__format__',
# '__ge__',
# '__getattr__',
# '__getattribute__',
# '__gt__',
# '__hash__',
# '__init__',
# '__init_subclass__',
# '__le__',
# '__len__',
# '__lt__',
# '__module__',
# '__ne__',
# '__new__',
# '__reduce__',
# '__reduce_ex__',
# '__repr__',
# '__setattr__',
# '__sizeof__',
# '__str__',
# '__subclasshook__',
# '__weakref__',
# 'abstract',
# 'accept',
# 'actions',
# 'addAttribute',
# 'addCurvedPart',
# 'addCurvedRing',
# 'addExpressionField',
# 'addFeature',
# 'addFeatureRendererGenerator',
# 'addFeatures',
# 'addJoin',
# 'addPart',
# 'addPartV2',
# 'addRing',
# 'addTopologicalPoints',
# 'afterCommitChanges',
# 'afterRollBack',
# 'aggregate',
# 'allFeatureIds',
# 'allowCommitChanged',
# 'appendError',
# 'attributeAdded',
# 'attributeAlias',
# 'attributeAliases',
# 'attributeDeleted',
# 'attributeDisplayName',
# 'attributeList',
# 'attributeTableConfig',
# 'attributeValueChanged',
# 'attribution',
# 'attributionUrl',
# 'autoRefreshInterval',
# 'autoRefreshIntervalChanged',
# 'auxiliaryLayer',
# 'beforeAddingExpressionField',
# 'beforeCommitChanges',
# 'beforeEditingStarted',
# 'beforeModifiedCheck',
# 'beforeRemovingExpressionField',
# 'beforeResolveReferences',
# 'beforeRollBack',
# 'beginEditCommand',
# 'blendMode',
# 'blendModeChanged',
# 'blockSignals',
# 'boundingBoxOfSelected',
# 'capabilitiesString',
# 'changeAttributeValue',
# 'changeAttributeValues',
# 'changeGeometry',
# 'childEvent',
# 'children',
# 'clone',
# 'commitChanges',
# 'commitErrors',
# 'committedAttributeValuesChanges',
# 'committedAttributesAdded',
# 'committedAttributesDeleted',
# 'committedFeaturesAdded',
# 'committedFeaturesRemoved',
# 'committedGeometriesChanges',
# 'conditionalStyles',
# 'configChanged',
# 'connectNotify',
# 'constraintDescription',
# 'constraintExpression',
# 'countSymbolFeatures',
# 'createExpressionContext',
# 'createExpressionContextScope',
# 'createMapRenderer',
# 'createProfileGenerator',
# 'crs',
# 'crsChanged',
# 'customEvent',
# 'customProperties',
# 'customProperty',
# 'customPropertyChanged',
# 'customPropertyKeys',
# 'dataChanged',
# 'dataComment',
# 'dataProvider',
# 'dataSourceChanged',
# 'dataUrl',
# 'dataUrlFormat',
# 'decodedSource',
# 'defaultValue',
# 'defaultValueDefinition',
# 'deleteAttribute',
# 'deleteAttributes',
# 'deleteFeature',
# 'deleteFeatures',
# 'deleteLater',
# 'deleteSelectedFeatures',
# 'deleteStyleFromDatabase',
# 'deleteVertex',
# 'dependencies',
# 'dependenciesChanged',
# 'deselect',
# 'destroyEditCommand',
# 'destroyed',
# 'diagramLayerSettings',
# 'diagramRenderer',
# 'diagramsEnabled',
# 'disconnect',
# 'disconnectNotify',
# 'displayExpression',
# 'displayExpressionChanged',
# 'displayField',
# 'drawVertexMarker',
# 'dumpObjectInfo',
# 'dumpObjectTree',
# 'dynamicPropertyNames',
# 'editBuffer',
# 'editCommandDestroyed',
# 'editCommandEnded',
# 'editCommandStarted',
# 'editFormConfig',
# 'editFormConfigChanged',
# 'editingStarted',
# 'editingStopped',
# 'editorWidgetSetup',
# 'elevationProperties',
# 'emitStyleChanged',
# 'encodedSource',
# 'endEditCommand',
# 'error',
# 'event',
# 'eventFilter',
# 'excludeAttributesWfs',
# 'excludeAttributesWms',
# 'exportNamedMetadata',
# 'exportNamedStyle',
# 'exportSldStyle',
# 'expressionField',
# 'extensionPropertyType',
# 'extent',
# 'featureAdded',
# 'featureBlendMode',
# 'featureBlendModeChanged',
# 'featureCount',
# 'featureDeleted',
# 'featureRendererGenerators',
# 'featuresDeleted',
# 'fieldConstraints',
# 'fieldConstraintsAndStrength',
# 'fields',
# 'findChild',
# 'findChildren',
# 'flags',
# 'flagsChanged',
# 'flushBuffer',
# 'formatLayerName',
# 'generateId',
# 'geometryChanged',
# 'geometryOptions',
# 'geometryType',
# 'getFeature',
# 'getFeatures',
# 'getGeometry',
# 'getSelectedFeatures',
# 'getStyleFromDatabase',
# 'hasAutoRefreshEnabled',
# 'hasDependencyCycle',
# 'hasFeatures',
# 'hasScaleBasedVisibility',
# 'hasSpatialIndex',
# 'htmlMetadata',
# 'id',
# 'importNamedMetadata',
# 'importNamedStyle',
# 'inherits',
# 'insertVertex',
# 'installEventFilter',
# 'invalidateWgs84Extent',
# 'invertSelection',
# 'invertSelectionInRectangle',
# 'isAuxiliaryField',
# 'isEditCommandActive',
# 'isEditable',
# 'isInScaleRange',
# 'isModified',
# 'isRefreshOnNotifyEnabled',
# 'isSignalConnected',
# 'isSpatial',
# 'isSqlQuery',
# 'isTemporary',
# 'isValid',
# 'isValidChanged',
# 'isWidgetType',
# 'isWindowType',
# 'joinBuffer',
# 'keywordList',
# 'killTimer',
# 'labeling',
# 'labelingFontNotFound',
# 'labelsEnabled',
# 'lastError',
# 'layerModified',
# 'legend',
# 'legendChanged',
# 'legendPlaceholderImage',
# 'legendUrl',
# 'legendUrlFormat',
# 'listStylesInDatabase',
# 'loadAuxiliaryLayer',
# 'loadDefaultMetadata',
# 'loadDefaultStyle',
# 'loadNamedMetadata',
# 'loadNamedMetadataFromDatabase',
# 'loadNamedStyle',
# 'loadNamedStyleFromDatabase',
# 'loadSldStyle',
# 'mapTipTemplate',
# 'mapTipTemplateChanged',
# 'materialize',
# 'maximumScale',
# 'maximumValue',
# 'metaObject',
# 'metadata',
# 'metadataChanged',
# 'metadataUri',
# 'metadataUrl',
# 'metadataUrlFormat',
# 'metadataUrlType',
# 'minimumAndMaximumValue',
# 'minimumScale',
# 'minimumValue',
# 'modifySelection',
# 'moveToThread',
# 'moveVertex',
# 'moveVertexV2',
# 'name',
# 'nameChanged',
# 'objectName',
# 'objectNameChanged',
# 'opacity',
# 'opacityChanged',
# 'originalXmlProperties',
# 'parent',
# 'primaryKeyAttributes',
# 'project',
# 'properties',
# 'property',
# 'providerType',
# 'publicSource',
# 'pyqtConfigure',
# 'raiseError',
# 'readCommonStyle',
# 'readCustomProperties',
# 'readCustomSymbology',
# 'readExtentFromXml',
# 'readLayerXml',
# 'readOnly',
# 'readOnlyChanged',
# 'readSld',
# 'readStyle',
# 'readStyleManager',
# 'readSymbology',
# 'readXml',
# 'recalculateExtents',
# 'receivers',
# 'referencingRelations',
# 'refreshOnNotifyMessage',
# 'reload',
# 'removeCustomProperty',
# 'removeEventFilter',
# 'removeExpressionField',
# 'removeFeatureRendererGenerator',
# 'removeFieldAlias',
# 'removeFieldConstraint',
# 'removeJoin',
# 'removeSelection',
# 'renameAttribute',
# 'renderer',
# 'renderer3D',
# 'renderer3DChanged',
# 'rendererChanged',
# 'repaintRequested',
# 'request3DUpdate',
# 'reselect',
# 'resolveReferences',
# 'rollBack',
# 'saveDefaultMetadata',
# 'saveDefaultStyle',
# 'saveNamedMetadata',
# 'saveNamedStyle',
# 'saveSldStyle',
# 'saveStyleToDatabase',
# 'select',
# 'selectAll',
# 'selectByExpression',
# 'selectByIds',
# 'selectByRect',
# 'selectedFeatureCount',
# 'selectedFeatureIds',
# 'selectedFeatures',
# 'selectionChanged',
# 'sender',
# 'senderSignalIndex',
# 'serverProperties',
# 'setAbstract',
# 'setAttributeTableConfig',
# 'setAttribution',
# 'setAttributionUrl',
# 'setAutoRefreshEnabled',
# 'setAutoRefreshInterval',
# 'setAuxiliaryLayer',
# 'setBlendMode',
# 'setConstraintExpression',
# 'setCoordinateSystem',
# 'setCrs',
# 'setCustomProperties',
# 'setCustomProperty',
# 'setDataSource',
# 'setDataUrl',
# 'setDataUrlFormat',
# 'setDefaultValueDefinition',
# 'setDependencies',
# 'setDiagramLayerSettings',
# 'setDiagramRenderer',
# 'setDisplayExpression',
# 'setEditFormConfig',
# 'setEditorWidgetSetup',
# 'setError',
# 'setExcludeAttributesWfs',
# 'setExcludeAttributesWms',
# 'setExtent',
# 'setFeatureBlendMode',
# 'setFieldAlias',
# 'setFieldConstraint',
# 'setFlags',
# 'setKeywordList',
# 'setLabeling',
# 'setLabelsEnabled',
# 'setLayerOrder',
# 'setLegend',
# 'setLegendPlaceholderImage',
# 'setLegendUrl',
# 'setLegendUrlFormat',
# 'setMapTipTemplate',
# 'setMaximumScale',
# 'setMetadata',
# 'setMetadataUrl',
# 'setMetadataUrlFormat',
# 'setMetadataUrlType',
# 'setMinimumScale',
# 'setName',
# 'setObjectName',
# 'setOpacity',
# 'setOriginalXmlProperties',
# 'setParent',
# 'setProperty',
# 'setProviderEncoding',
# 'setProviderType',
# 'setReadExtentFromXml',
# 'setReadOnly',
# 'setRefreshOnNofifyMessage',
# 'setRefreshOnNotifyEnabled',
# 'setRenderer',
# 'setRenderer3D',
# 'setScaleBasedVisibility',
# 'setShortName',
# 'setSimplifyMethod',
# 'setSubLayerVisibility',
# 'setSubsetString',
# 'setTitle',
# 'setTransformContext',
# 'setValid',
# 'shortName',
# 'signalsBlocked',
# 'simplifyDrawingCanbeApplied',
# 'simplifyMethod',
# 'source',
# 'sourceCrs',
# 'sourceExtent',
# 'sourceName',
# 'splitFeatures',
# 'splitParts',
# 'startEditing',
# 'startTimer',
# 'staticMetaObject',
# 'statusChanged',
# 'storageType',
# 'storedExpressionManager',
# 'styleChanged',
# 'styleLoaded',
# 'styleManager',
# 'styleURI',
# 'subLayers',
# 'subsetString',
# 'subsetStringChanged',
# 'supportsEditing',
# 'supportsEditingChanged',
# 'symbolFeatureCountMapChanged',
# 'symbolFeatureIds',
# 'temporalProperties',
# 'thread',
# 'timerEvent',
# 'timestamp',
# 'title',
# 'tr',
# 'transformContext',
# 'translateFeature',
# 'trigger3DUpdate',
# 'triggerRepaint',
# 'type',
# 'undoStack',
# 'undoStackStyles',
# 'uniqueStringsMatching',
# 'uniqueValues',
# 'updateExpressionField',
# 'updateExtents',
# 'updateFeature',
# 'updateFields',
# 'updatedFields',
# 'vectorJoins',
# 'vectorLayerTypeFlags',
# 'wgs84Extent',
# 'willBeDeleted',
# 'wkbType',
# 'writeCommonStyle',
# 'writeCustomProperties',
# 'writeCustomSymbology',
# 'writeLayerXml',
# 'writeSld',
# 'writeStyle',
# 'writeStyleManager',
# 'writeSymbology',
# 'writeXml']

# pal = layer.renderer().symbol().symbolLayers()[0]
# print (type(pal))
# <class 'qgis._core.QgsSimpleMarkerSymbolLayer'>

# print (dir(pal))
# ['Arrow',
#  'ArrowHead',
#  'ArrowHeadFilled',
#  'AsteriskFill',
#  'Bottom',
#  'Circle',
#  'Cross',
#  'Cross2',
#  'CrossFill',
#  'Decagon',
#  'DiagonalHalfSquare',
#  'Diamond',
#  'DiamondStar',
#  'EquilateralTriangle',
#  'HCenter',
#  'HalfArc',
#  'HalfSquare',
#  'Heart',
#  'Hexagon',
#  'HorizontalAnchorPoint',
#  'Left',
#  'LeftHalfTriangle',
#  'Line',
#  'Octagon',
#  'ParallelogramLeft',
#  'ParallelogramRight',
#  'Pentagon',
#  'Property',
#  'PropertyAngle',
#  'PropertyArrowHeadLength',
#  'PropertyArrowHeadThickness',
#  'PropertyArrowHeadType',
#  'PropertyArrowStartWidth',
#  'PropertyArrowType',
#  'PropertyArrowWidth',
#  'PropertyAverageAngleLength',
#  'PropertyBlurRadius',
#  'PropertyCapStyle',
#  'PropertyCharacter',
#  'PropertyClipPoints',
#  'PropertyCoordinateMode',
#  'PropertyCustomDash',
#  'PropertyDashPatternOffset',
#  'PropertyDensityArea',
#  'PropertyDisplacementX',
#  'PropertyDisplacementY',
#  'PropertyDistanceX',
#  'PropertyDistanceY',
#  'PropertyFile',
#  'PropertyFillColor',
#  'PropertyFillStyle',
#  'PropertyFontFamily',
#  'PropertyFontStyle',
#  'PropertyGradientReference1IsCentroid',
#  'PropertyGradientReference1X',
#  'PropertyGradientReference1Y',
#  'PropertyGradientReference2IsCentroid',
#  'PropertyGradientReference2X',
#  'PropertyGradientReference2Y',
#  'PropertyGradientSpread',
#  'PropertyGradientType',
#  'PropertyHeight',
#  'PropertyHorizontalAnchor',
#  'PropertyInterval',
#  'PropertyJoinStyle',
#  'PropertyLayerEnabled',
#  'PropertyLineAngle',
#  'PropertyLineClipping',
#  'PropertyLineDistance',
#  'PropertyLineEndColorValue',
#  'PropertyLineEndWidthValue',
#  'PropertyLineStartColorValue',
#  'PropertyLineStartWidthValue',
#  'PropertyMarkerClipping',
#  'PropertyName',
#  'PropertyOffset',
#  'PropertyOffsetAlongLine',
#  'PropertyOffsetX',
#  'PropertyOffsetY',
#  'PropertyOpacity',
#  'PropertyPlacement',
#  'PropertyPointCount',
#  'PropertyPreserveAspectRatio',
#  'PropertyRandomOffsetX',
#  'PropertyRandomOffsetY',
#  'PropertyRandomSeed',
#  'PropertySecondaryColor',
#  'PropertyShapeburstIgnoreRings',
#  'PropertyShapeburstMaxDistance',
#  'PropertyShapeburstUseWholeShape',
#  'PropertySize',
#  'PropertyStrokeColor',
#  'PropertyStrokeStyle',
#  'PropertyStrokeWidth',
#  'PropertyTrimEnd',
#  'PropertyTrimStart',
#  'PropertyVerticalAnchor',
#  'PropertyWidth',
#  'QuarterArc',
#  'QuarterCircle',
#  'QuarterSquare',
#  'Right',
#  'RightHalfTriangle',
#  'RoundedSquare',
#  'SemiCircle',
#  'Shape',
#  'Shield',
#  'Square',
#  'SquareWithCorners',
#  'Star',
#  'ThirdArc',
#  'ThirdCircle',
#  'Top',
#  'Trapezoid',
#  'Triangle',
#  'VCenter',
#  'VerticalAnchorPoint',
#  '__class__',
#  '__delattr__',
#  '__dict__',
#  '__dir__',
#  '__doc__',
#  '__eq__',
#  '__format__',
#  '__ge__',
#  '__getattribute__',
#  '__gt__',
#  '__hash__',
#  '__init__',
#  '__init_subclass__',
#  '__le__',
#  '__lt__',
#  '__module__',
#  '__ne__',
#  '__new__',
#  '__reduce__',
#  '__reduce_ex__',
#  '__repr__',
#  '__setattr__',
#  '__sizeof__',
#  '__str__',
#  '__subclasshook__',
#  '__weakref__',
#  '_rotatedOffset',
#  'angle',
#  'availableShapes',
#  'bounds',
#  'calculateOffsetAndRotation',
#  'calculateSize',
#  'canCauseArtifactsBetweenAdjacentTiles',
#  'clone',
#  'color',
#  'copyDataDefinedProperties',
#  'copyPaintEffect',
#  'create',
#  'createFromSld',
#  'dataDefinedProperties',
#  'decodeShape',
#  'draw',
#  'drawMarker',
#  'drawPreviewIcon',
#  'dxfAngle',
#  'dxfBrushColor',
#  'dxfBrushStyle',
#  'dxfColor',
#  'dxfCustomDashPattern',
#  'dxfOffset',
#  'dxfPenStyle',
#  'dxfWidth',
#  'enabled',
#  'encodeShape',
#  'estimateMaxBleed',
#  'fillColor',
#  'flags',
#  'hasDataDefinedProperties',
#  'horizontalAnchorPoint',
#  'isCompatibleWithSymbol',
#  'isLocked',
#  'layerType',
#  'mapUnitScale',
#  'markerOffset',
#  'markerOffset2',
#  'markerOffsetWithWidthAndHeight',
#  'masks',
#  'offset',
#  'offsetMapUnitScale',
#  'offsetUnit',
#  'ogrFeatureStyle',
#  'outputUnit',
#  'paintEffect',
#  'penCapStyle',
#  'penJoinStyle',
#  'prepareCache',
#  'prepareExpressions',
#  'prepareMarkerPath',
#  'prepareMarkerShape',
#  'prepareMasks',
#  'properties',
#  'propertyDefinitions',
#  'renderPoint',
#  'renderingPass',
#  'restoreOldDataDefinedProperties',
#  'scaleMethod',
#  'setAngle',
#  'setColor',
#  'setDataDefinedProperties',
#  'setDataDefinedProperty',
#  'setEnabled',
#  'setFillColor',
#  'setHorizontalAnchorPoint',
#  'setLineAngle',
#  'setLocked',
#  'setMapUnitScale',
#  'setOffset',
#  'setOffsetMapUnitScale',
#  'setOffsetUnit',
#  'setOutputUnit',
#  'setPaintEffect',
#  'setPenCapStyle',
#  'setPenJoinStyle',
#  'setRenderingPass',
#  'setScaleMethod',
#  'setShape',
#  'setSize',
#  'setSizeMapUnitScale',
#  'setSizeUnit',
#  'setStrokeColor',
#  'setStrokeStyle',
#  'setStrokeWidth',
#  'setStrokeWidthMapUnitScale',
#  'setStrokeWidthUnit',
#  'setSubSymbol',
#  'setVerticalAnchorPoint',
#  'shape',
#  'shapeIsFilled',
#  'shapeToPolygon',
#  'size',
#  'sizeMapUnitScale',
#  'sizeUnit',
#  'startFeatureRender',
#  'startRender',
#  'stopFeatureRender',
#  'stopRender',
#  'strokeColor',
#  'strokeStyle',
#  'strokeWidth',
#  'strokeWidthMapUnitScale',
#  'strokeWidthUnit',
#  'subSymbol',
#  'toSld',
#  'type',
#  'usedAttributes',
#  'usesMapUnits',
#  'verticalAnchorPoint',
#  'writeDxf',
#  'writeSldMarker']
