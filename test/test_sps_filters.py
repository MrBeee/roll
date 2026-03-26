# coding=utf-8
import unittest

import numpy as np

from .plugin_loader import loadPluginModule

spsModule = loadPluginModule('sps_io_and_qc')

deletePntDuplicates = spsModule.deletePntDuplicates
deletePntOrphans = spsModule.deletePntOrphans
deleteRelDuplicates = spsModule.deleteRelDuplicates
deleteRelOrphans = spsModule.deleteRelOrphans
findRecOrphans = spsModule.findRecOrphans
findSrcOrphans = spsModule.findSrcOrphans
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


class SpsFilterFunctionsTest(unittest.TestCase):
    def testDeletePntDuplicatesRemovesEquivalentRows(self):
        points = buildPointArray(
            [
                {'Line': 20.0, 'Point': 200.0, 'Index': 2, 'Uniq': 0, 'InXps': 1},
                {'Line': 10.0, 'Point': 100.0, 'Index': 1, 'Uniq': 7, 'InXps': 1},
                {'Line': 10.0, 'Point': 100.0, 'Index': 1, 'Uniq': 0, 'InXps': 1},
            ]
        )

        filtered, before, after = deletePntDuplicates(points)

        self.assertEqual(before, 3)
        self.assertEqual(after, 2)
        self.assertEqual(filtered['Index'].tolist(), [1, 2])
        self.assertTrue(np.all(filtered['Uniq'] == 1))

    def testDeletePntOrphansKeepsOnlyRowsLinkedToXps(self):
        points = buildPointArray(
            [
                {'Line': 30.0, 'Point': 300.0, 'Index': 3, 'InXps': 1},
                {'Line': 10.0, 'Point': 100.0, 'Index': 1, 'InXps': 1},
                {'Line': 20.0, 'Point': 200.0, 'Index': 2, 'InXps': 0},
            ]
        )

        filtered, before, after = deletePntOrphans(points)

        self.assertEqual(before, 3)
        self.assertEqual(after, 2)
        self.assertEqual(filtered['Index'].tolist(), [1, 3])
        self.assertTrue(np.all(filtered['InXps'] == 1))

    def testFindSrcOrphansMarksPointAndRelationMembership(self):
        spsImport = buildPointArray(
            [
                {'Line': 10.0, 'Point': 100.0, 'Index': 1},
                {'Line': 20.0, 'Point': 200.0, 'Index': 2},
            ]
        )
        xpsImport = buildRelationArray(
            [
                {'SrcLin': 10.0, 'SrcPnt': 100.0, 'SrcInd': 1, 'RecNum': 1},
                {'SrcLin': 99.0, 'SrcPnt': 999.0, 'SrcInd': 9, 'RecNum': 2},
            ]
        )

        nSpsOrphans, nXpsOrphans = findSrcOrphans(spsImport, xpsImport)
        filtered, before, after = deleteRelOrphans(xpsImport, source=True)

        self.assertEqual((nSpsOrphans, nXpsOrphans), (1, 1))
        self.assertEqual(spsImport['InXps'].tolist(), [1, 0])
        self.assertEqual(xpsImport['InSps'].tolist(), [1, 0])
        self.assertEqual(before, 2)
        self.assertEqual(after, 1)
        self.assertEqual(filtered['SrcInd'].tolist(), [1])

    def testFindRecOrphansMarksReceiverRangesAndFiltersRelations(self):
        rpsImport = buildPointArray(
            [
                {'Line': 10.0, 'Point': 100.0, 'Index': 1},
                {'Line': 10.0, 'Point': 101.0, 'Index': 1},
            ]
        )
        xpsImport = buildRelationArray(
            [
                {'RecLin': 10.0, 'RecMin': 100.0, 'RecMax': 101.0, 'RecInd': 1, 'SrcInd': 1},
                {'RecLin': 10.0, 'RecMin': 200.0, 'RecMax': 200.0, 'RecInd': 1, 'SrcInd': 2},
            ]
        )

        nRpsOrphans, nXpsOrphans = findRecOrphans(rpsImport, xpsImport)
        filtered, before, after = deleteRelOrphans(xpsImport, source=False)

        self.assertEqual((nRpsOrphans, nXpsOrphans), (1, 0))
        self.assertEqual(xpsImport['InRps'].tolist(), [1, 0])
        self.assertEqual(before, 2)
        self.assertEqual(after, 1)
        self.assertEqual(filtered['SrcInd'].tolist(), [1])

    def testDeleteRelDuplicatesRemovesEquivalentRows(self):
        relations = buildRelationArray(
            [
                {'SrcLin': 20.0, 'SrcPnt': 200.0, 'SrcInd': 2, 'RecLin': 20.0, 'RecMin': 200.0, 'RecMax': 201.0, 'RecInd': 2, 'Uniq': 0},
                {'SrcLin': 10.0, 'SrcPnt': 100.0, 'SrcInd': 1, 'RecLin': 10.0, 'RecMin': 100.0, 'RecMax': 101.0, 'RecInd': 1, 'Uniq': 5},
                {'SrcLin': 10.0, 'SrcPnt': 100.0, 'SrcInd': 1, 'RecLin': 10.0, 'RecMin': 100.0, 'RecMax': 101.0, 'RecInd': 1, 'Uniq': 0},
            ]
        )

        filtered, before, after = deleteRelDuplicates(relations)

        self.assertEqual(before, 3)
        self.assertEqual(after, 2)
        self.assertEqual(filtered['SrcInd'].tolist(), [1, 2])
        self.assertTrue(np.all(filtered['Uniq'] == 1))


if __name__ == '__main__':
    unittest.main()
