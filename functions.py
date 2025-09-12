# Python routine to implement Cohen Sutherland algorithm for line clipping.
# See: https://www.geeksforgeeks.org/line-clipping-set-1-cohen-sutherland-algorithm/
# See: https://en.wikipedia.org/wiki/Cohen%E2%80%93Sutherland_algorithm
# See: https://www.geeksforgeeks.org/line-clipping-set-2-cyrus-beck-algorithm/?ref=rp

try:    # need to TRY importing numba, only to see if it is available
    haveNumba = True
    import numba  # pylint: disable=W0611
except ImportError:
    haveNumba = False

try:    # need to TRY importing ptvsd, only to see if it is available
    havePtvsd = True
    import ptvsd  # pylint: disable=W0611
except ImportError as ie:
    havePtvsd = False


import configparser
import importlib
import math
import os
import pickle
import re
import sys
from pathlib import Path

import numpy as np
import pyqtgraph as pg
import rasterio as rio
import wellpathpy as wp
from pyqtgraph.parametertree.parameterTypes import QtEnumParameter
from qgis.core import QgsGeometry, QgsPointXY
from qgis.PyQt.QtCore import PYQT_VERSION_STR, QT_VERSION_STR, QLineF, QPointF, QRectF, Qt
from qgis.PyQt.QtGui import QColor, QPen, QPolygonF, QTransform, QVector3D

from . import config  # used to pass initial settings


def myPrint(*args, **kwargs):                                                   # print function that can be suppressed
    if config.debug:
        print(*args, **kwargs)


# See: https://www.oreilly.com/library/view/python-cookbook/0596001673/ch14s08.html for introspective functions
def whoamI():
    return sys._getframe(1).f_code.co_name                                      # pylint: disable=W0212 # unfortunately need access to protected member


def lineNo():
    return sys._getframe(1).f_lineno                                            # pylint: disable=W0212 # unfortunately need access to protected member


def callerName():
    try:
        caller = sys._getframe(2)                                               # pylint: disable=W0212 # unfortunately need access to protected member
        return caller.f_code.co_name
    except ValueError:
        return 'unknown_caller'


def toFloat(value: any, default: float = 0.0) -> float:
    if value is None:                                                         # if you expect None to be passed
        return default
    try:
        return float(value)
    except ValueError:
        return default


def toInt(value: any, default: int = 0) -> int:
    if value is None:                                                         # if you expect None to be passed
        return default
    try:
        return int(value)
    except ValueError:
        return default


def knotToMeterperSec(speed: float) -> float:
    return speed * 0.514444444


def meterPerSecToKnot(speed: float) -> float:
    return speed * 1.94384449412


def newtonToTonForce(force: float) -> float:
    return force * 0.0001019716


def tonForceToNewton(force: float) -> float:
    return force * 9806.652


def stringToIntList(string: str):

    string = string.replace(',', ' ').replace(';', ' ')                         # first convert all delimiters back to spaces
    str_list = string.split()                                                   # split the string into a list of strings
    num_list = []

    for s in str_list:
        try:
            num_list.append(int(s))                                             # append the integer to the list
        except ValueError:
            return []                                                           # bummer; input error

    return num_list


def intListToString(num_list):

    delimiter = ' '                                                             # Define the delimiter to be used
    num_list_string = map(str, num_list)                                        # Convert each element into a string
    join_num_str = delimiter.join(num_list_string)                              # Join the strings using the delimiter
    return join_num_str


def odd(number):
    if number % 2 == 0:
        return False                                                            # even
    else:
        return True                                                             # odd


def even(number):
    if number % 2 == 0:
        return True                                                             # even
    else:
        return False                                                            # odd


def wideturnDetour(turnRadius, lineInterval):
    return max(lineInterval - 2.0 * turnRadius, 0.0)


def teardropDetour(turnRadius, lineInterval):
    # no teardrop effects for a wide turn
    if turnRadius <= 0.5 * lineInterval:
        return 0.0

    # amount of x-line compensation for each side of the teardrop
    teardropMoveout = turnRadius - 0.5 * lineInterval

    # get the angle of the pie segment
    teardropAngle = math.degrees(math.acos(1.0 - 0.5 * teardropMoveout / turnRadius))

    # there are two pie segments for each side of the teardrop; hence four segments in total
    detour = 4.0 * (teardropAngle / 360.0) * 2.0 * math.pi * turnRadius
    return detour


def lineturnDetour(turnRadius, saillineInterval, linesPerTrack, final=False):

    halfCircle = math.pi * turnRadius

    forwardLines = math.ceil(0.5 * linesPerTrack)
    backwardLines = math.floor(0.5 * linesPerTrack)

    xlineForward = forwardLines * saillineInterval
    xlineBackward = backwardLines * saillineInterval

    crosslineForward = wideturnDetour(turnRadius, xlineForward)
    crosslineBackward = wideturnDetour(turnRadius, xlineBackward)

    teardropForward = teardropDetour(turnRadius, xlineForward)
    teardropBackward = teardropDetour(turnRadius, xlineBackward)

    if final:
        lineturnTotal = halfCircle * backwardLines * 2
        crosslineTotal = (crosslineForward + crosslineBackward) * backwardLines
        teardropTotal = (teardropForward + teardropBackward) * backwardLines
    else:
        lineturnTotal = halfCircle * (forwardLines + backwardLines)
        crosslineTotal = crosslineForward * forwardLines + crosslineBackward * backwardLines
        teardropTotal = teardropForward * forwardLines + teardropBackward * backwardLines

    return (lineturnTotal, crosslineTotal, teardropTotal)


def maxTurnSpeedVsCableLength(length):
    maxSpeed = 49.7365 * length**-0.26803
    return maxSpeed


def maxCableLengthVsTurnSpeed(speed):
    maxLength = 2_138_916 * speed**-3.73094
    return maxLength


def makePenFromParms(parms):
    assert len(parms) == 6, "need 6 parameters for: ('color', 'width', 'style', 'capStyle', 'joinStyle', 'cosmetic')"

    ps = Qt.PenStyle
    cs = Qt.PenCapStyle
    js = Qt.PenJoinStyle

    color = parms[0]
    width = parms[1]
    pStyle = getattr(ps, parms[2])
    cStyle = getattr(cs, parms[3])
    jStyle = getattr(js, parms[4])
    cosmet = parms[5]
    # commented out; avoid using fn.mkPen() for proper capStyle and joinStyle
    # names = ('color', 'width', 'style', 'capStyle', 'joinStyle', 'cosmetic')
    # parms = (color, width, pStyle, cStyle, jStyle, cosmet)
    # opts = dict(zip(names, parms))
    # pen = fn.mkPen(**opts)

    r = color[0]
    g = color[1]
    b = color[2]
    a = color[3]
    c = QColor(r, g, b, a)

    pen = QPen(c, width, pStyle, cStyle, jStyle)
    pen.setCosmetic(cosmet)
    return pen


# def getNameFromQtEnum(enum, value):
#     # See: _getAllowedEnums(self, enum), defined in pyqtgraph; qtenum.py.
#     # References to PySide have been removed. QGIS uses PyQt5 only...
#     searchObj = Qt
#     vals = {}
#     for key in dir(searchObj):
#         val = getattr(searchObj, key)
#         if isinstance(val, enum):
#             vals[key] = val

#     result = [k for k, v in vals.items() if v == value][0]
#     return result


def getNameFromQtEnum(enum, value):
    """
    Returns the name of the enum member in Qt (PyQt5 or PyQt6) that matches the given value.
    Compatible with both PyQt5 and PyQt6.
    """
    # PyQt6 enums are subclasses of enum.Enum, PyQt5 are not
    import enum as std_enum

    # Handle PyQt6 enums (subclass of enum.Enum)
    if isinstance(enum, type) and issubclass(enum, std_enum.Enum):
        for member in enum:
            if member.value == value or member == value:
                return member.name
        # Try matching by int value if value is int and member.value is enum
        for member in enum:
            if hasattr(member.value, 'value') and member.value.value == value:
                return member.name
        raise ValueError(f'Value {value} not found in enum {enum}')

    # Handle PyQt5 enums (not subclass of enum.Enum)
    searchObj = Qt
    vals = {}
    for key in dir(searchObj):
        val = getattr(searchObj, key)
        if isinstance(val, enum):
            vals[key] = val
    # Try direct match
    for k, v in vals.items():
        if v == value:
            return k
    # Try int value match
    for k, v in vals.items():
        if hasattr(v, 'value') and v.value == value:
            return k
    raise ValueError(f'Value {value} not found in enum {enum}')


def getMethodFromModule(pmm: str):
    """getting a method from a package defined by a 'dot' separated string "package.module.method"
    note: within 'roll' the package name is 'roll'"""
    package, module, method = pmm.split('.')
    module = importlib.import_module(module, package=package)
    method = getattr(module, method)
    return method


