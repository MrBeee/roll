from datetime import datetime

import numpy as np
import pyqtgraph as pg
from qgis.core import QgsCoordinateTransform, QgsProject, QgsVector3D
from qgis.PyQt.QtCore import QFile, QIODevice, QTextStream
from qgis.PyQt.QtWidgets import QFileDialog

from .functions import myPrint, toFloat, toInt

# sps file formats
# See: https://seg.org/Portals/0/SEG/News%20and%20Resources/Technical%20Standards/seg_sps_rev2.1.pdf
# See: https://www.tutorialsandyou.com/python/numpy-data-types-66.html

# In the types below, first the full SPS format is shown and then some derived versions
#
#################### 'Field'   np.type  Fortran type
pntType = np.dtype(
    [
        # fmt : off
        ('RecID', 'U2'),  # A1 ('S' or 'R')
        ('Line',  'f4'),  # F10.2
        ('Point', 'f4'),  # F10.2
        ('Index', 'i4'),  # I1
        ('Code',  'U2'),  # A2
        ('Static','i4'),  # I4
        ('Depth', 'f4'),  # I4
        ('Datum', 'i4'),  # I4
        ('Uhole', 'i4'),  # I2
        ('Water', 'f4'),  # F6.1
        ('East',  'f4'),  # F9.1
        ('North', 'f4'),  # F10.1
        ('Elev',  'f4'),  # F6.1
        ('Day',   'i4'),  # I3
        ('Time',  'i4'),  # 3I2
        # fmt : on
    ]
)

# this point-type includes local x, y coordinates
pntType1 = np.dtype(
    [
        # fmt : off
        ('Line',  'f4'),  # F10.2
        ('Point', 'f4'),  # F10.2
        ('Index', 'i4'),  # I1
        ('Code',  'U2'),  # A2
        ('Depth', 'f4'),  # I4
        ('East',  'f4'),  # F9.1
        ('North', 'f4'),  # F10.1
        ('Elev',  'f4'),  # F6.1
        ('Uniq',  'i4'),  # check if record is unique
        ('InXps', 'i4'),  # check if record is orphan
        ('InUse', 'i4'),  # check if record is in use
        ('LocX',  'f4'),  # F9.1
        ('LocY',  'f4'),  # F10.1
        # fmt : on
    ]
)

# pntType2 = np.dtype(
#     [
#         # fmt : on
#         ('Line',  'f4'),  # F10.2
#         ('Point', 'f4'),  # F10.2
#         ('Index', 'i4'),  # I1
#         ('Code',  'U2'),  # A2
#         ('Depth', 'f4'),  # I4
#         ('East',  'f4'),  # F9.1
#         ('North', 'f4'),  # F10.1
#         ('Elev',  'f4'),  # F6.1
#         ('Uniq',  'i4'),  # check if record is unique
#         ('InXps', 'i4'),  # check if record is orphan
#         # fmt : off
#     ])

pntType3 = np.dtype(
    # pntType3 is used to shorten the SPS/RPS records to Line-Point-Index records
    [
        ('Line', 'f4'),   # F10.2
        ('Point', 'f4'),  # F10.2
        ('Index', 'i4'),  # I1
    ])

pntType4 = np.dtype(
    [
        # fmt : off
        ('Line',  'f4'),  # F10.2
        ('Point', 'f4'),  # F10.2
        ('Index', 'i4'),  # I1
        ('Code',  'U2'),  # A2
        ('Depth', 'f4'),  # I4
        ('East',  'f4'),  # F9.1
        ('North', 'f4'),  # F10.1
        ('Elev',  'f4'),  # F6.1
        ('Day',   'i4'),  # I3
        ('Hour',  'i1'),  # I2
        ('Min',   'i1'),  # I2
        ('Sec',   'i1'),  # I2
        ('Stub',  'i1'),  # I2
        # fmt : on
    ])

pntType5 = np.dtype(
    [
        ('LocX', 'f4'),  # F9.1
        ('LocY', 'f4'),  # F10.1
        ('Elev', 'f4'),  # F6.1
    ])

relType = np.dtype(
    [
        # fmt : off
        ('RecID',  'U2'),  # A1 ('X')
        ('TapeNo', 'U8'),  # 3A2
        ('RecNum', 'i4'),  # I8
        ('RecInc', 'i4'),  # I1
        ('Instru', 'U2'),  # A1
        ('SrcLin', 'f4'),  # F10.2
        ('SrcPnt', 'f4'),  # F10.2
        ('SrcInd', 'i4'),  # I1
        ('ChaMin', 'i4'),  # I5
        ('ChaMax', 'i4'),  # I5
        ('ChaInc', 'i4'),  # I1    (e.g. 3 to record 3C data; 4 for 4C nodes)
        ('RecLin', 'f4'),  # F10.2
        ('RecMin', 'f4'),  # F10.2
        ('RecMax', 'f4'),  # F10.2
        ('RecInd', 'i4'),  # I1
        # fmt : on
    ])

relType2 = np.dtype(
    [
        # fmt : off
        ('SrcLin', 'f4'),  # F10.2
        ('SrcPnt', 'f4'),  # F10.2
        ('SrcInd', 'i4'),  # I1
        ('RecNum', 'i4'),  # I8
        ('RecLin', 'f4'),  # F10.2
        ('RecMin', 'f4'),  # F10.2
        ('RecMax', 'f4'),  # F10.2
        ('RecInd', 'i4'),  # I1
        ('Uniq',   'i4'),  # check if record is unique
        ('InSps',  'i4'),  # check if record is orphan
        ('InRps',  'i4'),  # check if record is orphan
        # fmt : on
    ])

relType3 = np.dtype(
    [
        ('RecLin', 'f4'),  # F10.2
        ('RecMin', 'f4'),  # F10.2
        ('RecMax', 'f4'),  # F10.2
        ('RecInd', 'i4'),  # I1
    ])

anaType = np.dtype(
    [
        # fmt : off
        ('SrcX', np.float32),  # Src (x, y)
        ('SrcY', np.float32),
        ('RecX', np.float32),  # Rec (x, y)
        ('RecY', np.float32),
        ('CmpX', np.float32),  # Cmp (x, y); needed for spider plot when binning against dipping plane
        ('CmpY', np.float32),
        ('SrcL', np.int32),    # SrcLine, SrcPoint
        ('SrcP', np.int32),
        ('RecL', np.int32),    # RecLine, RecPoint
        ('RecP', np.int32),
        # fmt : on
    ])

