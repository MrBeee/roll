# this section contains experimental code for CFP (Common Focal Point) analysis;

try:
    from numba import jit, prange
except ImportError:
    prange = range

    def jit(*args, **kwargs):
        if args and callable(args[0]) and not kwargs:
            return args[0]

        def decorator(func):
            return func

        return decorator

import numpy as np


@jit(nopython=True, cache=True)
def compute_one_way_beam(focal_x, focal_y, focal_z, surf_x, surf_y, surf_z, freqs, v_int, matlab_compat=False):
    """
    Computes the one-way synthesized wavefield beam at a specific subsurface
    focal point across an array of surface coordinates and frequency bands.

    Parameters:
    -----------
    focal_x, focal_y, focal_z : float
        Coordinates of the target subsurface focal point.
    surf_x, surf_y, surf_z : 1D float arrays
        Coordinates of the active surface channels (either sources or receivers).
    freqs : 1D float array
        The discrete frequency spectrum to evaluate (e.g., 10 to 60 Hz).
    v_int : float
        Interval velocity (vint from your XML configuration).

    Returns:
    --------
    beam_spectrum : 1D complex array
        The synthesized monochromatic energy summed across the array per frequency (complex64).
    """
    n_surf = len(surf_x)
    n_freq = len(freqs)

    beam_spectrum = np.zeros(n_freq, dtype=np.complex64)

    # Special case: single source/receiver, beam should be flat everywhere (except at the source location)
    if n_surf == 1:
        for f_idx in prange(n_freq):
            # For Matlab compatibility, use amplitude = 1, phase = 0 everywhere (except at the source)
            # This matches the expected flat field in the single-point case
            beam_spectrum[f_idx] = 1.0 + 0.0j
        return beam_spectrum

    # General case: sum over all sources/receivers
    for f_idx in prange(n_freq):
        omega = 2.0 * np.pi * freqs[f_idx]
        k = omega / v_int
        total_field = 0.0 + 0.0j
        for s_idx in range(n_surf):
            dx = surf_x[s_idx] - focal_x
            dy = surf_y[s_idx] - focal_y
            dz = surf_z[s_idx] - focal_z
            r = np.sqrt(dx * dx + dy * dy + dz * dz)
            if r < 1e-3:
                continue
            if matlab_compat:
                amplitude = 1.0 / r
                phase = -k * r
            else:
                obliquity = np.abs(dz) / r
                phase = -k * r
                amplitude = (obliquity / (2.0 * np.pi * r)) * (1.0 / r)
            real_part = amplitude * np.cos(phase)
            imag_part = amplitude * np.sin(phase)
            total_field += complex(real_part, imag_part)
        beam_spectrum[f_idx] = total_field

    return beam_spectrum


@jit(nopython=True, cache=True)
def compute_weighted_one_way_beam(focal_x, focal_y, focal_z, surf_x, surf_y, surf_z, surf_weights, freqs, v_int, matlab_compat=False):
    """
    Weighted monochromatic beam calculation at a focal point, preserving
    station multiplicity (useful for relation-based proxy calculations).
    """
    n_surf = len(surf_x)
    n_freq = len(freqs)
    beam_spectrum = np.zeros(n_freq, dtype=np.complex64)

    for f_idx in prange(n_freq):
        omega = 2.0 * np.pi * freqs[f_idx]
        k = omega / v_int
        total_field = 0.0 + 0.0j
        for s_idx in range(n_surf):
            dx = surf_x[s_idx] - focal_x
            dy = surf_y[s_idx] - focal_y
            dz = surf_z[s_idx] - focal_z
            r = np.sqrt(dx * dx + dy * dy + dz * dz)
            if r < 1e-3:
                continue
            if matlab_compat:
                amplitude = (1.0 / r) * surf_weights[s_idx]
                phase = -k * r
            else:
                obliquity = np.abs(dz) / r
                phase = -k * r
                amplitude = (obliquity / (2.0 * np.pi * r * r)) * surf_weights[s_idx]
            real_part = amplitude * np.cos(phase)
            imag_part = amplitude * np.sin(phase)
            total_field += complex(real_part, imag_part)
        beam_spectrum[f_idx] = total_field

    return beam_spectrum


