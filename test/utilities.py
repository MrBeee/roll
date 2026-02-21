# coding=utf-8
import logging
import os
import sys

# QGIS imports (must run inside QGIS/OSGeo4W Python environment)
from qgis.core import QgsApplication
from qgis.gui import QgsMapCanvas
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtWidgets import QWidget

LOGGER = logging.getLogger('QGIS')

# Ensure repo root is importable when tests are run directly
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(TEST_DIR)
if PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)

# Handle both package and direct-script test execution
try:
    from .qgis_interface import QgisInterface
except ImportError:
    from qgis_interface import QgisInterface

QGIS_APP = None
CANVAS = None
PARENT = None
IFACE = None


def get_qgis_app():
    """Start one QGIS application instance for tests."""
    global QGIS_APP, CANVAS, PARENT, IFACE                                      # pylint: disable=W0603

    if QGIS_APP is None:
        QGIS_APP = QgsApplication(sys.argv, True)
        QGIS_APP.initQgis()
        LOGGER.debug(QGIS_APP.showSettings())

    if PARENT is None:
        PARENT = QWidget()

    if CANVAS is None:
        CANVAS = QgsMapCanvas(PARENT)
        CANVAS.resize(QSize(400, 400))

    if IFACE is None:
        IFACE = QgisInterface(CANVAS)

    return QGIS_APP, CANVAS, IFACE, PARENT