def readRPSFiles(filenames, resultArray, fmt) -> int:

    # To use QFile and QTextStream for sps import, for more information:
    # See: https://srinikom.github.io/pyside-docs/PySide/QtCore/QFile.html
    # See: https://python.hotexamples.com/examples/PyQt4.QtCore/QTextStream/-/python-qtextstream-class-examples.html
    # See: https://stackoverflow.com/questions/14750997/load-txt-file-from-resources-in-python

    if not filenames:
        return -1

    index = 0
    for filename in filenames:
        f = QFile(filename)
        if f.open(QIODevice.ReadOnly | QFile.Text):
            text = QTextStream(f)
        else:
            return -1

        while not text.atEnd():
            line = text.readLine()

            if len(line) == 0 or line[0] != fmt['rec']:
                continue

            # fmt: off
            lin = toFloat(line[fmt[ 'line'][0] : fmt[ 'line'][1]].strip())
            pnt = toFloat(line[fmt['point'][0] : fmt['point'][1]].strip())
            idx =   toInt(line[fmt['index'][0] : fmt['index'][1]].strip())
            cod =         line[fmt[ 'code'][0] : fmt[ 'code'][1]].strip()
            dep = toFloat(line[fmt['depth'][0] : fmt['depth'][1]].strip())
            eas = toFloat(line[fmt[ 'east'][0] : fmt[ 'east'][1]].strip())
            nor = toFloat(line[fmt['north'][0] : fmt['north'][1]].strip())
            ele = toFloat(line[fmt[ 'elev'][0] : fmt[ 'elev'][1]].strip())
            # fmt : on

            record = (lin, pnt, idx, cod, dep, eas, nor, ele, 1, 1, 1, 0.0, 0.0)
            resultArray[index] = record
            index += 1
        f.close()

    if index < resultArray.shape[0]:
        resultArray.resize(index, refcheck=False)        # See: https://numpy.org/doc/stable/reference/generated/numpy.ndarray.resize.html

    return index

def readSPSFiles(filenames, resultArray, fmt) -> int:

    if not filenames:
        return -1

    index = 0
    for filename in filenames:
        f = QFile(filename)
        if f.open(QIODevice.ReadOnly | QFile.Text):
            text = QTextStream(f)
        else:
            return -1

        while not text.atEnd():
            line = text.readLine()

            if len(line) == 0 or line[0] != fmt['src']:
                continue

            # fmt: off
            lin = toFloat(line[fmt[ 'line'][0] : fmt[ 'line'][1]].strip())
            pnt = toFloat(line[fmt['point'][0] : fmt['point'][1]].strip())
            idx =   toInt(line[fmt['index'][0] : fmt['index'][1]].strip())
            cod =         line[fmt[ 'code'][0] : fmt[ 'code'][1]].strip()
            dep = toFloat(line[fmt['depth'][0] : fmt['depth'][1]].strip())
            eas = toFloat(line[fmt[ 'east'][0] : fmt[ 'east'][1]].strip())
            nor = toFloat(line[fmt['north'][0] : fmt['north'][1]].strip())
            ele = toFloat(line[fmt[ 'elev'][0] : fmt[ 'elev'][1]].strip())
            # fmt: off

            record = (lin, pnt, idx, cod, dep, eas, nor, ele, 1, 1, 1, 0.0, 0.0)
            resultArray[index] = record
            index += 1
        f.close()

    if index < resultArray.shape[0]:
        resultArray.resize(index, refcheck=False)        # See: https://numpy.org/doc/stable/reference/generated/numpy.ndarray.resize.html

    return index

def readXPSFiles(filenames, resultArray, fmt) -> int:

    if not filenames:
        return -1

    index = 0
    for filename in filenames:
        f = QFile(filename)
        if f.open(QIODevice.ReadOnly | QFile.Text):
            text = QTextStream(f)
        else:
            return -1

        while not text.atEnd():
            line = text.readLine()

            if len(line) == 0 or line[0] != fmt['rel']:
                continue

            # This is the order that parameters appear on in an xps file
            # However, we move recNum to the fourth place in the xps record
            # fmt: off
            recNum =   toInt(line[fmt['recNum'][0] : fmt['recNum'][1]].strip())
            srcLin = toFloat(line[fmt['srcLin'][0] : fmt['srcLin'][1]].strip())
            srcPnt = toFloat(line[fmt['srcPnt'][0] : fmt['srcPnt'][1]].strip())
            srcInd =   toInt(line[fmt['srcInd'][0] : fmt['srcInd'][1]].strip())
            recLin = toFloat(line[fmt['recLin'][0] : fmt['recLin'][1]].strip())
            recMin = toFloat(line[fmt['recMin'][0] : fmt['recMin'][1]].strip())
            recMax = toFloat(line[fmt['recMax'][0] : fmt['recMax'][1]].strip())
            recInd =   toInt(line[fmt['recInd'][0] : fmt['recInd'][1]].strip())
            # fmt: off

            record = (srcLin, srcPnt, srcInd, recNum, recLin, recMin, recMax, recInd, 1, 1, 1)
            resultArray[index] = record
            index += 1
        f.close()

    if index < resultArray.shape[0]:
        resultArray.resize(index, refcheck=False)        # See: https://numpy.org/doc/stable/reference/generated/numpy.ndarray.resize.html

    return index

def readRpsLine(line_number, line, rpsImport, fmt) -> int:
    if len(line) == 0 or line[0] != fmt['rec']:                                 # check if line is empty or not a receiver line
        return 0

    # fmt: off
    lin = toFloat(line[fmt[ 'line'][0] : fmt[ 'line'][1]].strip())
    pnt = toFloat(line[fmt['point'][0] : fmt['point'][1]].strip())
    idx =   toInt(line[fmt['index'][0] : fmt['index'][1]].strip())
    cod =         line[fmt[ 'code'][0] : fmt[ 'code'][1]].strip()
    dep = toFloat(line[fmt['depth'][0] : fmt['depth'][1]].strip())
    eas = toFloat(line[fmt[ 'east'][0] : fmt[ 'east'][1]].strip())
    nor = toFloat(line[fmt['north'][0] : fmt['north'][1]].strip())
    ele = toFloat(line[fmt[ 'elev'][0] : fmt[ 'elev'][1]].strip())
    # fmt: on

    record = (lin, pnt, idx, cod, dep, eas, nor, ele, 1, 1, 1, 0.0, 0.0)
    rpsImport[line_number] = record
    return 1