# See: https://github.com/bensarthou/pynufft_benchmark/blob/master/NDFT.py # now accelerated in funtions_numba.py
def ndft_1Da(x, f, kMax, dK):
    """non-equispaced discrete Fourier transform on x with weights (1/0) in f"""
    # n = x.shape[0]                                            # normalize by maximum nr of available races
    n = np.count_nonzero(f)                                     # normalize by actual  nr of available traces
    a = 1 / n if n > 0 else 0
    k = np.arange(0, kMax, dK)
    r = np.dot(f, np.exp(2j * np.pi * k * x[:, np.newaxis])) * a
    return r


def ndft_1Db(x, kMax, dK):
    """non-equispaced discrete Fourier transform on x with equal weights defined by size of transform"""
    n = x.shape[0]
    a = 1 / n if n > 0 else 0
    k = np.arange(0, kMax, dK)
    r = np.exp(2j * np.pi * k * x[:, np.newaxis]) * a
    s = r.sum(axis=0)
    return s


def rotatePoint2D(x: float, y: float, angle: float) -> tuple:
    # rotate a point around the origin
    # x' = x * cos(angle) - y * sin(angle)
    # y' = x * sin(angle) + y * cos(angle)
    angle = math.radians(angle)
    x1 = x * math.cos(angle) - y * math.sin(angle)
    y1 = x * math.sin(angle) + y * math.cos(angle)
    return x1, y1


def dummyText_on_nDFT():
    # For the Kr stack response, we need to do a DFT (not an FFT)
    # With a stack response you don't have even intervals between subsequent points as in a 'nornal' DFT/FFT
    # The intervals are defined by the |offset| increments between subsequent traces
    # The keyword here is "NUFFT" (Non Uniform FFT) as well as "NFFT" (another package).
    # See: https://nl.mathworks.com/help/matlab/ref/double.nufft.html
    # See: https://pynufft.readthedocs.io/en/latest/index.html
    # And: https://pynufft.readthedocs.io/en/latest/tutor/example.html
    # See: https://github.com/bensarthou/pynufft_benchmark
    # Ref: https://stackoverflow.com/questions/62785140/coding-a-discrete-fourier-transform-on-python-without-using-built-in-functions
    # Ref: https://stackoverflow.com/questions/63534781/how-to-obtain-frequencies-in-non-uniform-dfft

    # See: https://en.wikipedia.org/wiki/Non-uniform_discrete_Fourier_transform
    # See: https://www-user.tu-chemnitz.de/~potts/nfft/
    # See: https://github.com/ghisvail/pyNFFT
    # See: https://pythonhosted.org/pyNFFT/tutorial.html
    # See: https://pythonhosted.org/pyNFFT/api/nfft.html
    # See: https://stackoverflow.com/questions/26014375/fourier-coefficients-for-nfft-non-uniform-fast-fourier-transform
    # See: https://stackoverflow.com/questions/67350588/example-python-nfft-fourier-transform-issues-with-signal-reconstruction-normal
    # See: https://indico.cern.ch/event/484296/contributions/2002827/attachments/1215869/1775559/OscarBLANCO_Commissioning2016.pdf
    # See: https://notebook.community/jakevdp/nfft/notebooks/ImplementationWalkthrough
    # See: https://rdrr.io/github/gzt/rNFFT/man/ndft_1d.html

    # def progress(count, total, status=''):
    # 	bar_len = 60
    # 	filled_len = int(round(bar_len * count / float(total)))
    # 	percents = round(100.0 * count / float(total), 1)
    # 	bar = '=' * filled_len + '-' * (bar_len - filled_len)
    # 	sys.stdout.write('[%s] %s%s ...%s\r' % (bar, percents, '%', status))
    # 	sys.stdout.flush()
    #
    # def ndft_1D(x, f, N):
    # 	"""non-equispaced discrete Fourier transform"""
    # 	k = -(N // 2) + np.arange(N)
    # 	return np.dot(f, np.exp(2j * np.pi * k * x[:, np.newaxis]))
    #
    #
    # def ndft_2D(x, f, Nd):
    # 	M,N = Nd[0], Nd[1]
    # 	K = np.shape(x)[0]
    # 	ndft2d = [0.0 for i in range(K)]
    # 	for k in range(K):
    # 		# print('k',k ,'sur ', K)
    # 		progress(k, K)
    # 		sum_ = 0.0
    # 		for m in range(M):
    # 			for n in range(N):
    # 				# print(n,m)
    # 				value = f[m, n]
    # 				e = np.exp(- 1j * 2*np.pi * (x[k,0] + x[k,1]))
    # 				sum_ += value * e
    # 		ndft2d[k] = sum_ / M / N
    # 	return ndft2d
    #
    # https://stackoverflow.com/questions/11333454/2d-fft-using-1d-fft
    ...


def makeParmsFromPen(pen):
    ps = Qt.PenStyle
    cs = Qt.PenCapStyle
    js = Qt.PenJoinStyle

    color = pen.color()
    width = pen.width()
    pStyle = getNameFromQtEnum(ps, pen.style())
    cStyle = getNameFromQtEnum(cs, pen.capStyle())
    jStyle = getNameFromQtEnum(js, pen.joinStyle())
    cosmet = pen.isCosmetic()

    r = color.red()
    g = color.green()
    b = color.blue()
    a = color.alpha()
    c = (r, g, b, a)

    params = (c, width, pStyle, cStyle, jStyle, cosmet)
    return params


def natural_sort(lst):
    def convert(text):
        return int(text) if text.isdigit() else text.lower()

    def alphanum_key(key):
        return [convert(c) for c in re.split('([0-9]+)', key)]

    return sorted(lst, key=alphanum_key)


def containsPoint2D(border: QRectF, point: QPointF) -> bool:
    if border.isNull():
        return True                                                             # no need to clip with an empty rect
    return border.contains(point)


def containsPoint3D(border: QRectF, point: QVector3D) -> bool:
    if border.isNull():
        return True                                                             # no need to clip with an empty rect
    return border.contains(point.toPointF())


def clipRectF(rect: QRectF, border: QRectF) -> QRectF:
    if border.isNull():
        return QRectF(rect)                                                     # don't clip against an empty rect !
    return QRectF(rect) & border                                                # get the area inside the border


def clipLineF(line: QLineF, border: QRectF) -> QLineF:

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

    if border.isNull():
        return QLineF(line)                                                     # don't clip against an empty rect !
    if line.isNull():
        return QLineF()                                                         # null in ?  null out !

    # for sake of ease; copy the line & rect elements to individual real values
    x1 = line.x1()
    y1 = line.y1()
    x2 = line.x2()
    y2 = line.y2()
    y_min = border.top()
    x_min = border.left()
    y_max = border.bottom()
    x_max = border.right()

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
        return QLineF(x1, y1, x2, y2)                                           # return the clipped line

    return QLineF()                                                             # return a null line


# some functions to count number of lines in a text file.
# See: https://stackoverflow.com/questions/845058/how-to-get-line-count-of-a-large-file-cheaply-in-python/68385697#68385697
def rawcount(filename):
    with open(filename, 'rb') as f:
        lines = 0
        buf_size = 1024 * 1024
        read_f = f.raw.read

        buf = read_f(buf_size)
        while buf:
            lines += buf.count(b'\n')
            buf = read_f(buf_size)
    return lines


def buf_count_newlines_gen(fname):
    def _make_gen(reader):
        while True:
            b = reader(2**16)
            if not b:
                break
            yield b

    with open(fname, 'rb') as f:
        count = sum(buf.count(b'\n') for buf in _make_gen(f.raw.read))
    return count


def countHeaderLines(filename):
    # This function uses a for-loop directly on the file pointer
    count = 0

    with open(filename, encoding='utf-8') as fp:
        for line in fp:
            if line[0] == 'H':
                count += 1
            else:
                return count


def countHeaderLines2(filename):
    # See: https://pynative.com/python-count-number-of-lines-in-file/
    # This function uses readlines to first establish total number of lines
    count = 0
    with open(filename, encoding='utf-8') as fp:
        lines = fp.readlines()
        for line in lines:
            if line[0] == 'H':
                count += 1
            else:
                return count
    return count


def isFileInUse(file_path):
    path = Path(file_path)

    if not path.exists():
        # raise FileNotFoundError
        return False

    try:
        path.rename(path)
    except PermissionError:
        return True
    else:
        return False


def get_unpicklable(instance, exception=None, string='', first_only=True):
    # See: https://stackoverflow.com/questions/30499341/establishing-why-an-object-cant-be-pickled
    """
    Recursively go through all attributes of instance and return a list of whatever can't be pickled.

    Set first_only to only print the first problematic element in a list, tuple or
    dict (otherwise there could be lots of duplication).
    """
    problems = []
    if isinstance(instance, tuple) or isinstance(instance, list):
        for k, v in enumerate(instance):
            try:
                pickle.dumps(v)
            except BaseException as e:
                problems.extend(get_unpicklable(v, e, string + f'[{k}]'))
                if first_only:
                    break
    elif isinstance(instance, dict):
        for k in instance:
            try:
                pickle.dumps(k)
            except BaseException as e:
                problems.extend(get_unpicklable(k, e, string + f'[key type={type(k).__name__}]'))
                if first_only:
                    break
        for v in instance.values():
            try:
                pickle.dumps(v)
            except BaseException as e:
                problems.extend(get_unpicklable(v, e, string + f'[val type={type(v).__name__}]'))
                if first_only:
                    break
    else:
        for k, v in instance.__dict__.items():
            try:
                pickle.dumps(v)
            except BaseException as e:
                problems.extend(get_unpicklable(v, e, string + '.' + k))

    # if we get here, it means pickling instance caused an exception (string is not
    # empty), yet no member was a problem (problems is empty), thus instance itself
    # is the problem.
    if string != '' and not problems:
        problems.append(string + f" (Type '{type(instance).__name__}' caused: {exception})")
    return problems


