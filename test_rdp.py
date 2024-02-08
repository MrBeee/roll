########## TESTING rdp.filter() #############################################################

# PyQtGraph related imports
import numpy as np  # Numpy functions needed for plot creation
import pyqtgraph as pg

from .rdp import filter as rdp


# Local function; only used here in the functional test
def plotline(pnts, plotname='', color='b'):
    pen = pg.mkPen(color=color, width=3)
    return pg.plot(pnts, name=plotname, pen=pen, symbol='s', symbolSize=2, symbolBrush=(color))


points = np.random.uniform(-100, 100, size=(10, 2))
mask = rdp(points, threshold=10)
print(mask)

rawLine = plotline(points, 'Before filtering', 'b')                             # plot the line
rawLine.setXRange(-100, 100)                                                    # set manual scaling for example template
rawLine.setYRange(-100, 100)


# truncLines = plotline(U, V, "After truncation", 'r')
# truncLines.setXRange(-100, 100)                                                 # set manual scaling for example template
# truncLines.setYRange(-100, 100)

if __name__ == '__main__':                                                      # do some tests here
    pg.exec()
