# this file contains experimental code for CFP (Common Focal Point) analysis;

import numpy as np
import pyqtgraph as pg
from qgis.PyQt.QtCore import QRectF, QThread, pyqtSignal
from qgis.PyQt.QtWidgets import QVBoxLayout, QWidget

from .cfp_aux_functions_numba import (compute_one_way_beam,
                                      filter_indices_by_aperture)


def calculate_resolution_matrix(focal_x, focal_y, focal_z, src_coords, rec_coords, freqs, v_int, matlab_compat=False):
    """
    Computes the final round-trip focal beam response (Resolution Matrix).
    """
    # 1. Synthesize Source Beam
    B_s = compute_one_way_beam(
        focal_x, focal_y, focal_z,
        src_coords['x'], src_coords['y'], src_coords['z'],
        freqs, v_int, matlab_compat=matlab_compat
    )

    # 2. Synthesize Receiver Beam
    B_r = compute_one_way_beam(
        focal_x, focal_y, focal_z,
        rec_coords['x'], rec_coords['y'], rec_coords['z'],
        freqs, v_int, matlab_compat=matlab_compat
    )

    # 3. Double-Focusing Synthesis (Element-wise multiplication in frequency)
    B_res = B_s * B_r

    # 4. Integrate across the source spectrum band to yield total energy
    total_energy = np.sum(np.abs(B_res))

    return total_energy


def extract_active_geometry_vectors(mmap_data, active_trace_indices):
    """
    Extracts explicit, flat x,y,z coordinate vectors from the application's
    memory-mapped analysis file for a specific subset of active traces.

    Parameters:
    -----------
    mmap_data : memmap or structure
        Your open binary memory-mapped trace header/geometry table.
    active_trace_indices : 1D array of int
        The row indices corresponding to the selected live template or spatial aperture.
    """
    # Allocate standard contiguous NumPy arrays for the numba engine
    n_traces = len(active_trace_indices)

    src_x = np.zeros(n_traces, dtype=np.float64)
    src_y = np.zeros(n_traces, dtype=np.float64)
    src_z = np.zeros(n_traces, dtype=np.float64)

    rec_x = np.zeros(n_traces, dtype=np.float64)
    rec_y = np.zeros(n_traces, dtype=np.float64)
    rec_z = np.zeros(n_traces, dtype=np.float64)

    # Direct block slice reads out of the memory-mapped arrays
    # (Adjust field descriptors like 'source_x' to match your explicit structural names)
    src_x[:] = mmap_data['source_x'][active_trace_indices]
    src_y[:] = mmap_data['source_y'][active_trace_indices]
    src_z[:] = mmap_data['source_z'][active_trace_indices]

    rec_x[:] = mmap_data['receiver_x'][active_trace_indices]
    rec_y[:] = mmap_data['receiver_y'][active_trace_indices]
    rec_z[:] = mmap_data['receiver_z'][active_trace_indices]

    return src_x, src_y, src_z, rec_x, rec_y, rec_z


def evaluate_subsurface_focal_point(focal_coord, mmap_data, active_indices, freqs, v_int, matlab_compat=False):
    """
    Acts as the main operational wrapper bridging Roll's memory architecture
    and the high-speed numba Rayleigh propagation functions.

    Parameters:
    -----------
    focal_coord : tuple (x, y, z)
        The specific subsurface target spatial point being evaluated.
    """
    f_x, f_y, f_z = focal_coord

    # 1. Unpack structured memory maps to contiguous 1D float arrays
    src_x, src_y, src_z, rec_x, rec_y, rec_z = extract_active_geometry_vectors(
        mmap_data, active_indices
    )

    # 2. Call the numba njit function for the Source Wavefront Beam
    # (Using the compute_one_way_beam function defined previously)
    B_s = compute_one_way_beam(
        f_x, f_y, f_z,
        src_x, src_y, src_z,
        freqs, v_int, matlab_compat=matlab_compat
    )

    # 3. Call the numba njit function for the Receiver Wavefront Beam
    B_r = compute_one_way_beam(
        f_x, f_y, f_z,
        rec_x, rec_y, rec_z,
        freqs, v_int, matlab_compat=matlab_compat
    )

    # 4. Synthesize round-trip focal energy response across the spectrum
    # (Double-focusing principle)
    B_res = B_s * B_r

    # Integrate energy across frequency to compress to a single scalar magnitude
    total_energy = np.sum(np.abs(B_res))

    return total_energy


