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


@jit(nopython=True, cache=False)
def _compare_source_key(src_ind, src_line, src_point, key_ind, key_line, key_point, idx):
    if key_ind[idx] < src_ind:
        return -1
    if key_ind[idx] > src_ind:
        return 1
    if key_line[idx] < src_line:
        return -1
    if key_line[idx] > src_line:
        return 1
    if key_point[idx] < src_point:
        return -1
    if key_point[idx] > src_point:
        return 1
    return 0


@jit(nopython=True, cache=False)
def _find_source_key(src_ind, src_line, src_point, key_ind, key_line, key_point):
    left = 0
    right = key_ind.shape[0]
    while left < right:
        mid = (left + right) // 2
        cmp = _compare_source_key(src_ind, src_line, src_point, key_ind, key_line, key_point, mid)
        if cmp < 0:
            left = mid + 1
        elif cmp > 0:
            right = mid
        else:
            return mid
    return -1


@jit(nopython=True, cache=False)
def _compare_line_key(rec_ind, rec_line, key_ind, key_line, idx):
    if key_ind[idx] < rec_ind:
        return -1
    if key_ind[idx] > rec_ind:
        return 1
    if key_line[idx] < rec_line:
        return -1
    if key_line[idx] > rec_line:
        return 1
    return 0


@jit(nopython=True, cache=False)
def _find_line_key(rec_ind, rec_line, key_ind, key_line):
    left = 0
    right = key_ind.shape[0]
    while left < right:
        mid = (left + right) // 2
        cmp = _compare_line_key(rec_ind, rec_line, key_ind, key_line, mid)
        if cmp < 0:
            left = mid + 1
        elif cmp > 0:
            right = mid
        else:
            return mid
    return -1


@jit(nopython=True, cache=False)
def _lower_bound_int(values, start, end, target):
    left = start
    right = end
    while left < right:
        mid = (left + right) // 2
        if values[mid] < target:
            left = mid + 1
        else:
            right = mid
    return left


@jit(nopython=True, cache=False)
def _upper_bound_int(values, start, end, target):
    left = start
    right = end
    while left < right:
        mid = (left + right) // 2
        if values[mid] <= target:
            left = mid + 1
        else:
            right = mid
    return left


@jit(nopython=True, cache=False)
def scan_cfp_geometry_relations_numba(
    rel_src_ind,
    rel_src_line,
    rel_src_point,
    rel_rec_ind,
    rel_rec_line,
    rel_rec_min,
    rel_rec_max,
    rel_in_sps,
    rel_in_rps,
    src_ind,
    src_line,
    src_point,
    src_x,
    src_y,
    inactive_src_ind,
    inactive_src_line,
    inactive_src_point,
    rec_group_ind,
    rec_group_line,
    rec_group_start,
    rec_group_end,
    rec_point,
    rec_x,
    rec_y,
    source_weights,
    receiver_weights,
    focal_x,
    focal_y,
    aperture_radius_squared,
):
    total_trace_count = 0
    contributing_relation_count = 0
    contributing_trace_count = 0
    inactive_source_relation_count = 0
    source_orphan_relation_count = 0
    receiver_orphan_relation_count = 0
    missing_source_count = 0
    missing_receiver_count = 0

    n_rel = rel_src_ind.shape[0]
    for rel_idx in range(n_rel):
        if rel_in_sps[rel_idx] == 0:
            source_orphan_relation_count += 1
            continue

        if rel_in_rps[rel_idx] == 0:
            receiver_orphan_relation_count += 1
            continue

        src_idx = _find_source_key(
            rel_src_ind[rel_idx],
            rel_src_line[rel_idx],
            rel_src_point[rel_idx],
            src_ind,
            src_line,
            src_point,
        )
        if src_idx < 0:
            inactive_src_idx = _find_source_key(
                rel_src_ind[rel_idx],
                rel_src_line[rel_idx],
                rel_src_point[rel_idx],
                inactive_src_ind,
                inactive_src_line,
                inactive_src_point,
            )
            if inactive_src_idx >= 0:
                inactive_source_relation_count += 1
            else:
                missing_source_count += 1
            continue

        source_dx = src_x[src_idx] - focal_x
        source_dy = src_y[src_idx] - focal_y
        if source_dx * source_dx + source_dy * source_dy > aperture_radius_squared:
            continue

        rec_group_idx = _find_line_key(rel_rec_ind[rel_idx], rel_rec_line[rel_idx], rec_group_ind, rec_group_line)
        if rec_group_idx < 0:
            missing_receiver_count += 1
            continue

        rec_min = rel_rec_min[rel_idx]
        rec_max = rel_rec_max[rel_idx]
        if rec_max < rec_min:
            continue

        group_start = rec_group_start[rec_group_idx]
        group_end = rec_group_end[rec_group_idx]
        left = _lower_bound_int(rec_point, group_start, group_end, rec_min)
        right = _upper_bound_int(rec_point, group_start, group_end, rec_max)
        if right <= left:
            missing_receiver_count += 1
            continue

        total_trace_count += right - left
        receiver_count = 0
        for rec_idx in range(left, right):
            receiver_dx = rec_x[rec_idx] - focal_x
            receiver_dy = rec_y[rec_idx] - focal_y
            if receiver_dx * receiver_dx + receiver_dy * receiver_dy <= aperture_radius_squared:
                receiver_weights[rec_idx] += 1.0
                receiver_count += 1

        if receiver_count > 0:
            source_weights[src_idx] += receiver_count
            contributing_relation_count += 1
            contributing_trace_count += receiver_count

    return (
        total_trace_count,
        contributing_relation_count,
        contributing_trace_count,
        inactive_source_relation_count,
        source_orphan_relation_count,
        receiver_orphan_relation_count,
        missing_source_count,
        missing_receiver_count,
    )


