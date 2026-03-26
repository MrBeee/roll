# coding=utf-8
"""QGIS plugin implementation.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

.. note:: This source code was copied from the 'postgis viewer' application
     with original authors:
     Copyright (c) 2010 by Ivan Mincik, ivan.mincik@gista.sk
     Copyright (c) 2011 German Carrillo, geotux_tuxman@linuxmail.org
     Copyright (c) 2014 Tim Sutton, tim@linfiniti.com

"""

__author__ = 'tim@linfiniti.com'
__revision__ = '$Format:%H$'
__date__ = '10/01/2011'
__copyright__ = (
    'Copyright (c) 2010 by Ivan Mincik, ivan.mincik@gista.sk and '
    'Copyright (c) 2011 German Carrillo, geotux_tuxman@linuxmail.org'
    'Copyright (c) 2014 Tim Sutton, tim@linfiniti.com'
)

import contextlib
import logging

from qgis.core import QgsProject
from qgis.PyQt.QtCore import QObject, pyqtSignal

LOGGER = logging.getLogger('QGIS')


#noinspection PyMethodMayBeStatic,PyPep8Naming
class QgisInterface(QObject):
    """Class to expose QGIS objects and functions to plugins.

    This class is here for enabling us to run unit tests only,
    so most methods are simply stubs.
    """
    currentLayerChanged = pyqtSignal(object)

    def __init__(self, canvas):
        """Constructor
        :param canvas:
        """
        QObject.__init__(self)
        self.canvas = canvas
        self.project = QgsProject.instance()
        # Set up slots so we can mimic the behaviour of QGIS when layers
        # are added.
        LOGGER.debug('Initialising canvas...')
        # noinspection PyArgumentList
        self.project.layersAdded.connect(self.addLayers)
        # noinspection PyArgumentList
        self.project.layerWasAdded.connect(self.addLayer)
        # noinspection PyArgumentList
        self.project.removeAll.connect(self.removeAllLayers)

        # For processing module
        self.destCrs = None
        self.pluginMenuActions = {}

    def addLayers(self, layers):
        """Handle layers being added to the registry so they show up in canvas.

        :param layers: list<QgsMapLayer> list of map layers that were added

        .. note:: The QgsInterface api does not include this method,
            it is added here as a helper to facilitate testing.
        """
        #LOGGER.debug('addLayers called on qgis_interface')
        #LOGGER.debug('Number of layers being added: %s' % len(layers))
        #LOGGER.debug('Layer Count Before: %s' % len(self.canvas.layers()))
        currentLayers = list(self.canvas.layers())
        finalLayers = list(currentLayers)
        finalLayers.extend(layers)

        if hasattr(self.canvas, 'setLayers'):
            self.canvas.setLayers(finalLayers)
        elif hasattr(self.canvas, 'setLayerSet'):
            self.canvas.setLayerSet(finalLayers)
        #LOGGER.debug('Layer Count After: %s' % len(self.canvas.layers()))

    def addLayer(self, layer):
        """Handle a layer being added to the registry so it shows up in canvas.

        :param layer: list<QgsMapLayer> list of map layers that were added

        .. note: The QgsInterface api does not include this method, it is added
                 here as a helper to facilitate testing.

        .. note: The addLayer method was deprecated in QGIS 1.8 so you should
                 not need this method much.
        """

    def removeAllLayers(self):
        """Remove layers from the canvas before they get deleted."""
        if hasattr(self.canvas, 'setLayers'):
            self.canvas.setLayers([])
        elif hasattr(self.canvas, 'setLayerSet'):
            self.canvas.setLayerSet([])

    def newProject(self):
        """Create new project."""
        # noinspection PyArgumentList
        self.project.removeAllMapLayers()

    # ---------------- API Mock for QgsInterface follows -------------------

    def zoomFull(self):
        """Zoom to the map full extent."""

    def zoomToPrevious(self):
        """Zoom to previous view extent."""

    def zoomToNext(self):
        """Zoom to next view extent."""

    def zoomToActiveLayer(self):
        """Zoom to extent of active layer."""

    def addVectorLayer(self, path, base_name, provider_key):
        """Add a vector layer.

        :param path: Path to layer.
        :type path: str

        :param base_name: Base name for layer.
        :type base_name: str

        :param provider_key: Provider key e.g. 'ogr'
        :type provider_key: str
        """

    def addRasterLayer(self, path, base_name):
        """Add a raster layer given a raster layer file name

        :param path: Path to layer.
        :type path: str

        :param base_name: Base name for layer.
        :type base_name: str
        """

    def activeLayer(self):
        """Get pointer to the active layer (layer selected in the legend)."""
        # noinspection PyArgumentList
        layers = self.project.mapLayers()
        for item in layers:
            return layers[item]

    def addToolBarIcon(self, action):
        """Add an icon to the plugins toolbar.

        :param action: Action to add to the toolbar.
        :type action: QAction
        """

    def removeToolBarIcon(self, action):
        """Remove an action (icon) from the plugin toolbar.

        :param action: Action to add to the toolbar.
        :type action: QAction
        """

    def addPluginToMenu(self, menu, action):
        """Record a plugin menu action for tests."""
        self.pluginMenuActions.setdefault(menu, []).append(action)

    def removePluginMenu(self, menu, action):
        """Remove a plugin menu action for tests."""
        if menu not in self.pluginMenuActions:
            return
        with contextlib.suppress(ValueError):
            self.pluginMenuActions[menu].remove(action)
        if not self.pluginMenuActions[menu]:
            self.pluginMenuActions.pop(menu, None)

    def addToolBar(self, name):
        """Add toolbar with specified name.

        :param name: Name for the toolbar.
        :type name: str
        """

    def mapCanvas(self):
        """Return a pointer to the map canvas."""
        return self.canvas

    def mainWindow(self):
        """Return a pointer to the main window.

        In case of QGIS it returns an instance of QgisApp.
        """
        return None

    def addDockWidget(self, area, dock_widget):
        """Add a dock widget to the main window.

        :param area: Where in the ui the dock should be placed.
        :type area:

        :param dock_widget: A dock widget to add to the UI.
        :type dock_widget: QDockWidget
        """

    def legendInterface(self):
        """Get the legend."""
        return self.canvas
