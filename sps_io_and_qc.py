from datetime import datetime

import numpy as np
import pyqtgraph as pg
# from numpy.compat import asstr
from qgis.PyQt.QtCore import QFile, QIODevice, QTextStream
from qgis.PyQt.QtWidgets import QFileDialog

from .functions import toFloat, toInt

# sps file formats
# See: https://seg.org/Portals/0/SEG/News%20and%20Resources/Technical%20Standards/seg_sps_rev2.1.pdf
# See: https://www.tutorialsandyou.com/python/numpy-data-types-66.html

# In the types below, first the full SPS format is shown and then some derived versions
#
#################### 'Field'   np.type  Fortran type
pntType = np.dtype(
    [
        ('RecID', 'U2'),  # A1 ('S' or 'R')
        ('Line', 'f4'),  # F10.2
        ('Point', 'f4'),  # F10.2
        ('Index', 'i4'),  # I1
        ('Code', 'U2'),  # A2
        ('Static', 'i4'),  # I4
        ('Depth', 'f4'),  # I4
        ('Datum', 'i4'),  # I4
        ('Uhole', 'i4'),  # I2
        ('Water', 'f4'),  # F6.1
        ('East', 'f4'),  # F9.1
        ('North', 'f4'),  # F10.1
        ('Elev', 'f4'),  # F6.1
        ('Day', 'i4'),  # I3
        ('Time', 'i4'),  # 3I2
    ]
)

# this point-type includes local x, y coordinates
pntType1 = np.dtype(
    [
        ('Line', 'f4'),  # F10.2
        ('Point', 'f4'),  # F10.2
        ('Index', 'i4'),  # I1
        ('Code', 'U2'),  # A2
        ('Depth', 'f4'),  # I4
        ('East', 'f4'),  # F9.1
        ('North', 'f4'),  # F10.1
        ('Elev', 'f4'),  # F6.1
        ('Uniq', 'i4'),  # check if record is unique
        ('InXps', 'i4'),  # check if record is orphan
        ('LocX', 'f4'),  # F9.1
        ('LocY', 'f4'),  # F10.1
    ]
)

pntType2 = np.dtype(
    [
        ('Line', 'f4'),  # F10.2
        ('Point', 'f4'),  # F10.2
        ('Index', 'i4'),  # I1
        ('Code', 'U2'),  # A2
        ('Depth', 'f4'),  # I4
        ('East', 'f4'),  # F9.1
        ('North', 'f4'),  # F10.1
        ('Elev', 'f4'),  # F6.1
        ('Uniq', 'i4'),  # check if record is unique
        ('InXps', 'i4'),  # check if record is orphan
    ]
)

# pntType3 is used to shorten the SPS/RPS records to Line-Point-Index records
pntType3 = np.dtype([('Line', 'f4'), ('Point', 'f4'), ('Index', 'i4')])  # F10.2  # F10.2  # I1

pntType4 = np.dtype(
    [
        ('Line', 'f4'),  # F10.2
        ('Point', 'f4'),  # F10.2
        ('Index', 'i4'),  # I1
        ('Code', 'U2'),  # A2
        ('Depth', 'f4'),  # I4
        ('East', 'f4'),  # F9.1
        ('North', 'f4'),  # F10.1
        ('Elev', 'f4'),  # F6.1
        ('Day', 'i4'),  # I3
        ('Hour', 'i1'),  # I2
        ('Min', 'i1'),  # I2
        ('Sec', 'i1'),  # I2
        ('Stub', 'i1'),  # I2
    ]
)

pntType5 = np.dtype([('LocX', 'f4'), ('LocY', 'f4'), ('Elev', 'f4')])  # F9.1  # F10.1   # F6.1

relType = np.dtype(
    [
        ('RecID', 'U2'),  # A1 ('X')
        ('TapeNo', 'U8'),  # 3A2
        ('RecNo', 'i4'),  # I8
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
    ]
)

relType2 = np.dtype(
    [
        ('SrcLin', 'f4'),  # F10.2
        ('SrcPnt', 'f4'),  # F10.2
        ('SrcInd', 'i4'),  # I1
        ('RecNo', 'i4'),  # I8
        ('RecLin', 'f4'),  # F10.2
        ('RecMin', 'f4'),  # F10.2
        ('RecMax', 'f4'),  # F10.2
        ('RecInd', 'i4'),  # I1
        ('Uniq', 'i4'),  # check if record is unique
        ('InSps', 'i4'),  # check if record is orphan
        ('InRps', 'i4'),  # check if record is orphan
    ]
)

