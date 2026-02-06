"""
In this module the availability of numba is first tested.
If not available, a dummy '@jit' decorator is applied

The @jit decoration can be suppressed by disabling numba in Roll's settings menu.
This will set 'DISABLE_JIT' to True in the module numba.config.
As a result, the decorated functions are no longer precompiled.

See: https://numba.readthedocs.io/en/stable/user/jit.html for preferred way of using @jit
See: https://stackoverflow.com/questions/57774497/how-do-i-make-a-dummy-do-nothing-jit-decorator
"""
import importlib

import numpy as np
from qgis.PyQt.QtCore import QLineF, QRectF  # needed for pointsInRect

try:
    nb = importlib.import_module('numba')
except ImportError:
    nb = importlib.import_module('.nonumba', package='roll')                    # relative import requires package name


# rather than importing nonumba, try this: https://stackoverflow.com/questions/10724854/how-to-do-a-conditional-decorator-in-python


# @nb.jit((nb.types.Array(nb.float32, 3, 'C'), nb.boolean), nopython=True)      # numba needs array specs to work properly
@nb.jit(nopython=True)
def numbaFilterSlice2D(slice2D: np.ndarray, unique=False):
    # size = slice3D.shape[0]
    # fold = slice3D.shape[1]
    # para = slice3D.shape[2]

    # slice2D = slice3D.reshape(size * fold, para)                    # convert to 2D

    if unique is True:                                              # we'd like to use unique offsets
        havUnique = slice2D[:, 12]                                  # get all available cmp values belonging to this row
        useUnique = True if havUnique.min() == -1 else False        # are there any -1 records ?
    else:
        useUnique = False                                           # unique not required or not available

    if useUnique:
        I = (slice2D[:, 2] > 0) & (slice2D[:, 12] == -1)            # fold > 0 AND unique == -1
    else:
        I = slice2D[:, 2] > 0                                       # fold > 0

    slice2D = slice2D[I, :]                                         # filter the 2D slice
    return slice2D                                                  # return array, potentially with shape[0,13] when empty


@nb.jit(nopython=True)
def numbaSlice3D(slice3D: np.ndarray, unique=False):
    if unique:                                                                  # we'd like to use unique offsets; but does it make sense ?
        havUnique = slice3D[:, :, 12]                                           # get all available cmp values belonging to this slice
        useUnique = True if havUnique.min() == -1 else False                    # are there any -1 records ?
    else:
        useUnique = False                                                       # unique not required or not available

    if useUnique:
        I = (slice3D[:, :, 2] > 0) & (slice3D[:, :, 12] == -1)                  # fold > 0 AND unique == -1
    else:
        I = slice3D[:, :, 2] > 0                                                # fold > 0

    return (slice3D, I)                                                         # tuple of information (array, mask)


# it would be nice to cache the outcome of the following routine.
# See: https://github.com/numba/numba/issues/4062
# See: https://stackoverflow.com/questions/74491198/how-to-set-signature-if-use-np-array-as-an-input-in-numba
# See: https://stackoverflow.com/questions/67213411/initizalizing-a-return-list-of-tuples-in-numba
# See: https://stackoverflow.com/questions/30363253/multiple-output-and-numba-signatures
# See: https://stackoverflow.com/questions/55765255/how-do-i-specify-a-tuple-in-a-numba-vectorize-signature

# @nb.jit(nb.types.Tuple((nb.float32[:], nb.float32[:], nb.boolean))(nb.float32[:, :, :, :], nb.boolean), nopython=True)                    # numba needs array specs to work
def numbaSliceStats(slice4D: np.ndarray, unique=False):

# fmt: off
    fold    = slice4D[:, :, :,  2]                                              # we are left with 1 dimension
    offsets = slice4D[:, :, :, 10]                                              # we are left with 1 dimension
    azimuth = slice4D[:, :, :, 11]                                              # we are left with 1 dimension
    include = slice4D[:, :, :, 12]                                              # we are left with 1 dimension
# fmt: on

    if unique is True:                                                          # we'd like to use unique offsets
        useUnique = True if include.min() == -1 else False                      # are there any -1 records ?
    else:
        useUnique = False                                                       # unique not required or not available

    if useUnique:
        I = (fold > 0) & (include == -1)                                        # fold > 0 AND unique == -1
    else:
        I = fold > 0                                                            # fold value > 0

    if np.count_nonzero(I) == 0:                                                # nothing to show here
        return (None, None, True)

    offsets = offsets[I]                                                        # filter the 1D slice
    azimuth = azimuth[I]                                                        # filter the 1D slice
    return (offsets, azimuth, False)


