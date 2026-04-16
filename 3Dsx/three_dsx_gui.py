import sys

import numpy as np
import three_dsx as sx
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5.QtWidgets import (QApplication, QComboBox, QDoubleSpinBox,
                             QFileDialog, QGridLayout, QGroupBox, QHBoxLayout,
                             QLabel, QPushButton, QVBoxLayout, QWidget)


# ---------------------------------------------------------
# Matplotlib canvas widget
# ---------------------------------------------------------
class PlotCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None):
        fig = Figure(figsize=(6, 5))
        self.ax = fig.add_subplot(111)
        super().__init__(fig)
        self.setParent(parent)

    def clear(self):
        self.ax.clear()

    def draw_plot(self):
        self.draw()


# ---------------------------------------------------------
# Main GUI
# ---------------------------------------------------------
class ThreeDSXGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3Dsx Diagnostics – Python Edition")

        self.rx = None
        self.ry = None
        self.sx = None
        self.sy = None

        self.init_ui()

    # -----------------------------------------------------
    # UI Layout
    # -----------------------------------------------------
    def init_ui(self):
        layout = QHBoxLayout(self)

        # Left panel: controls
        control_panel = QVBoxLayout()

        # Load geometry button
        load_btn = QPushButton("Load Geometry (NumPy .npz)")
        load_btn.clicked.connect(self.load_geometry)
        control_panel.addWidget(load_btn)

        # Diagnostic selector
        diag_box = QGroupBox("Diagnostic")
        diag_layout = QVBoxLayout()
        self.diag_select = QComboBox()
        self.diag_select.addItems([
            "Offset Histogram",
            "Azimuth Histogram",
            "Spider Plot",
            "Multiple Suppression",
            "Stack Response",
            "DMO Spray"
        ])
        diag_layout.addWidget(self.diag_select)
        diag_box.setLayout(diag_layout)
        control_panel.addWidget(diag_box)

        # Parameter panel
        param_box = QGroupBox("Parameters")
        grid = QGridLayout()

        # Example parameters
        grid.addWidget(QLabel("Min Offset"), 0, 0)
        self.min_off = QDoubleSpinBox()
        self.min_off.setRange(0, 5000)
        self.min_off.setValue(0)
        grid.addWidget(self.min_off, 0, 1)

        grid.addWidget(QLabel("Max Offset"), 1, 0)
        self.max_off = QDoubleSpinBox()
        self.max_off.setRange(0, 5000)
        self.max_off.setValue(2500)
        grid.addWidget(self.max_off, 1, 1)

        grid.addWidget(QLabel("Velocity (m/s)"), 2, 0)
        self.vel = QDoubleSpinBox()
        self.vel.setRange(500, 6000)
        self.vel.setValue(2000)
        grid.addWidget(self.vel, 2, 1)

        grid.addWidget(QLabel("t0 (s)"), 3, 0)
        self.t0 = QDoubleSpinBox()
        self.t0.setRange(0.1, 5)
        self.t0.setValue(1.0)
        grid.addWidget(self.t0, 3, 1)

        param_box.setLayout(grid)
        control_panel.addWidget(param_box)

        # Run button
        run_btn = QPushButton("Run Diagnostic")
        run_btn.clicked.connect(self.run_diagnostic)
        control_panel.addWidget(run_btn)

        control_panel.addStretch()
        layout.addLayout(control_panel)

        # Right panel: plot
        self.canvas = PlotCanvas(self)
        layout.addWidget(self.canvas)

    # -----------------------------------------------------
    # Load geometry
    # -----------------------------------------------------
    def load_geometry(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Load Geometry", "", "NumPy files (*.npz)")
        if not fname:
            return

        data = np.load(fname)
        self.rx = data["rx"]
        self.ry = data["ry"]
        self.sx = data["sx"]
        self.sy = data["sy"]

    # -----------------------------------------------------
    # Run selected diagnostic
    # -----------------------------------------------------
    def run_diagnostic(self):
        if self.rx is None:
            return

        diag = self.diag_select.currentText()
        self.canvas.clear()

        offsets = sx.compute_offsets(self.rx, self.ry, self.sx, self.sy)
        az = sx.compute_azimuths(self.rx, self.ry, self.sx, self.sy)

        if diag == "Offset Histogram":
            self.canvas.ax.hist(offsets, bins=30)
            self.canvas.ax.set_title("Offset Histogram")

        elif diag == "Azimuth Histogram":
            self.canvas.ax.hist(np.degrees(az) % 360, bins=36)
            self.canvas.ax.set_title("Azimuth Histogram")

        elif diag == "Spider Plot":
            self.canvas.ax = self.canvas.figure.add_subplot(111, projection="polar")
            self.canvas.ax.scatter(az, offsets, s=5)
            self.canvas.ax.set_title("Spider Plot")

        elif diag == "Multiple Suppression":
            R = sx.multiple_suppression(
                offsets,
                fmin=5, fmax=60,
                VM=self.vel.value(),
                VP=self.vel.value() * 1.2,
                t0=self.t0.value()
            )
            self.canvas.ax.text(0.1, 0.5, f"Multiple Suppression:\n{R:.4f}", fontsize=14)
            self.canvas.ax.set_axis_off()

        elif diag == "Stack Response":
            R = sx.stack_response(offsets, lam_min=50, lam_max=500)
            self.canvas.ax.text(0.1, 0.5, f"Stack Response:\n{R:.4f}", fontsize=14)
            self.canvas.ax.set_axis_off()

        elif diag == "DMO Spray":
            shift_x, shift_y = sx.dmo_point_movement(
                offsets,
                dip_deg=20,
                azimuth_deg=45,
                V=self.vel.value(),
                t0=self.t0.value()
            )
            self.canvas.ax.plot(offsets, shift_x, label="Inline shift")
            self.canvas.ax.plot(offsets, shift_y, label="Crossline shift")
            self.canvas.ax.set_xlabel("Offset (m)")
            self.canvas.ax.set_ylabel("Shift (m)")
            self.canvas.ax.set_title("DMO Spray")
            self.canvas.ax.legend()

        self.canvas.draw_plot()


# ---------------------------------------------------------
# Run the application
# ---------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = ThreeDSXGUI()
    gui.show()
    sys.exit(app.exec_())
