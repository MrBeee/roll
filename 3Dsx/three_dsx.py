# three_dsx.py

import numpy as np

# ---------------------------------------------------------
# GEOMETRY UTILITIES
# ---------------------------------------------------------

def compute_offsets(rx, ry, sx, sy):
    rx, ry, sx, sy = map(np.asarray, (rx, ry, sx, sy))
    return np.sqrt((rx - sx)**2 + (ry - sy)**2)

def compute_azimuths(rx, ry, sx, sy):
    rx, ry, sx, sy = map(np.asarray, (rx, ry, sx, sy))
    return np.arctan2(ry - sy, rx - sx)  # radians

# ---------------------------------------------------------
# OFFSET DIAGNOSTICS
# ---------------------------------------------------------

def multiplicity(offsets, min_off, max_off):
    offsets = np.asarray(offsets)
    return np.sum((offsets >= min_off) & (offsets <= max_off))


def offset_uniformity(offsets, min_off, max_off, interval):
    bins = np.arange(min_off, max_off + interval, interval)
    hist, _ = np.histogram(offsets, bins=bins)
    return np.sum(hist > 0)


def discrimination_multiplicity(offsets, disc):
    offs = np.sort(offsets)
    count = 1
    last = offs[0]
    for x in offs[1:]:
        if x - last > disc:
            count += 1
            last = x
    return count


def effective_fold(offsets, min_off, max_off, avg_sep):
    dr = avg_sep / 2
    offs = np.sort(offsets)

    intervals = [(o - dr, o + dr) for o in offs]

    merged = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)

    total_range = max_off - min_off
    covered = sum(max(0, min(end, max_off) - max(start, min_off))
                  for start, end in merged)

    fraction = covered / total_range
    ideal = total_range / avg_sep + 1

    return ideal * fraction


def delta_offset_rms(offsets):
    offs = np.sort(offsets)
    diffs = np.diff(offs)
    mean_dx = np.mean(diffs)
    return np.sqrt(np.mean((diffs - mean_dx)**2))


def inline_offset(rx, sx):
    return np.mean(np.asarray(rx) - np.asarray(sx))


def crossline_offset(ry, sy):
    return np.mean(np.asarray(ry) - np.asarray(sy))


def offset_range(offsets):
    return np.max(offsets) - np.min(offsets)


def largest_gap(offsets):
    offs = np.sort(offsets)
    return np.max(np.diff(offs))

# ---------------------------------------------------------
# COHERENT NOISE SUPPRESSION
# ---------------------------------------------------------

def multiple_suppression(offsets, fmin, fmax, VM, VP, t0, nfreq=200):
    offsets = np.asarray(offsets)
    freqs = np.linspace(fmin, fmax, nfreq)

    t = np.sqrt(t0**2 + (offsets/VM)**2) - (offsets/VP)**2

    Rf = np.array([
        np.mean(np.exp(2j * np.pi * f * t))
        for f in freqs
    ])

    return np.trapz(np.abs(Rf)**2, freqs) / (fmax - fmin)


def multiple_suppression_arrays(offsets, fmin, fmax, VM, VP, t0,
                                RR, RS, nfreq=200):
    offsets = np.asarray(offsets)
    freqs = np.linspace(fmin, fmax, nfreq)

    t = np.sqrt(t0**2 + (offsets/VM)**2) - (offsets/VP)**2

    Rf = []
    for f in freqs:
        k = 2*np.pi*f/VM * np.sqrt(1 + (offsets/VM)**2)
        Rf.append(np.mean(np.exp(2j*np.pi*f*t) * RR(k) * RS(k)))

    Rf = np.array(Rf)
    return np.trapz(np.abs(Rf)**2, freqs) / (fmax - fmin)


def stack_response(offsets, lam_min, lam_max, n_k=200):
    offsets = np.asarray(offsets)
    kmin = 2*np.pi / lam_max
    kmax = 2*np.pi / lam_min
    ks = np.linspace(kmin, kmax, n_k)

    Rk = np.array([
        np.mean(np.exp(1j * k * offsets))
        for k in ks
    ])

    return np.trapz(np.abs(Rk)**2, ks) / (kmax - kmin)


def stack_response_arrays(offsets, lam_min, lam_max, RR, RS, n_k=200):
    offsets = np.asarray(offsets)
    kmin = 2*np.pi / lam_max
    kmax = 2*np.pi / lam_min
    ks = np.linspace(kmin, kmax, n_k)

    Rk = []
    for k in ks:
        Rk.append(np.mean(np.exp(1j*k*offsets) * RR(k) * RS(k)))

    Rk = np.array(Rk)
    return np.trapz(np.abs(Rk)**2, ks) / (kmax - kmin)

# ---------------------------------------------------------
# ARRAY RESPONSE
# ---------------------------------------------------------

def array_response(elements, weights, lam, theta):
    elements = np.asarray(elements)
    weights = np.asarray(weights)

    x, y = elements[:,0], elements[:,1]
    d = np.sqrt(x**2 + y**2)
    theta_n = np.arctan2(y, x)

    p = d * np.cos(theta_n - theta)
    phase = np.exp(1j * 2*np.pi * p / lam)

    return np.sum(weights * phase) / np.sum(weights)


def array_response_uncertain(elements, weights, lam, theta, sigma_x, sigma_y):
    R = array_response(elements, weights, lam, theta)

    k = 2*np.pi / lam
    kx = k * np.cos(theta)
    ky = k * np.sin(theta)

    B = np.exp(-(sigma_x**2) * kx**2 - (sigma_y**2) * ky**2)

    wsum = np.sum(weights)
    w2sum = np.sum(weights**2)

    return np.abs(R)**2 * B + (1 - B) * (w2sum / wsum**2)

# ---------------------------------------------------------
# DMO MOVEMENT & BINNING
# ---------------------------------------------------------

def dmo_point_movement(offsets, dip_deg, azimuth_deg, V, t0):
    offsets = np.asarray(offsets)
    h = offsets / 2.0

    dip = np.radians(dip_deg)
    az = np.radians(azimuth_deg)

    dx = np.cos(az)
    dy = np.sin(az)

    shift = (h**2 / (V**2 * t0)) * np.tan(dip)

    shift_x = shift * dx
    shift_y = shift * dy

    return shift_x, shift_y


def dmo_binning(cmp_x, cmp_y, offsets, dip, az, V, t0, bin_size):
    cmp_x = np.asarray(cmp_x)
    cmp_y = np.asarray(cmp_y)
    offsets = np.asarray(offsets)

    shift_x, shift_y = dmo_point_movement(offsets, dip, az, V, t0)

    dmo_x = cmp_x + shift_x
    dmo_y = cmp_y + shift_y

    bin_i = np.floor(dmo_x / bin_size).astype(int)
    bin_j = np.floor(dmo_y / bin_size).astype(int)

    bins = {}
    for i, j in zip(bin_i, bin_j):
        bins.setdefault((i, j), 0)
        bins[(i, j)] += 1

    return bins