relType3 = np.dtype([('RecLin', 'f4'), ('RecMin', 'f4'), ('RecMax', 'f4'), ('RecInd', 'i4')])  # F10.2  # F10.2  # F10.2  # I1

anaType = np.dtype(
    [
        ('SrcX', np.float32),
        ('SrcY', np.float32),  # Src (x, y)
        ('RecX', np.float32),
        ('RecY', np.float32),  # Rec (x, y)
        ('CmpX', np.float32),
        ('CmpY', np.float32),  # Cmp (x, y); needed for spider plot when binning against dipping plane
        ('SrcL', np.int32),
        ('SrcP', np.int32),  # SrcLine, SrcPoint
        ('RecL', np.int32),
        ('RecP', np.int32),
    ]
)   # RecLine, RecPoint


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

            lin = toFloat(line[fmt['line'][0] : fmt['line'][1]].strip())
            pnt = toFloat(line[fmt['point'][0] : fmt['point'][1]].strip())
            idx = toInt(line[fmt['index'][0] : fmt['index'][1]].strip())
            cod = line[fmt['code'][0] : fmt['code'][1]].strip()
            dep = toFloat(line[fmt['depth'][0] : fmt['depth'][1]].strip())
            eas = toFloat(line[fmt['east'][0] : fmt['east'][1]].strip())
            nor = toFloat(line[fmt['north'][0] : fmt['north'][1]].strip())
            ele = toFloat(line[fmt['elev'][0] : fmt['elev'][1]].strip())

            record = (lin, pnt, idx, cod, dep, eas, nor, ele, 0, 0, 0.0, 0.0)
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

            pt0 = fmt['point'][0]
            pt1 = fmt['point'][1]
            pnt = line[pt0:pt1]
            pnt = toFloat(line[pt0:pt1])

            lin = toFloat(line[fmt['line'][0] : fmt['line'][1]].strip())
            pnt = toFloat(line[fmt['point'][0] : fmt['point'][1]].strip())
            idx = toInt(line[fmt['index'][0] : fmt['index'][1]].strip())
            cod = line[fmt['code'][0] : fmt['code'][1]].strip()
            dep = toFloat(line[fmt['depth'][0] : fmt['depth'][1]].strip())
            eas = toFloat(line[fmt['east'][0] : fmt['east'][1]].strip())
            nor = toFloat(line[fmt['north'][0] : fmt['north'][1]].strip())
            ele = toFloat(line[fmt['elev'][0] : fmt['elev'][1]].strip())

            record = (lin, pnt, idx, cod, dep, eas, nor, ele, 0, 0, 0.0, 0.0)
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
            # However, we move RecNo to the fourth place in the xps record
            recNo = toInt(line[fmt['recNo'][0] : fmt['recNo'][1]].strip())
            srcLin = toFloat(line[fmt['srcLin'][0] : fmt['srcLin'][1]].strip())
            srcPnt = toFloat(line[fmt['srcPnt'][0] : fmt['srcPnt'][1]].strip())
            srcInd = toInt(line[fmt['srcInd'][0] : fmt['srcInd'][1]].strip())
            recLin = toFloat(line[fmt['recLin'][0] : fmt['recLin'][1]].strip())
            recMin = toFloat(line[fmt['recMin'][0] : fmt['recMin'][1]].strip())
            recMax = toFloat(line[fmt['recMax'][0] : fmt['recMax'][1]].strip())
            recInd = toInt(line[fmt['recInd'][0] : fmt['recInd'][1]].strip())

            record = (srcLin, srcPnt, srcInd, recNo, recLin, recMin, recMax, recInd, 0, 0, 0)
            resultArray[index] = record
            index += 1
        f.close()

    if index < resultArray.shape[0]:
        resultArray.resize(index, refcheck=False)        # See: https://numpy.org/doc/stable/reference/generated/numpy.ndarray.resize.html

    return index


