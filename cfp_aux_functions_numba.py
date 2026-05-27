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
def compute_one_way_beam(focal_x, focal_y, focal_z, surf_x, surf_y, surf_z, freqs, v_int):
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
        The synthesized monochromatic energy summed across the array per frequency.
    """
    n_surf = len(surf_x)
    n_freq = len(freqs)

    # Pre-allocate output array for each frequency channel
    beam_spectrum = np.zeros(n_freq, dtype=np.complex128)

    # Loop over frequencies in parallel
    for f_idx in prange(n_freq):
        omega = 2.0 * np.pi * freqs[f_idx]
        k = omega / v_int  # Wavenumber

        total_field = 0.0 + 0.0j

        # Vectorized/Optimized loop over surface layout coordinates
        for s_idx in range(n_surf):
            dx = surf_x[s_idx] - focal_x
            dy = surf_y[s_idx] - focal_y
            dz = surf_z[s_idx] - focal_z    # Usually 0.0 or elevation

            # Distance from target point to surface coordinate
            r = np.sqrt(dx * dx + dy * dy + dz * dz)

            if r < 1e-3:
                continue

            # Rayleigh-II green's function equation components
            obliquity = np.abs(dz) / r
            phase = -k * r
            amplitude = (obliquity / (2.0 * np.pi * r)) * (1.0 / r)

            # Complex wavefield: Amplitude * exp(j * phase) * scaling factor
            # (Simplification ignoring the near-field 1/r terms for deep targets)
            real_part = amplitude * np.cos(phase)
            imag_part = amplitude * np.sin(phase)

            total_field += complex(real_part, imag_part)

        beam_spectrum[f_idx] = total_field

    return beam_spectrum


@jit(nopython=True, cache=True)
def filter_indices_by_aperture(focal_x, focal_y, focal_z, max_dip_degrees, mmap_mid_x, mmap_mid_y):
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

    # Store complex components as complex128 array
    wavefield = np.zeros(n_stations, dtype=np.complex128)

    for i in prange(n_stations):
        dx = surf_x[i] - focal_x
        dy = surf_y[i] - focal_y
        r = np.sqrt(dx*dx + dy*dy + focal_z*focal_z)

        if r < 1e-3:
            continue

        # Rayleigh-II obliquity factor and green's function wave propagation
        obliquity = np.abs(focal_z) / r
        phase = -k * r
        amplitude = obliquity / (2.0 * np.pi * r * r)

        wavefield[i] = complex(amplitude * np.cos(phase), amplitude * np.sin(phase))

    return wavefield


@jit(parallel=True, cache=True)
def compute_monochromatic_beam_xy_grid(eval_x, eval_y, eval_z, surf_x, surf_y, surf_z, freq, v_int):
    """
    Calculates a monochromatic one-way beam image on an x/y grid at a fixed z level.
    """
    n_x = len(eval_x)
    n_y = len(eval_y)
    n_stations = len(surf_x)
    omega = 2.0 * np.pi * freq
    k = omega / v_int
    beam_grid = np.zeros((n_y, n_x), dtype=np.complex128)

    for y_idx in prange(n_y):
        y_pos = eval_y[y_idx]
        for x_idx in range(n_x):
            x_pos = eval_x[x_idx]
            total_field = 0.0 + 0.0j

            for station_idx in range(n_stations):
                dx = surf_x[station_idx] - x_pos
                dy = surf_y[station_idx] - y_pos
                dz = surf_z[station_idx] - eval_z
                r = np.sqrt(dx * dx + dy * dy + dz * dz)

                if r < 1e-3:
                    continue

                obliquity = np.abs(dz) / r
                phase = -k * r
                amplitude = obliquity / (2.0 * np.pi * r * r)
                total_field += complex(amplitude * np.cos(phase), amplitude * np.sin(phase))

            beam_grid[y_idx, x_idx] = total_field

    return beam_grid


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
    temp_src = np.zeros((n_y, n_px), dtype=np.complex128)
    temp_rec = np.zeros((n_y, n_px), dtype=np.complex128)

    # Step 2 & Normalization state
    radon_src_final = np.empty((n_py, n_px), dtype=np.complex128)
    radon_rec_final = np.empty((n_py, n_px), dtype=np.complex128)
    radon_avp_final = np.empty((n_py, n_px), dtype=np.complex128)

    max_s_local = np.zeros(n_py, dtype=np.float64)
    max_r_local = np.zeros(n_py, dtype=np.float64)
    max_a_local = np.zeros(n_py, dtype=np.float64)

    for j in prange(n_px):
        p_x = px[j]
        # Precompute phase along x for this p_x
        exs = np.empty(n_x, dtype=np.complex128)
        for ix in range(n_x):
            arg_x = two_pi_f * p_x * eval_x[ix]
            exs[ix] = complex(np.cos(arg_x), np.sin(arg_x))

        for iy in range(n_y):
            s_sum = 0.0 + 0.0j
            r_sum = 0.0 + 0.0j
            for ix in range(n_x):
                s_sum += source_field[iy, ix] * exs[ix]
                r_sum += receiver_field[iy, ix] * exs[ix]
            temp_src[iy, j] = s_sum
            temp_rec[iy, j] = r_sum

    for i in prange(n_py):
        p_y = py[i]
        # Precompute phase along y for this p_y
        eys = np.empty(n_y, dtype=np.complex128)
        for iy in range(n_y):
            arg_y = two_pi_f * p_y * eval_y[iy]
            eys[iy] = complex(np.cos(arg_y), np.sin(arg_y))

        for j in range(n_px):
            s_sum = 0.0 + 0.0j
            r_sum = 0.0 + 0.0j
            for iy in range(n_y):
                s_sum += eys[iy] * temp_src[iy, j]
                r_sum += eys[iy] * temp_rec[iy, j]

            s_val = s_sum
            r_val = r_sum
            a_val = np.conj(s_val) * r_val

            radon_src_final[i, j] = s_val
            radon_rec_final[i, j] = r_val
            radon_avp_final[i, j] = a_val

            # Track max in the same pass (Real Abs)
            ms = abs(s_val.real); mr = abs(r_val.real); ma = abs(a_val.real)    # noqa: E702
            if ms > max_s_local[i]:
                max_s_local[i] = ms
            if mr > max_r_local[i]:
                max_r_local[i] = mr
            if ma > max_a_local[i]:
                max_a_local[i] = ma

    # Global reduction
    max_s = np.max(max_s_local); max_r = np.max(max_r_local); max_a = np.max(max_a_local)    # noqa: E702

    # Final scaling pass (parallel)
    src_img = np.empty((n_py, n_px), dtype=np.float32)
    rec_img = np.empty((n_py, n_px), dtype=np.float32)
    avp_img = np.empty((n_py, n_px), dtype=np.float32)

    is_s = 1.0 / max_s if max_s > 0 else 0.0
    is_r = 1.0 / max_r if max_r > 0 else 0.0
    is_a = 1.0 / max_a if max_a > 0 else 0.0

    for i in prange(n_py):
        for j in range(n_px):
            if is_s > 0:
                src_img[i, j] = np.float32(abs(radon_src_final[i, j].real) * is_s)
            else:
                src_img[i, j] = 0.0

            if is_r > 0:
                rec_img[i, j] = np.float32(abs(radon_rec_final[i, j].real) * is_r)
            else:
                rec_img[i, j] = 0.0

            if is_a > 0:
                avp_img[i, j] = np.float32(abs(radon_avp_final[i, j].real) * is_a)
            else:
                avp_img[i, j] = 0.0

    return src_img, rec_img, avp_img


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
    max_res_local = np.zeros(n_y, dtype=np.float64)

    for i in prange(n_y):
        ms = 0.0; mr = 0.0; mres = 0.0  # noqa: E702
        for j in range(n_x):
            s_val = source_field[i, j]
            r_val = receiver_field[i, j]
            res_val = s_val * r_val

            as_val = abs(s_val.real)
            ar_val = abs(r_val.real)
            ares_val = abs(res_val.real)

            if as_val > ms:
                ms = as_val
            if ar_val > mr:
                mr = ar_val
            if ares_val > mres:
                mres = ares_val

        max_s_local[i] = ms
        max_r_local[i] = mr
        max_res_local[i] = mres

    max_s = np.max(max_s_local)
    max_r = np.max(max_r_local)
    max_res = np.max(max_res_local)

    # Pass 2: Scale and convert to dB
    is_s = 1.0 / max_s if max_s > 0 else 0.0
    is_r = 1.0 / max_r if max_r > 0 else 0.0
    is_res = 1.0 / max_res if max_res > 0 else 0.0

    for i in prange(n_y):
        for j in range(n_x):
            # Source dB
            if is_s > 0:
                norm = abs(source_field[i, j].real) * is_s
                if norm < 1e-6:
                    s_img[i, j] = np.float32(db_min)
                else:
                    s_img[i, j] = np.float32(max(20.0 * np.log10(norm), db_min))
            else:
                s_img[i, j] = np.float32(db_min)

            # Receiver dB
            if is_r > 0:
                norm = abs(receiver_field[i, j].real) * is_r
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
                norm = abs(res_val.real) * is_res
                if norm < 1e-6:
                    res_img[i, j] = np.float32(db_min)
                else:
                    res_img[i, j] = np.float32(max(20.0 * np.log10(norm), db_min))
            else:
                res_img[i, j] = np.float32(db_min)

    return s_img, r_img, res_img


@jit(nopython=True, cache=True)
def _find_max_real_abs_numba(field):
    """Helper to find max of absolute real part."""
    n_y, n_x = field.shape
    max_val = 0.0
    for i in range(n_y):
        for j in range(n_x):
            val = abs(field[i, j].real)
            if val > max_val:
                max_val = val
    return max_val


@jit(parallel=True, nopython=True, cache=True)
def convert_to_db_image_numba(field, db_min=-60.0):
    """
    Fused Numba kernel for dB conversion and normalization.
    """
    max_amp = _find_max_real_abs_numba(field)
    n_y, n_x = field.shape
    out = np.empty((n_y, n_x), dtype=np.float32)
    if max_amp <= 0.0:
        out.fill(np.float32(db_min))
        return out

    inv_max = 1.0 / max_amp
    for i in prange(n_y):
        for j in range(n_x):
            norm = abs(field[i, j].real) * inv_max
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
    max_amp = _find_max_real_abs_numba(field)
    n_y, n_x = field.shape
    out = np.empty((n_y, n_x), dtype=np.float32)
    if max_amp <= 0.0:
        out.fill(np.float32(0.0))
        return out

    inv_max = 1.0 / max_amp
    for i in prange(n_y):
        for j in range(n_x):
            out[i, j] = np.float32(abs(field[i, j].real) * inv_max)
    return out


@jit(parallel=True, nopython=True, cache=True)
def compute_resolution_db_numba(source_field, receiver_field, db_min=-60.0):
    """
    Fused kernel for complex multiplication and dB conversion.
    """
    n_y, n_x = source_field.shape
    temp = source_field * receiver_field
    max_amp = _find_max_real_abs_numba(temp)
    out = np.empty((n_y, n_x), dtype=np.float32)
    if max_amp <= 0.0:
        out.fill(np.float32(db_min))
        return out

    inv_max = 1.0 / max_amp
    for i in prange(n_y):
        for j in range(n_x):
            norm = abs(temp[i, j].real) * inv_max
            if norm < 1e-6:
                out[i, j] = np.float32(db_min)
            else:
                val = 20.0 * np.log10(norm)
                out[i, j] = np.float32(max(val, db_min))
    return out


@jit(parallel=True, cache=True)
def compute_monochromatic_weighted_beam_xy_grid(eval_x, eval_y, eval_z, surf_x, surf_y, surf_z, surf_weights, freq, v_int):
    """
    Calculates a monochromatic one-way beam image on an x/y grid at a fixed z level,
    while preserving multiplicity through per-station weights.
    """
    n_x = len(eval_x)
    n_y = len(eval_y)
    n_stations = len(surf_x)
    omega = 2.0 * np.pi * freq
    k = omega / v_int
    beam_grid = np.zeros((n_y, n_x), dtype=np.complex128)

    for y_idx in prange(n_y):
        y_pos = eval_y[y_idx]
        for x_idx in range(n_x):
            x_pos = eval_x[x_idx]
            total_field = 0.0 + 0.0j

            for station_idx in range(n_stations):
                dx = surf_x[station_idx] - x_pos
                dy = surf_y[station_idx] - y_pos
                dz = surf_z[station_idx] - eval_z
                r = np.sqrt(dx * dx + dy * dy + dz * dz)

                if r < 1e-3:
                    continue

                obliquity = np.abs(dz) / r
                phase = -k * r
                amplitude = (obliquity / (2.0 * np.pi * r * r)) * surf_weights[station_idx]
                total_field += complex(amplitude * np.cos(phase), amplitude * np.sin(phase))

            beam_grid[y_idx, x_idx] = total_field

    return beam_grid