@jit(nopython=True, cache=True)
def filter_indices_by_aperture(focal_x, focal_y, focal_z, max_dip_degrees, mmap_mid_x, mmap_mid_y, matlab_compat=False):
    """
    Scans the memory-mapped coordinates and isolates trace indices that fall
    within the physical illumination cone of the specific subsurface target.

    Parameters:
    -----------
    focal_x, focal_y, focal_z : float
        Coordinates of the target subsurface focal point.
    max_dip_degrees : float
        The maximum structural dip angle to clear for imaging (e.g., 35.0 or 45.0).
    mmap_mid_x, mmap_mid_y : 1D float arrays (Memory-Mapped)
        The horizontal surface midpoints for ALL traces in the survey design file.

    Returns:
    --------
    valid_indices : 1D int64 array
        The filtered subset of indices to pass to your extraction engine.
    """
    n_traces = len(mmap_mid_x)

    # Calculate the maximum allowable horizontal distance on the surface
    if matlab_compat:
        # MATLAB: no dip limit, use a very large aperture
        max_radius_sq = 1e20
    else:
        theta_rad = np.radians(max_dip_degrees)
        max_radius = np.abs(focal_z) * np.tan(theta_rad)
        max_radius_sq = max_radius * max_radius

    # Step 1: Pre-screen flag array to allow parallel execution without race conditions
    keep_mask = np.zeros(n_traces, dtype=np.bool_)

    for i in prange(n_traces):
        dx = mmap_mid_x[i] - focal_x
        dy = mmap_mid_y[i] - focal_y

        # Euclidean distance squared (avoids calculating expensive square roots)
        distance_sq = dx * dx + dy * dy

        if distance_sq <= max_radius_sq:
            keep_mask[i] = True

    # Step 2: Extract active index locations
    # (Using non-parallel standard loop to cleanly compress the index mask)
    valid_indices = np.where(keep_mask)[0]

    return valid_indices


@jit(parallel=True, cache=True)
def filter_sps_relations_by_aperture(focal_x, focal_y, max_radius, src_x, src_y, rec_x, rec_y):
    """
    Screens memory-mapped active relation arrays to isolate traces where
    BOTH source and receiver contribute to the CFP focal point.
    """
    n_traces = len(src_x)
    keep_mask = np.zeros(n_traces, dtype=np.bool_)
    r_sq = max_radius * max_radius

    for i in prange(n_traces):
        # 1. Evaluate Source Proximity
        dsx = src_x[i] - focal_x
        dsy = src_y[i] - focal_y
        if (dsx*dsx + dsy*dsy) > r_sq:
            continue  # Source is outside aperture

        # 2. Evaluate Receiver Proximity
        drx = rec_x[i] - focal_x
        dry = rec_y[i] - focal_y
        if (drx*drx + dry*dry) > r_sq:
            continue  # Receiver is outside aperture

        keep_mask[i] = True

    return np.where(keep_mask)[0]


@jit(parallel=True, cache=True)
def compute_monochromatic_beam(focal_x, focal_y, focal_z, surf_x, surf_y, freq, v_int):
    """
    Calculates a single frequency wavefront component for the isolated target channels.
    """
    n_stations = len(surf_x)
    omega = 2.0 * np.pi * freq
    k = omega / v_int

    # Store complex components as complex64 array
    wavefield = np.zeros(n_stations, dtype=np.complex64)

    for i in prange(n_stations):
        dx = np.float32(surf_x[i] - focal_x)
        dy = np.float32(surf_y[i] - focal_y)
        r = np.sqrt(dx*dx + dy*dy + np.float32(focal_z*focal_z))

        if r < 1e-3:
            continue

        # Rayleigh-II obliquity factor and green's function wave propagation
        obliquity = np.abs(focal_z) / r
        phase = -k * r
        amplitude = obliquity / (2.0 * np.pi * r * r)

        wavefield[i] = np.complex64(complex(amplitude * np.cos(phase), amplitude * np.sin(phase)))

    return wavefield