# @nb.jit(nopython=True)
def numbaNdft_1D(kMax: float, dK: float, slice3D: np.ndarray, inclu3D: np.ndarray):
    kR = np.arange(0, kMax, dK)                                                 # numpy array with k-values [0 ... kMax]
    nK = kR.shape[0]                                                            # number of points along y-axis (size of kR array)
    nP = slice3D.shape[0]                                                       # number of points along x-axis

    radialStk = np.zeros(shape=(nP, nK), dtype=np.float32)                      # start with empty array of the right size and type

    for p in range(nP):                                                         # iterate over all points in the current direction
        offRadial = slice3D[p, :, 10]                                           # get all available offsets belonging to this row
        incRadial = inclu3D[p, :]                                               # not all points will be valid, in case of unique offsets
        n = np.count_nonzero(incRadial)                                         # normalize by actual  nr of available traces
        a = 1 / n if n > 0 else 0                                               # response will be zero for n = zero
        response = np.dot(incRadial, np.exp(2j * np.pi * kR * offRadial[:, np.newaxis])) * a
        abs_response = np.abs(response)
        log_response = np.log(abs_response) * 20.0
        radialStk[p, :] = log_response

    return radialStk


# there are three nested for loops in the following function; *** SLOW ***. Improve performance by:
# 1) use numba to get optimized precompiled code
#    see: https://www.infoworld.com/article/3622013/speed-up-your-python-with-numba.html
# 2) use numpy arrays, similar as done in the 1D transform
# 3) spawn a different process.
#    get result in an async manner http://pymotw.com/2/multiprocessing/communication.html
# 4) save results in a cache to prevent recalculation
#    see: https://docs.python.org/dev/library/functools.html#functools.lru_cache
@nb.jit(nopython=True)
def numbaNdft_2D(kMin: float, kMax: float, dK: float, offsetX: np.ndarray, offsetY: np.ndarray):

    kX = np.arange(kMin, kMax, dK)
    kY = np.arange(kMin, kMax, dK)
    nX = kX.shape[0]
    nY = kY.shape[0]
    nP = offsetX.shape[0]

    xyCellStk = np.zeros(shape=(nX, nY), dtype=np.float32)  # start with empty array of the right size and type

    for x in range(nX):                                                         # execute 3 loops; x, y, fold
        for y in range(nY):
            response = 0.0
            for p in range(nP):
                e = np.exp(2j * np.pi * (kX[x] * offsetX[p] + kY[y] * offsetY[p]))
                response += e
            abs_response = np.abs(response) / nP
            # log_response = np.round(np.log(abs_response) * 20.0, 2)           # np.round is only handy to review array contents
            log_response = np.log(abs_response) * 20.0
            xyCellStk[x, y] = log_response

    return xyCellStk


@nb.jit(nopython=True)
def numbaOffInline(slice2D: np.ndarray, ox: float):
    x__Inline = slice2D[:, 7]                                                   # get all available cmp values belonging to this row
    offInline = slice2D[:, 10]                                                  # get all available offsets belonging to this row

    x = np.empty((2 * x__Inline.size), dtype=x__Inline.dtype)
    x[0::2] = x__Inline - ox
    x[1::2] = x__Inline + ox

    y = np.empty((2 * offInline.size), dtype=offInline.dtype)
    y[0::2] = offInline
    y[1::2] = offInline

    return (x, y)


@nb.jit(nopython=True)
def numbaOffX_line(slice2D: np.ndarray, oy: float):
    y__Inline = slice2D[:, 8]                                                   # get all available cmp values belonging to this row
    offInline = slice2D[:, 10]                                                  # get all available offsets belonging to this row

    x = np.empty((2 * y__Inline.size), dtype=y__Inline.dtype)
    x[0::2] = y__Inline - oy
    x[1::2] = y__Inline + oy

    y = np.empty((2 * offInline.size), dtype=offInline.dtype)
    y[0::2] = offInline
    y[1::2] = offInline

    return (x, y)


@nb.jit(nopython=True)
def numbaAziInline(slice2D: np.ndarray, ox: float):
    x__Inline = slice2D[:, 7]                                                   # get all available cmp values belonging to this row
    offInline = slice2D[:, 11]                                                  # get all available azimuths belonging to this row

    x = np.empty((2 * x__Inline.size), dtype=x__Inline.dtype)
    x[0::2] = x__Inline - ox
    x[1::2] = x__Inline + ox

    y = np.empty((2 * offInline.size), dtype=offInline.dtype)
    y[0::2] = offInline
    y[1::2] = offInline

    return (x, y)