def markUniqueRPSrecords(rpsImport, sort=True) -> int:
    # See: https://stackoverflow.com/questions/51933936/python-3-6-type-checking-numpy-arrays-and-use-defined-classes for type checking
    # See: https://stackoverflow.com/questions/12569452/how-to-identify-numpy-types-in-python same thing
    # See: https://stackoverflow.com/questions/11585793/are-numpy-arrays-passed-by-reference for passing a numpy array by reference
    # See: https://numpy.org/doc/stable/reference/generated/numpy.ndarray.sort.html for sorting in place
    if rpsImport is None:
        return -1

    rpsUnique, rpsIndices = np.unique(rpsImport, return_index=True)

    for index in np.nditer(rpsIndices):
        rpsImport[index]['Uniq'] = 1

    if sort:
        rpsImport.sort(order=['Index', 'Line', 'Point'])

    nUnique = rpsUnique.shape[0]
    return nUnique


def markUniqueSPSrecords(spsImport, sort=True) -> int:
    if spsImport is None:
        return -1

    spsUnique, spsIndices = np.unique(spsImport, return_index=True)

    for index in np.nditer(spsIndices):
        spsImport[index]['Uniq'] = 1

    if sort:
        spsImport.sort(order=['Index', 'Line', 'Point'])

    nUnique = spsUnique.shape[0]
    return nUnique


def markUniqueXPSrecords(xpsImport, sort=True) -> int:
    if xpsImport is None:
        return -1

    xpsUnique, xpsIndices = np.unique(xpsImport, return_index=True)

    for index in np.nditer(xpsIndices):
        xpsImport[index]['Uniq'] = 1

    if sort:
        xpsImport.sort(order=['SrcInd', 'SrcLin', 'SrcPnt', 'RecInd', 'RecLin', 'RecMin', 'RecMax'])

    nUnique = xpsUnique.shape[0]
    return nUnique


def calcMaxXPStraces(xpsImport) -> int:
    last = xpsImport['RecMax']                                                # get nr of traces from xps data
    first = xpsImport['RecMin']
    total = last - first
    traces = int(total.sum() + total.shape[0])
    return traces


def findSrcOrphans(spsImport, xpsImport) -> (int, int):
    if spsImport is None or xpsImport is None:
        return (-1, -1)

    # pntType3 = np.dtype([('Line',   'f4'),   # F10.2
    #                      ('Point',  'f4'),   # F10.2
    #                      ('Index',  'i4'),   # I1
    nSps = spsImport.shape[0]
    nXps = xpsImport.shape[0]

    # shorten the SPS records to Line-Point-Index records
    spsShort = np.zeros(shape=nSps, dtype=pntType3)
    spsShort['Line'] = spsImport['Line']
    spsShort['Point'] = spsImport['Point']
    spsShort['Index'] = spsImport['Index']

    # shorten the XPS records to Line-Point-Index records
    xpsShort = np.zeros(shape=nXps, dtype=pntType3)
    xpsShort['Line'] = xpsImport['SrcLin']
    xpsShort['Point'] = xpsImport['SrcPnt']
    xpsShort['Index'] = xpsImport['SrcInd']

    # find unique records in (shorted) xps array
    xpsUnique = np.unique(xpsShort)

    # find unique records in (shorted) sps array
    spsUnique = np.unique(spsShort)

    # find unique xps records present in (shorted) sps array
    spsMask = np.isin(spsShort, xpsUnique, assume_unique=False)
    intMask = 1 * spsMask
    spsImport['InXps'] = np.asarray(intMask)                                    # Update the sps array with 'unique' mask

    nXpsOrphans = nSps - intMask.sum()                                          # sps-records contain 'nXpsOrphans' xps-orphans

    # find unique sps elements present in (shorted) xps array
    xpsMask = np.isin(xpsShort, spsUnique, assume_unique=False)
    intMask = 1 * xpsMask
    xpsImport['InSps'] = np.asarray(intMask)                                    # Update the xps array with 'unique' mask

    nSpsOrphans = nXps - intMask.sum()                                          # xps-records contain 'nSpsOrphans' sps-orphans

    return (nSpsOrphans, nXpsOrphans)


