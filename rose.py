import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

QPointF = getattr(QtCore, 'QPointF')
QPainterPath = getattr(QtGui, 'QPainterPath')
QGraphicsPathItem = getattr(QtWidgets, 'QGraphicsPathItem')
QGraphicsEllipseItem = getattr(QtWidgets, 'QGraphicsEllipseItem')


def createSectorPath(sectorRadius, startAngle, endAngle, samples=24):
    path = QPainterPath(QPointF(0.0, 0.0))
    sectorAngles = np.linspace(startAngle, endAngle, samples)

    for sectorAngle in sectorAngles:
        x = sectorRadius * np.cos(sectorAngle)
        y = sectorRadius * np.sin(sectorAngle)
        path.lineTo(x, y)

    path.closeSubpath()
    return path

# 1. Setup PyQtGraph application
app = pg.mkQApp("Rose Diagram Example")
win = pg.GraphicsLayoutWidget(show=True, size=(800, 800))
win.setWindowTitle('PyQtGraph Rose Diagram')

# 2. Setup Plot
plot = win.addPlot(title="Sample Rose Plot")
plot.setAspectLocked(True)
plot.hideAxis('bottom')
plot.hideAxis('left')
plot.showGrid(x=False, y=False)

# Generate Sample Data (e.g., 16 directions, 22.5 degrees apart)
num_sectors = 16
angles = np.linspace(0, 2 * np.pi, num_sectors, endpoint=False)
# Random magnitudes representing frequencies or wind speeds
radii = np.random.normal(size=num_sectors, loc=10, scale=3)
radii[radii < 0] = 0  # Ensure no negative radii

# 3. Create Sectors for Rose Diagram
width = (2 * np.pi / num_sectors) * 0.8
max_radius = float(np.max(radii)) if len(radii) else 1.0

for angle, radius in zip(angles, radii):
    start_angle = angle - width / 2.0
    end_angle = angle + width / 2.0
    sector = QGraphicsPathItem(createSectorPath(radius, start_angle, end_angle))
    sector.setPen(pg.mkPen('w', width=1.0))
    sector.setBrush(pg.mkBrush(70, 130, 180, 190))
    plot.addItem(sector)

# Add simple radial reference rings.
for fraction in (0.25, 0.5, 0.75, 1.0):
    radius = max_radius * fraction
    ring = QGraphicsEllipseItem(-radius, -radius, 2 * radius, 2 * radius)
    ring.setPen(pg.mkPen((160, 160, 160), width=1))
    ring.setBrush(pg.mkBrush(0, 0, 0, 0))
    plot.addItem(ring)

# Add crosshair axes for orientation.
plot.addLine(x=0, pen=pg.mkPen((160, 160, 160), width=1))
plot.addLine(y=0, pen=pg.mkPen((160, 160, 160), width=1))

# 4. Customize Axis
plot.setRange(
    xRange=[-max_radius * 1.1, max_radius * 1.1],
    yRange=[-max_radius * 1.1, max_radius * 1.1],
    padding=0,
)

if __name__ == '__main__':
    pg.exec()
