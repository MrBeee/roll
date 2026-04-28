# coding=utf-8
import os
import tempfile
import unittest

import numpy as np

from .plugin_loader import loadPluginModule

spsModule = loadPluginModule('sps_io_and_qc')
configModule = loadPluginModule('config')

deletePntDuplicates = spsModule.deletePntDuplicates
deletePntOrphans = spsModule.deletePntOrphans
deleteRelDuplicates = spsModule.deleteRelDuplicates
deleteRelOrphans = spsModule.deleteRelOrphans
findRecOrphans = spsModule.findRecOrphans
findSrcOrphans = spsModule.findSrcOrphans
pntType1 = spsModule.pntType1
readRPSFiles = spsModule.readRPSFiles
readRpsLine = spsModule.readRpsLine
readSPSFiles = spsModule.readSPSFiles
readSpsLine = spsModule.readSpsLine
readXPSFiles = spsModule.readXPSFiles
readXpsLine = spsModule.readXpsLine
relType2 = spsModule.relType2


def formatFixedWidthLine(recordType, fmt, values):
    width = 80
    chars = [' '] * width
    chars[0] = recordType

    for fieldName, value in values.items():
        start, end = fmt[fieldName]
        text = str(value)
        fieldWidth = end - start
        chars[start:end] = list(text.rjust(fieldWidth)[:fieldWidth])

    return ''.join(chars)