def findRecOrphans(rpsImport, xpsImport) -> (int, int):
    if rpsImport is None or xpsImport is None:
        return (-1, -1)

    nRps = rpsImport.shape[0]
    nXps = xpsImport.shape[0]

    # find unique rps elements present in (shorted) xps array
    xpsShort = np.zeros(shape=nXps, dtype=relType3)
    xpsShort['RecLin'] = xpsImport['RecLin']
    xpsShort['RecMin'] = xpsImport['RecMin']
    xpsShort['RecMax'] = xpsImport['RecMax']
    xpsShort['RecInd'] = xpsImport['RecInd']

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
    rpsShort = np.zeros(shape=nRps, dtype=pntType3)
    rpsShort['Line'] = rpsImport['Line']
    rpsShort['Point'] = rpsImport['Point']
    rpsShort['Index'] = rpsImport['Index']

    # shorten the XPS records to Line-Point-Index records
    xpsShortMin = np.zeros(shape=nXps, dtype=pntType3)
    xpsShortMin['Line'] = xpsImport['RecLin']
    xpsShortMin['Point'] = xpsImport['RecMin']
    xpsShortMin['Index'] = xpsImport['RecInd']

    xpsShortMax = np.zeros(shape=nXps, dtype=pntType3)
    xpsShortMax['Line'] = xpsImport['RecLin']
    xpsShortMax['Point'] = xpsImport['RecMin']
    xpsShortMax['Index'] = xpsImport['RecInd']

    # find unique xps records from (shorted) rps array
    rpsUnique = np.unique(rpsShort)
    xpsMaskMin = np.isin(xpsShortMin, rpsUnique, assume_unique=False)
    xpsMaskMax = np.isin(xpsShortMax, rpsUnique, assume_unique=False)
    xpsMask = np.logical_and(xpsMaskMin, xpsMaskMax)
    intMask = 1 * xpsMask
    xpsImport['InRps'] = np.asarray(intMask)                                    # Update the xps array with 'unique' mask

    xpsImport.sort(order=['RecInd', 'RecLin', 'RecMin', 'RecMax', 'SrcLin', 'SrcPnt', 'SrcInd'])
    rpsImport.sort(order=['Index', 'Line', 'Point'])

    nSpsOrphans = nXps - intMask.sum()                                          # xps-records contain 'nSpsOrphans' sps-orphans
    nXpsOrphans = rpsImport['InXps'].sum()

    return (nSpsOrphans, nXpsOrphans)


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


def fileExportAsR01(parent, fileName, data, crs):

    fn, selectedFilter = QFileDialog.getSaveFileName(
        parent,  # the main window
        'Save as...',  # caption
        fileName,  # start directory + filename + extension
        'sps receiver file format (*.r01);;sps receiver file format (*.rps);;All files (*.*)',
    )                                                      # file extensions (options -> not used)

    if not fn:
        return (None, 0)

    extension = '.r01'                                                          # default extension value

    if selectedFilter == 'sps receiver file format (*.r01)':                    # select appropriate extension
        extension = '.r01'
    elif selectedFilter == 'sps receiver file format (*.rps)':
        extension = '.rps'

    if not fn.lower().endswith(extension):                                      # make sure file extension is okay
        fn += extension                                                         # just add the file extension

    fmt = '%1s', '%10.2f', '%10.2f  ', '%1d', '%2s', '%4d', '%4.1f', '%4d', '%2d', '%6.1f', '%9.1f', '%10.1f', '%6.1f', '%3d', '%6d'
    #     'RecID','Line',   'Point',    'Index', 'Code', 'Static', 'Depth', 'Datum', 'Uhole', 'Water', 'East',  'North',  'Elev', 'Day',  'Time'
    # Note: Point is followed by two spaces (Col 22-23 as per SPS 2.1 format)

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

    rpsData['RecID'] = 'R'
    rpsData['Line'] = data['Line']
    rpsData['Point'] = data['Point']
    rpsData['Index'] = data['Index']
    rpsData['Code'] = data['Code']
    rpsData['East'] = data['East']
    rpsData['North'] = data['North']
    rpsData['Day'] = JulianDay
    rpsData['Time'] = timeOfDay

    hdr = f'H00 SPS format version          SPS V2.1 revised Jan, 2006\n' f'H13 Geodetic Coordinate System  {crs.authid()}'

    with pg.BusyCursor():
        # delimiter ='' to prevent tabs, comma's from occurring
        # comments='' to prevent '# ' at the start of a header line
        np.savetxt(fn, rpsData, delimiter='', fmt=fmt, comments='', header=hdr)

    return (fn, size)


