# CFP single-template parity matrix (MATLAB vs Python)

Date: 2026-05-29
Scope: Single-template, non-rolling parity audit anchored on demo_bart_4 call chain.

Ground-truth MATLAB chain:
- [matlab/demo_bart_4.m](matlab/demo_bart_4.m)
- [matlab/acq_rolltempl_pp.m](matlab/acq_rolltempl_pp.m)
- [matlab/acq_ftbeam_homogen.m](matlab/acq_ftbeam_homogen.m)

Active Python path:
- [worker_threads.py](worker_threads.py)
- [cfp_aux_functions_numba.py](cfp_aux_functions_numba.py)

## 1) Call-flow parity

MATLAB flow:
1. demo builds geometry/frequency/grid and calls rolltempl per target.
2. rolltempl calls ftbeam for source and receiver beams.
3. rolltempl computes resolution I and AVP in Radon domain.

Python flow:
1. worker initializes XY grid and accumulates source/receiver beam fields.
2. Numba kernels compute XY fields and Radon images.
3. worker builds source/receiver/resolution/AVP image products.

Status: Conceptually aligned.

## 2) Formula-level parity matrix

### 2.1 Radon slowness axes
- MATLAB uses full slowness range:
  - [matlab/acq_rolltempl_pp.m](matlab/acq_rolltempl_pp.m#L59)
  - [matlab/acq_rolltempl_pp.m](matlab/acq_rolltempl_pp.m#L60)
- Python uses dip-limited range in worker orchestration:
  - [worker_threads.py](worker_threads.py#L545)

Parity status: Not equal (domain extent differs).

### 2.2 One-way beam kernel amplitude
- MATLAB kernel includes Jacobian and frequency-square scaling via Js/Jr and (p*w)^2:
  - [matlab/acq_ftbeam_homogen.m](matlab/acq_ftbeam_homogen.m#L167)
  - [matlab/acq_ftbeam_homogen.m](matlab/acq_ftbeam_homogen.m#L213)
- Python kernel uses obliquity/(2*pi*r^2) style scaling:
  - [cfp_aux_functions_numba.py](cfp_aux_functions_numba.py#L256)

Parity status: Not equal (amplitude law differs).

### 2.3 z-propagation when evaluation depth differs (z1 != z)
- MATLAB applies explicit phase-rotation Wt branch:
  - [matlab/acq_ftbeam_homogen.m](matlab/acq_ftbeam_homogen.m#L173)
  - [matlab/acq_ftbeam_homogen.m](matlab/acq_ftbeam_homogen.m#L222)
- Active Python XY beam kernel has no equivalent branch:
  - [cfp_aux_functions_numba.py](cfp_aux_functions_numba.py#L229)

Parity status: Not equal for off-target depth evaluation.

### 2.4 Resolution function in XY
- MATLAB resolution is I = Bs .* Br:
  - [matlab/acq_rolltempl_pp.m](matlab/acq_rolltempl_pp.m#L87)
- Python resolution product is also source*receiver in fused image conversion:
  - [cfp_aux_functions_numba.py](cfp_aux_functions_numba.py#L498)

Parity status: Aligned in structure; values still depend on kernel mismatch above.

### 2.5 AVP construction in Radon domain
- MATLAB AVP:
  - [matlab/acq_rolltempl_pp.m](matlab/acq_rolltempl_pp.m#L88)
- Python AVP currently uses conj(source_radon)*receiver_radon in Numba:
  - [cfp_aux_functions_numba.py](cfp_aux_functions_numba.py#L379)

Parity status: Similar intent, not guaranteed identical algebra under all conventions.

## 3) Why worker_threads changes are needed

Even if kernels are edited, final products can still differ unless worker orchestration matches MATLAB assumptions:

1. Worker defines Radon grid extent and sampling (currently dip-limited):
- [worker_threads.py](worker_threads.py#L545)

2. Worker defines transform coordinates passed into Radon kernel (centered evalX/evalY):
- [worker_threads.py](worker_threads.py#L555)

3. Worker controls image normalization/SNR output path and metadata used in displays:
- [worker_threads.py](worker_threads.py#L552)
- [worker_threads.py](worker_threads.py#L559)

4. Worker chooses beam accumulation semantics and weighting path:
- [worker_threads.py](worker_threads.py#L412)
- [worker_threads.py](worker_threads.py#L421)

Therefore, strict parity needs both:
- kernel-level updates in [cfp_aux_functions_numba.py](cfp_aux_functions_numba.py)
- orchestration-level updates in [worker_threads.py](worker_threads.py)

## 4) Change set required for strict single-template parity

Minimum compatibility-mode changes:
1. Add MATLAB-compatible beam kernel mode (Jacobian + frequency-square scaling terms).
2. Add explicit z1!=z propagation branch support in compatible path.
3. Add MATLAB-compatible Radon axis option using [-1/v, +1/v].
4. Add AVP compatibility option to mirror MATLAB transform convention.
5. Keep current fast mode as default; expose compatibility mode for parity runs.

## 5) Validation protocol for your upcoming one-template survey file

When the one-template non-rolling survey file is ready:
1. Run MATLAB baseline with matching focal point, velocity, frequency, x/y grid.
2. Run Python in compatibility mode with same parameters.
3. Compare normalized panels for Source XY, Receiver XY, Resolution XY, Radon Source, Radon Receiver, AVP.
4. Report max-abs error, mean-abs error, and correlation per panel.

Suggested acceptance for single-template parity pilot:
- Correlation >= 0.995 on all six panels.
- Mean-abs error <= 0.01 after matched normalization.
- Max-abs error <= 0.05 (edge artifacts excluded if grids differ by one sample).

## 6) Current conclusion

For single-template non-rolling physics, current implementation is conceptually aligned but not yet strict-parity with MATLAB formulas. The main differences are in beam amplitude law, depth phase branch handling, and Radon domain setup.
