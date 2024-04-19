# Python routine to implement Cohen Sutherland algorithm for line clipping.
# See: https://www.geeksforgeeks.org/line-clipping-set-1-cohen-sutherland-algorithm/
# See: https://en.wikipedia.org/wiki/Cohen%E2%80%93Sutherland_algorithm
# See: https://www.geeksforgeeks.org/line-clipping-set-2-cyrus-beck-algorithm/?ref=rp

try:
    import numba
except ImportError:
    numba = None

import configparser
import os
import pickle
import re
import sys
from pathlib import Path

import numpy as np
import pyqtgraph as pg
import rasterio as rio
import wellpathpy as wp
from qgis.PyQt.QtCore import PYQT_VERSION_STR, QT_VERSION_STR, QLineF, QPointF, QRectF, Qt
from qgis.PyQt.QtGui import QColor, QPen, QPolygonF, QVector3D


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


def getNameFromQtEnum(enum, value):
    # See: _getAllowedEnums(self, enum), defined in pyqtgraph; qtenum.py.
    # References to PySide have been removed. QGIS uses PyQt5 only...
    searchObj = Qt
    vals = {}
    for key in dir(searchObj):
        val = getattr(searchObj, key)
        if isinstance(val, enum):
            vals[key] = val

    result = [k for k, v in vals.items() if v == value][0]
    return result


# See: https://github.com/bensarthou/pynufft_benchmark/blob/master/NDFT.py
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

    # Earlier I had a problem that the class Line(QlineF) returned a QLineF object instead of a Line object
    # So I decided to define the clipping function outside of a class.

    # Define region codes
    INSIDE = 0  # 0000
    LEFT = 1  # 0001
    RIGHT = 2  # 0010
    BOTTOM = 4  # 0100
    TOP = 8  	# 1000

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
        if x < x_min:                                                         # to the left of rectangle
            code |= LEFT
        elif x > x_max:                                                         # to the right of rectangle
            code |= RIGHT
        if y < y_min:                                                         # below the rectangle
            code |= BOTTOM
        elif y > y_max:                                                         # above the rectangle
            code |= TOP
        return code

    # Compute region codes for P1, P2
    code1 = computeCode(x1, y1)
    code2 = computeCode(x2, y2)
    accept = False

    while True:                                                                 # Keep doing this, till we can escape

        if code1 == 0 and code2 == 0:                                      # both endpoints lie within rectangle
            accept = True
            break

        if (code1 & code2) != 0:                                          # both endpoints are outside rectangle
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
        if code_out & TOP:  		                                        # point is above the clip rectangle
            x = x1 + (x2 - x1) * (y_max - y1) / (y2 - y1)
            y = y_max

        elif code_out & BOTTOM:  		                                    # point is below the clip rectangle
            x = x1 + (x2 - x1) * (y_min - y1) / (y2 - y1)
            y = y_min

        elif code_out & RIGHT:  		                                    # point is to the right of the clip rectangle
            y = y1 + (y2 - y1) * (x_max - x1) / (x2 - x1)
            x = x_max

        elif code_out & LEFT:  		                                    # point is to the left of the clip rectangle
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
        return QLineF(x1, y1, x2, y2)                                       # return the clipped line

    return QLineF()                                                     # return a null line


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


# def deviation(northing, easting, depth):
#     """Deviation survey

#     Compute an approximate deviation survey from the position log, i.e. the
#     measured that would be convertable to this well path. It is assumed
#     that inclination, azimuth, and measured-depth starts at 0.

#     Returns
#     -------
#     dev : deviation

#     The implementation is based on this [1] stackexchange answer by tma,
#     which is included verbatim for future reference.