@nb.jit(nopython=True)
def numbaAziX_line(slice2D: np.ndarray, oy: float):
    y__Inline = slice2D[:, 8]                                                   # get all available cmp values belonging to this row
    offInline = slice2D[:, 11]                                                  # get all available azimuths belonging to this row

    x = np.empty((2 * y__Inline.size), dtype=y__Inline.dtype)
    x[0::2] = y__Inline - oy
    x[1::2] = y__Inline + oy

    y = np.empty((2 * offInline.size), dtype=offInline.dtype)
    y[0::2] = offInline
    y[1::2] = offInline

    return (x, y)


@nb.jit(nopython=True)
def numbaOffsetBin(slice2D: np.ndarray, unique=False):
    if unique is True:                                                          # we'd like to use unique offsets
        havUnique = slice2D[:, 12]                                              # get all available cmp values belonging to this row
        useUnique = True if havUnique.min() == -1 else False                    # are there any -1 records ?
    else:
        useUnique = False                                                       # unique not required or not available

    if useUnique:
        I = (slice2D[:, 2] > 0) & (slice2D[:, 12] == -1)                        # fold > 0 AND unique == -1
    else:
        I = slice2D[:, 2] > 0                                                   # fold > 0

    noData = np.count_nonzero(I) == 0
    if noData:
        return (None, None, noData)                                             # nothing to show; return

    slice2D = slice2D[I, :]                                                     # filter the 2D slice

    offsetX = slice2D[:, 5] - slice2D[:, 3]                                     # x-component of available offsets
    offsetY = slice2D[:, 6] - slice2D[:, 4]                                     # y-component of available offsets

    return (offsetX, offsetY, noData)


@nb.jit(nopython=True)
def numbaSpiderBin(slice2D: np.ndarray):                                        # slicing should already have reduced fold to account for unique fold, if need be

    foldX2 = slice2D.shape[0] * 2

    spiderSrcX = np.zeros(shape=foldX2, dtype=np.float32)                       # needed to display data points
    spiderSrcY = np.zeros(shape=foldX2, dtype=np.float32)                       # needed to display data points
    spiderRecX = np.zeros(shape=foldX2, dtype=np.float32)                       # needed to display data points
    spiderRecY = np.zeros(shape=foldX2, dtype=np.float32)                       # needed to display data points

    spiderSrcX[0::2] = slice2D[:, 3]                                            # src-x
    spiderSrcX[1::2] = slice2D[:, 7]                                            # src-x

    spiderSrcY[0::2] = slice2D[:, 4]                                            # src-y
    spiderSrcY[1::2] = slice2D[:, 8]                                            # src-y

    spiderRecX[0::2] = slice2D[:, 5]                                            # rec-x
    spiderRecX[1::2] = slice2D[:, 7]                                            # rec-x

    spiderRecY[0::2] = slice2D[:, 6]                                            # rec-y
    spiderRecY[1::2] = slice2D[:, 8]                                            # rec-y

    return (spiderSrcX, spiderSrcY, spiderRecX, spiderRecY)


def pointsInRect(pointArray: np.ndarray, rect: QRectF):
    l = rect.left()
    r = rect.right()
    t = rect.top()
    b = rect.bottom()

    return numbaPointsInRect(pointArray, l, r, t, b)


@nb.jit(nopython=True)
def numbaPointsInRect(pointArray: np.ndarray, l: float, r: float, t: float, b: float):
    I = (pointArray[:, 0] >= l) & (pointArray[:, 0] <= r) & (pointArray[:, 1] >= t) & (pointArray[:, 1] <= b)
    return I


# See: https://stackoverflow.com/questions/49907604/setting-structured-array-field-in-numba
# See: https://stackoverflow.com/questions/52409479/python-numba-accessing-structured-numpy-array-elements-as-fast-as-possible
# See: https://stackoverflow.com/questions/58786392/how-to-create-a-list-of-structured-scalars-in-numba
# See: https://stackoverflow.com/questions/60118008/accessing-structured-data-types-in-numba-vs-numpy
# See: https://stackoverflow.com/questions/74438714/numba-signature-for-structured-arrays
# See: https://stackoverflow.com/questions/53175601/what-the-best-way-to-get-structured-array-dataframe-like-structures-in-numba
# See: https://stackoverflow.com/questions/72747804/how-to-return-a-1d-structured-array-mixed-types-from-a-numba-jit-compiled-func
# See: http://numba.pydata.org/numba-doc/0.13/arrays.html#array-creation-loop-jitting
# See: https://stackoverflow.com/questions/73892609/how-exactly-to-work-with-string-arrays-in-numba
# See: https://numba.pydata.org/numba-doc/dev/reference/pysupported.html#typed-dict
# See: https://numba.pydata.org/numba-doc/0.15.1/tutorial_firststeps.html