def writeTempFixedWidthFile(lines):
    tempDir = tempfile.TemporaryDirectory()
    filePath = os.path.join(tempDir.name, 'sample.dat')
    with open(filePath, 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')
    return tempDir, filePath


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
    def testReadSPSFilesSkipsNonSourceLinesAndResizesResult(self):
        fmt = configModule.getDefaultSpsFormats()[0]
        tempDir, filePath = writeTempFixedWidthFile(
            [
                formatFixedWidthLine(fmt['hdr'], fmt, {}),
                '',
                formatFixedWidthLine(
                    fmt['src'],
                    fmt,
                    {
                        'line': '1001',
                        'point': '2001',
                        'index': '1',
                        'code': 'AA',
                        'depth': '10',
                        'east': '1111111',
                        'north': '2222222',
                        'elev': '333',
                    },
                ),
                formatFixedWidthLine(fmt['rec'], fmt, {'line': '9999'}),
                formatFixedWidthLine(
                    fmt['src'],
                    fmt,
                    {
                        'line': '1002',
                        'point': '2002',
                        'index': '2',
                        'code': 'BB',
                        'depth': '20',
                        'east': '4444444',
                        'north': '5555555',
                        'elev': '666',
                    },
                ),
            ]
        )
        self.addCleanup(tempDir.cleanup)
        spsImport = np.zeros(shape=5, dtype=pntType1)

        parsed = readSPSFiles([filePath], spsImport, fmt)

        self.assertEqual(parsed, 2)
        self.assertEqual(spsImport.shape[0], 2)
        self.assertEqual(spsImport['Line'].tolist(), [1001.0, 1002.0])
        self.assertEqual(spsImport['Point'].tolist(), [2001.0, 2002.0])
        self.assertEqual(spsImport['Code'].tolist(), ['AA', 'BB'])

    def testReadRPSFilesSkipsNonReceiverLinesAndResizesResult(self):
        fmt = configModule.getDefaultRpsFormats()[0]
        tempDir, filePath = writeTempFixedWidthFile(
            [
                formatFixedWidthLine(fmt['hdr'], fmt, {}),
                formatFixedWidthLine(fmt['src'], fmt, {'line': '9999'}),
                formatFixedWidthLine(
                    fmt['rec'],
                    fmt,
                    {
                        'line': '3001',
                        'point': '4001',
                        'index': '3',
                        'code': 'CC',
                        'depth': '30',
                        'east': '6666666',
                        'north': '7777777',
                        'elev': '888',
                    },
                ),
                '',
                formatFixedWidthLine(
                    fmt['rec'],
                    fmt,
                    {
                        'line': '3002',
                        'point': '4002',
                        'index': '4',
                        'code': 'DD',
                        'depth': '40',
                        'east': '9999999',
                        'north': '1111111',
                        'elev': '222',
                    },
                ),
            ]
        )
        self.addCleanup(tempDir.cleanup)
        rpsImport = np.zeros(shape=5, dtype=pntType1)

        parsed = readRPSFiles([filePath], rpsImport, fmt)

        self.assertEqual(parsed, 2)
        self.assertEqual(rpsImport.shape[0], 2)
        self.assertEqual(rpsImport['Line'].tolist(), [3001.0, 3002.0])
        self.assertEqual(rpsImport['Point'].tolist(), [4001.0, 4002.0])
        self.assertEqual(rpsImport['Code'].tolist(), ['CC', 'DD'])

    def testReadXPSFilesSkipsNonRelationLinesAndResizesResult(self):
        fmt = configModule.getDefaultXpsFormats()[0]
        tempDir, filePath = writeTempFixedWidthFile(
            [
                formatFixedWidthLine(fmt['hdr'], fmt, {}),
                formatFixedWidthLine(fmt['src'], fmt, {'srcLin': '9999'}),
                formatFixedWidthLine(
                    fmt['rel'],
                    fmt,
                    {
                        'recNum': '101',
                        'srcLin': '5001',
                        'srcPnt': '6001',
                        'srcInd': '5',
                        'recLin': '7001',
                        'recMin': '8001',
                        'recMax': '8003',
                        'recInd': '6',
                    },
                ),
                '',
                formatFixedWidthLine(
                    fmt['rel'],
                    fmt,
                    {
                        'recNum': '102',
                        'srcLin': '5002',
                        'srcPnt': '6002',
                        'srcInd': '7',
                        'recLin': '7002',
                        'recMin': '9001',
                        'recMax': '9004',
                        'recInd': '8',
                    },
                ),
            ]
        )
        self.addCleanup(tempDir.cleanup)
        xpsImport = np.zeros(shape=5, dtype=relType2)

        parsed = readXPSFiles([filePath], xpsImport, fmt)

        self.assertEqual(parsed, 2)
        self.assertEqual(xpsImport.shape[0], 2)
        self.assertEqual(xpsImport['RecNum'].tolist(), [101, 102])
        self.assertEqual(xpsImport['SrcLin'].tolist(), [5001.0, 5002.0])
        self.assertEqual(xpsImport['RecMin'].tolist(), [8001.0, 9001.0])
        self.assertEqual(xpsImport['RecMax'].tolist(), [8003.0, 9004.0])

    def testReadSpsLineParsesConfiguredFixedWidthFields(self):
        fmt = configModule.getDefaultSpsFormats()[0]
        spsImport = np.zeros(shape=1, dtype=pntType1)
        line = formatFixedWidthLine(
            fmt['src'],
            fmt,
            {
                'line': '1234',
                'point': '5678',
                'index': '3',
                'code': 'AB',
                'depth': '45',
                'east': '1234567',
                'north': '7654321',
                'elev': '321',
            },
        )

        parsed = readSpsLine(0, line, spsImport, fmt)

        self.assertEqual(parsed, 1)
        self.assertEqual(spsImport[0]['Line'], 1234.0)
        self.assertEqual(spsImport[0]['Point'], 5678.0)
        self.assertEqual(spsImport[0]['Index'], 3)
        self.assertEqual(spsImport[0]['Code'], 'AB')
        self.assertEqual(spsImport[0]['Depth'], 45.0)
        self.assertEqual(spsImport[0]['East'], 1234567.0)
        self.assertEqual(spsImport[0]['North'], 7654321.0)
        self.assertEqual(spsImport[0]['Elev'], 321.0)
        self.assertEqual(spsImport[0]['Uniq'], 1)
        self.assertEqual(spsImport[0]['InXps'], 1)
        self.assertEqual(spsImport[0]['InUse'], 1)

    def testReadRpsLineIgnoresNonReceiverLine(self):
        fmt = configModule.getDefaultRpsFormats()[0]
        rpsImport = np.zeros(shape=1, dtype=pntType1)
        line = formatFixedWidthLine(
            fmt['src'],
            fmt,
            {
                'line': '1111',
                'point': '2222',
                'index': '1',
                'code': 'CD',
                'depth': '10',
                'east': '1111111',
                'north': '2222222',
                'elev': '333',
            },
        )

        parsed = readRpsLine(0, line, rpsImport, fmt)

        self.assertEqual(parsed, 0)
        self.assertEqual(rpsImport[0]['Line'], 0.0)
        self.assertEqual(rpsImport[0]['Point'], 0.0)
        self.assertEqual(rpsImport[0]['Index'], 0)

    def testReadRpsLineParsesConfiguredFixedWidthFields(self):
        fmt = configModule.getDefaultRpsFormats()[0]
        rpsImport = np.zeros(shape=1, dtype=pntType1)
        line = formatFixedWidthLine(
            fmt['rec'],
            fmt,
            {
                'line': '4321',
                'point': '8765',
                'index': '4',
                'code': 'EF',
                'depth': '54',
                'east': '2345678',
                'north': '8765432',
                'elev': '123',
            },
        )

        parsed = readRpsLine(0, line, rpsImport, fmt)

        self.assertEqual(parsed, 1)
        self.assertEqual(rpsImport[0]['Line'], 4321.0)
        self.assertEqual(rpsImport[0]['Point'], 8765.0)
        self.assertEqual(rpsImport[0]['Index'], 4)
        self.assertEqual(rpsImport[0]['Code'], 'EF')
        self.assertEqual(rpsImport[0]['Depth'], 54.0)
        self.assertEqual(rpsImport[0]['East'], 2345678.0)
        self.assertEqual(rpsImport[0]['North'], 8765432.0)
        self.assertEqual(rpsImport[0]['Elev'], 123.0)

    def testReadXpsLineParsesConfiguredFixedWidthFields(self):
        fmt = configModule.getDefaultXpsFormats()[0]
        xpsImport = np.zeros(shape=1, dtype=relType2)
        line = formatFixedWidthLine(
            fmt['rel'],
            fmt,
            {
                'recNum': '123',
                'srcLin': '1001',
                'srcPnt': '2002',
                'srcInd': '5',
                'recLin': '3003',
                'recMin': '4004',
                'recMax': '5005',
                'recInd': '6',
            },
        )

        parsed = readXpsLine(0, line, xpsImport, fmt)

        self.assertEqual(parsed, 1)
        self.assertEqual(xpsImport[0]['SrcLin'], 1001.0)
        self.assertEqual(xpsImport[0]['SrcPnt'], 2002.0)
        self.assertEqual(xpsImport[0]['SrcInd'], 5)
        self.assertEqual(xpsImport[0]['RecNum'], 123)
        self.assertEqual(xpsImport[0]['RecLin'], 3003.0)
        self.assertEqual(xpsImport[0]['RecMin'], 4004.0)
        self.assertEqual(xpsImport[0]['RecMax'], 5005.0)
        self.assertEqual(xpsImport[0]['RecInd'], 6)
        self.assertEqual(xpsImport[0]['Uniq'], 1)
        self.assertEqual(xpsImport[0]['InSps'], 1)
        self.assertEqual(xpsImport[0]['InRps'], 1)

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

    def testFindRecOrphansMarksXpsLinkedWhenReceiverFallsInsideRange(self):
        rpsImport = buildPointArray(
            [
                {'Line': 10.0, 'Point': 150.0, 'Index': 1},
            ]
        )
        xpsImport = buildRelationArray(
            [
                {'RecLin': 10.0, 'RecMin': 100.0, 'RecMax': 200.0, 'RecInd': 1, 'SrcInd': 1},
                {'RecLin': 10.0, 'RecMin': 300.0, 'RecMax': 400.0, 'RecInd': 1, 'SrcInd': 2},
            ]
        )

        nRpsOrphans, nXpsOrphans = findRecOrphans(rpsImport, xpsImport)
        filtered, before, after = deleteRelOrphans(xpsImport, source=False)

        self.assertEqual((nRpsOrphans, nXpsOrphans), (1, 0))
        self.assertEqual(xpsImport['InRps'].tolist(), [1, 0])
        self.assertEqual(before, 2)
        self.assertEqual(after, 1)
        self.assertEqual(filtered['SrcInd'].tolist(), [1])

    def testFindRecOrphansHandlesOverlappingReceiverIntervals(self):
        rpsImport = buildPointArray(
            [
                {'Line': 10.0, 'Point': 100.0, 'Index': 1},
                {'Line': 10.0, 'Point': 115.0, 'Index': 1},
                {'Line': 10.0, 'Point': 140.0, 'Index': 1},
                {'Line': 10.0, 'Point': 210.0, 'Index': 1},
            ]
        )
        xpsImport = buildRelationArray(
            [
                {'RecLin': 10.0, 'RecMin': 90.0, 'RecMax': 120.0, 'RecInd': 1, 'SrcInd': 1},
                {'RecLin': 10.0, 'RecMin': 110.0, 'RecMax': 150.0, 'RecInd': 1, 'SrcInd': 2},
                {'RecLin': 10.0, 'RecMin': 200.0, 'RecMax': 205.0, 'RecInd': 1, 'SrcInd': 3},
            ]
        )

        nRpsOrphans, nXpsOrphans = findRecOrphans(rpsImport, xpsImport)
        filtered, before, after = deleteRelOrphans(xpsImport, source=False)

        self.assertEqual((nRpsOrphans, nXpsOrphans), (1, 1))
        self.assertEqual(rpsImport['InXps'].tolist(), [1, 1, 1, 0])
        self.assertEqual(xpsImport['InRps'].tolist(), [1, 1, 0])
        self.assertEqual(before, 3)
        self.assertEqual(after, 2)
        self.assertEqual(filtered['SrcInd'].tolist(), [1, 2])

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