def compute_lcm(x, y):
    # function to find the Least Common Multiple (LCM) of two input numbers
    # choose the greater number
    if x > y:
        greater = x
    else:
        greater = y

    while True:
        if (greater % x == 0) and (greater % y == 0):
            lcm = greater
            break
        greater += 1

    return lcm


def convexHull(x, y):
    # see: https://stackoverflow.com/questions/1500595/convex-hull-in-python
    # see: https://bitbucket.org/william_rusnack/minimumboundingbox/src/master/MinimumBoundingBox.py
    # see: https://github.com/dbworth/minimum-area-bounding-rectangle/tree/master
    # see: https://gist.github.com/kchr/77a0ee945e581df7ed25

    points = np.column_stack((x, y))

    def link(a, b):
        return np.concatenate((a, b[1:]))

    def edge(a, b):
        return np.concatenate(([a], [b]))

    def dome(points, base):
        h, t = base
        dists = np.dot(points - h, np.dot(((0, -1), (1, 0)), (t - h)))
        outer = np.repeat(points, dists > 0, 0)
        if len(outer):
            pivot = points[np.argmax(dists)]
            return link(dome(outer, edge(h, pivot)), dome(outer, edge(pivot, t)))
        else:
            return base

    if len(points) > 2:
        axis = points[:, 0]
        base = np.take(points, [np.argmin(axis), np.argmax(axis)], 0)
        return link(dome(points, base), dome(points, base[::-1]))
    else:
        return points


def transformConvexHull(hull_points, transform):
    """
    Transforms the output of convexHull(x, y) using QTransform.map().

    :param hull_points: A NumPy array of points (x, y) representing the convex hull.
                        Expected shape: (n, 2), where n is the number of vertices.
    :param transform: A QTransform object to apply the transformation.
    :return: A transformed NumPy array of points (x, y).
    """
    if hull_points is None or len(hull_points) < 1:
        raise ValueError('Invalid convex hull points. At least 1 point is required.')

    if not isinstance(transform, QTransform):
        raise TypeError('The transform parameter must be a QTransform object.')

    # Apply the transformation to each point
    transformed_points = np.array([transform.map(x, y) for x, y in hull_points])

    return transformed_points


def convexHullToQgisPolygon(hull_points):
    """
    Converts the output of convexHull(x, y) to a QGIS polygon.

    :param hull_points: A NumPy array of points (x, y) representing the convex hull.
                        Expected shape: (n, 2), where n is the number of vertices.
    :return: A QGIS polygon geometry (QgsGeometry).
    """
    if hull_points is None or len(hull_points) < 3:
        raise ValueError('Invalid convex hull points. At least 3 points are required to form a polygon.')

    # Convert the NumPy array of points to a list of QgsPointXY
    vertices = [QgsPointXY(x, y) for x, y in hull_points]

    # Ensure the polygon is closed by appending the first point to the end
    if vertices[0] != vertices[-1]:
        vertices.append(vertices[0])

    # Create a QGIS polygon geometry
    polygon = QgsGeometry.fromPolygonXY([vertices])

    return polygon


def numpyToQpolygonF(xdata, ydata):
    # See: https://github.com/PlotPyStack/PythonQwt/blob/master/qwt/plot_curve.py#L63
    """
    Utility function to convert two 1D-NumPy arrays representing curve data
    (X-axis, Y-axis data) into a single polyline (QtGui.PolygonF object).
    License/copyright: MIT License © Pierre Raybaut 2020-2021.

    :param numpy.ndarray xdata: 1D-NumPy array
    :param numpy.ndarray ydata: 1D-NumPy array
    :return: Polyline
    :rtype: QtGui.QPolygonF
    """
    if not xdata.size == ydata.size == xdata.shape[0] == ydata.shape[0]:
        raise ValueError('Arguments must be 1D NumPy arrays with same size')
    size = xdata.size
    polyline = QPolygonF(size)
    buffer = polyline.data()
    buffer.setsize(16 * size)  # 16 bytes per point: 8 bytes per X,Y value (float64)
    memory = np.frombuffer(buffer, np.float64)
    memory[: (size - 1) * 2 + 1 : 2] = np.array(xdata, dtype=np.float64, copy=False)
    memory[1 : (size - 1) * 2 + 2 : 2] = np.array(ydata, dtype=np.float64, copy=False)
    return polyline


def aboutText() -> str:
    # See : https://github.com/qgis/QGIS/blob/master/python/utils.py#L291 for version info

    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, 'metadata.txt')

    parser = configparser.ConfigParser()
    parser.optionxform = str
    parser.read(file_path)

    metadata = []
    metadata.extend(parser.items('general'))
    metaDict = dict(metadata)                                               # See: https://stackoverflow.com/questions/2191699/find-an-element-in-a-list-of-tuples
    rollVersion = metaDict['version']

    pythonVersionList = sys.version.split(' ')
    pythonVersion = pythonVersionList[0]

    numbaVersion = numba.__version__ if haveNumba else 'not installed'
    ptvsdVersion = ptvsd.__version__ if havePtvsd else 'not installed'

    sourceUrl = "<a href='https://github.com/MrBeee/roll'>here</a>"
    sampleUrl = "<a href='https://github.com/MrBeee/roll_samples'>here</a>"

    text = (
        f'Roll can be used to generate seismic survey geometries. <br>'
        f'Both for Land/OBN as well as marine seismic surveys. <ul>'
        f'<li>Roll version: {rollVersion}. </li></ul>'
        f'The following Python & framework versions are used: <ul>'
        f'<li>Python version: {pythonVersion} </li>'
        f'<li>Qt version: {QT_VERSION_STR} </li>'
        f'<li>PyQt version: {PYQT_VERSION_STR} </li></ul>'
        f'The following libraries are used: <ul>'
        f'<li>Numba version: {numbaVersion} </li>'
        f'<li>Numpy version: {np.__version__} </li>'
        f'<li>Ptvsd version: {ptvsdVersion} </li>'
        f'<li>PyQtGraph version: {pg.__version__} </li>'
        f'<li>Rasterio version: {rio.__version__} </li>'
        f'<li>Wellpathpy version: {wp.__version__} </li></ul>'
        f'Source code is available on GitHub {sourceUrl} <br> '
        f'Sample projects are available on GitHub {sampleUrl} <br><br> '
        f'Copyright © 2022-2025 by Duijndam.Dev'
    )

    return text


def highDpiText() -> str:

    dpiUrl = "<a href='https://github.com/qgis/QGIS/issues/53898'>here</a>"

    dpiText = (
        f'As of V3.32 High DPI UI scaling issues have arisen in QGIS. <br>'
        f'See the following discussion on GitHub {dpiUrl} <br> '
        f'The work around that has been proposed is as follows: <ol>'
        f"<li>Right click 'qgis-bin.exe' in folder 'C:\\Program Files\\QGIS 3.36.3\\bin' </li>"
        f"<li>Select 'Properties' </li>"
        f'<li>Select the Compatibility tab </li>'
        f"<li>Select 'change high DPI settings' </li>"
        f"<li>Set the tickmark before 'Override high DPI ...' </li>"
        f"<li>Have scaling performed by 'Application' </li>"
        f"<li>In the same folder edit the file 'qgis-bin.env' </li>"
        f'<li>Add one line at the very end: </li>'
        f'<li>QT_SCALE_FACTOR_ROUNDING_POLICY=Floor </li>'
        f"<li>Save the file in a different folder as 'C:\\Program Files' is write-protected </li>"
        f"<li>Copy the edited file back to the 'C:\\Program Files\\QGIS 3.36.3\\bin' folder </li>"
        f"<li>You'll be asked to confirm you want to overwrite the existing file. Go ahead. </li></ol>"
        f'This addresses the font and button scaling problems ! Finally: <br>'
        f'It is recommended to use font size 8.0 and Icon size 24, in Settings -> Options... -> General'
    )

    return dpiText


def licenseText() -> str:
    licenseTxt = """
    Copyright  © 2022-2024 by Duijndam.Dev. All rights reserved.

    Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

    Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

    Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

    Neither the name of Mapbox nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS “AS IS” AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL DUIJNDAM.DEV BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."""
    return licenseTxt