# numType1 = nb.from_dtype(pntType1)  # create a Numba type corresponding to the Numpy dtype
# unfortunately, this isn't recognized in time for the following jit decoration
# @nb.jit('void(numType1[:], i8, f8, f8, i8, f8, f8, f4[3])', nopython=True)
# likewise, the following description isn't recognized at numba compile time
# numType1 = 'Record(  Line[type=float32;offset=0],   \
#                     Point[type=float32;offset=4],   \
#                     Index[type=int32;offset=8],     \
#                     Code[type=[unichr x 2];offset=12],  \
#                     Depth[type=float32;offset=20],  \
#                     East[type=float32;offset=24],   \
#                     North[type=float32;offset=28],  \
#                     Elev[type=float32;offset=32],   \
#                     Uniq[type=int32;offset=36],     \
#                     InXps[type=int32;offset=40],    \
#                     LocX[type=float32;offset=44],   \
#                     LocY[type=float32;offset=48];52;False)'


@nb.jit(nopython=True)
def numbaSetPointRecord(array: np.ndarray, index: int, line: float, point: float, block: int, east: float, north: float, pnt: np.ndarray) -> None:
    # pntType1 = np.dtype(
    #     [
    #         ('Line', 'f4'),  # F10.2
    #         ('Point', 'f4'),  # F10.2
    #         ('Index', 'i4'),  # I1
    #         ('Code', 'U2'),  # A2
    #         ('Depth', 'f4'),  # I4
    #         ('East', 'f4'),  # F9.1
    #         ('North', 'f4'),  # F10.1
    #         ('Elev', 'f4'),  # F6.1
    #         ('Uniq', 'i4'),  # check if record is unique
    #         ('InXps', 'i4'),  # check if record is orphan
    #         ('InUse', 'i4'),  # check if record is in use
    #         ('LocX', 'f4'),  # F9.1
    #         ('LocY', 'f4'),  # F10.1
    #     ]
    # )
    array[index]['Line'] = float(int(line))
    array[index]['Point'] = float(int(point))
    array[index]['Index'] = block % 10 + 1                                      # the single digit point index is used to indicate block nr
    array[index]['East'] = east
    array[index]['North'] = north
    array[index]['LocX'] = pnt[0]                                               # x-component of 3D-location
    array[index]['LocY'] = pnt[1]                                               # y-component of 3D-location
    array[index]['Elev'] = pnt[2]                                               # z-value not affected by CRS transform
    array[index]['Uniq'] = 1                                                    # later, we want to use Uniq == 1 to remove empty records at the end
    array[index]['InUse'] = 1                                                   # later, we want to use InUse == 1 to check if the point is active
    array[index]['InXps'] = 1                                                   # later, we want to use InXps == 1 to check for any xps orphns


@nb.jit(nopython=True)
def numbaSetRelationRecord(array: np.ndarray, index: int, srcLin: float, srcPnt: float, srcInd: int, shtRec: int, recLin: float, recMin: float, recMax: float):
    array[index]['SrcLin'] = float(int(srcLin))
    array[index]['SrcPnt'] = float(int(srcPnt))
    array[index]['SrcInd'] = srcInd
    array[index]['RecNum'] = shtRec
    array[index]['RecLin'] = int(recLin)
    array[index]['RecMin'] = float(int(recMin))
    array[index]['RecMax'] = float(int(recMax))
    array[index]['RecInd'] = srcInd
    array[index]['Uniq'] = 1    # needed for compacting array later (remove empty records)


@nb.jit(nopython=True)
def numbaFixRelationRecord(array: np.ndarray, index: int, recStkX: float):
    recMin = min(array[index]['RecMin'], int(recStkX))
    recMax = max(array[index]['RecMax'], int(recStkX))

    array[index]['RecMin'] = recMin
    array[index]['RecMax'] = recMax


