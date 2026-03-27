# coding=utf-8
import unittest

import numpy as np

from .plugin_loader import loadPluginModule
from .utilities import getQgisApp

QGIS_APP = getQgisApp()

filterServiceModule = loadPluginModule('filter_service')
spsModule = loadPluginModule('sps_io_and_qc')

FilterService = filterServiceModule.FilterService
pntType1 = spsModule.pntType1
relType2 = spsModule.relType2


class FilterServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = FilterService()

    def testApplyPointDuplicateFilterRecomputesSpatialState(self):
        records = np.zeros(3, dtype=pntType1)
        records[0] = (100.0, 10.0, 1, 'AA', 0.0, 1000.0, 2000.0, 0.0, 1, 1, 1, 0.0, 0.0)
        records[1] = (100.0, 10.0, 1, 'AA', 0.0, 1000.0, 2000.0, 0.0, 1, 1, 1, 0.0, 0.0)
        records[2] = (101.0, 11.0, 1, 'AA', 0.0, 1010.0, 2010.0, 0.0, 1, 1, 1, 0.0, 0.0)

        result = self.service.applyFilter('rps_duplicates', records)

        self.assertTrue(result.changed)
        self.assertEqual((result.before, result.after), (3, 2))
        self.assertTrue(result.refreshLayout)
        self.assertIsNotNone(result.derivedState)
        self.assertIsNotNone(result.derivedState.bound)
        self.assertEqual(result.derivedState.liveE.shape[0], 2)
        self.assertIn('rps-duplicates', result.message)

    def testApplyPointOrphanFilterWithoutHullKeepsBoundEmpty(self):
        records = np.zeros(2, dtype=pntType1)
        records[0] = (200.0, 20.0, 1, 'AA', 0.0, 1100.0, 2100.0, 0.0, 1, 1, 1, 0.0, 0.0)
        records[1] = (201.0, 21.0, 1, 'AA', 0.0, 1110.0, 2110.0, 0.0, 1, 0, 1, 0.0, 0.0)

        result = self.service.applyFilter('rec_orphans', records)

        self.assertTrue(result.changed)
        self.assertEqual((result.before, result.after), (2, 1))
        self.assertTrue(result.refreshLayout)
        self.assertIsNotNone(result.derivedState)
        self.assertIsNone(result.derivedState.bound)
        self.assertIn('rec/rel-orphans', result.message)

    def testApplyRelationFilterDoesNotRequestLayoutRefresh(self):
        records = np.zeros(2, dtype=relType2)
        records[0] = (100.0, 10.0, 1, 1000, 200.0, 1.0, 2.0, 1, 1, 1, 1)
        records[1] = (101.0, 11.0, 1, 1001, 201.0, 1.0, 2.0, 1, 1, 0, 1)

        result = self.service.applyFilter('xps_sps_orphans', records)

        self.assertTrue(result.changed)
        self.assertEqual((result.before, result.after), (2, 1))
        self.assertFalse(result.refreshLayout)
        self.assertIsNone(result.derivedState)
        self.assertIn('xps/sps-orphans', result.message)


if __name__ == '__main__':
    unittest.main()