#         In order to get a better picture you should look at the problem in
#         2d. Your arc from (x1,y1,z1) to (x2,y2,z2) lives in a 2d plane,
#         also in the same pane the tangents (a1,i1) and (a2, i2). The 2d
#         plane is given by the vector (x1,y1,y3) to (x2,y2,z2) and vector
#         converted from polar to Cartesian of (a1, i1). In case their
#         co-linear is just a straight line and your done. Given the angle
#         between the (x1,y1,z2) and (a1, i1) be alpha, then the angle
#         between (x2,y2,z2) and (a2, i2) is â€“alpha. Use the normal vector of
#         the 2d plane and rotate normalized vector (x1,y1,z1) to (x2,y2,z2)
#         by alpha (maybe â€“alpha) and converter back to polar coordinates,
#         which gives you (a2,i2). If d is the distance from (x1,y1,z1) to
#         (x2,y2,z2) then MD = d* alpha /sin(alpha).

#     In essence, the well path (in cartesian coordinates) is evaluated in
#     segments from top to bottom, and for every segment the inclination and
#     azimuth "downwards" are reconstructed. The reconstructed inc and azi is
#     used as "entry angle" of the well bore into the next segment. This uses
#     some assumptions deriving from knowing that the position log was
#     calculated with the min-curve method, since a straight
#     cartesian-to-spherical conversion could be very sensitive [2].

#     [1] https://math.stackexchange.com/a/1191620
#     [2] I observed low error on average, but some segments could be off by
#         80 degrees azimuth
#     """
#     upper = zip(northing[:-1], easting[:-1], depth[:-1])
#     lower = zip(northing[1:], easting[1:], depth[1:])

#     # Assume the initial depth and angles are all zero, but this can likely
#     # be parametrised.
#     incs, azis, mds = [0], [0], [0]
#     i1, a1 = 0, 0

#     for up, lo in zip(upper, lower):
#         up = np.array(up)
#         lo = np.array(lo)

#         # Make two vectors
#         # v1 is the vector from the upper survey station to the lower
#         # v2 is the vector formed by the initial inc/azi (given by the
#         # previous iteration).
#         #
#         # The v1 and v2 vectors form a plane the well path arc lives in.
#         v1 = lo - up
#         v2 = np.array(wp.geometry.direction_vector(i1, a1))

#         alpha = wp.geometry.angle_between(v1, v2)
#         normal = wp.geometry.normal_vector(v1, v2)

#         # v3 is the "exit vector", i.e. the direction of the well bore
#         # at the lower survey station, which would in turn be "entry
#         # direction" in the next segment.
#         v3 = wp.geometry.rotate(v1, normal, -alpha)
#         i2, a2 = wp.geometry.spherical(*v3)

#         # d is the length of the vector (straight line) from the upper
#         # station to the lower station.
#         d = np.linalg.norm(v1)
#         incs.append(i2)
#         azis.append(a2)
#         if alpha == 0:
#             mds.append(d)
#         else:
#             mds.append(d * alpha / np.sin(alpha))
#         # The current lower station is the upper station in the next
#         # segment.
#         i1 = i2
#         a1 = a2

#     mds = np.cumsum(mds)
#     return wp.deviation(md=np.array(mds), inc=np.array(incs), azi=np.array(azis))


# def read_wws_header(filename):
#     header = {'datum': 'dfe', 'elevation_units': 'm', 'elevation': None, 'surface_coordinates_units': 'm', 'surface_easting': None, 'surface_northing': None}
#     # Note: datum = kb (kelly bushing), dfe (drill floor elevation), or rt (rotary table)

#     # need to adjust northing and easting and elevation; use keywords from the well file itself
#     keywords = ['$Wellbore_name:', '$Well_name:', '$Status_of_Well:', '$Well_northing:', '$Well_easting:', '$Derrick_elevation:']
#     # example output
#     # 0 $Wellbore_name: PR01
#     # 1 $Well_name: PR01
#     # 2 $Status_of_Well: EXISTING
#     # 3 $Well_northing: 7623750.00
#     # 4 $Well_easting: 185250.00
#     # 5 $Derrick_elevation: 0.00