def exampleSurveyXmlText() -> str:
    xmlText = """<?xml version="1.0" encoding="UTF-8"?>
    <survey version="1.0">
        <type>Orthogonal</type>
        <name>New survey</name>
        <surveyCrs>
            <spatialrefsys nativeFormat="Wkt">
                <wkt>PROJCRS["Amersfoort / RD New",BASEGEOGCRS["Amersfoort",DATUM["Amersfoort",ELLIPSOID["Bessel 1841",6377397.155,299.1528128,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4289]],CONVERSION["RD New",METHOD["Oblique Stereographic",ID["EPSG",9809]],PARAMETER["Latitude of natural origin",52.1561605555556,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],PARAMETER["Longitude of natural origin",5.38763888888889,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],PARAMETER["Scale factor at natural origin",0.9999079,SCALEUNIT["unity",1],ID["EPSG",8805]],PARAMETER["False easting",155000,LENGTHUNIT["metre",1],ID["EPSG",8806]],PARAMETER["False northing",463000,LENGTHUNIT["metre",1],ID["EPSG",8807]]],CS[Cartesian,2],AXIS["easting (X)",east,ORDER[1],LENGTHUNIT["metre",1]],AXIS["northing (Y)",north,ORDER[2],LENGTHUNIT["metre",1]],USAGE[SCOPE["Engineering survey, topographic mapping."],AREA["Netherlands - onshore, including Waddenzee, Dutch Wadden Islands and 12-mile offshore coastal zone."],BBOX[50.75,3.2,53.7,7.22]],ID["EPSG",28992]]</wkt>
                <proj4>+proj=sterea +lat_0=52.1561605555556 +lon_0=5.38763888888889 +k=0.9999079 +x_0=155000 +y_0=463000 +ellps=bessel +units=m +no_defs</proj4>
                <srsid>2517</srsid>
                <srid>28992</srid>
                <authid>EPSG:28992</authid>
                <description>Amersfoort / RD New</description>
                <projectionacronym>sterea</projectionacronym>
                <ellipsoidacronym>EPSG:7004</ellipsoidacronym>
                <geographicflag>false</geographicflag>
            </spatialrefsys>
        </surveyCrs>
        <limits>
            <output xmax="7225.0" ymax="1800.0" xmin="6975.0" ymin="1400.0"/>
            <angles refmin="0.0" azimin="0.0" azimax="360.0" refmax="45.0"/>
            <offset rmin="0.0" xmax="5976.0" rmax="6027.0" ymax="776.0" xmin="-5976.0" ymin="-776.0"/>
            <unique deltaoff="200.0" deltaazi="5.0" apply="False" write="False"/>
            <binning vint="2000.0" method="cmp"/>
        </limits>
        <reflectors>
            <plane azi="45.0" z0="-2000.0" dip="4.0" y0="450000.0" x0="150000.0"/>
            <!--Plane equation: -0.049325·x + -0.049325·y + 0.997564·z + 31590.294922 = 0  -->
            <!--Plane is defined in global coordinates. Subsurface corresponds with negative z-values-->
            <sphere z0="-4000.0" radius="2000.0" y0="456100.0" x0="153900.0"/>
            <!--Sphere is defined in global coordinates. Subsurface corresponds with negative z-values-->
        </reflectors>
        <grid>
            <local l0="1000.0" s0="1000.0" fold="-1" dl="25.0" dy="25.0" y0="12.5" dx="25.0" ds="25.0" x0="12.5"/>
            <global azi="45.0" sy="1.0" sx="1.0" y0="450000.0" x0="150000.0"/>
            <!--Forward transform: A0=150000.000, B0=450000.000, A1=0.707107, B1=0.707107, A2=-0.707107, B2=0.707107-->
            <!--Inverse transform: A0=-424264.069, B0=-212132.034, A1=0.707107, B1=-0.707107, A2=0.707107, B2=0.707107-->
            <!--See EPSG:9624 (https://epsg.io/9624-method) for the affine parametric transform definition-->
        </grid>
        <block_list>
            <block>
                <name>Block-1</name>
                <borders>
                    <src_border xmax="20000.0" ymax="20000.0" ymin="-20000.0" xmin="-20000.0"/>
                    <rec_border xmax="0.0" ymax="0.0" ymin="0.0" xmin="0.0"/>
                </borders>
                <template_list>
                    <template>
                        <name>Template-1</name>
                        <roll_list>
                            <translate dz="0.0" dy="0.0" n="1" dx="0.0"/>
                            <translate dz="0.0" dy="200.0" n="10" dx="0.0"/>
                            <translate dz="0.0" dy="0.0" n="10" dx="250.0"/>
                        </roll_list>
                        <seed_list>
                            <seed azi="False" typno="0" z0="0.0" y0="625.0" argb="#77ff0000" x0="5975.0" src="True" patno="0">
                                <name>Src-1</name>
                                <grid roll="False" points="4">
                                    <translate dz="0.0" dy="0.0" n="1" dx="0.0"/>
                                    <translate dz="0.0" dy="0.0" n="1" dx="250.0"/>
                                    <translate dz="0.0" dy="50.0" n="4" dx="0.0"/>
                                </grid>
                            </seed>
                            <seed azi="False" typno="0" z0="0.0" y0="0.0" argb="#7700b0f0" x0="0.0" src="False" patno="1">
                                <name>Rec-1</name>
                                <grid roll="False" points="1920">
                                    <translate dz="0.0" dy="0.0" n="1" dx="0.0"/>
                                    <translate dz="0.0" dy="200.0" n="8" dx="0.0"/>
                                    <translate dz="0.0" dy="0.0" n="240" dx="50.0"/>
                                </grid>
                            </seed>
                        </seed_list>
                    </template>
                </template_list>
            </block>
        </block_list>
        <pattern_list>
            <pattern>
                <name>src-array</name>
                <seed_list>
                    <seed azi="False" z0="0.0" y0="-12.5" argb="#ffff0000" x0="-0.0">
                        <name>seed-1</name>
                        <grid roll="True" points="3">
                            <translate dz="0.0" dy="0.0" n="1" dx="0.0"/>
                            <translate dz="0.0" dy="0.0" n="1" dx="0.0"/>
                            <translate dz="0.0" dy="12.5" n="3" dx="0.0"/>
                        </grid>
                    </seed>
                </seed_list>
            </pattern>
            <pattern>
                <name>rec-array</name>
                <seed_list>
                    <seed azi="False" z0="0.0" y0="-20.83" argb="#ff0000ff" x0="-20.83">
                        <name>seed-1</name>
                        <grid roll="True" points="18">
                            <translate dz="0.0" dy="0.0" n="3" dx="16.66670036315918"/>
                            <translate dz="0.0" dy="8.333000183105469" n="2" dx="8.333000183105469"/>
                            <translate dz="0.0" dy="16.66699981689453" n="3" dx="0.0"/>
                        </grid>
                    </seed>
                </seed_list>
            </pattern>
        </pattern_list>
    </survey>"""
    return xmlText


def qgisCheatSheetText() -> str:
    qgisText = """
    <h2>QGIS Cheat Sheet</h2>
    <ul>
        <li><b>Ctrl + Shift + P</b>: Open Python console</li>
        <li><b>Ctrl + Shift + C</b>: Copy selected feature(s)</li>
        <li><b>Ctrl + Shift + V</b>: Paste copied feature(s)</li>
        <li><b>Ctrl + Shift + R</b>: Refresh the map canvas</li>
        <li><b>Ctrl + Shift + T</b>: Toggle the visibility of the attribute table</li>
        <li><b>Ctrl + Shift + E</b>: Open the expression dialog</li>
        <li><b>Ctrl + Shift + L</b>: Toggle the visibility of the layer list</li>
        <li><b>Ctrl + Shift + I</b>: Open the identify features tool</li>
    </ul>
    """
    return qgisText


