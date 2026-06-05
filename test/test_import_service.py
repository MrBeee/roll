# coding=utf-8
import unittest
from unittest.mock import patch

import numpy as np

from .plugin_loader import loadPluginModule

importServiceModule = loadPluginModule('import_service')
spsModule = loadPluginModule('sps_io_and_qc')

ImportService = importServiceModule.ImportService
pntType1 = spsModule.pntType1
relType2 = spsModule.relType2


def buildPointArray(records):
    data = np.zeros(shape=len(records), dtype=pntType1)
    for index, record in enumerate(records):
        data[index]['Line'] = record.get('Line', 0.0)
        data[index]['Point'] = record.get('Point', 0.0)
        data[index]['Index'] = record.get('Index', 0)
        data[index]['Code'] = record.get('Code', 'AA')
        data[index]['Depth'] = record.get('Depth', 0.0)
        data[index]['East'] = record.get('East', 0.0)
        data[index]['North'] = record.get('North', 0.0)
        data[index]['Elev'] = record.get('Elev', 0.0)
        data[index]['Uniq'] = record.get('Uniq', 0)
        data[index]['InXps'] = record.get('InXps', 0)
        data[index]['InUse'] = record.get('InUse', 1)
        data[index]['LocX'] = record.get('LocX', 0.0)
        data[index]['LocY'] = record.get('LocY', 0.0)
    return data


def buildRelationArray(records):
    data = np.zeros(shape=len(records), dtype=relType2)
    for index, record in enumerate(records):
        data[index]['SrcLin'] = record.get('SrcLin', 0.0)
        data[index]['SrcPnt'] = record.get('SrcPnt', 0.0)
        data[index]['SrcInd'] = record.get('SrcInd', 0)
        data[index]['RecNum'] = record.get('RecNum', 0)
        data[index]['RecLin'] = record.get('RecLin', 0.0)
        data[index]['RecMin'] = record.get('RecMin', 0.0)
        data[index]['RecMax'] = record.get('RecMax', 0.0)
        data[index]['RecInd'] = record.get('RecInd', 0)
        data[index]['Uniq'] = record.get('Uniq', 0)
        data[index]['InSps'] = record.get('InSps', 0)
        data[index]['InRps'] = record.get('InRps', 0)
    return data


class ImportServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = ImportService()

    def testImportTextDataBuildsArraysAndTrimsUnusedRows(self):
        def fakeReadSps(index, line, array, _format):
            array[index]['Line'] = float(line)
            return 1

        def fakeReadXps(index, line, array, _format):
            array[index]['SrcInd'] = int(line)
            return 1

        def fakeReadRps(index, line, array, _format):
            array[index]['Point'] = float(line)
            return 1

        with patch.object(importServiceModule, 'readSpsLine', side_effect=fakeReadSps), \
             patch.object(importServiceModule, 'readXpsLine', side_effect=fakeReadXps), \
             patch.object(importServiceModule, 'readRpsLine', side_effect=fakeReadRps):
            result = self.service.importTextData(
                spsData=['10', '20'],
                xpsData=['1'],
                rpsData=['100', '200', '300'],
                spsFormat={},
                xpsFormat={},
                rpsFormat={},
            )

        self.assertFalse(result.cancelled)
        self.assertEqual(result.spsRead, 2)
        self.assertEqual(result.xpsRead, 1)
        self.assertEqual(result.rpsRead, 3)
        self.assertEqual(result.spsImport.shape[0], 2)
        self.assertEqual(result.xpsImport.shape[0], 1)
        self.assertEqual(result.rpsImport.shape[0], 3)
        self.assertEqual(result.spsImport['Line'].tolist(), [10.0, 20.0])
        self.assertEqual(result.xpsImport['SrcInd'].tolist(), [1])
        self.assertEqual(result.rpsImport['Point'].tolist(), [100.0, 200.0, 300.0])

    def testImportTextDataStopsCleanlyWhenCancelled(self):
        cancelChecks = {'count': 0}

        def shouldCancel():
            cancelChecks['count'] += 1
            return cancelChecks['count'] >= 1

        result = self.service.importTextData(
            spsData=['10', '20'],
            spsFormat={},
            shouldCancel=shouldCancel,
        )

        self.assertTrue(result.cancelled)
        self.assertEqual(result.cancelMessage, 'Import : importing SPS data canceled by user.')
        self.assertIsNone(result.spsImport)
        self.assertEqual(result.spsRead, 0)

    def testRunQualityChecksReturnsMessagesAndMutatesArrays(self):
        spsImport = buildPointArray(
            [
                {'Line': 10.0, 'Point': 100.0, 'Index': 1, 'East': 1000.0, 'North': 2000.0},
                {'Line': 20.0, 'Point': 200.0, 'Index': 2, 'East': 1100.0, 'North': 2100.0},
            ]
        )
        rpsImport = buildPointArray(
            [
                {'Line': 10.0, 'Point': 100.0, 'Index': 1, 'East': 1200.0, 'North': 2200.0},
                {'Line': 10.0, 'Point': 101.0, 'Index': 1, 'East': 1210.0, 'North': 2210.0},
            ]
        )
        xpsImport = buildRelationArray(
            [
                {'SrcLin': 10.0, 'SrcPnt': 100.0, 'SrcInd': 1, 'RecLin': 10.0, 'RecMin': 100.0, 'RecMax': 101.0, 'RecInd': 1},
                {'SrcLin': 99.0, 'SrcPnt': 999.0, 'SrcInd': 9, 'RecLin': 10.0, 'RecMin': 200.0, 'RecMax': 200.0, 'RecInd': 1},
            ]
        )

        with patch.object(importServiceModule, 'convertCrs', side_effect=lambda array, src, dst: array), \
             patch.object(importServiceModule, 'calculateLineStakeTransform', return_value=(1000.0, 2000.0, 100.0, 10.0, 25.0, 50.0, 5.0, 10.0, 90.0)):
            result = self.service.runQualityChecks(
                rpsImport=rpsImport,
                spsImport=spsImport,
                xpsImport=xpsImport,
                importCrs=object(),
                surveyCrs=object(),
            )

        self.assertTrue(result.showRpsList)
        self.assertTrue(result.showSpsList)
        self.assertTrue(any('analysed rps-records' in message for message in result.messages))
        self.assertTrue(any('analysed sps-records' in message for message in result.messages))
        self.assertTrue(any('analysed xps-records' in message for message in result.messages))
        self.assertTrue(any('sps-records contain' in message for message in result.messages))
        self.assertTrue(any('rps-records contain' in message for message in result.messages))
        self.assertEqual(spsImport['InXps'].tolist(), [1, 0])
        self.assertEqual(xpsImport['InSps'].tolist(), [1, 0])
        self.assertEqual(xpsImport['InRps'].tolist(), [1, 0])


if __name__ == '__main__':
    unittest.main()
