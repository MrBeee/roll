"""
In this module the availability of numba is tested.
If not available, a dummy '@jit' decorator is defined

The @jit decoration can be suppressed by disabling numba in the settings menu.
This will set 'DISABLE_JIT' to True in the module numba.config.
As a result, the numbaXxx functions are no longer precompiled.

See: https://github.com/pyqtgraph/pyqtgraph/issues/1253, how to use numba with PyQtGraph
See: https://numba.readthedocs.io/en/stable/user/jit.html for preferred way of using @jit
See: https://stackoverflow.com/questions/57774497/how-do-i-make-a-dummy-do-nothing-jit-decorator
"""

import numpy as np

try:
    # See: https://github.com/pyqtgraph/pyqtgraph/issues/1253, how to use numba with PyQtGraph
    from numba import jit
except ImportError:

    def jit(**kwargs):                                                          # pylint: disable=W0613 # unused argument
        return lambda fn: fn


# @jit(nopython=True)
def numbaSlice2D(slice3D: np.ndarray, unique=False):
    size = slice3D.shape[0]
    fold = slice3D.shape[1]
    para = slice3D.shape[2]

    slice2D = slice3D.reshape(size * fold, para)                    # convert to 2D

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

    noData = np.count_nonzero(I) == 0
    return (slice2D, I, noData)                                     # triplet of information (array, mask, flag)


# @jit(nopython=True)
def numbaSlice3D(slice3D: np.ndarray, unique=False):
    if unique:                                                      # we'd like to use unique offsets; but does it make sense ?
        havUnique = slice3D[:, :, 12]                               # get all available cmp values belonging to this slice
        useUnique = True if havUnique.min() == -1 else False        # are there any -1 records ?
    else:
        useUnique = False                                           # unique not required or not available

    if useUnique:
        I = (slice3D[:, :, 2] > 0) & (slice3D[:, :, 12] == -1)      # fold > 0 AND unique == -1
    else:
        I = slice3D[:, :, 2] > 0                                    # fold > 0

    noData = np.count_nonzero(I) == 0
    return (slice3D, I, noData)                                     # triplet of information (array, mask, flag)


# @jit(nopython=True)
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
        # log_response = np.round(np.log(abs_response) * 20.0, 2)
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
@jit(nopython=True)
def numbaNdft_2D(kMin: float, kMax: float, dK: float, offsetX: np.ndarray, offsetY: np.ndarray):

    kX = np.arange(kMin, kMax, dK)
    kY = np.arange(kMin, kMax, dK)
    nX = kX.shape[0]
    nY = kY.shape[0]
    nP = offsetX.shape[0]

    xyCellStk = np.zeros(shape=(nX, nY), dtype=np.float32)  # start with empty array of the right size and type

    for x in range(nX):
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
