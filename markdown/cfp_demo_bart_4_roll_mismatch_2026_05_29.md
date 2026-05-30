# CFP mismatch checklist for demo_bart_4.roll

Date: 2026-05-29
Project tested: D:/Roll/roll_testing/CFP/demo_bart_4.roll

## Confirmed geometry match
- Source station geometry in file matches demo intent (32 shots, 50 m spacing, centered in y).
- Receiver station geometry in file matches demo intent (4 x 120, 200 m by 50 m spacing, centered around x=-2975..+2975, y around -300..+300).

## Confirmed non-geometry mismatches that change CFP output

1. Target depth mismatch used by CFP worker
- In this .roll file, global plane anchor is z0=-4000 in [D:/Roll/roll_testing/CFP/demo_bart_4.roll](D:/Roll/roll_testing/CFP/demo_bart_4.roll).
- CFP worker takes focalZ from plane anchor in [worker_operation_controller.py](worker_operation_controller.py#L289).
- MATLAB demo uses target depth 2000 m (equivalent local z=-2000 in Roll convention).

2. Target XY mismatch by default
- MATLAB demo target is r1=[0;500;2000].
- CFP worker target XY is spider point if set, otherwise analysis-area center in [worker_operation_controller.py](worker_operation_controller.py#L347).
- Current output rect center from file is y=0, not y=500.

3. Aperture filter active in Python but not in MATLAB demo chain
- Python template scan always applies aperture filtering using maxDip-derived radius in [roll_survey.py](roll_survey.py#L830) and [roll_survey.py](roll_survey.py#L792).
- With z=-4000 and maxDip from reflection max (45 deg), radius=4000 m; this still changes trace selection behavior versus MATLAB demo flow which does not prefilter this way.

4. Analysis window and sample grid mismatch
- Current .roll output window is x:[-1500,1500], y:[-600,600], dx=dy=25 in [D:/Roll/roll_testing/CFP/demo_bart_4.roll](D:/Roll/roll_testing/CFP/demo_bart_4.roll).
- MATLAB demo uses x=y=-800:12.5:800.

5. Radon slowness domain mismatch
- Python worker uses dip-limited slowness range in [worker_threads.py](worker_threads.py#L545).
- MATLAB rolltempl uses full [-1/v,+1/v] in [matlab/acq_rolltempl_pp.m](matlab/acq_rolltempl_pp.m#L59).

## Fast alignment checklist before rerun

1. Set local target depth to -2000 for CFP run.
2. Set target XY to (0,500) via spider point before launching CFP.
3. Set reflection max angle high enough to include all stations for parity test (e.g. 89 deg).
4. Set output window and bin size to match MATLAB grid:
   - xmin=-800, xmax=800
   - ymin=-800, ymax=800
   - dx=dy=12.5
5. Keep frequency=40 and vint=4000 (already aligned).

## Note
Even after parameter alignment, strict parity is still limited by known formula differences in kernel/orchestration documented in [markdown/cfp_single_template_parity_matrix_2026_05_29.md](markdown/cfp_single_template_parity_matrix_2026_05_29.md).

Yes, there are real Python-side mismatches, and at least one likely bug.

Most probable reasons for the discrepancy:

1. Python uses complex magnitude, MATLAB displays real-part amplitude first.

- MATLAB panels explicitly do real(...) before scaling/display, then abs(...) for plotting in [acq_disp_analysis_result.m:122](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html), [acq_disp_analysis_result.m:146](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html), [acq_disp_analysis_result.m:170](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html), [acq_disp_analysis_result.m:182](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html).
- Python uses abs(complex) directly for XY and Radon images in [cfp_aux_functions_numba.py:490](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html), [cfp_aux_functions_numba.py:500](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html), [cfp_aux_functions_numba.py:408](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html), [cfp_aux_functions_numba.py:413](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html), [cfp_aux_functions_numba.py:418](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html).
- Effect: MATLAB interference lobes/striping are suppressed in Python, giving smoother/broader patterns.

1. Beam physics is not equivalent between implementations.

- MATLAB beam kernel includes Jacobian and frequency/slowness weighting terms Js/Jr and (p*w)^2 in [acq_ftbeam_homogen.m:121](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html), [acq_ftbeam_homogen.m:122](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html), [acq_ftbeam_homogen.m:179](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html), [acq_ftbeam_homogen.m:236](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html).
- Python uses simplified amplitude obliquity/(2*pi*r^2) in [cfp_aux_functions_numba.py:256](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html).
- Effect: different beam shape even before plotting/normalization.

1. Radon p-domain setup differs.

- MATLAB uses full slowness range [-1/c, +1/c] in [acq_rolltempl_pp.m:59](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html), [acq_rolltempl_pp.m:60](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html).
- Python limits to sin(maxDip)/vint and uses 256 samples in [worker_threads.py:542](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html), [worker_threads.py:544](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html).
- Effect: lobe widths and side-lobe distribution can differ significantly unless maxDip=90 deg and velocity settings match exactly.

1. Likely bug: focal center used for Radon recentering is forced to analysis-window center, not request focal point.

- Request focal is captured in [worker_threads.py:871](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html), [worker_threads.py:872](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html).
- Accumulator resets focal to window center in [worker_threads.py:383](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html), [worker_threads.py:384](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html).
- Radon phase uses evalX - focalX in [worker_threads.py:555](vscode-file://vscode-app/c:/Users/BartD/AppData/Local/Programs/Microsoft VS Code/f6cfa2ea24/resources/app/out/vs/code/electron-browser/workbench/workbench.html).
- Effect: if requested focal point is not exactly window center, Radon panels are phase-centered at the wrong origin.

So to your question "must there be errors in Python?":

- Yes, very likely at least one true bug exists (focal recentering mismatch).
- The rest are also major implementation mismatches versus MATLAB (not just cosmetics), and they fully explain why the six Python CFP panels do not match the MATLAB reference look.

I did not modify any MATLAB script.

Completed: *Trace Python pipeline for errors* (2/3)

GPT-5.3-Codex • 0.9x
