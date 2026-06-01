import matplotlib.pyplot as plt
import numpy as np

# --- 1. Parameter Setup ---
# Grid dimensions (Downsized slightly for memory/speed in 3D)
nx, ny, nz = 101, 101, 81
dx = dy = dz = 10.0 # grid spacing in meters

x = np.arange(nx) * dx
y = np.arange(ny) * dy
z = np.arange(nz) * dz

# Create 3D Meshgrid
X, Y, Z = np.meshgrid(x, y, z, indexing='ij')

velocity = 2000.0 # m/s
frequency = 25.0 # Hz
omega = 2 * np.pi * frequency
k = omega / velocity # Wavenumber

# Target Focus Point (3D CFP)
xf, yf, zf = 500.0, 500.0, 500.0

# 2D Surface Arrays at z=0 (Apertures)
# Defining a grid of sources and receivers on the surface
src_x_line = np.arange(200, 801, 20)
src_y_line = np.arange(200, 801, 20)
SRC_X, SRC_Y = np.meshgrid(src_x_line, src_y_line)
src_x_flat = SRC_X.flatten()
src_y_flat = SRC_Y.flatten()

# For simplicity, we'll assume co-located receiver arrays, 
# but they can be defined independently.
rec_x_flat = src_x_flat
rec_y_flat = src_y_flat

# --- 2. 3D Beam Calculation Function ---
def calculate_beam_3d(aperture_x, aperture_y, target_xf, target_yf, target_zf, X_grid, Y_grid, Z_grid, k):
    """Calculates the 3D focused beam response using 3D Green's functions."""
    beam = np.zeros(X_grid.shape, dtype=complex)
    
    # 1. Calculate 3D focusing operator (phase conjugation)
    r_focus = np.sqrt((aperture_x - target_xf)**2 + (aperture_y - target_yf)**2 + (0 - target_zf)**2)
    focusing_operator = np.exp(-1j * k * r_focus)
    
    # 2. Superimpose wavefields from the 2D surface aperture into the 3D volume
    for i in range(len(aperture_x)):
        x_elem = aperture_x[i]
        y_elem = aperture_y[i]
        
        # 3D Distance from surface element to all points in the subsurface volume
        r = np.sqrt((X_grid - x_elem)**2 + (Y_grid - y_elem)**2 + Z_grid**2)
        r[r == 0] = 1e-3 # Avoid singularity
        
        # 3D Green's function amplitude decay is 1/r
        element_wavefield = (np.exp(1j * k * r) / (4 * np.pi * r)) * focusing_operator[i]
        beam += element_wavefield
        
    return np.abs(beam)

# --- 3. Compute 3D Source and Receiver Beams ---
print("Computing 3D Source Beam...")
source_beam_3d = calculate_beam_3d(src_x_flat, src_y_flat, xf, yf, zf, X, Y, Z, k)

print("Computing 3D Receiver Beam...")
receiver_beam_3d = calculate_beam_3d(rec_x_flat, rec_y_flat, xf, yf, zf, X, Y, Z, k)

# Combined 3D Response
combined_response_3d = source_beam_3d * receiver_beam_3d


def clip_for_display(slice_data, percentile=99.5):
    """Clip a slice to a robust upper bound so a few outliers do not dominate the colormap."""
    vmax = np.percentile(slice_data, percentile)
    if not np.isfinite(vmax) or vmax <= 0.0:
        return slice_data, 1.0
    return np.clip(slice_data, 0.0, vmax), vmax


def normalize_to_focus(profile, focus_index):
    """Normalize a 1D profile to the amplitude at the focus sample when available."""
    focus_amplitude = profile[focus_index]
    if np.isfinite(focus_amplitude) and focus_amplitude > 0.0:
        return profile / focus_amplitude

    peak_amplitude = np.max(profile)
    if not np.isfinite(peak_amplitude) or peak_amplitude <= 0.0:
        return profile

    return profile / peak_amplitude


def calculate_phase_focus_metric_1d(
    aperture_x,
    aperture_y,
    target_xf,
    target_yf,
    target_zf,
    sample_x,
    sample_y,
    sample_z,
    wavenumber,
):
    """Return a phase-only focus metric that peaks at the requested focus sample."""
    r_focus = np.sqrt((aperture_x - target_xf)**2 + (aperture_y - target_yf)**2 + target_zf**2)
    r_samples = np.sqrt(
        (aperture_x[:, np.newaxis] - sample_x)**2
        + (aperture_y[:, np.newaxis] - sample_y)**2
        + sample_z[np.newaxis, :]**2
    )
    phase_residual = np.exp(1j * wavenumber * (r_samples - r_focus[:, np.newaxis]))
    return np.abs(np.mean(phase_residual, axis=0))

