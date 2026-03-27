# coding=utf-8
import unittest

import numpy as np
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QBrush

from .plugin_loader import loadPluginModule
from .utilities import getQgisApp

QGIS_APP = getQgisApp()

tableModelModule = loadPluginModule('table_model_view')
spsModule = loadPluginModule('sps_io_and_qc')

SpsTableModel = tableModelModule.SpsTableModel
RpsTableModel = tableModelModule.RpsTableModel
pntType1 = spsModule.pntType1


class TableModelViewTest(unittest.TestCase):
    def _buildPointRecords(self):
        records = np.zeros(2, dtype=pntType1)
        records[0] = (100.0, 10.0, 1, 'AA', 0.0, 1000.0, 2000.0, 0.0, 1, 0, 1, 0.0, 0.0)
        records[1] = (101.0, 11.0, 1, 'AA', 0.0, 1010.0, 2010.0, 0.0, 1, 1, 0, 0.0, 0.0)
        return records

    def testSpsOrphanRowsKeepReadableForeground(self):
        model = SpsTableModel(self._buildPointRecords())

        orphanIndex = model.index(0, 0)
        inactiveIndex = model.index(1, 0)

        orphanForeground = model.data(orphanIndex, Qt.ItemDataRole.ForegroundRole)
        inactiveForeground = model.data(inactiveIndex, Qt.ItemDataRole.ForegroundRole)

        self.assertFalse(isinstance(orphanForeground, QBrush))
        self.assertIsInstance(inactiveForeground, QBrush)

    def testRpsOrphanRowsKeepReadableForeground(self):
        model = RpsTableModel(self._buildPointRecords())

        orphanIndex = model.index(0, 0)
        inactiveIndex = model.index(1, 0)

        orphanForeground = model.data(orphanIndex, Qt.ItemDataRole.ForegroundRole)
        inactiveForeground = model.data(inactiveIndex, Qt.ItemDataRole.ForegroundRole)

        self.assertFalse(isinstance(orphanForeground, QBrush))
        self.assertIsInstance(inactiveForeground, QBrush)


if __name__ == '__main__':
    unittest.main()