def compute_monochromatic_beam_xy_grid(eval_x, eval_y, eval_z, surf_x, surf_y, surf_z, freq, v_int, matlab_compat=False, beam_type="src", focal_x=0.0, focal_y=0.0):
    """
    Calculates a monochromatic one-way beam image on an x/y grid at the focal depth.

    This follows the Fourier/slowness formulation used by acq_ftbeam_homogen.m for
    the z == z1 case.  The beam phase is controlled by the slowness vector from
    each surface station to the focal point, not by a fresh spherical distance from
    each station to each output pixel.
    """
    _ = (matlab_compat, beam_type)
    return _compute_ft_beam_xy_grid_numba(eval_x, eval_y, eval_z, surf_x, surf_y, surf_z, freq, v_int, focal_x, focal_y)


@jit(parallel=True, nopython=True, cache=True)
def _compute_ft_beam_xy_grid_numba(eval_x, eval_y, eval_z, surf_x, surf_y, surf_z, freq, v_int, focal_x, focal_y):
    n_x = len(eval_x)
    n_y = len(eval_y)
    n_stations = len(surf_x)
    omega = 2.0 * np.pi * freq
    c = v_int
    p = 1.0 / c

    beam_grid = np.zeros((n_y, n_x), dtype=np.complex64)

    if n_stations == 0:
        return beam_grid

    slowness_x = np.empty(n_stations, dtype=np.float32)
    slowness_y = np.empty(n_stations, dtype=np.float32)
    station_weight = np.empty(n_stations, dtype=np.float32)
    scale = 1.0 / (4.0 * np.pi * np.pi)
    omega_over_c = p * omega

    for station_idx in range(n_stations):
        dx_focus = surf_x[station_idx] - focal_x
        dy_focus = surf_y[station_idx] - focal_y
        dz_focus = surf_z[station_idx] - eval_z
        r_focus = np.sqrt(dx_focus * dx_focus + dy_focus * dy_focus + dz_focus * dz_focus)
        if r_focus < 1e-3:
            slowness_x[station_idx] = 0.0
            slowness_y[station_idx] = 0.0
            station_weight[station_idx] = 0.0
            continue
        slowness_x[station_idx] = p * dx_focus / r_focus
        slowness_y[station_idx] = p * dy_focus / r_focus
        jacobian = (dz_focus * dz_focus) / (r_focus * r_focus * r_focus * r_focus)
        station_weight[station_idx] = scale * jacobian * omega_over_c * omega_over_c

    for y_idx in prange(n_y):
        y_pos = eval_y[y_idx] - focal_y
        for x_idx in range(n_x):
            x_pos = eval_x[x_idx] - focal_x
            total_field = 0.0 + 0.0j
            for station_idx in range(n_stations):
                amplitude = station_weight[station_idx]
                if amplitude == 0.0:
                    continue
                phase = omega * (x_pos * slowness_x[station_idx] + y_pos * slowness_y[station_idx])
                real_part = amplitude * np.cos(phase)
                imag_part = amplitude * np.sin(phase)
                total_field += complex(real_part, imag_part)
            beam_grid[y_idx, x_idx] = total_field

    return beam_grid