def clipLineF(line: QLineF, border: QRectF) -> QLineF:

    if border.isNull():
        return QLineF(line)                                                     # don't clip against an empty rect !
    if line.isNull():
        return QLineF()                                                         # null in ?  null out !

    x1 = line.x1()                                                              # copy the line elements to individual float values
    y1 = line.y1()
    x2 = line.x2()
    y2 = line.y2()

    y_min = border.top()                                                        # copy the rect elements to individual float values
    x_min = border.left()
    y_max = border.bottom()
    x_max = border.right()

    x1, y1, x2, y2 = numbaClipLineF(x1, y1, x2, y2, x_min, x_max, y_min, y_max)
    return QLineF(x1, y1, x2, y2)                                               # return the clipped line


@nb.jit(nopython=True)
def numbaClipLineF(x1: float, y1: float, x2: float, y2: float, x_min: float, x_max: float, y_min: float, y_max: float) -> tuple:

    # Python routine to implement Cohen Sutherland algorithm for line clipping.
    # See: https://www.geeksforgeeks.org/line-clipping-set-1-cohen-sutherland-algorithm/
    # See: https://en.wikipedia.org/wiki/Cohen%E2%80%93Sutherland_algorithm
    # See: https://www.geeksforgeeks.org/line-clipping-set-2-cyrus-beck-algorithm/?ref=rp

    # Define region codes
    INSIDE = 0                                                                  # 0000
    LEFT = 1                                                                    # 0001
    RIGHT = 2                                                                   # 0010
    BOTTOM = 4                                                                  # 0100
    TOP = 8  	                                                                # 1000

    # Inner function to compute the region code for a point(x, y) relative to the border of the rectangle
    def computeCode(x, y):
        code = INSIDE
        if x < x_min:                                                           # to the left of rectangle
            code |= LEFT
        elif x > x_max:                                                         # to the right of rectangle
            code |= RIGHT
        if y < y_min:                                                           # below the rectangle
            code |= BOTTOM
        elif y > y_max:                                                         # above the rectangle
            code |= TOP
        return code

    # Compute region codes for P1, P2
    code1 = computeCode(x1, y1)
    code2 = computeCode(x2, y2)
    accept = False

    while True:                                                                 # Keep doing this, till we can escape

        if code1 == 0 and code2 == 0:                                           # both endpoints lie within rectangle
            accept = True
            break

        if (code1 & code2) != 0:                                                # both endpoints are outside rectangle
            break

        # If we get here, the line needs clipping
        # At least one of the points is outside of rect, select it

        x = 1.0
        y = 1.0

        if code1 != 0:
            code_out = code1
        else:
            code_out = code2

        # Find intersection point using formulas
        #   y = y1 + slope * (x - x1),
        #   x = x1 + (1 / slope) * (y - y1)
        if code_out & TOP:  		                                            # point is above the clip rectangle
            x = x1 + (x2 - x1) * (y_max - y1) / (y2 - y1)
            y = y_max

        elif code_out & BOTTOM:  		                                        # point is below the clip rectangle
            x = x1 + (x2 - x1) * (y_min - y1) / (y2 - y1)
            y = y_min

        elif code_out & RIGHT:  		                                        # point is to the right of the clip rectangle
            y = y1 + (y2 - y1) * (x_max - x1) / (x2 - x1)
            x = x_max

        elif code_out & LEFT:  		                                            # point is to the left of the clip rectangle
            y = y1 + (y2 - y1) * (x_min - x1) / (x2 - x1)
            x = x_min

        # Now an intersection point (x, y) has been found,
        # we replace the point outside clipping rectangle
        # by the intersection point
        if code_out == code1:
            x1 = x
            y1 = y
            code1 = computeCode(x1, y1)
        else:
            x2 = x
            y2 = y
            code2 = computeCode(x2, y2)

    if accept:
        return (x1, y1, x2, y2)                                                 # return the clipped line

    return (0.0, 0.0, 0.0, 0.0)                                                 # return a null line


@nb.jit(nopython=True, parallel=True)
def pointInPolygon(xy, poly):
    # See: https://stackoverflow.com/questions/52471590/use-multithreading-in-numba
    D = np.empty(len(xy), dtype=bool)
    n = len(poly)
    for i in range(1, len(D) - 1):
        inside = False
        p2x = 0.0
        p2y = 0.0
        xints = 0.0
        p1x, p1y = poly[0]
        x = xy[i][0]
        y = xy[i][1]
        for i in range(n + 1):
            p2x, p2y = poly[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xints:
                            inside = not inside
            p1x, p1y = p2x, p2y
        D[i] = inside
    return D
