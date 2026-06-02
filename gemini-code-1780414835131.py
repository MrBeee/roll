import matplotlib.pyplot as plt
import numpy as np

# --- 1. Survey and Grid Parameters ---
nx_map, ny_map = 80, 80   # Map view grid size (Subsurface target area)
dx = dy = 15.0            # Grid spacing in meters
target_z = 1200.0         # Target depth of the reservoir layer (meters)

x_map = np.arange(nx_map) * dx
y_map = np.arange(ny_map) * dy
X_map, Y_map = np.meshgrid(x_map, y_map, indexing='ij')

# --- 2. Define the Acquisition Geometry Template ---
# Example: Coarse Shot lines (sparse along Y) and Dense Receiver lines
shot_x = np.arange(200, 1000, 40)
shot_y = np.arange(200, 1000, 150)  # Coarse spacing creates acquisition footprint
SRC_X, SRC_Y = np.meshgrid(shot_x, shot_y)
src_x = SRC_X.flatten()
src_y = SRC_Y.flatten()

rec_x_line = np.arange(100, 1100, 20)
rec_y_line = np.arange(100, 1100, 40)  # Standard 3D orthogonal template
REC_X, REC_Y = np.meshgrid(rec_x_line, rec_y_line)
rec_x = REC_X.flatten()
rec_y = REC_Y.flatten()


# --- 3. Efficient Target-Point Map Calculation ---
def compute_illumination(X_targets, Y_targets, z_target, s_x, s_y, r_x, r_y):
    """
    Computes the combined CFP focal amplitude across a 2D target grid
    to evaluate illumination strength.
    """
    map_data = np.zeros(X_targets.shape)

    # Flatten targets for vectorization loops if necessary,
    # but evaluating point-by-point reveals the footprint clearly.
    for i in range(X_targets.shape[0]):
        for j in range(X_targets.shape[1]):
            xf = X_targets[i, j]
            yf = Y_targets[i, j]

            # --- Source Beam Energy at (xf, yf, z_target) ---
            # Distance from all sources to this single focus point
            r_src = np.sqrt((s_x - xf)**2 + (s_y - yf)**2 + z_target**2)
            # In a perfectly calibrated model, the focused energy collapses
            # into the sum of the Green's function amplitudes.
            src_amplitude = np.sum(1.0 / (4 * np.pi * r_src))

            # --- Receiver Beam Energy at (xf, yf, z_target) ---
            r_rec = np.sqrt((r_x - xf)**2 + (r_y - yf)**2 + z_target**2)
            rec_amplitude = np.sum(1.0 / (4 * np.pi * r_rec))

            # Combined focal response at this map location
            map_data[i, j] = src_amplitude * rec_amplitude

    # Normalize the map
    map_data /= np.max(map_data)
    return map_data


# --- 4. Run Calculation ---
print("Calculating illumination map view...")
illumination_result = compute_illumination(X_map, Y_map, target_z, src_x, src_y, rec_x, rec_y)

# --- 5. Plotting the Map View ---
plt.figure(figsize=(12, 5))

# Plot 1: The Geometry Template
plt.subplot(1, 2, 1)
plt.scatter(src_x, src_y, color='red', marker='*', s=15, alpha=0.6, label='Sources (Shots)')
plt.scatter(rec_x, rec_y, color='blue', marker='.', s=2, alpha=0.3, label='Receivers')
plt.title("Surface Acquisition Template")
plt.xlabel("X Position (m)")
plt.ylabel("Y Position (m)")
plt.legend(loc='upper right')
plt.grid(True)

# Plot 2: The CFP Illumination Map View
plt.subplot(1, 2, 2)
im = plt.imshow(illumination_result.T, extent=[x_map[0], x_map[-1], y_map[-1], y_map[0]],
                cmap='viridis', aspect='auto')
plt.colorbar(im, label='Normalized Illumination Intensity')
plt.title(f"CFP Illumination Map (Depth = {target_z}m)")
plt.xlabel("Subsurface X (m)")
plt.ylabel("Subsurface Y (m)")

plt.tight_layout()
plt.show()