@jit(parallel=True, nopython=True, cache=False)
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


@jit(parallel=True, nopython=True, cache=False)
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


@jit(parallel=True, nopython=True, cache=False)
def compute_illumination_row_numba(focal_y, eval_x, focal_z, src_coords, src_weights, rec_coords, rec_weights, freqs, vint, max_radius, matlab_compat=False):
    """
    Optimized kernel to compute a single row of an illumination (energy) map.
    Applies a moving spatial aperture filter per pixel in parallel.
    """
    _ = matlab_compat
    n_x = len(eval_x)
    n_sources = src_coords.shape[0]
    n_receivers = rec_coords.shape[0]
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

            for src_idx in range(n_sources):
                dsx = src_coords[src_idx, 0] - f_x
                dsy = src_coords[src_idx, 1] - focal_y
                rs_sq = dsx * dsx + dsy * dsy
                if rs_sq > r_sq_limit:
                    continue

                w = src_weights[src_idx]
                rs = np.sqrt(rs_sq + dsz2_vals[src_idx])
                if rs > 1e-3:
                    bs += np.complex64((abs_dsz_vals[src_idx] / (two_pi * rs * rs)) * w) * np.exp(1j * (-k * rs))

            for rec_idx in range(n_receivers):
                drx = rec_coords[rec_idx, 0] - f_x
                dry = rec_coords[rec_idx, 1] - focal_y
                rr_sq = drx * drx + dry * dry
                if rr_sq > r_sq_limit:
                    continue

                w = rec_weights[rec_idx]
                rr = np.sqrt(rr_sq + drz2_vals[rec_idx])
                if rr > 1e-3:
                    br += np.complex64((abs_drz_vals[rec_idx] / (two_pi * rr * rr)) * w) * np.exp(1j * (-k * rr))

            pixel_energy += np.abs(bs * br)

        row_energy[ix] = pixel_energy
    return row_energy


@jit(parallel=True, nopython=True, cache=False)
def compute_illumination_row_incoherent_numba(focal_y, eval_x, focal_z, src_coords, src_weights, rec_coords, rec_weights, freqs, vint, max_radius, matlab_compat=False):
    """
    Incoherent illumination QC kernel: ignores phase interference and accumulates amplitude products.
    For each source-receiver pair, compute scalar amplitudes and sum their products (no phase cancellation).
    This is a diagnostic companion map; coherent illumination remains the physics-facing default.
    """
    _ = matlab_compat
    _ = vint
    n_x = len(eval_x)
    n_sources = src_coords.shape[0]
    n_receivers = rec_coords.shape[0]
    n_freqs = len(freqs)
    r_sq_limit = np.float32(max_radius * max_radius)
    two_pi = np.float32(2.0 * np.pi)

    row_energy = np.zeros(n_x, dtype=np.float32)

    dsz_vals = src_coords[:, 2] - focal_z
    dsz2_vals = dsz_vals * dsz_vals
    abs_dsz_vals = np.abs(dsz_vals)

    drz_vals = rec_coords[:, 2] - focal_z
    drz2_vals = drz_vals * drz_vals
    abs_drz_vals = np.abs(drz_vals)

    for ix in prange(n_x):
        f_x = eval_x[ix]
        pixel_energy = 0.0

        for _ in range(n_freqs):
            for src_idx in range(n_sources):
                dsx = src_coords[src_idx, 0] - f_x
                dsy = src_coords[src_idx, 1] - focal_y
                rs_sq = dsx * dsx + dsy * dsy
                if rs_sq > r_sq_limit:
                    continue

                ws = src_weights[src_idx]
                rs = np.sqrt(rs_sq + dsz2_vals[src_idx])
                if rs < 1e-3:
                    continue
                bs_amp = (abs_dsz_vals[src_idx] / (two_pi * rs * rs)) * ws

                for rec_idx in range(n_receivers):
                    drx = rec_coords[rec_idx, 0] - f_x
                    dry = rec_coords[rec_idx, 1] - focal_y
                    rr_sq = drx * drx + dry * dry
                    if rr_sq > r_sq_limit:
                        continue

                    wr = rec_weights[rec_idx]
                    rr = np.sqrt(rr_sq + drz2_vals[rec_idx])
                    if rr > 1e-3:
                        br_amp = (abs_drz_vals[rec_idx] / (two_pi * rr * rr)) * wr
                        pixel_energy += bs_amp * br_amp

        row_energy[ix] = pixel_energy

    return row_energy


@jit(parallel=True, nopython=True, cache=False)
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


@jit(nopython=True, cache=False)
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


@jit(parallel=True, nopython=True, cache=False)
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


def compute_monochromatic_weighted_beam_xy_grid(eval_x, eval_y, eval_z, surf_x, surf_y, surf_z, surf_weights, freq, v_int, focal_x=0.0, focal_y=0.0):
    """
    Calculates the Fourier/slowness CFP beam while preserving multiplicity through
    per-station weights.
    """
    return _compute_weighted_ft_beam_xy_grid_numba(eval_x, eval_y, eval_z, surf_x, surf_y, surf_z, surf_weights, freq, v_int, focal_x, focal_y)


@jit(parallel=True, nopython=True, cache=False)
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