@jit(parallel=True, nopython=True, cache=True)
def compute_illumination_row_numba(focal_y, eval_x, focal_z, src_coords, rec_coords, weights, freqs, vint, max_radius, matlab_compat=False):
    """
    Optimized kernel to compute a single row of an illumination (energy) map.
    Applies a moving spatial aperture filter per pixel in parallel.
    """
    _ = matlab_compat
    n_x = len(eval_x)
    n_traces = src_coords.shape[0]
    n_freqs = len(freqs)
    r_sq_limit = np.float32(max_radius * max_radius)

    row_energy = np.zeros(n_x, dtype=np.float32)
    two_pi = np.float32(2.0 * np.pi)

    dsz_vals = src_coords[:, 2] - focal_z
    dsz2_vals = dsz_vals * dsz_vals
    abs_dsz_vals = np.abs(dsz_vals)

    drz_vals = rec_coords[:, 2] - focal_z
    drz2_vals = drz_vals * drz_vals
    abs_drz_vals = np.abs(drz_vals)

    for ix in prange(n_x):
        f_x = eval_x[ix]
        pixel_energy = 0.0

        for f_idx in range(n_freqs):
            k = np.float32(two_pi * freqs[f_idx] / vint)
            bs = np.complex64(0.0 + 0.0j)
            br = np.complex64(0.0 + 0.0j)

            for t_idx in range(n_traces):
                # Trace-based aperture check (Source and Receiver must illuminate focal point)
                dsx = src_coords[t_idx, 0] - f_x
                dsy = src_coords[t_idx, 1] - focal_y
                rs_sq = dsx * dsx + dsy * dsy
                if rs_sq > r_sq_limit:
                    continue

                drx = rec_coords[t_idx, 0] - f_x
                dry = rec_coords[t_idx, 1] - focal_y
                rr_sq = drx * drx + dry * dry
                if rr_sq > r_sq_limit:
                    continue

                # Compute Green's functions for valid trace components
                w = weights[t_idx]
                rs = np.sqrt(rs_sq + dsz2_vals[t_idx])
                if rs > 1e-3:
                    bs += np.complex64((abs_dsz_vals[t_idx] / (two_pi * rs * rs)) * w) * np.exp(1j * (-k * rs))

                rr = np.sqrt(rr_sq + drz2_vals[t_idx])
                if rr > 1e-3:
                    br += np.complex64((abs_drz_vals[t_idx] / (two_pi * rr * rr)) * w) * np.exp(1j * (-k * rr))

            pixel_energy += np.abs(bs * br)

        row_energy[ix] = pixel_energy
    return row_energy


