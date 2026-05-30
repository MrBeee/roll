import time

import numpy as np

from acq_ftbeam_homogen import acq_ftbeam_homogen
from acq_rolltempl_pp import acq_rolltempl_pp


def demo_bart_4(verbose=0):

    # ---------------------------------------------------------
    # Receiver geometry
    # ---------------------------------------------------------
    xr = np.arange(1, 121) * 50.0
    xr = xr - np.mean(xr)

    yr = np.arange(1, 5) * 200.0
    yr = yr - np.mean(yr)

    xr, yr = np.meshgrid(xr, yr)
    zr = np.zeros_like(xr)

    rr = np.vstack([xr.ravel(), yr.ravel(), zr.ravel()])

    # ---------------------------------------------------------
    # Source geometry
    # ---------------------------------------------------------
    ys = np.arange(1, 33) * 50.0
    ys = ys - np.mean(ys)

    xs = np.array([0.0])
    xs, ys = np.meshgrid(xs, ys)
    zs = np.zeros_like(xs)

    rs = np.vstack([xs.ravel(), ys.ravel(), zs.ravel()])

    # ---------------------------------------------------------
    # Groups (none)
    # ---------------------------------------------------------
    rgr = np.array([[0.0], [0.0], [0.0]])
    rgs = np.array([[0.0], [0.0], [0.0]])

    # ---------------------------------------------------------
    # Template roll-along parameters
    # ---------------------------------------------------------
    dxt = 250.0
    dyt = 150.0

    xt = np.arange(1, 2) * dxt
    xt = xt - np.mean(xt)

    yt = np.arange(1, 2) * dyt
    yt = yt - np.mean(yt)

    # ---------------------------------------------------------
    # Frequency, velocity, target point
    # ---------------------------------------------------------
    freq = 40.0
    cp = 4000.0
    r1 = np.array([0.0, 500.0, 2000.0])
    z = r1[2]

    # ---------------------------------------------------------
    # Beam grid
    # ---------------------------------------------------------
    x = np.arange(-800.0, 800.1, 12.5)
    y = x.copy()

    # ---------------------------------------------------------
    # Output filename
    # ---------------------------------------------------------
    fnam = "demo_bart_4"
    posno = 1
    result_file = f"{fnam}{posno}"
    print(f"Output filename: {result_file}.mat")

    # ---------------------------------------------------------
    # Ray-parameter grids
    # ---------------------------------------------------------
    Npx = 128
    px = np.linspace(-1.0 / cp, 1.0 / cp, Npx)

    Npy = 128
    py = np.linspace(-1.0 / cp, 1.0 / cp, Npy)

    # ---------------------------------------------------------
    # Radon transform kernels
    # ---------------------------------------------------------
    L1 = np.exp(1j * 2 * np.pi * freq * np.outer(x, px))
    L2 = np.exp(1j * 2 * np.pi * freq * np.outer(py, y))

    # ---------------------------------------------------------
    # Determine rolled-in / rolled-out receivers
    # ---------------------------------------------------------
    rr_min = rr[:, rr[0, :] < (np.min(rr[0, :]) + dxt)]
    rr_max = rr[:, rr[0, :] > (np.max(rr[0, :]) - dxt)]

    # ---------------------------------------------------------
    # Main roll-along loops
    # ---------------------------------------------------------
    nyt = len(yt)

    for l in range(nyt):
        print(f"Rollstep {l+1} of {nyt} started")
        t0 = time.time()

        # First x-position
        k = 1
        rt = np.array([xt[k-1], yt[l], 0.0])

        x_, y_, f_, Bs_s, Br_s, I_s, px_, py_, AVP_s = acq_rolltempl_pp(
            rs, rr, rgs, rgr, rt, r1, x, y, z, freq, cp, 0
        )

        if l == 0 and k == 1:
            Bs_t = np.squeeze(Bs_s)
            Br_t = np.squeeze(Br_s)
            I_t = np.squeeze(I_s)
            AVP_t = np.squeeze(AVP_s)
        else:
            Bs_t += np.squeeze(Bs_s)
            Br_t += np.squeeze(Br_s)
            I_t += np.squeeze(I_s)
            AVP_t += np.squeeze(AVP_s)

        # -----------------------------------------------------
        # Roll along x-direction
        # -----------------------------------------------------
        nxt = len(xt)

        for k in range(2, nxt + 1):

            # Remove receivers rolling out
            rt_prev = np.array([xt[k-2], yt[l], 0.0])
            _, _, _, Br = acq_ftbeam_homogen(
                rs + rt_prev.reshape(3, 1),
                rr_min + rt_prev.reshape(3, 1),
                rgs, rgr, r1, x, y, z, freq, cp, 2, 0, 1
            )
            Br_s = np.squeeze(Br_s) - Br.T

            # Add receivers rolling in
            rt_new = np.array([xt[k-1], yt[l], 0.0])

            _, _, _, Bs = acq_ftbeam_homogen(
                rs + rt_new.reshape(3, 1),
                rr_max + rt_new.reshape(3, 1),
                rgs, rgr, r1, x, y, z, freq, cp, 1, 0, 1
            )
            _, _, _, Br = acq_ftbeam_homogen(
                rs + rt_new.reshape(3, 1),
                rr_max + rt_new.reshape(3, 1),
                rgs, rgr, r1, x, y, z, freq, cp, 2, 0, 1
            )

            Bs_s = Bs.T
            Br_s = np.squeeze(Br_s) + Br.T

            # Focal functions
            I_s = Bs_s * Br_s
            AVP_s = (np.conj(L2) @ Bs_s.T @ np.conj(L1)) * (L2 @ Br_s.T @ L1)
            AVP_s = AVP_s.T

            # Accumulate totals
            Bs_t += Bs_s
            Br_t += Br_s
            I_t += I_s
            AVP_t += AVP_s

        t1 = time.time()
        print(f"Rollstep {l+1} took {t1 - t0:.2f} s")

    # ---------------------------------------------------------
    # Save results
    # ---------------------------------------------------------
    import scipy.io
    scipy.io.savemat(result_file + ".mat", {
        "x": x, "y": y, "freq": freq,
        "Bs_t": Bs_t, "Br_t": Br_t, "I_t": I_t, "AVP_t": AVP_t,
        "px": px, "py": py
    })

    print("Saved:", result_file + ".mat")


if __name__ == "__main__":
    demo_bart_4(verbose=0)