def readSpsLine(line_number, line, spsImport, fmt) -> int:
    if len(line) == 0 or line[0] != fmt['src']:                                 # check if line is empty or not a source line
        return 0

    # fmt: off
    lin = toFloat(line[fmt[ 'line'][0] : fmt[ 'line'][1]].strip())
    pnt = toFloat(line[fmt['point'][0] : fmt['point'][1]].strip())
    idx =   toInt(line[fmt['index'][0] : fmt['index'][1]].strip())
    cod =         line[fmt[ 'code'][0] : fmt[ 'code'][1]].strip()
    dep = toFloat(line[fmt['depth'][0] : fmt['depth'][1]].strip())
    eas = toFloat(line[fmt[ 'east'][0] : fmt[ 'east'][1]].strip())
    nor = toFloat(line[fmt['north'][0] : fmt['north'][1]].strip())
    ele = toFloat(line[fmt[ 'elev'][0] : fmt[ 'elev'][1]].strip())
    # fmt: on

    record = (lin, pnt, idx, cod, dep, eas, nor, ele, 1, 1, 1, 0.0, 0.0)
    spsImport[line_number] = record
    return 1

def readXpsLine(line_number, line, xpsImport, fmt) -> int:
    if len(line) == 0 or line[0] != fmt['rel']:                                 # check if line is empty or not a relation line
        return 0

    # This is the order that parameters appear on in an xps file
    # However, we move recNum to the fourth place in the xps record
    # fmt: off
    recNum =   toInt(line[fmt['recNum'][0] : fmt['recNum'][1]].strip())
    srcLin = toFloat(line[fmt['srcLin'][0] : fmt['srcLin'][1]].strip())
    srcPnt = toFloat(line[fmt['srcPnt'][0] : fmt['srcPnt'][1]].strip())
    srcInd =   toInt(line[fmt['srcInd'][0] : fmt['srcInd'][1]].strip())
    recLin = toFloat(line[fmt['recLin'][0] : fmt['recLin'][1]].strip())
    recMin = toFloat(line[fmt['recMin'][0] : fmt['recMin'][1]].strip())
    recMax = toFloat(line[fmt['recMax'][0] : fmt['recMax'][1]].strip())
    recInd =   toInt(line[fmt['recInd'][0] : fmt['recInd'][1]].strip())
    # fmt: off

    record = (srcLin, srcPnt, srcInd, recNum, recLin, recMin, recMax, recInd, 1, 1, 1)
    xpsImport[line_number] = record
    return 1

def markUniqueRPSrecords(rpsImport, sort=True) -> int:
    # See: https://stackoverflow.com/questions/51933936/python-3-6-type-checking-numpy-arrays-and-use-defined-classes for type checking
    # See: https://stackoverflow.com/questions/12569452/how-to-identify-numpy-types-in-python same thing
    # See: https://stackoverflow.com/questions/11585793/are-numpy-arrays-passed-by-reference for passing a numpy array by reference
    # See: https://numpy.org/doc/stable/reference/generated/numpy.ndarray.sort.html for sorting in place
    if rpsImport is None or rpsImport.shape[0] == 0:
        return -1

    rpsUnique, rpsIndices = np.unique(rpsImport, return_index=True)
    rpsImport[rpsIndices]['Uniq'] = 1       # Set 'Uniq' value at the applicable indices using NumPy advanced indexing

    # # note, this for-loop is needed to set 'Uniq' value at the applicable indices
    # for index in np.nditer(rpsIndices):
    #     rpsImport[index]['Uniq'] = 1

    if sort:
        rpsImport.sort(order=['Index', 'Line', 'Point'])

    nUnique = rpsUnique.shape[0]
    return nUnique

def markUniqueSPSrecords(spsImport, sort=True) -> int:
    if spsImport is None or spsImport.shape[0] == 0:
        return -1

    spsUnique, spsIndices = np.unique(spsImport, return_index=True)
    spsImport[spsIndices]['Uniq'] = 1       # Set 'Uniq' value at the applicable indices using NumPy advanced indexing

    # # note, this for-loop is needed to set 'Uniq' value at the applicable indices
    # for index in np.nditer(spsIndices):
    #     spsImport[index]['Uniq'] = 1

    if sort:
        spsImport.sort(order=['Index', 'Line', 'Point'])

    nUnique = spsUnique.shape[0]
    return nUnique

def markUniqueXPSrecords(xpsImport, sort=True) -> int:
    if xpsImport is None or xpsImport.shape[0] == 0:
        return -1

    xpsUnique, xpsIndices = np.unique(xpsImport, return_index=True)
    xpsImport[xpsIndices]['Uniq'] = 1       # Set 'Uniq' value at the applicable indices using NumPy advanced indexing

    # # note, this for-loop is needed to set 'Uniq' value at the applicable indices
    # for index in np.nditer(xpsIndices):
    #     xpsImport[index]['Uniq'] = 1

    if sort:
        xpsImport.sort(order=['SrcInd', 'SrcLin', 'SrcPnt', 'RecInd', 'RecLin', 'RecMin', 'RecMax'])

    nUnique = xpsUnique.shape[0]
    return nUnique

def calcMaxXPStraces(xpsImport) -> int:
    last = xpsImport['RecMax']                                                  # get vector of last receiver points from xps data
    first = xpsImport['RecMin']                                                 # get vector of first receiver points from xps data
    total = last - first
    traces = int(total.sum() + total.shape[0])                                  # add the number of traces to arrive at the total number of receiver points
    return traces

def findSrcOrphans(spsImport, xpsImport) -> (int, int):
    if spsImport is None or xpsImport is None:
        return (-1, -1)

    # pntType3 = np.dtype([('Line',   'f4'),   # F10.2
    #                      ('Point',  'f4'),   # F10.2
    #                      ('Index',  'i4'),   # I1

    # shorten the SPS records to Line-Point-Index records
    nSps = spsImport.shape[0]
    spsShort = np.zeros(shape=nSps, dtype=pntType3)
    spsShort['Index'] = spsImport['Index']
    spsShort['Line'] = spsImport['Line']
    spsShort['Point'] = spsImport['Point']

    # shorten the XPS records to Line-Point-Index records
    nXps = xpsImport.shape[0]
    xpsShort = np.zeros(shape=nXps, dtype=pntType3)
    xpsShort['Index'] = xpsImport['SrcInd']
    xpsShort['Line'] = xpsImport['SrcLin']
    xpsShort['Point'] = xpsImport['SrcPnt']

    xpsUnique = np.unique(xpsShort)                                             # find unique records in (shorted) xps array
    spsMask = np.isin(spsShort, xpsUnique, assume_unique=False)                 # find unique xps records present in (shorted) sps array
    intMask = 1 * spsMask                                                       # convert bool to integer
    spsImport['InXps'] = np.asarray(intMask)                                    # Update the sps array with 'unique' mask
    nXpsOrphans = nSps - intMask.sum()                                          # The sps-records contain 'nXpsOrphans' xps-orphans

    spsUnique = np.unique(spsShort)                                             # find unique records in (shorted) sps array
    xpsMask = np.isin(xpsShort, spsUnique, assume_unique=False)                 # find unique sps elements present in (shorted) xps array
    intMask = 1 * xpsMask                                                       # convert bool to integer
    xpsImport['InSps'] = np.asarray(intMask)                                    # Update the xps array with 'unique' mask
    nSpsOrphans = nXps - intMask.sum()                                          # The xps-records contain 'nSpsOrphans' sps-orphans

    return (nSpsOrphans, nXpsOrphans)

