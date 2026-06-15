import matplotlib.pyplot as plt
import numpy as np
from numba import njit, prange

# ------------------------------------------------------------
# Geometry and traveltime
# ------------------------------------------------------------


@njit
def traveltime_const_vel(x1, z1, x2, z2, v):
    """
    Straight-ray traveltime in constant velocity.
    """
    dx = x2 - x1
    dz = z2 - z1
    return np.sqrt(dx * dx + dz * dz) / v


# ------------------------------------------------------------
# CFP acquisition imprint using UNIT data (pure acquisition)
# ------------------------------------------------------------

@njit(parallel=True)
def cfp_acq_imprint_unit(
    sx, rx,             # (ns,), (nr,)
    x_grid, z_grid,     # (nx,), (nz,)
    depth,              # reflector depth (positive)
    v,                  # velocity
    omega               # angular frequency 2πf
):
    ns = sx.size
    nr = rx.size
    nx = x_grid.size
    nz = z_grid.size

    imprint = np.zeros((nz, nx), dtype=np.float32)

    for iz in prange(nz):
        zf = -z_grid[iz]    # reflector plane

        for ix in range(nx):
            xf = x_grid[ix]

            real_acc = 0.0
            imag_acc = 0.0

            for isrc in range(ns):
                Ts = traveltime_const_vel(sx[isrc], 0.0, xf, zf, v)

                for irec in range(nr):
                    Tr = traveltime_const_vel(rx[irec], 0.0, xf, zf, v)

                    phase = -omega * (Ts + Tr)
                    cos_p = np.cos(phase)
                    sin_p = np.sin(phase)

                    # unit complex data: 1 + 0i
                    real_acc += cos_p
                    imag_acc += sin_p

            imprint[iz, ix] = np.sqrt(real_acc * real_acc + imag_acc * imag_acc)

    return imprint


# ------------------------------------------------------------
# CFP acquisition imprint using ACTUAL complex data at 1 freq
# ------------------------------------------------------------

@njit(parallel=True)
def cfp_acq_imprint_data(
    data_freq,          # (ns, nr) complex64
    sx, rx,             # (ns,), (nr,)
    x_grid, z_grid,     # (nx,), (nz,)
    depth,              # reflector depth (positive)
    v,                  # velocity
    omega               # angular frequency 2πf
):
    ns = sx.size
    nr = rx.size
    nx = x_grid.size
    nz = z_grid.size

    imprint = np.zeros((nz, nx), dtype=np.float32)

    for iz in prange(nz):
        zf = -z_grid[iz]

        for ix in range(nx):
            xf = x_grid[ix]

            real_acc = 0.0
            imag_acc = 0.0

            for isrc in range(ns):
                Ts = traveltime_const_vel(sx[isrc], 0.0, xf, zf, v)

                for irec in range(nr):
                    Tr = traveltime_const_vel(rx[irec], 0.0, xf, zf, v)

                    phase = -omega * (Ts + Tr)
                    cos_p = np.cos(phase)
                    sin_p = np.sin(phase)

                    c = data_freq[isrc, irec]

                    # c * exp(i*phase)
                    real_acc += c.real * cos_p - c.imag * sin_p
                    imag_acc += c.real * sin_p + c.imag * cos_p

            imprint[iz, ix] = np.sqrt(real_acc * real_acc + imag_acc * imag_acc)

    return imprint


# ------------------------------------------------------------
# Normalization helper
# ------------------------------------------------------------

def normalize_imprint(imprint):
    """
    Normalize imprint map to [0, 1].
    """
    m = imprint.max()
    if m > 0:
        return imprint / m
    return imprint


# ------------------------------------------------------------
# Plotting helper
# ------------------------------------------------------------

def plot_imprint(imprint, x_grid, z_grid, title="CFP Acquisition Imprint"):
    """
    Plot the imprint map using matplotlib.
    """
    plt.figure(figsize=(10, 6))
    extent = [x_grid.min(), x_grid.max(), z_grid.max(), z_grid.min()]

    plt.imshow(imprint, cmap="viridis", aspect="auto", extent=extent)
    plt.colorbar(label="Amplitude")
    plt.xlabel("X (m)")
    plt.ylabel("Depth (m)")
    plt.title(title)
    plt.tight_layout()
    plt.show()


# ------------------------------------------------------------
# Example usage
# ------------------------------------------------------------

if __name__ == "__main__":

    # Geometry
    ns, nr = 50, 50
    sx = np.linspace(0, 3000, ns).astype(np.float32)
    rx = np.linspace(0, 3000, nr).astype(np.float32)

    # Subsurface grid
    x_grid = np.linspace(0, 3000, 151).astype(np.float32)
    z_grid = np.linspace(200, 2500, 80).astype(np.float32)

    depth = 1500.0
    v = 2000.0
    f0 = 20.0
    omega = 2 * np.pi * f0

    print("Computing acquisition imprint (unit data)...")
    imprint_unit = cfp_acq_imprint_unit(
        sx, rx, x_grid, z_grid, depth, v, omega
    )

    imprint_unit_norm = normalize_imprint(imprint_unit)
    plot_imprint(imprint_unit_norm, x_grid, z_grid,
                 title="CFP Acquisition Imprint (Unit Data)")

    # Example: using synthetic complex data at one frequency
    data_freq = (np.random.randn(ns, nr) + 1j * np.random.randn(ns, nr)).astype(np.complex64)

    print("Computing acquisition imprint (actual data)...")
    imprint_data = cfp_acq_imprint_data(
        data_freq, sx, rx, x_grid, z_grid, depth, v, omega
    )

    imprint_data_norm = normalize_imprint(imprint_data)
    plot_imprint(imprint_data_norm, x_grid, z_grid,
                 title="CFP Acquisition Imprint (Actual Data)")