def fileExportAsS01(parent, fileName, data, crs):

    fn, selectedFilter = QFileDialog.getSaveFileName(
        parent, 'Save as...', fileName, 'sps source file format (*.s01);;sps source file format (*.sps);;All files (*.*)'  # the main window  # caption  # start directory + filename + extension
    )                                                      # file extensions (options -> not used)

    if not fn:
        return (None, 0)

    extension = '.s01'                                                          # default extension value

    if selectedFilter == 'sps source file format (*.s01)':                      # select appropriate extension
        extension = '.s01'
    elif selectedFilter == 'sps source file format (*.sps)':
        extension = '.sps'

    if not fn.lower().endswith(extension):                                      # make sure file extension is okay
        fn += extension                                                         # just add the file extension

    fmt = '%1s', '%10.2f', '%10.2f  ', '%1d', '%2s', '%4d', '%4.1f', '%4d', '%2d', '%6.1f', '%9.1f', '%10.1f', '%6.1f', '%3d', '%6d'
    #     'RecID','Line',   'Point',    'Index', 'Code', 'Static', 'Depth', 'Datum', 'Uhole', 'Water', 'East',  'North',  'Elev', 'Day',  'Time'
    # Note: Point is followed by two spaces (Col 22-23 as per SPS 2.1 format)

    size = data.shape[0]
    JulianDay = datetime.now().timetuple().tm_yday                              # returns 1 for January 1st
    timeOfDay = datetime.now().strftime('%H%M%S')
    spsData = np.zeros(shape=size, dtype=pntType)

    spsData['RecID'] = 'S'
    spsData['Line'] = data['Line']
    spsData['Point'] = data['Point']
    spsData['Index'] = data['Index']
    spsData['Code'] = data['Code']
    spsData['East'] = data['East']
    spsData['North'] = data['North']
    spsData['Day'] = JulianDay
    spsData['Time'] = timeOfDay

    hdr = f'H00 SPS format version          SPS V2.1 revised Jan, 2006\n' f'H13 Geodetic Coordinate System  {crs.authid()}'

    with pg.BusyCursor():
        # delimiter ='' to prevent tabs, comma's from occurring
        np.savetxt(fn, spsData, delimiter='', fmt=fmt, comments='', header=hdr)

    return (fn, size)


def fileExportAsX01(parent, fileName, data, crs):

    fn, selectedFilter = QFileDialog.getSaveFileName(
        parent,  # the main window
        'Save as...',  # caption
        fileName,  # start directory + filename + extension
        'sps relation file format (*.x01);;sps relation file format (*.xps);;All files (*.*)',
    )                                                      # file extensions (options -> not used)

    if not fn:
        return (None, 0)

    extension = '.x01'                                                          # default extension value

    if selectedFilter == 'sps relation file format (*.x01)':                    # select appropriate extension
        extension = '.x01'
    elif selectedFilter == 'sps relation file format (*.xps)':
        extension = '.xps'

    if not fn.lower().endswith(extension):                                      # make sure file extension is okay
        fn += extension                                                         # just add the file extension

    fmt = '%1s', '%6s', '%8d', '%1d', '%1s', '%10.2f', '%10.2f', '%1d', '%5d', '%5d', '%1d', '%10.2f', '%10.2f', '%10.2f', '%1d'
    # 'RecID', 'TapeNo', 'RecNo', 'RecInc', 'Instru', 'SrcLin', 'SrcPnt', 'SrcInd', 'ChaMin', 'ChaMax', 'ChaInc', 'RecLin', 'RecMin', 'RecMax', 'RecInd'

    # relType2 used in the rel/rps model:
    # ('SrcLin', 'f4'),   # F10.2
    # ('SrcPnt', 'f4'),   # F10.2
    # ('SrcInd', 'i4'),   # I1
    # ('RecNo',  'i4'),   # I8
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
    # ('RecNo',  'i4'),   # I8
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

    size = data.shape[0]
    xpsData = np.zeros(shape=size, dtype=relType)
    xpsData['RecID'] = 'X'
    xpsData['TapeNo'] = ' tape1'
    xpsData['RecNo'] = data['RecNo']
    xpsData['RecInc'] = 1
    xpsData['Instru'] = '1'
    xpsData['SrcLin'] = data['SrcLin']
    xpsData['SrcPnt'] = data['SrcPnt']
    xpsData['SrcInd'] = data['SrcInd']
    xpsData['RecLin'] = data['RecLin']
    xpsData['RecMin'] = data['RecMin']
    xpsData['RecMax'] = data['RecMax']
    xpsData['RecInd'] = data['RecInd']

    # delimiter = ''                                        # use this elsewhere
    # format = asstr(delimiter).join(map(asstr, fmt))

    hdr = f'H00 SPS format version          SPS V2.1 revised Jan, 2006\n' f'H13 Geodetic Coordinate System  {crs.authid()}'

    with pg.BusyCursor():
        # delimiter ='' to prevent tabs, comma's from occurring
        np.savetxt(fn, xpsData, delimiter='', fmt=fmt, comments='', header=hdr)

    return (fn, size)