def findRecOrphansOld(rpsImport, xpsImport) -> (int, int):
    if rpsImport is None or xpsImport is None:
        return (-1, -1)

    # find unique rps elements present in (shorted) xps array
    nXps = xpsImport.shape[0]
    xpsShort = np.zeros(shape=nXps, dtype=relType3)
    xpsShort['RecInd'] = xpsImport['RecInd']
    xpsShort['RecLin'] = xpsImport['RecLin']
    xpsShort['RecMin'] = xpsImport['RecMin']
    xpsShort['RecMax'] = xpsImport['RecMax']

    # delete all duplicate xps-records, resulting in xpsUnique
    xpsUnique = np.unique(xpsShort)
    xpsUnique.sort(order=['RecInd', 'RecLin', 'RecMin', 'RecMax'])
    rpsImport.sort(order=['Index', 'Line', 'Point'])

    # now iterate over rpsImport to check if elements are listed in xpsUnique
    marker = 0
    for rpsRecord in rpsImport:
        for j in range(marker, xpsUnique.shape[0]):
            xpsRecord = xpsUnique[j]

            # iR = rpsRecord['Index']
            # iX = xpsRecord['RecInd']

            if rpsRecord['Index'] < xpsRecord['RecInd']:
                # rpsIndex too small; we won't ever find a 'mate' in sorted list
                rpsRecord['InXps'] = 0
                break                                                           # break inner loop

            if rpsRecord['Index'] > xpsRecord['RecInd']:
                # rpsIndex too large; keep looking for matching xpsIndex
                marker += 1
                continue                                                        # continue looking for a match

            # when we arrive here, Index == RecInd. Now check line number

            # lR = rpsRecord['Line']
            # lX = xpsRecord['RecLin']

            if rpsRecord['Line'] < xpsRecord['RecLin']:
                # rpsLine too small; we won't ever find a 'mate' in sorted list
                rpsRecord['InXps'] = 0
                break                                                           # break inner loop

            if rpsRecord['Line'] > xpsRecord['RecLin']:
                # rpsLine too large; keep looking for matching xpsRecLin
                marker += 1
                continue                                                        # continue looking for a match

            # when we arrive here, Index == RecInd AND Line == RecLin. Now check stake number

            # pR = rpsRecord['Point']
            # pX1 = xpsRecord['RecMin']
            # pX2 = xpsRecord['RecMax']

            if rpsRecord['Point'] >= xpsRecord['RecMin'] and rpsRecord['Point'] <= xpsRecord['RecMax']:
                # yes, we're in business
                rpsRecord['InXps'] = 1
                break                                                           # break inner loop

    # shorten the RPS records to Line-Point-Index records
    nRps = rpsImport.shape[0]
    rpsShort = np.zeros(shape=nRps, dtype=pntType3)
    rpsShort['Index'] = rpsImport['Index']
    rpsShort['Line'] = rpsImport['Line']
    rpsShort['Point'] = rpsImport['Point']

    # shorten the XPS records to Line-Point-Index records
    xpsShortMin = np.zeros(shape=nXps, dtype=pntType3)
    xpsShortMin['Index'] = xpsImport['RecInd']
    xpsShortMin['Line'] = xpsImport['RecLin']
    xpsShortMin['Point'] = xpsImport['RecMin']

    xpsShortMax = np.zeros(shape=nXps, dtype=pntType3)
    xpsShortMax['Index'] = xpsImport['RecInd']
    xpsShortMax['Line'] = xpsImport['RecLin']
    xpsShortMax['Point'] = xpsImport['RecMax']

    # find unique xps records from (shorted) rps array
    rpsUnique = np.unique(rpsShort)
    xpsMaskMin = np.isin(xpsShortMin, rpsUnique, assume_unique=False)
    xpsMaskMax = np.isin(xpsShortMax, rpsUnique, assume_unique=False)
    xpsMask = np.logical_and(xpsMaskMin, xpsMaskMax)
    intMask = 1 * xpsMask                                                       # convert bool to integer
    xpsImport['InRps'] = np.asarray(intMask)                                    # Update the xps array with 'unique' mask

    xpsImport.sort(order=['RecInd', 'RecLin', 'RecMin', 'RecMax', 'SrcLin', 'SrcPnt', 'SrcInd'])
    rpsImport.sort(order=['Index', 'Line', 'Point'])

    nRpsOrphans = nXps - intMask.sum()                                          # xps-records contain 'nSpsOrphans' sps-orphans
    nXpsOrphans = nRps - rpsImport['InXps'].sum()

    return (nRpsOrphans, nXpsOrphans)