def generate_horizon_illumination_map(target_z, x_range, y_range, step_size, mmap_data, active_indices, freqs, v_int, max_dip, matlab_compat=False):
    """
    Generates a full 2D grid matrix mapping illumination anomalies and
    footprints at target depth using spatial aperture pre-filtering.

    Parameters:
    -----------
    target_z : float
        The absolute subsurface depth of your structured target horizon.
    x_range : tuple (x_min, x_max)
        The horizontal spatial limits for the In-line axis.
    y_range : tuple (y_min, y_max)
        The horizontal spatial limits for the Cross-line axis.
    step_size : float
        The spatial grid increments (typically matching your survey bin size).
    mmap_data : memmap
        Your open binary memory-mapped trace header/geometry table.
    active_indices : 1D array of int
        The row indices corresponding to the selected live template traces.
    freqs : 1D float array
        The discrete frequency spectrum to evaluate.
    v_int : float
        Interval velocity (vint from your XML configuration).
    max_dip : float
        The maximum structural dip angle (in degrees) to clear for imaging.
    """
    # Unpack boundaries
    x_min, x_max = x_range
    y_min, y_max = y_range

    grid_x = np.arange(x_min, x_max, step_size)
    grid_y = np.arange(y_min, y_max, step_size)

    illumination_matrix = np.zeros((len(grid_y), len(grid_x)), dtype=np.float64)

    # Loop over the horizon coordinate mesh grid
    for j, y_f in enumerate(grid_y):
        for i, x_f in enumerate(grid_x):
            # Pass all parameters down to the optimized evaluation function
            energy = evaluate_subsurface_focal_point_optimized(
                (x_f, y_f, target_z),
                mmap_data,
                max_dip,        # Placed into the execution thread chain
                freqs,
                v_int,
                matlab_compat=matlab_compat
            )
            illumination_matrix[j, i] = energy

    # Normalize the final raster grid from 0.0 to 1.0 for UI display
    max_energy = np.max(illumination_matrix)
    if max_energy > 0:
        illumination_matrix /= max_energy

    return grid_x, grid_y, illumination_matrix


def evaluate_subsurface_focal_point_optimized(focal_coord, mmap_data, max_dip, freqs, v_int, matlab_compat=False):
    """
    Optimized wrapper that filters out non-illuminating surface traces
    before executing the heavy Rayleigh integral math.
    """
    f_x, f_y, f_z = focal_coord

    # 1. Isolate relevant surface indices using the memory-mapped midpoint columns
    # (Assumes your mmap structure has 'midpoint_x' and 'midpoint_y' pre-computed)
    active_indices = filter_indices_by_aperture(
        f_x, f_y, f_z,
        max_dip,
        mmap_data['midpoint_x'],
        mmap_data['midpoint_y'],
        matlab_compat=matlab_compat
    )

    # If no surface traces illuminate this deep point, skip entirely
    if len(active_indices) == 0:
        return 0.0

    # 2. Extract ONLY the necessary geometry records into contiguous memory arrays
    src_x, src_y, src_z, rec_x, rec_y, rec_z = extract_active_geometry_vectors(
        mmap_data, active_indices
    )

    # 3. Perform wavefield extrapolation only on the surviving traces
    B_s = compute_one_way_beam(f_x, f_y, f_z, src_x, src_y, src_z, freqs, v_int, matlab_compat=matlab_compat)
    B_r = compute_one_way_beam(f_x, f_y, f_z, rec_x, rec_y, rec_z, freqs, v_int, matlab_compat=matlab_compat)

    # 4. Synthesize round-trip focal energy response
    B_res = B_s * B_r
    total_energy = np.sum(np.abs(B_res))

    return total_energy


class RollIlluminationMapWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        # Create a GraphicsLayoutWidget for standard scientific plots
        self.win = pg.GraphicsLayoutWidget()
        layout.addWidget(self.win)

        # Add a 2D Plot view to host the raster matrix
        self.plot_item = self.win.addPlot()
        self.plot_item.setLabel('bottom', 'In-Line Coordinate', units='m')
        self.plot_item.setLabel('left', 'Cross-Line Coordinate', units='m')
        self.plot_item.setTitle('Subsurface Horizon Illumination Mask (CFP Method)')
        self.plot_item.setAspectLocked(True)  # Keeps aspect ratio 1:1 spatially

        # Create the optimized ImageItem container for the raster data
        self.image_item = pg.ImageItem()
        self.plot_item.addItem(self.image_item)

        # Set up a clear seismic/illumination colormap (Inferno)
        # Low energy (footprints/shadows) = Black/Purple | High energy = Orange/White
        colormap = pg.colormap.get('inferno')
        bar = pg.ColorBarItem(values=(0, 1))
        bar.setImageItem(self.image_item)
        bar.setColorMap(colormap)
        self.win.addItem(bar)

    def update_map(self, grid_x, grid_y, illumination_matrix):
        """
        Pipes the calculated numpy outputs directly into the graphics view.

        Parameters:
        -----------
        grid_x : 1D float array (In-line coordinates)
        grid_y : 1D float array (Cross-line coordinates)
        illumination_matrix : 2D float array (Normalized energy values [0.0 - 1.0])
        """
        # Transpose needed because PyQtGraph maps matrices as image space (X, Y)
        # instead of standard matrix index space (Rows/Y, Cols/X)
        render_matrix = illumination_matrix.T

        # Calculate bounding box transform details
        x_min, x_max = grid_x[0], grid_x[-1]
        y_min, y_max = grid_y[0], grid_y[-1]

        # x_scale = (x_max - x_min) / max(1, (len(grid_x) - 1))
        # y_scale = (y_max - y_min) / max(1, (len(grid_y) - 1))

        # Pass data matrix to item
        self.image_item.setImage(render_matrix)

        # Set the spatial positioning so scales match real-world map coordinates
        self.image_item.setRect(QRectF(x_min, y_min, x_max - x_min, y_max - y_min))


class CFPComputeWorker(QThread):
    # Custom signal to emit the raw arrays safely across threads when finished
    computation_finished = pyqtSignal(np.ndarray, np.ndarray, np.ndarray)

    def __init__(self, target_z, x_range, y_range, step, mmap_data, active_idx, freqs, v_int, max_dip):
        super().__init__()
        self.target_z = target_z
        self.x_range = x_range
        self.y_range = y_range
        self.step = step
        self.mmap_data = mmap_data
        self.active_idx = active_idx
        self.freqs = freqs
        self.v_int = v_int
        self.max_dip = max_dip

    def run(self):
        # Trigger the full spatial pre-filtered loop function built in previous steps
        # This executes safely on a background CPU thread
        grid_x, grid_y, illumination_matrix = generate_horizon_illumination_map(
            self.target_z, self.x_range, self.y_range, self.step,
            self.mmap_data, self.active_idx, self.freqs, self.v_int, self.max_dip
        )
        # Emit data arrays safely back to the Main UI Thread
        self.computation_finished.emit(grid_x, grid_y, illumination_matrix)


# Inside your main window setup or response tab initiation module
def setup_illumination_analysis_tab(self):
    # 1. Instantiate the newly built graphing widget
    self.illumination_widget = RollIlluminationMapWidget()

    # 2. Add it as a new Tab option inside your main container layout
    self.ui.tabWidget.addTab(self.illumination_widget, "CFP Illumination Mask")

    # 3. Connect a calculation trigger button event
    self.ui.btnRunCFP.clicked.connect(self.start_cfp_analysis)


def start_cfp_analysis(self):
    # Disable button and show a status loading bar/indicator to prevent click spamming
    self.ui.btnRunCFP.setEnabled(False)

    # Extract operational parameters out of your active XML configurations / UI elements
    v_int = float(self.ui.txtVint.text())   # e.g. from <binning vint="2000.0"/>
    target_z = float(self.ui.txtTargetDepth.text())
    max_dip = float(self.ui.txtMaxDip.text())

    # Extract coordinate limits from your loaded SPS/Geometry bounds
    x_range = (self.survey.xmin, self.survey.xmax)
    y_range = (self.survey.ymin, self.survey.ymax)
    step = self.survey.bin_size

    freqs = np.array([10.0, 20.0, 30.0, 40.0, 50.0], dtype=np.float64)

    # Start background execution
    self.worker = CFPComputeWorker(
        target_z, x_range, y_range, step,
        self.mmap_analysis_file, self.active_trace_indices,
        freqs, v_int, max_dip
    )

    # Connect worker callback directly to the plot refresh function
    self.worker.computation_finished.connect(self.on_cfp_calculation_complete)
    self.worker.start()


def on_cfp_calculation_complete(self, grid_x, grid_y, illumination_matrix):
    # Update the PyQtGraph window canvas
    self.illumination_widget.update_map(grid_x, grid_y, illumination_matrix)

    # Re-enable controls
    self.ui.btnRunCFP.setEnabled(True)
