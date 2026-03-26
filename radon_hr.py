#!/usr/bin/env python
"""
High-resolution linear Radon transform in pure Python.

Features:
- SEGY input via segyio
- Automatic offset detection + synthetic offsets via nominal dx
- Linear Radon forward and adjoint operators
- IRLS-based L1-like sparse inversion
- Simple CLI for batch use

Usage examples:
    python radon_hr.py invert  input.sgy radon.npy --dx 25
    python radon_hr.py synth   input.sgy radon.npy output.npy --dx 12.5
"""

import argparse
from typing import Optional, Tuple
import numpy as np
import segyio

try:
    from numba import njit, prange
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False

    def njit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

    def prange(*args):
        return range(*args)


# ----------------------------------------------------------------------
# Offset utilities
# ----------------------------------------------------------------------

def build_nominal_offsets(ntraces: int, dx: float, center: float = 0.0) -> np.ndarray:
    """
    Build synthetic offsets when true geometry is missing.

    Offsets are centered around 'center' (default 0):
        x = center + (i - (ntraces-1)/2) * dx
    """
    mid = (ntraces - 1) / 2.0
    return center + (np.arange(ntraces) - mid) * dx


# ----------------------------------------------------------------------
# SEGY I/O
# ----------------------------------------------------------------------

def load_gather(
    filename: str,
    dx: Optional[float] = None,
    fid: Optional[int] = None,
    target_trid: Optional[int] = 12,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Load a 2D gather from SEGY.

    If offsets are missing or constant, synthetic offsets are generated
    using the nominal spacing dx.
    """
    with segyio.open(filename, "r", ignore_geometry=True) as f:
        dt = segyio.dt(f) / 1e6
        all_offsets = f.attributes(segyio.su.offset)[:]
        all_trids = f.attributes(segyio.su.trid)[:]

        if fid is None:
            if target_trid is None:
                selected_indices = np.arange(len(all_offsets))
            else:
                selected_indices = np.where(all_trids == target_trid)[0]
                if selected_indices.size == 0:
                    raise ValueError(f"No traces found for TRID {target_trid}")

            data = np.stack([f.trace[index] for index in selected_indices])
            offsets = np.asarray(all_offsets[selected_indices], dtype=float)
        else:
            field_records = f.attributes(segyio.su.fldr)[:]
            selection_mask = field_records == fid

            if target_trid is not None:
                selection_mask &= all_trids == target_trid

            selected_indices = np.where(selection_mask)[0]
            if selected_indices.size == 0:
                raise ValueError(
                    f"No traces found for FID {fid}"
                    + (f" and TRID {target_trid}" if target_trid is not None else "")
                )

            data = np.stack([f.trace[index] for index in selected_indices])
            offsets = np.asarray(all_offsets[selected_indices], dtype=float)

    # Detect missing or useless offsets
    if dx is not None:
        if np.all(offsets == 0) or np.allclose(offsets, offsets[0]):
            print("[load_gather] No valid offsets found → using nominal dx")
            offsets = build_nominal_offsets(len(offsets), dx)
    else:
        # If dx not provided and offsets are bad → raise
        if np.all(offsets == 0) or np.allclose(offsets, offsets[0]):
            raise ValueError(
                "Offsets are missing in SEGY and no nominal dx was provided."
            )

    return data, offsets, dt


def save_npy(filename: str, arr: np.ndarray) -> None:
    np.save(filename, arr)


def load_npy(filename: str) -> np.ndarray:
    return np.load(filename)


# ----------------------------------------------------------------------
# Radon operators (linear)
# ----------------------------------------------------------------------

@njit(cache=True, parallel=True)
def _radon_forward_kernel(m: np.ndarray,
                          offsets: np.ndarray,
                          q: np.ndarray,
                          dt: float) -> np.ndarray:
    nq, nt = m.shape
    nx = offsets.shape[0]
    d = np.zeros((nx, nt), dtype=np.float32)

    for ix in prange(nx):
        x = offsets[ix]
        for iq in range(nq):
            shift_dt = (q[iq] * x) / dt
            for it in range(nt):
                tshift = it + shift_dt
                lo = int(np.floor(tshift))
                hi = lo + 1
                if lo >= 0 and hi < nt:
                    w = tshift - lo
                    d[ix, it] += (1.0 - w) * m[iq, lo] + w * m[iq, hi]

    return d


@njit(cache=True, parallel=True)
def _radon_adjoint_kernel(d: np.ndarray,
                          offsets: np.ndarray,
                          q: np.ndarray,
                          dt: float) -> np.ndarray:
    nx, nt = d.shape
    nq = q.shape[0]
    m = np.zeros((nq, nt), dtype=np.float32)

    for iq in prange(nq):
        qv = q[iq]
        for ix in range(nx):
            shift_dt = (qv * offsets[ix]) / dt
            for it in range(nt):
                tshift = it + shift_dt
                lo = int(np.floor(tshift))
                hi = lo + 1
                if lo >= 0 and hi < nt:
                    w = tshift - lo
                    dv = d[ix, it]
                    m[iq, lo] += (1.0 - w) * dv
                    m[iq, hi] += w * dv

    return m


def _prepare_forward_inputs(m: np.ndarray,
                            offsets: np.ndarray,
                            q: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (
        np.ascontiguousarray(m, dtype=np.float32),
        np.ascontiguousarray(offsets, dtype=np.float64),
        np.ascontiguousarray(q, dtype=np.float64),
    )


def _prepare_adjoint_inputs(d: np.ndarray,
                            offsets: np.ndarray,
                            q: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (
        np.ascontiguousarray(d, dtype=np.float32),
        np.ascontiguousarray(offsets, dtype=np.float64),
        np.ascontiguousarray(q, dtype=np.float64),
    )

def radon_forward(m: np.ndarray,
                  offsets: np.ndarray,
                  q: np.ndarray,
                  dt: float) -> np.ndarray:
    """
    Forward linear Radon transform using t + qx moveout.
    """
    m_arr, offsets_arr, q_arr = _prepare_forward_inputs(m, offsets, q)
    return _radon_forward_kernel(m_arr, offsets_arr, q_arr, dt)


def radon_adjoint(d: np.ndarray,
                  offsets: np.ndarray,
                  q: np.ndarray,
                  dt: float) -> np.ndarray:
    """
    Adjoint linear Radon transform using t + qx moveout.
    """
    d_arr, offsets_arr, q_arr = _prepare_adjoint_inputs(d, offsets, q)
    return _radon_adjoint_kernel(d_arr, offsets_arr, q_arr, dt)


def adjoint_test(offsets: np.ndarray,
                 q: np.ndarray,
                 dt: float,
                 nt: int,
                 nx: int,
                 seed: int = 0) -> float:
    """
    Check <Rm, d> ≈ <m, R^T d>.
    """
    rng = np.random.default_rng(seed)
    m = rng.standard_normal((len(q), nt)).astype(np.float32)
    d = rng.standard_normal((nx, nt)).astype(np.float32)

    Rm = radon_forward(m, offsets, q, dt)
    RTd = radon_adjoint(d, offsets, q, dt)

    lhs = np.vdot(Rm, d)
    rhs = np.vdot(m, RTd)
    rel_err = np.abs(lhs - rhs) / (np.abs(lhs) + 1e-12)
    return float(rel_err)


# ----------------------------------------------------------------------
# IRLS solver
# ----------------------------------------------------------------------

def _apply_A(v: np.ndarray,
             offsets: np.ndarray,
             q: np.ndarray,
             dt: float,
             w: np.ndarray,
             lam: float,
             nt: int,
             nq: int) -> np.ndarray:
    """
    A v = R^T R v + lam * W v  (W diagonal via w).
    """
    v = v.reshape(nq, nt)
    Rv = radon_forward(v, offsets, q, dt)
    RT_Rv = radon_adjoint(Rv, offsets, q, dt)
    return (RT_Rv + lam * w * v).ravel()


def irls_radon(d: np.ndarray,
               offsets: np.ndarray,
               q: np.ndarray,
               dt: float,
               lam: float = 0.1,
               nouter: int = 15,
               ninner: int = 10,
               eps: float = 1e-6,
               cg_tol: float = 1e-6) -> np.ndarray:
    """
    High-resolution linear Radon via IRLS (L1-like).
    """
    _, nt = d.shape
    nq = len(q)

    m = np.zeros((nq, nt), dtype=np.float32)

    for _ in range(nouter):
        w = 1.0 / (np.abs(m) + eps)

        b = radon_adjoint(d, offsets, q, dt).ravel()

        def A(v, current_w=w):
            return _apply_A(v, offsets, q, dt, current_w, lam, nt, nq)

        x = m.ravel()
        r = b - A(x)
        p = r.copy()
        rsold = np.dot(r, r)

        for _ in range(ninner):
            Ap = A(p)
            alpha = rsold / (np.dot(p, Ap) + 1e-20)
            x = x + alpha * p
            r = r - alpha * Ap
            rsnew = np.dot(r, r)
            if np.sqrt(rsnew) < cg_tol:
                break
            p = r + (rsnew / (rsold + 1e-20)) * p
            rsold = rsnew

        m = x.reshape(nq, nt)

    return m


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def cmd_invert(args: argparse.Namespace) -> None:
    data, offsets, dt = load_gather(args.input, dx=args.dx)
    nx, nt = data.shape

    q = np.linspace(args.qmin, args.qmax, args.nq, dtype=np.float64)

    print(f"[invert] nx={nx}, nt={nt}, nq={len(q)}, dt={dt:.6e}")
    print(f"[invert] q in [{q[0]:.3e}, {q[-1]:.3e}]")

    m = irls_radon(
        d=data,
        offsets=offsets,
        q=q,
        dt=dt,
        lam=args.lam,
        nouter=args.nouter,
        ninner=args.ninner,
    )

    save_npy(args.output, m)
    print(f"[invert] saved Radon model to {args.output}")


def cmd_synth(args: argparse.Namespace) -> None:
    _, offsets, dt = load_gather(args.input, dx=args.dx)
    m = load_npy(args.model)
    nq, nt = m.shape

    q = np.linspace(args.qmin, args.qmax, nq, dtype=np.float64)

    print(f"[synth] using nq={nq}, nt={nt}, dt={dt:.6e}")
    d_syn = radon_forward(m, offsets, q, dt)
    save_npy(args.output, d_syn)
    print(f"[synth] saved synthetic/denoised gather to {args.output}")


def cmd_adjoint_test(args: argparse.Namespace) -> None:
    offsets = np.linspace(args.xmin, args.xmax, args.nx, dtype=np.float64)
    q = np.linspace(args.qmin, args.qmax, args.nq, dtype=np.float64)
    err = adjoint_test(offsets, q, args.dt, args.nt, args.nx)
    print(f"Adjoint test relative error: {err:.3e}")


def cmd_debug(args: argparse.Namespace) -> None:
    filename = args.input
    if filename is None:
        filename = input("SEG-Y file name: ").strip().strip('"').strip("'")
    if not filename:
        raise ValueError("A SEG-Y file name is required")

    fid = args.fid
    if fid is None:
        fid_text = input("FID number: ").strip()
        try:
            fid = int(fid_text)
        except ValueError as exc:
            raise ValueError(f"Invalid FID number: {fid_text}") from exc

    data, offsets, dt = load_gather(filename, dx=args.dx, fid=fid)
    print(f"[debug] file={filename}")
    print(f"[debug] FID={fid}")
    print(f"[debug] traces={data.shape[0]}, samples={data.shape[1]}, dt={dt:.6e} s")
    print(f"[debug] offset range=[{offsets.min():.3f}, {offsets.max():.3f}] m")
    print(f"[debug] trace amplitude max={np.max(np.abs(data)):.6g}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="High-resolution linear Radon (Python)")
    sub = p.add_subparsers(dest="cmd", required=True)

    # invert
    pi = sub.add_parser("invert", help="invert gather to Radon model")
    pi.add_argument("input", help="input SEGY gather")
    pi.add_argument("output", help="output .npy Radon model")
    pi.add_argument("--dx", type=float, default=None,
                    help="Nominal trace spacing (m) if offsets missing")
    pi.add_argument("--qmin", type=float, default=-1e-3)
    pi.add_argument("--qmax", type=float, default=1e-3)
    pi.add_argument("--nq", type=int, default=80)
    pi.add_argument("--lam", type=float, default=0.05)
    pi.add_argument("--nouter", type=int, default=15)
    pi.add_argument("--ninner", type=int, default=10)
    pi.set_defaults(func=cmd_invert)

    # synth
    ps = sub.add_parser("synth", help="synthesize/denoise gather from Radon model")
    ps.add_argument("input", help="input SEGY gather (for offsets, dt)")
    ps.add_argument("model", help="input .npy Radon model")
    ps.add_argument("output", help="output .npy gather")
    ps.add_argument("--dx", type=float, default=None,
                    help="Nominal trace spacing (m) if offsets missing")
    ps.add_argument("--qmin", type=float, default=-1e-3)
    ps.add_argument("--qmax", type=float, default=1e-3)
    ps.set_defaults(func=cmd_synth)

    # adjoint test
    pt = sub.add_parser("adjtest", help="run adjoint test")
    pt.add_argument("--nx", type=int, default=30)
    pt.add_argument("--nt", type=int, default=500)
    pt.add_argument("--xmin", type=float, default=0.0)
    pt.add_argument("--xmax", type=float, default=3000.0)
    pt.add_argument("--qmin", type=float, default=-1e-3)
    pt.add_argument("--qmax", type=float, default=1e-3)
    pt.add_argument("--nq", type=int, default=60)
    pt.add_argument("--dt", type=float, default=0.004)
    pt.set_defaults(func=cmd_adjoint_test)

    # debug
    pd = sub.add_parser("debug", help="interactively load a SEG-Y gather by FID")
    pd.add_argument("input", nargs="?", help="input SEGY gather")
    pd.add_argument("fid", nargs="?", type=int, help="FID / field record number")
    pd.add_argument("--dx", type=float, default=None,
                    help="Nominal trace spacing (m) if offsets missing")
    pd.set_defaults(func=cmd_debug)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()


# from the bash command line, you can run:
#   python radon_hr.py adjtest
#   python radon_hr.py invert  gather.sgy radon.npy
#   python radon_hr.py synth   gather.sgy radon.npy denoised.npy