@jit(parallel=True, nopython=True, cache=True)
def compute_radon_images_numba(source_field, receiver_field, eval_x, eval_y, px, py, freq):
    """
    Computes Radon-domain unit-normalized images directly to avoid multiple grid passes.
    """
    n_y, n_x = source_field.shape
    n_py = len(py)
    n_px = len(px)
    two_pi_f = 2.0 * np.pi * freq

    # Step 1: temp = field @ L1
    temp_src = np.zeros((n_y, n_px), dtype=np.complex64)
    temp_rec = np.zeros((n_y, n_px), dtype=np.complex64)

    # Step 2 & Normalization state
    radon_src_final = np.empty((n_py, n_px), dtype=np.complex64)
    radon_rec_final = np.empty((n_py, n_px), dtype=np.complex64)
    radon_avp_final = np.empty((n_py, n_px), dtype=np.complex64)

    max_s_local = np.zeros(n_py, dtype=np.float32)
    max_r_local = np.zeros(n_py, dtype=np.float32)

    for j in prange(n_px):
        p_x = px[j]
        # Precompute phase along x for this p_x
        exs = np.empty(n_x, dtype=np.complex64)
        for ix in range(n_x):
            exs[ix] = np.exp(1j * np.complex64(two_pi_f * p_x * eval_x[ix]))

        for iy in range(n_y):
            s_sum = np.complex64(0.0 + 0.0j)
            r_sum = np.complex64(0.0 + 0.0j)
            for ix in range(n_x):
                s_sum += source_field[iy, ix] * exs[ix]
                r_sum += receiver_field[iy, ix] * exs[ix]
            temp_src[iy, j] = s_sum
            temp_rec[iy, j] = r_sum

    for i in prange(n_py):
        p_y = py[i]
        # Precompute phase along y for this p_y
        eys = np.empty(n_y, dtype=np.complex64)
        for iy in range(n_y):
            eys[iy] = np.exp(1j * np.complex64(two_pi_f * p_y * eval_y[iy]))

        for j in range(n_px):
            s_sum = np.complex64(0.0 + 0.0j)
            r_sum = np.complex64(0.0 + 0.0j)
            for iy in range(n_y):
                s_sum += eys[iy] * temp_src[iy, j]
                r_sum += eys[iy] * temp_rec[iy, j]

            s_val = s_sum
            r_val = r_sum
            a_val = np.conj(s_val) * r_val

            radon_src_final[i, j] = s_val
            radon_rec_final[i, j] = r_val
            radon_avp_final[i, j] = a_val

            # Track the same quantity MATLAB displays: the real-part projection.
            ms = np.abs(np.real(s_val)); mr = np.abs(np.real(r_val))    # noqa: E702
            if ms > max_s_local[i]:
                max_s_local[i] = ms
            if mr > max_r_local[i]:
                max_r_local[i] = mr

    # Global reduction
    max_s = np.max(max_s_local); max_r = np.max(max_r_local)    # noqa: E702

    # Final scaling pass (parallel)
    src_img = np.empty((n_py, n_px), dtype=np.float32)
    rec_img = np.empty((n_py, n_px), dtype=np.float32)
    avp_img = np.empty((n_py, n_px), dtype=np.float32)

    is_s = 1.0 / max_s if max_s > 0 else 0.0
    is_r = 1.0 / max_r if max_r > 0 else 0.0
    # Joint normalization shows "Focusing Efficiency" (how well beams overlap)
    is_a = 1.0 / (max_s * max_r) if (max_s > 0 and max_r > 0) else 0.0

    for i in prange(n_py):
        for j in range(n_px):
            if is_s > 0:
                src_img[i, j] = np.float32(np.abs(np.real(radon_src_final[i, j])) * is_s)
            else:
                src_img[i, j] = 0.0

            if is_r > 0:
                rec_img[i, j] = np.float32(np.abs(np.real(radon_rec_final[i, j])) * is_r)
            else:
                rec_img[i, j] = 0.0

            if is_a > 0:
                avp_img[i, j] = np.float32(np.abs(np.real(radon_avp_final[i, j])) * is_a)
            else:
                avp_img[i, j] = 0.0

    return src_img, rec_img, avp_img


@jit(nopython=True, cache=True)
def calculate_panel_snr_numba(image):
    """
    Extracts an SNR metric (dB) from a unit-normalized [0, 1] Radon panel.
    Compares the peak (1.0) to the mean background energy level.
    """
    n_y, n_x = image.shape
    count = n_y * n_x
    if count == 0:
        return 0.0

    total = 0.0
    for i in range(n_y):
        for j in range(n_x):
            total += image[i, j]

    avg_noise = total / count
    return -20.0 * np.log10(avg_noise) if avg_noise > 1e-6 else 60.0