def findRecOrphans(rpsImport, xpsImport) -> (int, int):
    if rpsImport is None or xpsImport is None:
        return (-1, -1)

    # Create a structured array for xpsUnique
    xpsUnique = np.unique(
        np.array(
            list(zip(xpsImport['RecInd'], xpsImport['RecLin'], xpsImport['RecMin'], xpsImport['RecMax'])),
            dtype=[('RecInd', 'i4'), ('RecLin', 'f4'), ('RecMin', 'f4'), ('RecMax', 'f4')],
        )
    )

    # Broadcast rpsImport against xpsUnique for vectorized comparison
    rpsIndex = rpsImport['Index'][:, None]
    rpsLine = rpsImport['Line'][:, None]
    rpsPoint = rpsImport['Point'][:, None]

    xpsIndex = xpsUnique['RecInd']
    xpsLine = xpsUnique['RecLin']
    xpsMin = xpsUnique['RecMin']
    xpsMax = xpsUnique['RecMax']

    # Perform vectorized comparisons
    index_match = rpsIndex == xpsIndex
    line_match = rpsLine == xpsLine
    point_match = (rpsPoint >= xpsMin) & (rpsPoint <= xpsMax)

    # Combine all conditions
    match = index_match & line_match & point_match

    # Determine if each rpsRecord has a match in xpsUnique
    rpsImport['InXps'] = match.any(axis=1).astype(int)

    # Calculate orphans
    nXpsOrphans = rpsImport.shape[0] - rpsImport['InXps'].sum()

    # shorten the RPS records to Line-Point-Index records
    nRps = rpsImport.shape[0]
    rpsShort = np.zeros(shape=nRps, dtype=pntType3)
    rpsShort['Index'] = rpsImport['Index']
    rpsShort['Line'] = rpsImport['Line']
    rpsShort['Point'] = rpsImport['Point']

    # shorten the XPS records to Line-Point-Index records
    nXps = xpsImport.shape[0]
    xpsShortMin = np.zeros(shape=nXps, dtype=pntType3)
    xpsShortMin['Index'] = xpsImport['RecInd']
    xpsShortMin['Line'] = xpsImport['RecLin']
    xpsShortMin['Point'] = xpsImport['RecMin']

    xpsShortMax = np.zeros(shape=nXps, dtype=pntType3)
    xpsShortMax['Index'] = xpsImport['RecInd']
    xpsShortMax['Line'] = xpsImport['RecLin']
    xpsShortMax['Point'] = xpsImport['RecMax']

    # find those unique rps records that are in the xps array with either RecMin or RecMax
    rpsUnique = np.unique(rpsShort)
    xpsMaskMin = np.isin(xpsShortMin, rpsUnique, assume_unique=False)
    xpsMaskMax = np.isin(xpsShortMax, rpsUnique, assume_unique=False)
    xpsMask = np.logical_and(xpsMaskMin, xpsMaskMax)
    intMask = 1 * xpsMask                                                       # convert bool to integer
    xpsImport['InRps'] = np.asarray(intMask)                                    # Update the xps array with 'unique' mask

    xpsImport.sort(order=['RecInd', 'RecLin', 'RecMin', 'RecMax', 'SrcLin', 'SrcPnt', 'SrcInd'])
    rpsImport.sort(order=['Index', 'Line', 'Point'])

    nRpsOrphans = nXps - intMask.sum()                                          # xps-records contain 'nSpsOrphans' sps-orphans
    nXpsOrphans = nRps - rpsImport['InXps'].sum()

    return (nRpsOrphans, nXpsOrphans)

def deletePntDuplicates(rpsImport):

    before = rpsImport.shape[0]                                                 # get nr of records
    rpsImport['Uniq'] = 1                                                       # do this for all records, so they're all the same, 'Uniq' wise
    rpsImport = np.unique(rpsImport)                                            # get the 'really' unique records
    after = rpsImport.shape[0]                                                  # get nr of records again
    if after == 0:
        rpsImport = None
    else:
        rpsImport.sort(order=['Index', 'Line', 'Point'])                        # sort the whole lot

    return (rpsImport, before, after)

def deletePntOrphans(rpsImport):

    before = rpsImport.shape[0]
    rpsImport = rpsImport[rpsImport['InXps'] == 1]
    after = rpsImport.shape[0]
    if after == 0:
        rpsImport = None
    else:
        rpsImport.sort(order=['Index', 'Line', 'Point'])

    return (rpsImport, before, after)

def deleteRelDuplicates(xpsImport):

    before = xpsImport.shape[0]
    xpsImport['Uniq'] = 1
    xpsImport = np.unique(xpsImport)
    after = xpsImport.shape[0]
    if after == 0:
        xpsImport = None
    else:
        xpsImport.sort(order=['SrcInd', 'SrcLin', 'SrcPnt', 'RecInd', 'RecLin', 'RecMin', 'RecMax'])

    return (xpsImport, before, after)

def deleteRelOrphans(xpsImport, source=True):

    mode = 'InSps' if source is True else 'InRps'

    before = xpsImport.shape[0]
    xpsImport = xpsImport[xpsImport[mode] == 1]
    after = xpsImport.shape[0]
    if after == 0:
        xpsImport = None
    else:
        if source:
            xpsImport.sort(order=['SrcInd', 'SrcLin', 'SrcPnt', 'RecInd', 'RecLin', 'RecMin', 'RecMax'])
        else:
            xpsImport.sort(order=['RecInd', 'RecLin', 'RecMin', 'RecMax', 'SrcInd', 'SrcLin', 'SrcPnt'])

    return (xpsImport, before, after)

def fileExportAsR01(parent, fileName, extension, view, crs):
    # fmt: off
    fn, selectedFilter = QFileDialog.getSaveFileName(
        parent,                                                                 # the main window
        'Save as...',                                                           # caption
        fileName + extension,                                                   # start directory + filename + extension
        'sps receiver file format (*.r01);;sps receiver file format (*.rps);;All files (*.*)' # file extensions
        # options                                                               # options -> not used)
    )
    # fmt: on

    if not fn:
        return (0, '')                                                          # return 0 records, no filename given,

    extension = '.r01'                                                          # default extension value
    if selectedFilter == 'sps receiver file format (*.r01)':                    # select appropriate extension
        extension = '.r01'
    elif selectedFilter == 'sps receiver file format (*.rps)':
        extension = '.rps'

    if not fn.lower().endswith(extension):                                      # make sure file extension is okay
        fn += extension                                                         # just add the file extension

    # fmt: 0ff
    fmt = '%1s',  '%10.2f', '%10.2f', '%1d',   '%2s',  '%4d',    '%4.1f', '%4d',   '%2d',   '%6.1f', '%9.1f', '%10.1f', '%6.1f', '%3d', '%6d'
    #     'RecID','Line',   'Point',  'Index', 'Code', 'Static', 'Depth', 'Datum', 'Uhole', 'Water', 'East',  'North',  'Elev',  'Day', 'Time'
    # Note: Point is followed by two spaces (Col 22-23 as per SPS 2.1 format)
    # fmt: 0n

    data = view.model().getData()                                               # get the data from the model
    size = data.shape[0]

    JulianDay = datetime.now().timetuple().tm_yday                              # returns 1 for January 1st
    timeOfDay = datetime.now().strftime('%H%M%S')

    # ('RecID',  'U2'),   # A1 ('S' or 'R')
    # ('Line',   'f4'),   # F10.2
    # ('Point',  'f4'),   # F10.2
    # ('Index',  'i4'),   # I1
    # ('Code',   'U2'),   # A2
    # ('Static', 'i4'),   # I4
    # ('Depth',  'f4'),   # I4
    # ('Datum',  'i4'),   # I4
    # ('Uhole',  'i4'),   # I2
    # ('Water',  'f4'),   # F6.1
    # ('East',   'f4'),   # F9.1
    # ('North',  'f4'),   # F10.1
    # ('Elev',   'f4'),   # F6.1
    # ('Day',    'i4'),   # I3
    # ('Time',   'i4') ]) # 3I2

    rpsData = np.zeros(shape=size, dtype=pntType)
    # fmt: off
    rpsData['RecID'] = 'R'
    rpsData[ 'Line'] = data['Line']
    rpsData['Point'] = data['Point']
    rpsData['Index'] = data['Index']
    rpsData[ 'Code'] = data['Code']
    rpsData[ 'East'] = data['East']
    rpsData['North'] = data['North']
    rpsData[  'Day'] = JulianDay
    rpsData[ 'Time'] = timeOfDay
    # fmt: on

    hdr = f'H00 SPS format version          SPS V2.1 revised Jan, 2006\n' f'H13 Geodetic Coordinate System  {crs.authid()}'

    with pg.BusyCursor():
        # comments='' to prevent '# ' at the start of a header line
        # delimiter ='' to prevent tabs, comma's from being inserted
        np.savetxt(fn, rpsData, delimiter='', fmt=fmt, comments='', header=hdr)

    return (size, fn)

