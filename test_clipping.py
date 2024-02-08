########## TESTING clipLine() #############################################################

# PyQtGraph related imports

import numpy as np  # Numpy functions needed for plot creation
import pyqtgraph as pg
from qgis.PyQt.QtCore import QLineF, QRectF

from .functions import clipLine


# Local function; only used here in the functional test
def plotline(x, y, plotname='', color='b'):
    pen = pg.mkPen(color=color, width=3)
    return pg.plot(x, y, name=plotname, pen=pen, symbol='s', symbolSize=2, symbolBrush=(color), connect='pairs')


nPoints = 300
X = np.random.uniform(-100, 100, nPoints)
Y = np.random.uniform(-100, 100, nPoints)
rawLines = plotline(X, Y, 'Before truncation', 'b')                             # plot the line
rawLines.setXRange(-100, 100)                                                   # set manual scaling for example template
rawLines.setYRange(-100, 100)

border = QRectF(-40, -40, 80, 80)                                               # used to truncate against
U = np.zeros(nPoints)
V = np.zeros(nPoints)
for n in range(0, nPoints, 2):
    x1 = X[n]
    y1 = Y[n]
    x2 = X[n + 1]
    y2 = Y[n + 1]

    line = QLineF(x1, y1, x2, y2)
    line = clipLine(line, border)
    if line.isNull():
        U[n] = np.nan
        V[n] = np.nan
        U[n + 1] = np.nan
        V[n + 1] = np.nan
    else:
        U[n] = line.x1()
        V[n] = line.y1()
        U[n + 1] = line.x2()
        V[n + 1] = line.y2()

truncLines = plotline(U, V, 'After truncation', 'r')
truncLines.setXRange(-100, 100)                                                 # set manual scaling for example template
truncLines.setYRange(-100, 100)

if __name__ == '__main__':                                                      # do some tests here
    pg.exec()