@jit(parallel=True, nopython=True, cache=True)
def compute_xy_beam_images_numba(source_field, receiver_field, db_min=-60.0):
    """
    Fused Numba kernel to generate Source, Receiver, and Resolution dB images
    directly from wavefield buffers in one pass.
    """
    n_y, n_x = source_field.shape
    s_img = np.empty((n_y, n_x), dtype=np.float32)
    r_img = np.empty((n_y, n_x), dtype=np.float32)
    res_img = np.empty((n_y, n_x), dtype=np.float32)

    # Pass 1: Find maxima for all three fields
    max_s_local = np.zeros(n_y, dtype=np.float64)
    max_r_local = np.zeros(n_y, dtype=np.float64)

    for i in prange(n_y):
        ms = 0.0; mr = 0.0  # noqa: E702
        for j in range(n_x):
            s_val = source_field[i, j]
            r_val = receiver_field[i, j]

            as_val = np.abs(np.real(s_val))
            ar_val = np.abs(np.real(r_val))

            if as_val > ms:
                ms = as_val
            if ar_val > mr:
                mr = ar_val

        max_s_local[i] = ms
        max_r_local[i] = mr

    max_s = np.max(max_s_local)
    max_r = np.max(max_r_local)

    # Pass 2: Scale and convert to dB
    is_s = 1.0 / max_s if max_s > 0 else 0.0
    is_r = 1.0 / max_r if max_r > 0 else 0.0
    # Joint normalization shows the drop in resolution magnitude due to beam mismatch
    is_res = 1.0 / (max_s * max_r) if (max_s > 0 and max_r > 0) else 0.0

    for i in prange(n_y):
        for j in range(n_x):
            # Source dB
            if is_s > 0:
                norm = np.abs(np.real(source_field[i, j])) * is_s
                if norm < 1e-6:
                    s_img[i, j] = np.float32(db_min)
                else:
                    s_img[i, j] = np.float32(max(20.0 * np.log10(norm), db_min))
            else:
                s_img[i, j] = np.float32(db_min)

            # Receiver dB
            if is_r > 0:
                norm = np.abs(np.real(receiver_field[i, j])) * is_r
                if norm < 1e-6:
                    r_img[i, j] = np.float32(db_min)
                else:
                    r_img[i, j] = np.float32(max(20.0 * np.log10(norm), db_min))
            else:
                r_img[i, j] = np.float32(db_min)

            # Resolution dB
            if is_res > 0:
                # Note: recomputing product is faster than memory round-trips for small multiplications
                res_val = source_field[i, j] * receiver_field[i, j]
                norm = np.abs(np.real(res_val)) * is_res
                if norm < 1e-6:
                    res_img[i, j] = np.float32(db_min)
                else:
                    res_img[i, j] = np.float32(max(20.0 * np.log10(norm), db_min))
            else:
                res_img[i, j] = np.float32(db_min)

    return s_img, r_img, res_img


@jit(nopython=True, cache=True)
def _find_max_amp_numba(field):
    """Helper to find max of absolute magnitude."""
    n_y, n_x = field.shape
    max_val = 0.0
    for i in range(n_y):
        for j in range(n_x):
            val = np.abs(field[i, j])
            if val > max_val:
                max_val = val
    return max_val


@jit(parallel=True, nopython=True, cache=True)
def convert_to_db_image_numba(field, db_min=-60.0):
    """
    Fused Numba kernel for dB conversion and normalization.
    """
    max_amp = _find_max_amp_numba(field)
    n_y, n_x = field.shape
    out = np.empty((n_y, n_x), dtype=np.float32)
    if max_amp <= 0.0:
        out.fill(np.float32(db_min))
        return out

    inv_max = 1.0 / max_amp
    for i in prange(n_y):
        for j in range(n_x):
            norm = np.abs(field[i, j]) * inv_max
            if norm < 1e-6:
                out[i, j] = np.float32(db_min)
            else:
                val = 20.0 * np.log10(norm)
                out[i, j] = np.float32(max(val, db_min))
    return out


@jit(parallel=True, nopython=True, cache=True)
def convert_to_unit_image_numba(field):
    """
    Fused Numba kernel for unit normalization.
    """
    max_amp = _find_max_amp_numba(field)
    n_y, n_x = field.shape
    out = np.empty((n_y, n_x), dtype=np.float32)
    if max_amp <= 0.0:
        out.fill(np.float32(0.0))
        return out

    inv_max = 1.0 / max_amp
    for i in prange(n_y):
        for j in range(n_x):
            out[i, j] = np.float32(np.abs(field[i, j]) * inv_max)
    return out