def calculateLineStakeTransform(spsImport) -> []:
    # See: https://stackoverflow.com/questions/47780845/solve-over-determined-system-of-linear-equations
    # See: https://stackoverflow.com/questions/31411330/solving-overdetermined-system-in-numpy-when-the-value-of-one-variable-is-already
    # See: https://glowingpython.blogspot.com/2012/03/solving-overdetermined-systems-with-qr.html
    # See: https://riptutorial.com/numpy/example/16034/find-the-least-squares-solution-to-a-linear-system-with-np-linalg-lstsq for a useful example
    # See: https://www.askpython.com/python-modules/numpy/numpy-linalg-lstsq for some examples
    # See: https://stackoverflow.com/questions/45159314/decompose-2d-transformation-matrix for Transformation Matrix Decomposition
    # See: https://math.stackexchange.com/questions/612006/decomposing-an-affine-transformation as well
    # See: https://stackoverflow.com/questions/70357473/how-to-decompose-a-2x2-affine-matrix-with-sympy

    nRecords = spsImport.shape[0]

    x1 = np.zeros(shape=nRecords, dtype=np.float32)
    y1 = np.zeros(shape=nRecords, dtype=np.float32)
    x2 = np.zeros(shape=nRecords, dtype=np.float32)
    y2 = np.zeros(shape=nRecords, dtype=np.float32)

    x1 = spsImport['East']
    y1 = spsImport['North']
    x2 = spsImport['Point']
    y2 = spsImport['Line']

    # print (x1)
    # print (y1)
    # print (x2)
    # print (y2)

    # l1 = np.array([np.ones(nRecords),  np.zeros(nRecords), x2, y2])
    # l2 = np.array([np.zeros(nRecords), np.ones(nRecords),  y2, x2])

    l1 = np.array([np.ones(nRecords), np.zeros(nRecords), x2, np.zeros(nRecords), y2, np.zeros(nRecords)])
    l2 = np.array([np.zeros(nRecords), np.ones(nRecords), np.zeros(nRecords), x2, np.zeros(nRecords), y2])

    # print (l1)
    # print (l2)

    M1 = np.vstack([l1.T, l2.T])
    M2 = np.concatenate([x1, y1])

    # print (M1)
    # print (M2)

    # ABCDEF = np.linalg.lstsq(M1, M2)[0]                                       # A0_B0_A1_B1_A2_B2 array
    ABCDEF, residuals, *_ = np.linalg.lstsq(M1, M2)                             # unused rank, sing replaced by *_  # A0_B0_A1_B1_A2_B2 array

    print(ABCDEF)
    if residuals:
        print(residuals[0] / M1.shape[0])

    return ABCDEF   # type: ignore

    # I have a rather simple system of equations of the form:

    # 1*A + 0*B + x2*C + y2*D = x1
    # 0*A + 1*B + y2*C + x2*D = y1

    # where the pairs (x1,y1) and (x2,y2) are known floats of length N (the system is over-determined), and I need to solve for the A, B, C, D parameters.
    # I've been playing around with numpy.linalg.lstsq but I can't seem to get the shapes of the matrices right. This is what I have

    # import numpy as np

    # N = 10000
    # x1, y1 = np.random.uniform(0., 5000., (2, N))
    # x2, y2 = np.random.uniform(0., 5000., (2, N))

    # # 1 * A + 0 * B + x2 * C + y2 * D = x1
    # # 0 * A + 1 * B + y2 * C + x2 * D = y1

    # l1 = np.array([np.ones(N), np.zeros(N), x2, y2])
    # l2 = np.array([np.zeros(N), np.ones(N), y2, x2])

    # See: EPSG:9624 (https://epsg.io/9624-method
    # A0  +  A1 * Xs  +  A2 * Ys = Xt
    # B0  +  B1 * Xs  +  B2 * Ys = Yt  ==>

    #               A0                         + A1 * Xs                 + A2 * Ys              = Xt
    #                               B0                      + B1 * Xs                 + B2 * Ys = Yt  ==>
    #               1 * A         + 0 * B      + Xs * C     +  0 * D     + Ys * E     +  0 * F  = Xt
    #               0 * A         + 1 * B      +  0 * C     + Xs * D     +  0 * E     + YS * F  = Yt  ==>
    # l1 = np.array([np.ones(N),  np.zeros(N), x2,          np.zeros(N), y2,          np.zeros(N)])
    # l2 = np.array([np.zeros(N), np.ones(N),  np.zeros(N), x2,          np.zeros(N), y2])

    # M1 = np.array([l1, l2])
    # M2 = np.array([x1, y1])

    # ABCD = np.linalg.lstsq(M1, M2)[0]
    # print(ABCD)

    ####################################################

    # Keeping everything else fixed, changing M1 and M2 to

    # M1 = np.vstack([l1.T, l2.T])
    # M2 = np.concatenate([x1, y1])

    # should do the job.

    ###################################################
    # See: EPSG:9624 (https://epsg.io/9624-method
    # Note: These formulas have been transcribed from EPSG Guidance Note #7-2.

    # XT   =  A0  +  A1 * XS  +  A2 * YS
    # YT   =  B0  +  B1 * XS  +  B2 * YS
    # where
    # XT , YT  are the coordinates of a point P in the target coordinate reference system;
    # XS , YS   are the coordinates of P in the source coordinate reference system.

    # 1*A + 0*B + x2*C + y2*D = x1
    # 0*A + 1*B + y2*C + x2*D = y1

    #  x1 = 1*A + 0*B + x2*C + y2*D
    #  y1 = 0*A + 1*B + y2*C + x2*D

    #  x1 = A + C * x2 + D * y2 -> C = A1 = B2
    #  y1 = B + D * x2 + C * y2 -> D = B1 = A2 This solution is less universe than EPSG:9624 allows
    #
    # Reversibility
    # The reverse transformation is another affine transformation using the same formulas but with different parameter values.
    # The reverse parameter values, indicated by a prime (’), can be calculated from those of the forward transformation as follows:

    # D    = A1 * B2   –   A2 * B1
    # A0’ = (A2 * B0   –   B2 * A0) / D
    # B0’ = (B1 * A0   –   A1 * B0) / D
    # A1’ = +B2 / D
    # A2’ = – A2 / D
    # B1’ = – B1 / D
    # B2’ = +A1 / D

    # Then
    # XS =  A0' + A1' * XT  +  A2' * YT
    # YS =  B0' + B1' * XT  +  B2' * YT