def fileExportAsS01(parent, fileName, extension, view, crs):
    # fmt: off
    fn, selectedFilter = QFileDialog.getSaveFileName(
        parent,                                                                 # the main window
        'Save as...',                                                           # caption
        fileName + extension,                                                   # start directory + filename + extension
        'sps source file format (*.s01);;sps source file format (*.sps);;All files (*.*)', # file extensions
        # options                                                               # options -> not used
    )
    # fmt: on

    if not fn:
        return (0, '')                                                          # return 0 records, no filename given,

    extension = '.s01'                                                          # default extension value
    if selectedFilter == 'sps source file format (*.s01)':                      # select appropriate extension
        extension = '.s01'
    elif selectedFilter == 'sps source file format (*.sps)':
        extension = '.sps'

    if not fn.lower().endswith(extension):                                      # make sure file extension is okay
        fn += extension                                                         # just add the file extension

    # fmt: off
    fmt = '%1s',  '%10.2f', '%10.2f', '%1d',  '%2s',   '%4d',    '%4.1f', '%4d',   '%2d',   '%6.1f', '%9.1f', '%10.1f', '%6.1f', '%3d', '%6d'
    #     'RecID','Line',   'Point',  'Index', 'Code', 'Static', 'Depth', 'Datum', 'Uhole', 'Water', 'East',  'North',  'Elev',  'Day', 'Time'
    # Note: Point is followed by two spaces (Col 22-23 as per SPS 2.1 format)
    # fmt: on

    data = view.model().getData()                                               # get the data from the model
    size = data.shape[0]
    JulianDay = datetime.now().timetuple().tm_yday                              # returns 1 for January 1st
    timeOfDay = datetime.now().strftime('%H%M%S')
    spsData = np.zeros(shape=size, dtype=pntType)

    # fmt: off
    spsData['RecID'] = 'S'
    spsData[ 'Line'] = data['Line']
    spsData['Point'] = data['Point']
    spsData['Index'] = data['Index']
    spsData[ 'Code'] = data['Code']
    spsData[ 'East'] = data['East']
    spsData['North'] = data['North']
    spsData[  'Day'] = JulianDay
    spsData[ 'Time'] = timeOfDay
    # fmt: on

    hdr = f'H00 SPS format version          SPS V2.1 revised Jan, 2006\n' f'H13 Geodetic Coordinate System  {crs.authid()}'

    with pg.BusyCursor():
        # comments='' to prevent '# ' at the start of a header line
        # delimiter ='' to prevent tabs, comma's from being inserted
        np.savetxt(fn, spsData, delimiter='', fmt=fmt, comments='', header=hdr)

    return (size, fn)

def fileExportAsX01(parent, fileName, extension, view, crs):
    # fmt: off
    fn, selectedFilter = QFileDialog.getSaveFileName(
        parent,                                                                 # the main window
        'Save as...',                                                           # caption
        fileName + extension,                                                   # start directory + filename + extension
        'sps relation file format (*.x01);;sps relation file format (*.xps);;All files (*.*)',
        # options                                                               # options -> not used)
    )
    # fmt: on

    if not fn:
        return (0, '')                                                          # return 0 records, no filename given,

    extension = '.x01'                                                          # default extension value
    if selectedFilter == 'sps relation file format (*.x01)':                    # select appropriate extension
        extension = '.x01'
    elif selectedFilter == 'sps relation file format (*.xps)':
        extension = '.xps'

    if not fn.lower().endswith(extension):                                      # make sure file extension is okay
        fn += extension                                                         # just add the file extension

    # fmt: off
    fmt = '%1s',   '%6s',    '%8d',    '%1d',    '%1s',    '%10.2f', '%10.2f', '%1d',    '%5d',    '%5d',    '%1d',    '%10.2f', '%10.2f', '%10.2f', '%1d'
    #     'RecID', 'TapeNo', 'RecNum', 'RecInc', 'Instru', 'SrcLin', 'SrcPnt', 'SrcInd', 'ChaMin', 'ChaMax', 'ChaInc', 'RecLin', 'RecMin', 'RecMax', 'RecInd'
    # fmt: on

    # relType2 is used in the rel/rps model:
    # ('SrcLin', 'f4'),   # F10.2
    # ('SrcPnt', 'f4'),   # F10.2
    # ('SrcInd', 'i4'),   # I1
    # ('RecNum',  'i4'),  # I8
    # ('RecLin', 'f4'),   # F10.2
    # ('RecMin', 'f4'),   # F10.2
    # ('RecMax', 'f4'),   # F10.2
    # ('RecInd', 'i4'),   # I1
    # ('Uniq',   'i4'),   # check if record is unique
    # ('InSps',  'i4'),   # check if record is orphan
    # ('InRps',  'i4') ]) # check if record is orphan

    # need relType for export to xps
    # ('RecID',  'U2'),   # A1 ('X')
    # ('TapeNo', 'U8'),   # 3A2
    # ('RecNum',  'i4'),  # I8
    # ('RecInc', 'i4'),   # I1
    # ('Instru', 'U2'),   # A1
    # ('SrcLin', 'f4'),   # F10.2
    # ('SrcPnt', 'f4'),   # F10.2
    # ('SrcInd', 'i4'),   # I1
    # ('ChaMin', 'i4'),   # I5
    # ('ChaMax', 'i4'),   # I5
    # ('ChaInc', 'i4'),   # I1    (e.g. 3 to record 3C data; 4 for 4C nodes)
    # ('RecLin', 'f4'),   # F10.2
    # ('RecMin', 'f4'),   # F10.2
    # ('RecMax', 'f4'),   # F10.2
    # ('RecInd', 'i4') ]) # I1

    data = view.model().getData()                                               # get the data from the model
    size = data.shape[0]
    xpsData = np.zeros(shape=size, dtype=relType)
    xpsData['RecID'] = 'X'
    xpsData['TapeNo'] = ' tape1'
    xpsData['RecNum'] = data['RecNum']
    xpsData['RecInc'] = 1
    xpsData['Instru'] = '1'
    xpsData['SrcLin'] = data['SrcLin']
    xpsData['SrcPnt'] = data['SrcPnt']
    xpsData['SrcInd'] = data['SrcInd']
    xpsData['RecLin'] = data['RecLin']
    xpsData['RecMin'] = data['RecMin']
    xpsData['RecMax'] = data['RecMax']
    xpsData['RecInd'] = data['RecInd']

    hdr = f'H00 SPS format version          SPS V2.1 revised Jan, 2006\n' f'H13 Geodetic Coordinate System  {crs.authid()}'

    with pg.BusyCursor():
        # comments='' to prevent '# ' at the start of a header line
        # delimiter ='' to prevent tabs, comma's from being inserted
        np.savetxt(fn, xpsData, delimiter='', fmt=fmt, comments='', header=hdr)

    return (size, fn)