def qgisRollInterfaceText() -> str:
    qgisText = """
<!doctype html>
<html>
<head>
<meta charset='UTF-8'><meta name='viewport' content='width=device-width initial-scale=1'>

<link href='https://fonts.googleapis.com/css?family=Open+Sans:400italic,700italic,700,400&subset=latin,latin-ext' rel='stylesheet' type='text/css' /><style type='text/css'>html {overflow-x: initial !important;}:root { --bg-color: #ffffff; --text-color: #333333; --select-text-bg-color: #B5D6FC; --select-text-font-color: auto; --monospace: "Lucida Console",Consolas,"Courier",monospace; --title-bar-height: 20px; }
.mac-os-11 { --title-bar-height: 28px; }
html { font-size: 14px; background-color: var(--bg-color); color: var(--text-color); font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased; }
h1, h2, h3, h4, h5 { white-space: pre-wrap; }
body { margin: 0px; padding: 0px; height: auto; inset: 0px; font-size: 1rem; line-height: 1.42857; overflow-x: hidden; background: inherit; }
iframe { margin: auto; }
a.url { word-break: break-all; }
a:active, a:hover { outline: 0px; }
.in-text-selection, ::selection { text-shadow: none; background: var(--select-text-bg-color); color: var(--select-text-font-color); }
#write { margin: 0px auto; height: auto; width: inherit; word-break: normal; overflow-wrap: break-word; position: relative; white-space: normal; overflow-x: visible; padding-top: 36px; }
#write.first-line-indent p { text-indent: 2em; }
#write.first-line-indent li p, #write.first-line-indent p * { text-indent: 0px; }
#write.first-line-indent li { margin-left: 2em; }
.for-image #write { padding-left: 8px; padding-right: 8px; }
body.typora-export { padding-left: 30px; padding-right: 30px; }
.typora-export .footnote-line, .typora-export li, .typora-export p { white-space: pre-wrap; }
.typora-export .task-list-item input { pointer-events: none; }
@media screen and (max-width: 500px) {
  body.typora-export { padding-left: 0px; padding-right: 0px; }
  #write { padding-left: 20px; padding-right: 20px; }
}
#write li > figure:last-child { margin-bottom: 0.5rem; }
#write ol, #write ul { position: relative; }
img { max-width: 100%; vertical-align: middle; image-orientation: from-image; }
button, input, select, textarea { color: inherit; font: inherit; }
input[type="checkbox"], input[type="radio"] { line-height: normal; padding: 0px; }
*, ::after, ::before { box-sizing: border-box; }
#write h1, #write h2, #write h3, #write h4, #write h5, #write h6, #write p, #write pre { width: inherit; position: relative; }
#write svg h1, #write svg h2, #write svg h3, #write svg h4, #write svg h5, #write svg h6, #write svg p { position: static; }
p { line-height: inherit; }
h1, h2, h3, h4, h5, h6 { break-after: avoid-page; break-inside: avoid; orphans: 4; }
p { orphans: 4; }
h1 { font-size: 2rem; }
h2 { font-size: 1.8rem; }
h3 { font-size: 1.6rem; }
h4 { font-size: 1.4rem; }
h5 { font-size: 1.2rem; }
h6 { font-size: 1rem; }
.md-math-block, .md-rawblock, h1, h2, h3, h4, h5, h6, p { margin-top: 1rem; margin-bottom: 1rem; }
.hidden { display: none; }
.md-blockmeta { color: rgb(204, 204, 204); font-weight: 700; font-style: italic; }
a { cursor: pointer; }
sup.md-footnote { padding: 2px 4px; background-color: rgba(238, 238, 238, 0.7); color: rgb(85, 85, 85); border-radius: 4px; cursor: pointer; }
sup.md-footnote a, sup.md-footnote a:hover { color: inherit; text-transform: inherit; text-decoration: inherit; }
#write input[type="checkbox"] { cursor: pointer; width: inherit; height: inherit; }
figure { overflow-x: auto; margin: 1.2em 0px; max-width: calc(100% + 16px); padding: 0px; }
figure > table { margin: 0px; }
thead, tr { break-inside: avoid; break-after: auto; }
thead { display: table-header-group; }
table { border-collapse: collapse; border-spacing: 0px; width: 100%; overflow: auto; break-inside: auto; text-align: left; }
table.md-table td { min-width: 32px; }
.CodeMirror-gutters { border-right: 0px; background-color: inherit; }
.CodeMirror-linenumber { user-select: none; }
.CodeMirror { text-align: left; }
.CodeMirror-placeholder { opacity: 0.3; }
.CodeMirror pre { padding: 0px 4px; }
.CodeMirror-lines { padding: 0px; }
div.hr:focus { cursor: none; }
#write pre { white-space: pre-wrap; }
#write.fences-no-line-wrapping pre { white-space: pre; }
#write pre.ty-contain-cm { white-space: normal; }
.CodeMirror-gutters { margin-right: 4px; }
.md-fences { font-size: 0.9rem; display: block; break-inside: avoid; text-align: left; overflow: visible; white-space: pre; background: inherit; position: relative !important; }
.md-fences-adv-panel { width: 100%; margin-top: 10px; text-align: center; padding-top: 0px; padding-bottom: 8px; overflow-x: auto; }
#write .md-fences.mock-cm { white-space: pre-wrap; }
.md-fences.md-fences-with-lineno { padding-left: 0px; }
#write.fences-no-line-wrapping .md-fences.mock-cm { white-space: pre; overflow-x: auto; }
.md-fences.mock-cm.md-fences-with-lineno { padding-left: 8px; }
.CodeMirror-line, twitterwidget { break-inside: avoid; }
svg { break-inside: avoid; }
.footnotes { opacity: 0.8; font-size: 0.9rem; margin-top: 1em; margin-bottom: 1em; }
.footnotes + .footnotes { margin-top: 0px; }
.md-reset { margin: 0px; padding: 0px; border: 0px; outline: 0px; vertical-align: top; background: 0px 0px; text-decoration: none; text-shadow: none; float: none; position: static; width: auto; height: auto; white-space: nowrap; cursor: inherit; -webkit-tap-highlight-color: transparent; line-height: normal; font-weight: 400; text-align: left; box-sizing: content-box; direction: ltr; }
li div { padding-top: 0px; }
blockquote { margin: 1rem 0px; }
li .mathjax-block, li p { margin: 0.5rem 0px; }
li blockquote { margin: 1rem 0px; }
li { margin: 0px; position: relative; }
blockquote > :last-child { margin-bottom: 0px; }
blockquote > :first-child, li > :first-child { margin-top: 0px; }
.footnotes-area { color: rgb(136, 136, 136); margin-top: 0.714rem; padding-bottom: 0.143rem; white-space: normal; }
#write .footnote-line { white-space: pre-wrap; }
@media print {
  body, html { border: 1px solid transparent; height: 99%; break-after: avoid; break-before: avoid; font-variant-ligatures: no-common-ligatures; }
  #write { margin-top: 0px; border-color: transparent !important; padding-top: 0px !important; padding-bottom: 0px !important; }
  .typora-export * { -webkit-print-color-adjust: exact; }
  .typora-export #write { break-after: avoid; }
  .typora-export #write::after { height: 0px; }
  .is-mac table { break-inside: avoid; }
  #write > p:nth-child(1) { margin-top: 0px; }
  .typora-export-show-outline .typora-export-sidebar { display: none; }
  figure { overflow-x: visible; }
}
.footnote-line { margin-top: 0.714em; font-size: 0.7em; }
a img, img a { cursor: pointer; }
pre.md-meta-block { font-size: 0.8rem; min-height: 0.8rem; white-space: pre-wrap; background: rgb(204, 204, 204); display: block; overflow-x: hidden; }
p > .md-image:only-child:not(.md-img-error) img, p > img:only-child { display: block; margin: auto; }
#write.first-line-indent p > .md-image:only-child:not(.md-img-error) img { left: -2em; position: relative; }
p > .md-image:only-child { display: inline-block; width: 100%; }
#write .MathJax_Display { margin: 0.8em 0px 0px; }
.md-math-block { width: 100%; }
.md-math-block:not(:empty)::after { display: none; }
.MathJax_ref { fill: currentcolor; }
[contenteditable="true"]:active, [contenteditable="true"]:focus, [contenteditable="false"]:active, [contenteditable="false"]:focus { outline: 0px; box-shadow: none; }
.md-task-list-item { position: relative; list-style-type: none; }
.task-list-item.md-task-list-item { padding-left: 0px; }
.md-task-list-item > input { position: absolute; top: 0px; left: 0px; margin-left: -1.2em; margin-top: calc(1em - 10px); border: none; }
.math { font-size: 1rem; }
.md-toc { min-height: 3.58rem; position: relative; font-size: 0.9rem; border-radius: 10px; }
.md-toc-content { position: relative; margin-left: 0px; }
.md-toc-content::after, .md-toc::after { display: none; }
.md-toc-item { display: block; color: rgb(65, 131, 196); }
.md-toc-item a { text-decoration: none; }
.md-toc-inner:hover { text-decoration: underline; }
.md-toc-inner { display: inline-block; cursor: pointer; }
.md-toc-h1 .md-toc-inner { margin-left: 0px; font-weight: 700; }
.md-toc-h2 .md-toc-inner { margin-left: 2em; }
.md-toc-h3 .md-toc-inner { margin-left: 4em; }
.md-toc-h4 .md-toc-inner { margin-left: 6em; }
.md-toc-h5 .md-toc-inner { margin-left: 8em; }
.md-toc-h6 .md-toc-inner { margin-left: 10em; }
@media screen and (max-width: 48em) {
  .md-toc-h3 .md-toc-inner { margin-left: 3.5em; }
  .md-toc-h4 .md-toc-inner { margin-left: 5em; }
  .md-toc-h5 .md-toc-inner { margin-left: 6.5em; }
  .md-toc-h6 .md-toc-inner { margin-left: 8em; }
}
a.md-toc-inner { font-size: inherit; font-style: inherit; font-weight: inherit; line-height: inherit; }
.footnote-line a:not(.reversefootnote) { color: inherit; }
.reversefootnote { font-family: ui-monospace, sans-serif; }
.md-attr { display: none; }
.md-fn-count::after { content: "."; }
code, pre, samp, tt { font-family: var(--monospace); }
kbd { margin: 0px 0.1em; padding: 0.1em 0.6em; font-size: 0.8em; color: rgb(36, 39, 41); background: rgb(255, 255, 255); border: 1px solid rgb(173, 179, 185); border-radius: 3px; box-shadow: rgba(12, 13, 14, 0.2) 0px 1px 0px, rgb(255, 255, 255) 0px 0px 0px 2px inset; white-space: nowrap; vertical-align: middle; }
.md-comment { color: rgb(162, 127, 3); opacity: 0.6; font-family: var(--monospace); }
code { text-align: left; vertical-align: initial; }
a.md-print-anchor { white-space: pre !important; border-width: initial !important; border-style: none !important; border-color: initial !important; display: inline-block !important; position: absolute !important; width: 1px !important; right: 0px !important; outline: 0px !important; background: 0px 0px !important; text-decoration: initial !important; text-shadow: initial !important; }
.os-windows.monocolor-emoji .md-emoji { font-family: "Segoe UI Symbol", sans-serif; }
.md-diagram-panel > svg { max-width: 100%; }
[lang="flow"] svg, [lang="mermaid"] svg { max-width: 100%; height: auto; }
[lang="mermaid"] .node text { font-size: 1rem; }
table tr th { border-bottom: 0px; }
video { max-width: 100%; display: block; margin: 0px auto; }
iframe { max-width: 100%; width: 100%; border: none; }
.highlight td, .highlight tr { border: 0px; }
mark { background: rgb(255, 255, 0); color: rgb(0, 0, 0); }
.md-html-inline .md-plain, .md-html-inline strong, mark .md-inline-math, mark strong { color: inherit; }
.md-expand mark .md-meta { opacity: 0.3 !important; }
mark .md-meta { color: rgb(0, 0, 0); }
@media print {
  .typora-export h1, .typora-export h2, .typora-export h3, .typora-export h4, .typora-export h5, .typora-export h6 { break-inside: avoid; }
}
.md-diagram-panel .messageText { stroke: none !important; }
.md-diagram-panel .start-state { fill: var(--node-fill); }
.md-diagram-panel .edgeLabel rect { opacity: 1 !important; }
.md-fences.md-fences-math { font-size: 1em; }
.md-fences-advanced:not(.md-focus) { padding: 0px; white-space: nowrap; border: 0px; }
.md-fences-advanced:not(.md-focus) { background: inherit; }
.mermaid-svg { margin: auto; }
.typora-export-show-outline .typora-export-content { max-width: 1440px; margin: auto; display: flex; flex-direction: row; }
.typora-export-sidebar { width: 300px; font-size: 0.8rem; margin-top: 80px; margin-right: 18px; }
.typora-export-show-outline #write { --webkit-flex: 2; flex: 2 1 0%; }
.typora-export-sidebar .outline-content { position: fixed; top: 0px; max-height: 100%; overflow: hidden auto; padding-bottom: 30px; padding-top: 60px; width: 300px; }
@media screen and (max-width: 1024px) {
  .typora-export-sidebar, .typora-export-sidebar .outline-content { width: 240px; }
}
@media screen and (max-width: 800px) {
  .typora-export-sidebar { display: none; }
}
.outline-content li, .outline-content ul { margin-left: 0px; margin-right: 0px; padding-left: 0px; padding-right: 0px; list-style: none; overflow-wrap: anywhere; }
.outline-content ul { margin-top: 0px; margin-bottom: 0px; }
.outline-content strong { font-weight: 400; }
.outline-expander { width: 1rem; height: 1.42857rem; position: relative; display: table-cell; vertical-align: middle; cursor: pointer; padding-left: 4px; }
.outline-expander::before { content: "ï„¥"; position: relative; font-family: Ionicons; display: inline-block; font-size: 8px; vertical-align: middle; }
.outline-item { padding-top: 3px; padding-bottom: 3px; cursor: pointer; }
.outline-expander:hover::before { content: "ï„£"; }
.outline-h1 > .outline-item { padding-left: 0px; }
.outline-h2 > .outline-item { padding-left: 1em; }
.outline-h3 > .outline-item { padding-left: 2em; }
.outline-h4 > .outline-item { padding-left: 3em; }
.outline-h5 > .outline-item { padding-left: 4em; }
.outline-h6 > .outline-item { padding-left: 5em; }
.outline-label { cursor: pointer; display: table-cell; vertical-align: middle; text-decoration: none; color: inherit; }
.outline-label:hover { text-decoration: underline; }
.outline-item:hover { border-color: rgb(245, 245, 245); background-color: var(--item-hover-bg-color); }
.outline-item:hover { margin-left: -28px; margin-right: -28px; border-left: 28px solid transparent; border-right: 28px solid transparent; }
.outline-item-single .outline-expander::before, .outline-item-single .outline-expander:hover::before { display: none; }
.outline-item-open > .outline-item > .outline-expander::before { content: "ï„£"; }
.outline-children { display: none; }
.info-panel-tab-wrapper { display: none; }
.outline-item-open > .outline-children { display: block; }
.typora-export .outline-item { padding-top: 1px; padding-bottom: 1px; }
.typora-export .outline-item:hover { margin-right: -8px; border-right: 8px solid transparent; }
.typora-export .outline-expander::before { content: "+"; font-family: inherit; top: -1px; }
.typora-export .outline-expander:hover::before, .typora-export .outline-item-open > .outline-item > .outline-expander::before { content: "âˆ’"; }
.typora-export-collapse-outline .outline-children { display: none; }
.typora-export-collapse-outline .outline-item-open > .outline-children, .typora-export-no-collapse-outline .outline-children { display: block; }
.typora-export-no-collapse-outline .outline-expander::before { content: "" !important; }
.typora-export-show-outline .outline-item-active > .outline-item .outline-label { font-weight: 700; }
.md-inline-math-container mjx-container { zoom: 0.95; }
mjx-container { break-inside: avoid; }
.md-alert.md-alert-note { border-left-color: rgb(9, 105, 218); }
.md-alert.md-alert-important { border-left-color: rgb(130, 80, 223); }
.md-alert.md-alert-warning { border-left-color: rgb(154, 103, 0); }
.md-alert.md-alert-tip { border-left-color: rgb(31, 136, 61); }
.md-alert.md-alert-caution { border-left-color: rgb(207, 34, 46); }
.md-alert { padding: 0px 1em; margin-bottom: 16px; color: inherit; border-left: 0.25em solid rgb(0, 0, 0); }
.md-alert-text-note { color: rgb(9, 105, 218); }
.md-alert-text-important { color: rgb(130, 80, 223); }
.md-alert-text-warning { color: rgb(154, 103, 0); }
.md-alert-text-tip { color: rgb(31, 136, 61); }
.md-alert-text-caution { color: rgb(207, 34, 46); }
.md-alert-text { font-size: 0.9rem; font-weight: 700; }
.md-alert-text svg { fill: currentcolor; position: relative; top: 0.125em; margin-right: 1ch; overflow: visible; }
.md-alert-text-container::after { content: attr(data-text); text-transform: capitalize; pointer-events: none; margin-right: 1ch; }


:root {
    --side-bar-bg-color: #fafafa;
    --control-text-color: #777;
}

@include-when-export url(https://fonts.googleapis.com/css?family=Open+Sans:400italic,700italic,700,400&subset=latin,latin-ext);

/* open-sans-regular - latin-ext_latin */
  /* open-sans-italic - latin-ext_latin */
    /* open-sans-700 - latin-ext_latin */
    /* open-sans-700italic - latin-ext_latin */
  html {
    font-size: 16px;
    -webkit-font-smoothing: antialiased;
}

body {
    font-family: "Open Sans","Clear Sans", "Helvetica Neue", Helvetica, Arial, 'Segoe UI Emoji', sans-serif;
    color: rgb(51, 51, 51);
    line-height: 1.6;
}

#write {
    max-width: 860px;
  	margin: 0 auto;
  	padding: 30px;
    padding-bottom: 100px;
}

@media only screen and (min-width: 1400px) {
	#write {
		max-width: 1024px;
	}
}

@media only screen and (min-width: 1800px) {
	#write {
		max-width: 1200px;
	}
}

#write > ul:first-child,
#write > ol:first-child{
    margin-top: 30px;
}

a {
    color: #4183C4;
}
h1,
h2,
h3,
h4,
h5,
h6 {
    position: relative;
    margin-top: 1rem;
    margin-bottom: 1rem;
    font-weight: bold;
    line-height: 1.4;
    cursor: text;
}
h1:hover a.anchor,
h2:hover a.anchor,
h3:hover a.anchor,
h4:hover a.anchor,
h5:hover a.anchor,
h6:hover a.anchor {
    text-decoration: none;
}
h1 tt,
h1 code {
    font-size: inherit;
}
h2 tt,
h2 code {
    font-size: inherit;
}
h3 tt,
h3 code {
    font-size: inherit;
}
h4 tt,
h4 code {
    font-size: inherit;
}
h5 tt,
h5 code {
    font-size: inherit;
}
h6 tt,
h6 code {
    font-size: inherit;
}
h1 {
    font-size: 2.25em;
    line-height: 1.2;
    border-bottom: 1px solid #eee;
}
h2 {
    font-size: 1.75em;
    line-height: 1.225;
    border-bottom: 1px solid #eee;
}

/*@media print {
    .typora-export h1,
    .typora-export h2 {
        border-bottom: none;
        padding-bottom: initial;
    }

    .typora-export h1::after,
    .typora-export h2::after {
        content: "";
        display: block;
        height: 100px;
        margin-top: -96px;
        border-top: 1px solid #eee;
    }
}*/

h3 {
    font-size: 1.5em;
    line-height: 1.43;
}
h4 {
    font-size: 1.25em;
}
h5 {
    font-size: 1em;
}
h6 {
   font-size: 1em;
    color: #777;
}
p,
blockquote,
ul,
ol,
dl,
table{
    margin: 0.8em 0;
}
li>ol,
li>ul {
    margin: 0 0;
}
hr {
    height: 2px;
    padding: 0;
    margin: 16px 0;
    background-color: #e7e7e7;
    border: 0 none;
    overflow: hidden;
    box-sizing: content-box;
}

li p.first {
    display: inline-block;
}
ul,
ol {
    padding-left: 30px;
}
ul:first-child,
ol:first-child {
    margin-top: 0;
}
ul:last-child,
ol:last-child {
    margin-bottom: 0;
}
blockquote {
    border-left: 4px solid #dfe2e5;
    padding: 0 15px;
    color: #777777;
}
blockquote blockquote {
    padding-right: 0;
}
table {
    padding: 0;
    word-break: initial;
}
table tr {
    border: 1px solid #dfe2e5;
    margin: 0;
    padding: 0;
}
table tr:nth-child(2n),
thead {
    background-color: #f8f8f8;
}
table th {
    font-weight: bold;
    border: 1px solid #dfe2e5;
    border-bottom: 0;
    margin: 0;
    padding: 6px 13px;
}
table td {
    border: 1px solid #dfe2e5;
    margin: 0;
    padding: 6px 13px;
}
table th:first-child,
table td:first-child {
    margin-top: 0;
}
table th:last-child,
table td:last-child {
    margin-bottom: 0;
}

.CodeMirror-lines {
    padding-left: 4px;
}

.code-tooltip {
    box-shadow: 0 1px 1px 0 rgba(0,28,36,.3);
    border-top: 1px solid #eef2f2;
}

.md-fences,
code,
tt {
    border: 1px solid #e7eaed;
    background-color: #f8f8f8;
    border-radius: 3px;
    padding: 0;
    padding: 2px 4px 0px 4px;
    font-size: 0.9em;
}

code {
    background-color: #f3f4f4;
    padding: 0 2px 0 2px;
}

.md-fences {
    margin-bottom: 15px;
    margin-top: 15px;
    padding-top: 8px;
    padding-bottom: 6px;
}


.md-task-list-item > input {
  margin-left: -1.3em;
}

@media print {
    html {
        font-size: 13px;
    }
    pre {
        page-break-inside: avoid;
        word-wrap: break-word;
    }
}

.md-fences {
	background-color: #f8f8f8;
}
#write pre.md-meta-block {
	padding: 1rem;
    font-size: 85%;
    line-height: 1.45;
    background-color: #f7f7f7;
    border: 0;
    border-radius: 3px;
    color: #777777;
    margin-top: 0 !important;
}

.mathjax-block>.code-tooltip {
	bottom: .375rem;
}

.md-mathjax-midline {
    background: #fafafa;
}

#write>h3.md-focus:before{
	left: -1.5625rem;
	top: .375rem;
}
#write>h4.md-focus:before{
	left: -1.5625rem;
	top: .285714286rem;
}
#write>h5.md-focus:before{
	left: -1.5625rem;
	top: .285714286rem;
}
#write>h6.md-focus:before{
	left: -1.5625rem;
	top: .285714286rem;
}
.md-image>.md-meta {
    /*border: 1px solid #ddd;*/
    border-radius: 3px;
    padding: 2px 0px 0px 4px;
    font-size: 0.9em;
    color: inherit;
}

.md-tag {
    color: #a7a7a7;
    opacity: 1;
}

.md-toc { 
    margin-top:20px;
    padding-bottom:20px;
}

.sidebar-tabs {
    border-bottom: none;
}

#typora-quick-open {
    border: 1px solid #ddd;
    background-color: #f8f8f8;
}

#typora-quick-open-item {
    background-color: #FAFAFA;
    border-color: #FEFEFE #e5e5e5 #e5e5e5 #eee;
    border-style: solid;
    border-width: 1px;
}

/** focus mode */
.on-focus-mode blockquote {
    border-left-color: rgba(85, 85, 85, 0.12);
}

header, .context-menu, .megamenu-content, footer{
    font-family: "Segoe UI", "Arial", sans-serif;
}

.file-node-content:hover .file-node-icon,
.file-node-content:hover .file-node-open-state{
    visibility: visible;
}

.mac-seamless-mode #typora-sidebar {
    background-color: #fafafa;
    background-color: var(--side-bar-bg-color);
}

.mac-os #write{
    caret-color: AccentColor;
}

.md-lang {
    color: #b4654d;
}

/*.html-for-mac {
    --item-hover-bg-color: #E6F0FE;
}*/

#md-notification .btn {
    border: 0;
}

.dropdown-menu .divider {
    border-color: #e5e5e5;
    opacity: 0.4;
}

.ty-preferences .window-content {
    background-color: #fafafa;
}

.ty-preferences .nav-group-item.active {
    color: white;
    background: #999;
}

.menu-item-container a.menu-style-btn {
    background-color: #f5f8fa;
    background-image: linear-gradient( 180deg , hsla(0, 0%, 100%, 0.8), hsla(0, 0%, 100%, 0)); 
}



</style><title>Essential_QGis_operations</title>
</head>
<body class='typora-export os-windows'><div class='typora-export-content'>
<div id='write'  class=''><h1 id='essential-qgis-operations-in-roll'><span>Essential QGis operations in Roll</span></h1><h2 id='add-a-point-layer'><span>Add a Point Layer</span></h2><p><span>Adding a point layer may be needed to show the requested survey outline from a client (Area of interest), or a prospect outline from the geologist</span></p><ol><li><p><span>In QGis: Layer â†’ Add delimited text layer</span></p></li></ol><ol start='2' ><li><p><span>Select filename</span></p></li><li><p><span>Optionally, give it a layer name that is different from the file name</span></p></li><li><p><span>Check File Format</span></p></li><li><p><span>Check Record and Field Options (For header lines etc.)</span></p></li><li><p><span>Define columns that represent X, Y and optionally Z values</span></p></li><li><p><span>Finally, select </span><code>Add</code></p></li><li><p><span>Using Full Zoom </span><img src="mActionZoomFullExtent.svg" alt="mActionZoomFullExtent" style="zoom:100%;" /><span> (Ctrl+Shift+F) in QGis, you can now zoom to these points on the map</span></p></li></ol><h2 id='create-a-line-layer-from-points-vertices'><span>Create a Line layer from Points (Vertices)</span></h2><p><span>Once a point layer has been created, you can find them as a series of â€œsmall dotsâ€ in QGis. But these â€œdotsâ€ are hard to spot once you zoom out. It is therefore useful to turn these points into lines.</span></p><ol><li><p><span>In QGis: Processing â†’ Toolbox will show (or hide) the Processing Toolbox</span></p></li></ol><ol start='2' ><li><p><span>Processing Toolbox </span><strong><span>â†’</span></strong><span> Vector creation â†’ Points to path</span></p></li></ol><ol start='3' ><li><p><span>Select Input layer</span></p></li><li><p><span>Create closed path (optionally)</span></p></li><li><p><span>Then, select </span><code>Run</code><span> to create a multi-line in order the points are listed</span></p></li></ol><h2 id='create-a-filled-polygon-layer-from-lines'><span>Create a (filled) Polygon Layer from Lines</span></h2><p><span>The lines are much better visible than points, but you cannot fill a line layer. To do so, you need to convert the lines to a polygon.</span></p><ol><li><p><span>In QGis: Processing â†’ Toolbox will show (or hide) the Processing Toolbox</span></p></li></ol><ol start='2' ><li><p><span>Processing Toolbox â†’ Vector geometry â†’ Lines to polygons</span></p></li></ol><ol start='3' ><li><p><span>Select Input layer</span></p></li><li><p><span>Then, select </span><code>Run</code><span> to create a filled polygon</span></p></li><li><p><span>Double-click the polygon to show the Layer Properties</span></p></li><li><p><span>Under </span><code>Symbology</code><span> adjust the Color to a meaningful color</span></p></li><li><p><span>Reduce Opacity to less than 100% to see features in underlying layers</span></p></li><li><p><span>You can also add an outline to the polygon. To do so:</span></p></li></ol><p><span>	</span><span>a.   Add a Symbol Layer by pressing the green </span><code>Plus</code><span> Icon</span></p><p><span>	</span><span>b.   For symbol layer type select: </span><code>Outline: Simple Line</code><span> (Sits at the bottom of the list)</span></p><p><span>	</span><span>c.   Select appropriate color and Stroke width</span></p><p><span>	</span><span>d.   Select </span><strong><code>OK</code></strong></p><ol start='9' ><li><p><span>Finally, in Layers Panel â†’ context menu of the created layer â†’ Make permanent</span></p></li><li><p><span>When an outline has been added to the polygon; you may delete the line layer. The line layer served its purpose (creating a polygon) and is no longer needed for the following steps, where we edit the exported src/rec and sps/rps data in QGis.</span></p></li></ol><h3 id='export-srcrec-and-spsrps-data-from-roll-to-qgis'><span>Export src/rec and sps/rps data from Roll to QGIS</span></h3><ol start='' ><li><p><span>In Roll: File â†’ Export to QGis â†’ Export Geometry â†’ Export xxx Records to QGis</span></p></li></ol><ol start='2' ><li><p><span>Alternatively: SPS import tab â†’ Export to QGIS buttons for SPS and RPS records</span></p></li></ol><ol start='3' ><li><p><span>Alternatively: Geometry tab â†’ Export to QGIS buttons for SRC and REC records</span></p></li></ol><ol start='4' ><li><p><span>This will create in-memory (â€œscratchâ€) layers in QGIS with the exported data</span></p></li></ol><h2 id='make-scratch-srcrec-and-spsrps-layers-permanent'><span>Make scratch src/rec and sps/rps layers permanent</span></h2><p><span>To make the exported source and receiver data permanent, and available when you open the QGis project the next time, follow the steps below</span></p><ol><li><p><span>in Layers Panel â†’ context menu of the scratch layer â†’ Rename layer</span></p></li><li><p><span>Use Ctrl+C to copy the layer name. Hit escape, and do not rename</span></p></li><li><p><span>in Layers Panel â†’ context menu of the scratch layer â†’ Make Permanent</span></p></li><li><p><span>Alternatively â†’ push the â€˜scratchâ€™ button on the right side of the layerâ€™s name</span></p></li><li><p><span>Select ESRI Shapefile as file format</span></p></li><li><p><span>Select ellipses ( â€¦ ) next to filename â†’ navigate to desired file location in the dialog</span></p></li><li><p><span>Paste the â€œfilenameâ€ from clipboard in the dialogâ€™s </span><code>File name</code><span> field</span></p></li><li><p><span>Select ok. The layer is now permanent, and will be restored if the project is opened again.</span></p></li></ol><h2 id='move-srcrec-and-spsrps-points-around-in-qgis'><span>Move src/rec and sps/rps points around in QGIS</span></h2><p><span>To make changes to any of the layers you need to enable editing. To do so:</span></p><ol><li><p><span>in Layers Panel â†’ context menu of the layer with point data from Roll â†’ Toggle editing</span></p></li><li><p><span>A pencil icon will appear left of the layer name.</span></p></li><li><p><span>The pencil on the digitizing toolbar will also be highlighted.</span></p></li><li><p><span>In the digitizing toolbar select the Vertex tool for the current layer. This allows you to manipulate vertices on the active layer using one of the following methods:</span></p></li></ol><p><span>	</span><span>Â·    Right click to lock on a feature</span></p><p><span>	</span><span>Â·    Click and drag to select vertices by rectangle</span></p><p><span>	</span><span>Â·    Alt+click to select vertices by polygon</span></p><p><span>	</span><span>Â·    Shift+click/drag to add vertices to selection</span></p><p><span>	</span><span>Â·    Ctrl+click/drag to remove vertices from selection</span></p><p><span>	</span><span>Â·    Shift+R to enable range selection</span></p><h2 id='read-srcrec-and-spsrps-points-from-qgis-back-into-roll'><span>Read src/rec and sps/rps points from QGIS back into Roll</span></h2><p><span>Once changes have been made to point locations in QGis (</span><em><span>or when points have been made inactive, or have been deleted</span></em><span>) it can be useful to read these points back into Roll, to rerun analysis for Binning of Geometry data, or binning of imported SPS data. To lod modified point data back into Roll:</span></p><ol><li><p><span>In Roll: Geometry tab â†’ </span><code>Read from QGIS</code><span> buttons (for SRC and REC data separately)</span></p></li><li><p><span>In Roll: SPS import tab â†’ </span><code>Read from QGIS</code><span> buttons (for SPS and RPS data separately)</span></p></li><li><p><span>In the layer dialog that pops up:</span></p></li></ol><p><span>	</span><span>a.   Select the correct point layer from QGis, containing SPS/RPS and SRC/REC data</span></p><p><span>	</span><span>b.   Check that the CRS of the selected point layer matches that of the Roll project</span></p><p><span>	</span><span>c.   Decide whether (or not) to use a selection field code. Normally this is the </span><code>inuse</code><span> field.</span></p><p><span>	</span><span>d.   To see what fields are available in a point layer in QGis, you can:</span></p><p><span>                i.   In Layers panel â†’ Select the appropriate layer</span></p><p><span>                ii.   In context menu â†’ Open Attribute Table (Shift+F6)</span></p><p><span>               iii.   Check column headers. Roll expects the following fields:</span>
<span>			</span><code>line</code><span>, </span><code>stake</code><span>,</span><code>index</code><span>, </span><code>code</code><span>, </span><code>depth</code><span>, </span><code>elev</code><span> and </span><code>inuse</code></p><p><span>               iv.   </span><code>inuse</code><span> = 0 is used to deselect a point for analysis in Roll</span></p><p><span>                v.   Integer fields other than </span><code>inuse</code><span> may also be used to select active/passive points in Roll. See next paragraph</span></p><p><span>To update the analysis results in Roll:</span></p><ol start='4' ><li><p><span>In Rollâ€™s processing menu â†’ Binning from Geometry or Binning from Imported SPS</span></p></li></ol><h2 id='bulk-edit-srcrec-and-spsrps-points-in-qgis'><span>Bulk edit src/rec and sps/rps points in QGIS</span></h2><p><span>In Roll, survey geometry created is created using one or more rectangular blocks. In reality, a survey rarely consists of one or more rectangular shapes, but its outline is truncated according to the concession boundary, or impacted by features such as cities, lakes, etcetera. So, it will be necessary to cut (completely remove) or to switch off (mute) points in certain areas. In QGis this can be done by checking if points fall inside a polygon. There are two obvious solutions:</span></p><h4 id='clipping-the-easy-way-out'><span>Clipping: the easy way out</span></h4><p><span>Clipping will remove all points outside a selected polygonal area. It is quick and easy, but wonâ€™t allow for points to be reinstated at a later stage; gone-is-gone. This can be cumbersome when the survey area is being finetuned over several iterations. Steps are straightforward:</span></p><ol><li><p><span>Vector â†’ Geoprocessing Tools â†’ Clip â€¦</span></p></li><li><p><span>Select Input layer: the layer containing SRC/REC or SPS/RPS points</span></p></li><li><p><span>Select Overlay layer: the layer with the boundary polygon</span></p></li><li><p><span>Select Run</span></p></li><li><p><span>The clipped point layer is now created as a scratch layer.</span></p></li></ol><h4 id='clipping-future-proofing-your-edits'><span>Clipping: future proofing your edits</span></h4><p><span>This approach first selects all points that lay inside a polygon, and is followed by turning the selection flag into a permanent attribute value (normally applied to </span><code>inuse</code><span>)</span></p><ol><li><p><span>Vector â†’ Research Tools â†’ Select by Location â€¦</span></p></li><li><p><span>Select features from: chose appropriate SPS/RPS or SRC/REC point layer</span></p></li><li><p><span>For features use: </span><code>are within</code><span> (and optionally </span><code>touch</code><span>) relative to the boundary polygon</span></p></li><li><p><span>Select the appropriate polygon layer</span></p></li><li><p><span>Create a new selection</span></p></li><li><p><span>Then, select </span><code>Run</code><span> to create a selection of points inside a polygon</span></p></li><li><p><span>These points will be highlighted in yellow and marked with a red cross</span></p></li><li><p><span>Now from the Attributes toolbar â†’ Open Field Calculator</span></p></li><li><p><span>Alternatively: First open the Attribute Table </span><img src="mActionOpenTable.svg" referrerpolicy="no-referrer" alt="mActionOpenTable"><span> (F6), and then open the Field Calculator </span><img src="mActionCalculateField.svg" referrerpolicy="no-referrer" alt="mActionCalculateField"><span> (Ctrl+I)</span></p></li><li><p><span>Uncheck </span><strong><code>Only update xxx selected feature(s)</code></strong><span>. We need to update </span><strong><span>all features</span></strong><span>, also those that have not been selected. If you forget to do so, only the already selected records will be altered, and in the unselected fields a NULL value will entered.</span></p></li><li><p><span>Now, either:</span></p></li></ol><p><span>	</span><span>a.   Create a new Field, with a 32-bit integer and use the default field length, or</span></p><p><span>	</span><span>b.   Update an existing integer field, such as the </span><code>inuse</code><span> field, already created by Roll</span></p><ol start='12' ><li><p><span>In the Expression widget type the following:  </span><strong><code>is_selected()</code></strong></p></li></ol><p><span>This function returns true (=1), when a point record has been selected, and false (=0) otherwise.</span></p><ol start='13' ><li><p><span>Press </span><strong><code>OK</code></strong><span> and let the operation run on all point records of the active layer.</span></p></li><li><p><span>Upon completion, check that everything went according to plan in the Attribute Table (F6)</span></p></li><li><p><span>Now the point layer is ready to be read back into Roll (See par above).</span></p></li></ol><p><span> </span></p></div></div>
</body>
</html>
    """
    return qgisText
