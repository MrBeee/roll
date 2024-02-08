import os
import os.path

import pyqtgraph as pg
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QLabel, QSizePolicy, QToolBar, QWidget

# See: https://www.pythonguis.com/tutorials/pyqt-actions-toolbars-menus/


class PgToolBar(QToolBar):
    def __init__(self, title: str, parent=None, plotWidget=None):
        super().__init__(parent)

        # access the plotwidget
        self.plotWidget = plotWidget

        # to set the button states
        self.rect = False
        self.XisY = True
        self.antA = False
        self.grid = True

        # to access the parent and its components
        self.setWindowTitle(title)
        self.setIconSize(QSize(24, 24))

        # define actions for PyQtGraph toolbar
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.actionZoomAll = QAction(QIcon(os.path.join(current_dir, 'resources/mActionZoomFullExtent.svg')), '&ZoomAll', self)
        self.actionZoomRect = QAction(QIcon(os.path.join(current_dir, 'resources/mActionZoomRect.svg')), '&ZoomRect', self)
        self.actionAntiAlias = QAction(QIcon(os.path.join(current_dir, 'resources/mActionPlotAntiAlias.svg')), '&antiAlias', self)
        self.actionAspectRatio = QAction(QIcon(os.path.join(current_dir, 'resources/mActionZoomAspectRatio.svg')), '&aspectRatio', self)
        self.actionGridLines = QAction(QIcon(os.path.join(current_dir, 'resources/mActionPlotGrid.svg')), '&Gridlines', self)

        # add actions to toolbar
        self.addAction(self.actionZoomAll)
        self.addAction(self.actionZoomRect)
        self.addAction(self.actionAspectRatio)
        self.addAction(self.actionAntiAlias)
        self.addAction(self.actionGridLines)

        # add widget(s) to show mouse position in toolbar
        self.emptyWidget = QWidget()
        self.emptyWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.addWidget(self.emptyWidget)

        self.posWidget = QLabel('(x, y): (0.00, 0.00)')
        self.addWidget(self.posWidget)

        # the following signals and slots are related to the plotWidget's toolbar
        self.actionZoomAll.triggered.connect(self.plotWidget.autoRange)

        self.actionZoomRect.setCheckable(True)
        self.actionZoomRect.setChecked(self.rect)
        self.actionZoomRect.triggered.connect(self.plotZoomRect)

        self.actionAspectRatio.setCheckable(True)
        self.actionAspectRatio.setChecked(self.XisY)
        self.actionAspectRatio.triggered.connect(self.plotAspectRatio)

        self.actionAntiAlias.setCheckable(True)
        self.actionAntiAlias.setChecked(self.antA)
        self.actionAntiAlias.triggered.connect(self.plotAntiAlias)

        self.actionGridLines.setCheckable(True)
        self.actionGridLines.setChecked(self.grid)
        self.actionGridLines.triggered.connect(self.plotGridLines)

        if not self.plotWidget is None:
            self.plotWidget.scene().sigMouseMoved.connect(self.MouseMovedInPlot)

    def setPlotWidget(self, plotWidget):
        self.plotWidget = plotWidget
        self.plotWidget.scene().sigMouseMoved.connect(self.MouseMovedInPlot)

    def plotZoomRect(self):
        if not self.plotWidget is None:
            self.rect = not self.rect
            if self.rect:
                self.plotWidget.getViewBox().setMouseMode(pg.ViewBox.RectMode)
            else:
                self.plotWidget.getViewBox().setMouseMode(pg.ViewBox.PanMode)

    def plotAspectRatio(self):
        if not self.plotWidget is None:
            self.XisY = not self.XisY
            self.plotWidget.setAspectLocked(self.XisY)

    def plotAntiAlias(self):
        if not self.plotWidget is None:
            self.antA = not self.antA
            self.plotWidget.setAntialiasing(self.antA)                          # enabl/disable aa plotting

    def plotGridLines(self):
        if not self.plotWidget is None:
            self.grid = not self.grid
            if self.grid:
                self.plotWidget.showGrid(x=True, y=True, alpha=0.5)             # shows the grey grid lines
            else:
                self.plotWidget.showGrid(x=False, y=False)                      # hides the grey grid lines

    def MouseMovedInPlot(self, evt):                                            # See: https://stackoverflow.com/questions/46166205/display-coordinates-in-pyqtgraph
        if not self.plotWidget is None:
            pos = evt
            if self.plotWidget.sceneBoundingRect().contains(pos):
                mousePoint = self.plotWidget.plotItem.vb.mapSceneToView(pos)
                x = float(f'{mousePoint.x():.2f}')
                y = float(f'{mousePoint.y():.2f}')
                self.posWidget.setText(f'(x, y): {x, y}')
