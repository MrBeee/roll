# Python routine to implement Cohen Sutherland algorithm for line clipping.
# See: https://www.geeksforgeeks.org/line-clipping-set-1-cohen-sutherland-algorithm/
# See: https://en.wikipedia.org/wiki/Cohen%E2%80%93Sutherland_algorithm
# See: https://www.geeksforgeeks.org/line-clipping-set-2-cyrus-beck-algorithm/?ref=rp

try:    # need to TRY importing numba, only to see if it is available
    haveNumba = True
    import numba  # pylint: disable=W0611
except ImportError:
    haveNumba = False

try:    # need to TRY importing debugpy, only to see if it is available
    haveDebugpy = True
    import debugpy  # pylint: disable=W0611
except ImportError as ie:
    haveDebugpy = False


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
from qgis.core import QgsGeometry, QgsPointXY
from qgis.PyQt.QtCore import (PYQT_VERSION_STR, QT_VERSION_STR, QLineF,
                              QPointF, QRectF, Qt)
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
    debugVersion = debugpy.__version__ if haveDebugpy else 'not installed'

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
        f'<li>Debugpy version: {debugVersion} </li>'
        f'<li>Numba version: {numbaVersion} </li>'
        f'<li>Numpy version: {np.__version__} </li>'
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