#     with open(filename, 'r', encoding='utf-8') as file:
#         for index, line in enumerate(file):
#             if not line.startswith('#'):
#                 break
#             for i, k in enumerate(keywords):
#                 if k in line:
#                     val = line.split(':')                                   # behind ':' sits the keyword value
#                     val = val[1].split('\n')                                # if keyword value followed by \n, get rid of it
#                     val = val[0].split('[')                                 # if keyword value followed by '[', get rid of what follows
#                     if len(val) > 1:
#                         unit = val[1].split(']')[0]
#                     else:
#                         unit = None
#                     val = val[0].strip()    	                            # turn list into string, get rid of leading/trailing spaces
#                     print('line:', index + 1, 'keyword nr:', i + 1, 'keyword:', k, 'value:', val, 'unit:', unit)
#                     if i == 3:
#                         header['surface_northing'] = float(val)
#                         header['surface_coordinates_units'] = unit
#                     if i == 4:
#                         header['surface_easting'] = float(val)
#                     if i == 5:
#                         header['elevation'] = float(val)
#                         header['elevation_units'] = unit
#     return header


# def read_well_header(filename):
#     header = {'datum': 'dfe', 'elevation_units': 'm', 'elevation': None, 'surface_coordinates_units': 'm', 'surface_easting': None, 'surface_northing': None}
#     # Note: datum = kb (kelly bushing), dfe (drill floor elevation), or rt (rotary table)

#     # need to adjust northing and easting and elevation; use keywords from the well file itself
#     keywords = ['Depth-Unit:', 'UniqOff Well ID:', 'Operator:', 'State:', 'County:', 'Surface coordinate:', 'Replacement velocity [from KB to SRD]:']

#     with open(filename, 'r', encoding='utf-8') as file:
#         nExclamation = 0
#         index = 0
#         for index, line in enumerate(file):
#             if line.startswith('!'):
#                 nExclamation += 1
#                 if nExclamation == 2:
#                     break                                               # time to start reading the data
#                 else:
#                     continue

#             for i, k in enumerate(keywords):
#                 if k in line:
#                     val = line.split(':')                               # behind ':' sits the keyword value
#                     val = val[1].split('\n')                            # if keyword value followed by \n, get rid of it
#                     val = val[0].strip()    	                        # turn list into string, get rid of leading/trailing spaces

#                     print('line:', index + 1, 'keyword nr:', i + 1, 'keyword:', k, 'value:', val)

#                     if i == 0:
#                         header['elevation_units'] = val.lower()[0]
#                         header['surface_coordinates_units'] = 'm'       # actually should be equal to coordinate units of CRS; could be feet
#                     if i == 5:
#                         val = val.strip(' ()')
#                         val = val.split(',')
#                         header['surface_northing'] = float(val[1])
#                         header['surface_easting'] = float(val[0])
#     return header, index


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

    if numba is None:
        numbaVersion = 'not installed'
    else:
        numbaVersion = numba.__version__

    sourceUrl = "<a href='https://github.com/MrBeee/roll'>here</a>"
    sampleUrl = "<a href='https://github.com/MrBeee/roll_samples'>here</a>"

    text = (
        f'Roll can be used to generate seismic survey geometries. <br>'
        f'Both for Land/OBN as well as marine seismic surveys. <ul>'
        f'<li>Roll version: {rollVersion}. </li></ul>'
        f'The following Qt-framework is used: <ul>'
        f'<li>Qt version: {QT_VERSION_STR} </li>'
        f'<li>PyQt version: {PYQT_VERSION_STR} </li></ul>'
        f'The following libraries are used: <ul>'
        f'<li>Numba version: {numbaVersion} </li>'
        f'<li>Numpy version: {np.__version__} </li>'
        f'<li>PyQtGraph version: {pg.__version__} </li>'
        f'<li>Rasterio version: {rio.__version__} </li>'
        f'<li>Wellpathpy version: {wp.__version__} </li></ul>'
        f'Source code is available on GitHub {sourceUrl} <br> '
        f'Sample projects are available on GitHub {sampleUrl} <br><br> '
        f'Copyright © 2022-2024 by Duijndam.Dev'
    )

    return text