def getRecGeometry(recGeom, connect=False):
    if recGeom is None:
        return (None, None, None)

    nRec = recGeom.shape[0]
    recCoordE = np.zeros(shape=nRec, dtype=np.float32)                          # needed to display data points
    recCoordN = np.zeros(shape=nRec, dtype=np.float32)
    recCoordI = None

    recCoordE = recGeom['East']                                                 # initialize northings and eastings
    recCoordN = recGeom['North']

    # source_list = [8, 4, 7, 3, 6, 1, 9]
    # for x in source_list[:-1]:
    #     print(x)

    if connect:
        recCoordI = np.zeros(shape=nRec, dtype=np.int32)
        lines = recGeom['Line']
        for index, line in enumerate(lines[:-1]):                               # do this for all points, apart from the last one
            nextLine = lines[index + 1]
            if line == nextLine:
                recCoordI[index] = 1                                            # yes; they sit on the same rec line

    return (recCoordE, recCoordN, recCoordI)


def getSrcGeometry(srcGeom, connect=False):
    if srcGeom is None:
        return (None, None, None)

    nSrc = srcGeom.shape[0]
    srcCoordE = np.zeros(shape=nSrc, dtype=np.float32)                          # needed to display data points
    srcCoordN = np.zeros(shape=nSrc, dtype=np.float32)
    srcCoordI = None

    srcCoordE = srcGeom['East']                                                 # initialize northings and eastings
    srcCoordN = srcGeom['North']

    if connect:
        srcCoordI = np.zeros(shape=nSrc, dtype=np.int32)
        lines = srcGeom['Point']
        for index, line in enumerate(lines[:-1]):                               # do this for all points, apart from the last one
            nextLine = lines[index + 1]
            if line == nextLine:
                srcCoordI[index] = 1                                            # yes; they sit on the same src line

    return (srcCoordE, srcCoordN, srcCoordI)
