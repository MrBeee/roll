# coding=utf-8
import unittest
from unittest.mock import patch

import numpy as np
from qgis.PyQt.QtCore import QEvent, Qt
from qgis.PyQt.QtGui import QBrush, QKeyEvent

from .plugin_loader import loadPluginModule
from .utilities import getQgisApp

QGIS_APP = getQgisApp()

tableModelModule = loadPluginModule('table_model_view')
spsModule = loadPluginModule('sps_io_and_qc')

SpsTableModel = tableModelModule.SpsTableModel
RpsTableModel = tableModelModule.RpsTableModel
TableView = tableModelModule.TableView
pntType1 = spsModule.pntType1


class TableModelViewTest(unittest.TestCase):
    def _buildPointRecords(self):
        records = np.zeros(2, dtype=pntType1)
        records[0] = (100.0, 10.0, 1, 'AA', 0.0, 1000.0, 2000.0, 0.0, 1, 0, 1, 0.0, 0.0)
        records[1] = (101.0, 11.0, 1, 'AA', 0.0, 1010.0, 2010.0, 0.0, 1, 1, 0, 0.0, 0.0)
        return records

    def _buildConsecutiveOrphanRecords(self):
        records = np.zeros(3, dtype=pntType1)
        records[0] = (100.0, 10.0, 1, 'AA', 0.0, 1000.0, 2000.0, 0.0, 1, 0, 1, 0.0, 0.0)
        records[1] = (101.0, 11.0, 1, 'AA', 0.0, 1010.0, 2010.0, 0.0, 1, 0, 1, 0.0, 0.0)
        records[2] = (102.0, 12.0, 1, 'AA', 0.0, 1020.0, 2020.0, 0.0, 1, 1, 1, 0.0, 0.0)
        return records

    def _buildConsecutiveRpsOrphanRecords(self):
        records = np.zeros(3, dtype=pntType1)
        records[0] = (200.0, 20.0, 1, 'AA', 0.0, 2000.0, 3000.0, 0.0, 1, 0, 1, 0.0, 0.0)
        records[1] = (201.0, 21.0, 1, 'AA', 0.0, 2010.0, 3010.0, 0.0, 1, 0, 1, 0.0, 0.0)
        records[2] = (202.0, 22.0, 1, 'AA', 0.0, 2020.0, 3020.0, 0.0, 1, 1, 1, 0.0, 0.0)
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

    def testCtrlNavigationWithoutSelectionDoesNotCrash(self):
        view = TableView()
        model = SpsTableModel(self._buildPointRecords())
        view.setModel(model)

        shortcuts = [Qt.Key.Key_PageDown, Qt.Key.Key_PageUp, Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_Right, Qt.Key.Key_Left]

        with patch.object(tableModelModule.winsound, 'PlaySound') as playSound:
            for key in shortcuts:
                event = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.ControlModifier)
                handled = view.eventFilter(view, event)
                self.assertTrue(handled)

        playSound.assert_not_called()

    def testCtrlDownMovesToNextConsecutiveSpsOrphanWithoutSound(self):
        view = TableView()
        model = SpsTableModel(self._buildConsecutiveOrphanRecords())
        view.setModel(model)
        view.selectRow(0)

        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.ControlModifier)

        with patch.object(tableModelModule.winsound, 'PlaySound') as playSound:
            handled = view.eventFilter(view, event)

        self.assertTrue(handled)
        self.assertEqual(view.selectionModel().selectedRows()[0].row(), 1)
        playSound.assert_not_called()

    def testCtrlDownOnLastSpsOrphanPlaysSound(self):
        view = TableView()
        model = SpsTableModel(self._buildPointRecords())
        view.setModel(model)
        view.selectRow(0)

        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.ControlModifier)

        with patch.object(tableModelModule.winsound, 'PlaySound') as playSound:
            handled = view.eventFilter(view, event)

        self.assertTrue(handled)
        self.assertEqual(view.selectionModel().selectedRows()[0].row(), 0)
        playSound.assert_called_once()

    def testCtrlUpOnFirstSpsOrphanPlaysSound(self):
        view = TableView()
        model = SpsTableModel(self._buildPointRecords())
        view.setModel(model)
        view.selectRow(0)

        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.ControlModifier)

        with patch.object(tableModelModule.winsound, 'PlaySound') as playSound:
            handled = view.eventFilter(view, event)

        self.assertTrue(handled)
        self.assertEqual(view.selectionModel().selectedRows()[0].row(), 0)
        playSound.assert_called_once()

    def testCtrlRightMovesToNextConsecutiveRpsOrphanWithoutSound(self):
        view = TableView()
        model = RpsTableModel(self._buildConsecutiveRpsOrphanRecords())
        view.setModel(model)
        view.selectRow(0)

        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier)

        with patch.object(tableModelModule.winsound, 'PlaySound') as playSound:
            handled = view.eventFilter(view, event)

        self.assertTrue(handled)
        self.assertEqual(view.selectionModel().selectedRows()[0].row(), 1)
        playSound.assert_not_called()

    def testCtrlRightOnLastRpsOrphanPlaysSound(self):
        view = TableView()
        model = RpsTableModel(self._buildPointRecords())
        view.setModel(model)
        view.selectRow(0)

        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier)

        with patch.object(tableModelModule.winsound, 'PlaySound') as playSound:
            handled = view.eventFilter(view, event)

        self.assertTrue(handled)
        self.assertEqual(view.selectionModel().selectedRows()[0].row(), 0)
        playSound.assert_called_once()

    def testCtrlLeftOnFirstRpsOrphanPlaysSound(self):
        view = TableView()
        model = RpsTableModel(self._buildPointRecords())
        view.setModel(model)
        view.selectRow(0)

        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Left, Qt.KeyboardModifier.ControlModifier)

        with patch.object(tableModelModule.winsound, 'PlaySound') as playSound:
            handled = view.eventFilter(view, event)

        self.assertTrue(handled)
        self.assertEqual(view.selectionModel().selectedRows()[0].row(), 0)
        playSound.assert_called_once()


if __name__ == '__main__':
    unittest.main()