# add export to flat text files here.
def exportDataAsTxt(parent, fileName, extension, view):
    fn, selectedFilter = QFileDialog.getSaveFileName(
        parent,  # that's the main window
        'Save as...',  # dialog caption
        fileName + extension,  # start directory + filename
        'comma separated file (*.csv);;semicolumn separated file (*.csv);;space separated file (*.csv);;tab separated file (*.csv);;All files (*.*)',  # file extensions
        # options                                                               # options not used
    )
    if not fn:
        return (0, '')                                                          # return 0 records, no filename given,

    delimiter = ','                                                             # default delimiter value
    if selectedFilter == 'semicolumn separated file (*.csv)':                   # select appropriate delimiter
        delimiter = ';'
    elif selectedFilter == 'space separated file (*.csv)':
        delimiter = ' '
    elif selectedFilter == 'tab separated file (*.csv)':
        delimiter = '\t'

    if not fn.lower().endswith(extension):                                      # make sure file extension is okay
        fn += extension                                                         # just add the file extension

    fmt = view.getFormatList()                                                  # get the format string from the model
    hdr = view.getNameList()                                                    # get the header string from the model
    hdr = delimiter.join(hdr)                                                   # turn list into string separated by delimiter
    dat = view.model().getData()                                                # get the data from the model

    with pg.BusyCursor():
        # comments='' to prevent '# ' at the start of a header line
        # delimiter ='' to prevent tabs, comma's from being inserted
        np.savetxt(fn, dat, delimiter=delimiter, fmt=fmt, comments='', header=hdr)
    return (dat.shape[0], fn)