# --- 4. Slicing and Visualization ---
# Find closest indices to the target focus point
ix_f = np.argmin(np.abs(x - xf))
iy_f = np.argmin(np.abs(y - yf))
iz_f = np.argmin(np.abs(z - zf))

# The z=0 acquisition plane contains the source singularity, so subsurface
# depth plots start below the aperture to keep the focus response visible.
z_plot_start = 1 if np.isclose(z[0], 0.0) else 0
z_plot = z[z_plot_start:]
iz_focus_plot = iz_f - z_plot_start

src_focus_metric_z = calculate_phase_focus_metric_1d(
    src_x_flat,
    src_y_flat,
    xf,
    yf,
    zf,
    xf,
    yf,
    z_plot,
    k,
)
rec_focus_metric_z = calculate_phase_focus_metric_1d(
    rec_x_flat,
    rec_y_flat,
    xf,
    yf,
    zf,
    xf,
    yf,
    z_plot,
    k,
)
combined_focus_metric_z = src_focus_metric_z * rec_focus_metric_z

xz_slice_display, xz_vmax = clip_for_display(combined_response_3d[:, iy_f, z_plot_start:].T)
xy_slice_display, xy_vmax = clip_for_display(combined_response_3d[:, :, iz_f].T)

plt.figure(figsize=(15, 10))

# Plot 1: X-Z Slice (Vertical Profile through Focus)
plt.subplot(2, 2, 1)
plt.imshow(xz_slice_display, extent=[x[0], x[-1], z_plot[-1], z_plot[0]], cmap='hot', vmin=0.0, vmax=xz_vmax)
plt.scatter(xf, zf, color='cyan', marker='x', s=100, label='Focus Point')
plt.title("Combined Response: X-Z Cross-Section (at Y-focus)")
plt.xlabel("X Distance (m)"); plt.ylabel("Depth Z (m)"); plt.legend()

# Plot 2: X-Y Slice (Horizontal Profile/Time-slice through Focus)
plt.subplot(2, 2, 2)
plt.imshow(xy_slice_display, extent=[x[0], x[-1], y[-1], y[0]], cmap='hot', vmin=0.0, vmax=xy_vmax)
plt.scatter(xf, yf, color='cyan', marker='x', s=100)
plt.title("Combined Response: X-Y Cross-Section (at Depth-focus)")
plt.xlabel("X Distance (m)"); plt.ylabel("Y Distance (m)")

# Plot 3: Vertical 1D Sidelobe Profile (Z-direction / Axial Resolution)
plt.subplot(2, 2, 3)
src_slice_z = normalize_to_focus(source_beam_3d[ix_f, iy_f, z_plot_start:], iz_focus_plot)
comb_slice_z = normalize_to_focus(combined_response_3d[ix_f, iy_f, z_plot_start:], iz_focus_plot)
plt.plot(z_plot, src_slice_z, label='Source Beam (3D)', color='blue')
plt.plot(z_plot, comb_slice_z, label='Combined Response', color='red', linestyle='--')
plt.plot(z_plot, src_focus_metric_z, label='Source Focus Metric', color='green', linestyle=':')
plt.plot(z_plot, combined_focus_metric_z, label='Combined Focus Metric', color='black', linestyle='-.')
plt.title("Spatial Sidelobes along Z-axis (Depth)")
plt.xlabel("Depth Z (m)"); plt.ylabel("Normalized Amplitude")
plt.grid(True); plt.legend()

# Plot 4: Horizontal 1D Sidelobe Profile (X-direction)
plt.subplot(2, 2, 4)
src_slice_x = normalize_to_focus(source_beam_3d[:, iy_f, iz_f], ix_f)
comb_slice_x = normalize_to_focus(combined_response_3d[:, iy_f, iz_f], ix_f)
plt.plot(x, src_slice_x, label='Source Beam (3D)', color='blue')
plt.plot(x, comb_slice_x, label='Combined Response', color='red', linestyle='--')
plt.title("Spatial Sidelobes along X-axis")
plt.xlabel("X Distance (m)"); plt.ylabel("Normalized Amplitude")
plt.grid(True); plt.legend()

plt.tight_layout()
plt.show()