def licenseText() -> str:
    licenseTxt = """
    Copyright  © 2022-2024 by Duijndam.Dev. All rights reserved.

    Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

    Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

    Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

    Neither the name of Mapbox nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS “AS IS” AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL DUIJNDAM.DEV BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
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
            <angles azimin="0.0" refmin="0.0" azimax="360.0" refmax="45.0"/>
            <binning method="cmp"/>
            <offset xmax="5976.0" ymin="-776.0" ymax="776.0" xmin="-5976.0" rmin="0.0" rmax="6027.0"/>
            <output xmax="7225.0" ymin="1400.0" ymax="1800.0" xmin="6975.0"/>
            <unique apply="False" deltaoff="200.0" deltaazi="5.0"/>
        </limits>
        <reflectors>
            <plane z0="-2000.0" y0="450000.0" dip="4.0" azi="45.0" x0="150000.0"/>
            <!--Plane equation: -0.049325·x + -0.049325·y + 0.997564·z + 31590.294922 = 0  -->
            <!--Plane is defined in global coordinates. Subsurface corresponds with negative z-values-->
            <sphere z0="-4000.0" y0="456100.0" radius="2000.0" x0="153900.0"/>
            <!--Sphere is defined in global coordinates. Subsurface corresponds with negative z-values-->
        </reflectors>
        <grid>
            <local x0="12.5" y0="12.5" fold="-1" dx="25.0" dy="25.0" l0="1000.0" s0="1000.0"/>
            <global x0="150000.0" sx="1.0" sy="1.0" y0="450000.0" azi="45.0"/>
            <!--Forward transform: A0=10000.000, B0=10000.000, A1=0.707107, B1=0.707107, A2=-0.707107, B2=0.707107-->
            <!--Inverse transform: A0=-14142.136, B0=0.000, A1=0.707107, B1=-0.707107, A2=0.707107, B2=0.707107-->
            <!--See EPSG:9624 (https://epsg.io/9624-method) for the affine parametric transform definition-->
        </grid>
        <block_list>
            <block>
                <name>Block-1</name>
                <borders>
                    <src_border xmin="-20000.0" xmax="20000.0" ymin="-20000.0" ymax="20000.0"/>
                    <rec_border xmin="0.0" xmax="0.0" ymin="0.0" ymax="0.0"/>
                </borders>
                <template_list>
                    <template>
                        <name>Template-1</name>
                        <roll_list>
                            <translate n="10" dx="0.0" dy="200.0"/>
                            <translate n="10" dx="250.0" dy="0.0"/>
                        </roll_list>
                        <seed_list>
                            <seed x0="5975.0" src="True" y0="625.0" argb="#77ff0000" typno="0" azi="False" patno="0">
                                <name>Src-1</name>
                                <grow_list>
                                    <translate n="1" dx="250.0" dy="0.0"/>
                                    <translate n="4" dx="0.0" dy="50.0"/>
                                </grow_list>
                            </seed>
                            <seed x0="0.0" src="False" y0="0.0" argb="#7700b0f0" typno="0" azi="False" patno="1">
                                <name>Rec-1</name>
                                <grow_list>
                                    <translate n="8" dx="0.0" dy="200.0"/>
                                    <translate n="240" dx="50.0" dy="0.0"/>
                                </grow_list>
                            </seed>
                        </seed_list>
                    </template>
                </template_list>
            </block>
        </block_list>
        <pattern_list>
            <pattern x0="-0.0" y0="-12.5" argb="#ffff0000">
                <name>src-array</name>
                <grow_list>
                    <translate n="1" dx="0.0" dy="0.0"/>
                    <translate n="3" dx="0.0" dy="12.5"/>
                </grow_list>
            </pattern>
            <pattern x0="-20.8333" y0="-20.825" argb="#ff0000ff">
                <name>rec-array</name>
                <grow_list>
                    <translate n="3" dx="16.6667" dy="0.0"/>
                    <translate n="2" dx="8.333" dy="8.333"/>
                    <translate n="3" dx="0.0" dy="16.667"/>
                </grow_list>
            </pattern>
        </pattern_list>
    </survey>"""
    return xmlText