def calculateLineStakeTransform(spsImport) -> []:
    # See: https://stackoverflow.com/questions/47780845/solve-over-determined-system-of-linear-equations
    # See: https://stackoverflow.com/questions/31411330/solving-overdetermined-system-in-numpy-when-the-value-of-one-variable-is-already
    # See: https://glowingpython.blogspot.com/2012/03/solving-overdetermined-systems-with-qr.html
    # See: https://riptutorial.com/numpy/example/16034/find-the-least-squares-solution-to-a-linear-system-with-np-linalg-lstsq for a useful example
    # See: https://www.askpython.com/python-modules/numpy/numpy-linalg-lstsq for some examples
    # See: https://stackoverflow.com/questions/45159314/decompose-2d-transformation-matrix for Transformation Matrix Decomposition
    # See: https://math.stackexchange.com/questions/612006/decomposing-an-affine-transformation as well
    # See: https://stackoverflow.com/questions/70357473/how-to-decompose-a-2x2-affine-matrix-with-sympy
    # see: https://pyqtgraph.readthedocs.io/en/latest/api_reference/functions.html#pyqtgraph.solveBilinearTransform  for a more general solution


    nRecords = spsImport.shape[0]
    assert nRecords > 2, "Not enough records in spsImport"

    spsImport.sort(order=['Line', 'Point', 'Index'])                            # sort the data by line and point
    pointNumIncrement = spsImport['Point'][1:] - spsImport['Point'][:-1]        # get the point number increment
    pointNumIncrement = np.median(pointNumIncrement)
    assert pointNumIncrement >= 0, "Point increment is not positive"
    if pointNumIncrement == 0:
        pointNumIncrement = 1.0                                                  # handle 2D data with no point increment

    eastIncrement = spsImport['East'][1:] - spsImport['East'][:-1]              # get the east increment
    northIncrement = spsImport['North'][1:] - spsImport['North'][:-1]           # get the north increment
    pointDisIncrement = np.sqrt(eastIncrement ** 2 + northIncrement ** 2)       # get the point distance increment
    pointDisIncrement = np.median(pointDisIncrement)
    if pointDisIncrement == 0:
        pointDisIncrement = 1.0                                                  # handle 2D data with no point increment
    else:
        pointNumIncrement = pointDisIncrement / pointNumIncrement

    lineMin = spsImport['Line'][0]
    pointMin = spsImport['Point'][0]
    origX = spsImport['East'][0]
    origY = spsImport['North'][0]

    spsImport.sort(order=['Point', 'Line', 'Index'])                            # sort the data by point and line
    lineNumIncrement = spsImport['Line'][1:] - spsImport['Line'][:-1]           # get the line number increment
    lineNumIncrement = np.median(lineNumIncrement)

    eastIncrement = spsImport['East'][1:] - spsImport['East'][:-1]              # get the east increment
    northIncrement = spsImport['North'][1:] - spsImport['North'][:-1]           # get the north increment
    lineDisIncrement = np.sqrt(eastIncrement ** 2 + northIncrement ** 2)        # get the distance increment
    # see: https://stackoverflow.com/questions/1401712/how-can-the-euclidean-distance-be-calculated-with-numpy
    # distIncrement = np.linalg.norm(eastIncrement - northIncrement)            # get the distance increment
    lineDisIncrement = np.median(lineDisIncrement)
    if lineNumIncrement == 0:
        lineNumIncrement = 1.0                                                  # handle 2D data with no line increment
    else:
        lineNumIncrement = lineDisIncrement / lineNumIncrement

    # See: https://stackoverflow.com/questions/47780845/solve-over-determined-system-of-linear-equations
    x1 = np.zeros(shape=nRecords, dtype=np.float32)
    y1 = np.zeros(shape=nRecords, dtype=np.float32)
    x2 = np.zeros(shape=nRecords, dtype=np.float32)
    y2 = np.zeros(shape=nRecords, dtype=np.float32)

    x1 = spsImport['East'] - origX
    y1 = spsImport['North'] - origY
    x2 = (spsImport['Point'] - pointMin) * pointNumIncrement
    y2 = (spsImport['Line']  - lineMin) * lineNumIncrement

    l1 = np.array([np.ones(nRecords), np.zeros(nRecords), x2, np.zeros(nRecords), y2, np.zeros(nRecords)])
    l2 = np.array([np.zeros(nRecords), np.ones(nRecords), np.zeros(nRecords), x2, np.zeros(nRecords), y2])

    M1 = np.vstack([l1.T, l2.T])
    M2 = np.concatenate([x1, y1])

    # ABCDEF = np.linalg.lstsq(M1, M2)[0]                                       # the A0_B0_A1_B1_A2_B2 array is first parameter to be returned
    ABCDEF, residuals, *_ = np.linalg.lstsq(M1, M2)                             # unused rank and sing replaced by *_ to avoid warning
    myPrint(ABCDEF)
    myPrint(residuals[0] if residuals.size > 0 else 0 / M1.shape[0])

    angle1 = np.arctan2(ABCDEF[3], ABCDEF[2]) * 180.0 / np.pi                   # angle1 and angle2 are identical, providing the correct angle
    # angle2 = np.arctan2(-ABCDEF[4], ABCDEF[5]) * 180.0 / np.pi
    # angle3 = np.arctan2(ABCDEF[3], ABCDEF[5]) * 180.0 / np.pi                 # angle 3 and angle4 are NOT identical, and differ from angle1 and angle2
    # angle4 = np.arctan2(-ABCDEF[4], ABCDEF[2]) * 180.0 / np.pi

    return (origX, origY, lineMin, pointMin, lineNumIncrement, pointNumIncrement, angle1)

    # See also: EPSG:9624 (https://epsg.io/9624-method
    # A0  +  A1 * Xs  +  A2 * Ys = Xt
    # B0  +  B1 * Xs  +  B2 * Ys = Yt  ==>

    #               A0                         + A1 * Xs                 + A2 * Ys              = Xt
    #                               B0                      + B1 * Xs                 + B2 * Ys = Yt  ==>

    #               1 * A         + 0 * B      + Xs * C     +  0 * D     + Ys * E     +  0 * F  = Xt
    #               0 * A         + 1 * B      +  0 * C     + Xs * D     +  0 * E     + YS * F  = Yt  ==>

    # l1 = np.array([np.ones(N),  np.zeros(N), x2,          np.zeros(N), y2,          np.zeros(N)])
    # l2 = np.array([np.zeros(N), np.ones(N),  np.zeros(N), x2,          np.zeros(N), y2]         )

    # M1 = np.array([l1, l2])
    # M2 = np.array([x1, y1])

    # ABCD = np.linalg.lstsq(M1, M2)[0]
    # print(ABCD)

def getAliveAndDead(geom):

    if geom is None or geom.shape[0] == 0:                                      # no geometry data
        return (None, None, None, None)

    try:
        I = geom['InUse'] > 0                                                   # select the live points, if we find the column
        nLive = np.count_nonzero(I)
    except ValueError:
        nLive = geom.shape[0]                                                   # assume only live points

    nPnts = geom.shape[0]
    nDead = nPnts - nLive

    if nDead > 0:                                                               # there must be some dead points
        pntLiveE = np.zeros(shape=nLive, dtype=np.float32)                      # reserve space to display live data points
        pntLiveN = np.zeros(shape=nLive, dtype=np.float32)
        pntDeadE = np.zeros(shape=nDead, dtype=np.float32)                      # reserve space to display dead data points
        pntDeadN = np.zeros(shape=nDead, dtype=np.float32)

        pntE = geom['East']                                                     # get the northings and eastings
        pntN = geom['North']

        pntLiveE = pntE[I]                                                      # Select the live points
        pntLiveN = pntN[I]

        I = np.logical_not(I)                                                   # get the complementary points
        pntDeadE = pntE[I]                                                      # select the dead points
        pntDeadN = pntN[I]
    else:
        pntLiveE = np.zeros(shape=nLive, dtype=np.float32)                      # reserve space to display live data points
        pntLiveN = np.zeros(shape=nLive, dtype=np.float32)
        pntDeadE = None                                                         # no dead data points
        pntDeadN = None

        pntLiveE = geom['East']                                                 # initialize northings and eastings
        pntLiveN = geom['North']

    return (pntLiveE, pntLiveN, pntDeadE, pntDeadN)                             # return the 4 arrays

def convertCrs(spsImport, crsFrom: QgsCoordinateTransform, crsTo: QgsCoordinateTransform) -> bool:

    if spsImport is None or not crsFrom.isValid() or not crsTo.isValid():
        return False

    if not QgsCoordinateTransform.isTransformationPossible(crsFrom, crsTo):
        return False

    # Convert the coordinates from the source CRS to the target CRS
    spsToProjectTransform = QgsCoordinateTransform(crsFrom, crsTo, QgsProject.instance())

    if not spsToProjectTransform.isValid():                                 # no valid transform found
        return False

    if spsToProjectTransform.isShortCircuited():                            # source and destination are equivalent.
        return True

    for record in spsImport:
        # Access individual fields of the record
        x = record['East']
        y = record['North']
        z = record['Elev']

        vector = spsToProjectTransform.transform(QgsVector3D(x, y, z))
        record['East'] = vector.x()                                         # Update the record with the transformed coordinates
        record['North'] = vector.y()                                        # the CRS transformation is performed in-place on the original record.
        record['Elev'] = vector.z()

    return True