@jit(parallel=True, nopython=True, cache=True)
def compute_resolution_db_numba(source_field, receiver_field, db_min=-60.0):
    """
    Fused kernel for complex multiplication and dB conversion.
    """
    n_y, n_x = source_field.shape
    max_s = _find_max_amp_numba(source_field)
    max_r = _find_max_amp_numba(receiver_field)

    out = np.empty((n_y, n_x), dtype=np.float32)
    if max_s <= 0.0 or max_r <= 0.0:
        out.fill(np.float32(db_min))
        return out

    inv_max = 1.0 / (max_s * max_r)
    for i in prange(n_y):
        for j in range(n_x):
            norm = np.abs(np.real(source_field[i, j] * receiver_field[i, j])) * inv_max
            if norm < 1e-6:
                out[i, j] = np.float32(db_min)
            else:
                val = 20.0 * np.log10(norm)
                out[i, j] = np.float32(max(val, db_min))
    return out


def compute_monochromatic_weighted_beam_xy_grid(eval_x, eval_y, eval_z, surf_x, surf_y, surf_z, surf_weights, freq, v_int, focal_x=0.0, focal_y=0.0):
    """
    Calculates the Fourier/slowness CFP beam while preserving multiplicity through
    per-station weights.
    """
    return _compute_weighted_ft_beam_xy_grid_numba(eval_x, eval_y, eval_z, surf_x, surf_y, surf_z, surf_weights, freq, v_int, focal_x, focal_y)


@jit(parallel=True, nopython=True, cache=True)
def _compute_weighted_ft_beam_xy_grid_numba(eval_x, eval_y, eval_z, surf_x, surf_y, surf_z, surf_weights, freq, v_int, focal_x, focal_y):
    n_x = len(eval_x)
    n_y = len(eval_y)
    n_stations = len(surf_x)
    omega = 2.0 * np.pi * freq
    p = 1.0 / v_int

    beam_grid = np.zeros((n_y, n_x), dtype=np.complex64)

    if n_stations == 0:
        return beam_grid

    slowness_x = np.empty(n_stations, dtype=np.float32)
    slowness_y = np.empty(n_stations, dtype=np.float32)
    station_weight = np.empty(n_stations, dtype=np.float32)
    scale = 1.0 / (4.0 * np.pi * np.pi)
    omega_over_c = p * omega

    for station_idx in range(n_stations):
        dx_focus = surf_x[station_idx] - focal_x
        dy_focus = surf_y[station_idx] - focal_y
        dz_focus = surf_z[station_idx] - eval_z
        r_focus = np.sqrt(dx_focus * dx_focus + dy_focus * dy_focus + dz_focus * dz_focus)
        if r_focus < 1e-3:
            slowness_x[station_idx] = 0.0
            slowness_y[station_idx] = 0.0
            station_weight[station_idx] = 0.0
            continue
        slowness_x[station_idx] = p * dx_focus / r_focus
        slowness_y[station_idx] = p * dy_focus / r_focus
        jacobian = (dz_focus * dz_focus) / (r_focus * r_focus * r_focus * r_focus)
        station_weight[station_idx] = scale * jacobian * omega_over_c * omega_over_c * surf_weights[station_idx]

    for y_idx in prange(n_y):
        y_pos = eval_y[y_idx] - focal_y
        for x_idx in range(n_x):
            x_pos = eval_x[x_idx] - focal_x
            total_field = np.complex64(0.0 + 0.0j)

            for station_idx in range(n_stations):
                amplitude = station_weight[station_idx]
                if amplitude == 0.0:
                    continue
                phase = omega * (x_pos * slowness_x[station_idx] + y_pos * slowness_y[station_idx])
                total_field += amplitude * np.exp(1j * phase)

            beam_grid[y_idx, x_idx] = total_field

    return beam_grid
