# CPENG-8450 — Public release package

Accompanying materials for:

> Peak-Aware Residual Learning with Integrated Kinematic Priors for Predicting Bridge Mid-Span Displacement from Ground-Motion Accelerations  
> *ASCE Journal of Computing in Civil Engineering* (CPENG-8450)

This folder is a **clean release slice**. It does **not** include manuscript Word/PDF files, reviewer correspondence, or internal working notes.

## Contents

| Path | Description |
|------|-------------|
| `code/models/attention_module.py` | M1–M4 model definitions |
| `code/train/` | Training entry points for M1, M2, M3 (k=5/k=3), M4-MSE, M4-Combined |
| `code/field/` | Field transfer / stability scripts |
| `code/data_prep/` | Dataset preparation and augmentation helpers |
| `code/paths.py` | Relative-path helpers (no machine-specific drives) |
| `checkpoints/` | Paper weights + `training_results.json` |
| `data/numerical/data_augmented/` | Numerical train (240) / test (300) splits |
| `data/field/transfer_dataset_v1.npz` | Prepared CESMD transfer set (4 train windows + 1 test) |
| `data/inventory/r2_32_ground_motions.csv` | 32-record PEER inventory (Table 2) |
| `configs/best_hyperparameters.json` | Shared backbone hyperparameters |
| `opensees/example_A-ELC_0p10g/` | Representative Ex4 OpenSees case used for §3.1 parameters |

## Checkpoint map (paper Table 5)

| Paper model | Folder |
|-------------|--------|
| M1 | `checkpoints/M1` |
| M2 | `checkpoints/M2` |
| M3 (k=5) | `checkpoints/M3_k5` ← use this residual checkpoint |
| M3 (k=3) | `checkpoints/M3_k3` |
| M4-MSE (3 seeds) | `checkpoints/M4_MSE_seed{1,2,3}` |
| M4-Combined (3 seeds) | `checkpoints/M4_Combined_seed{1,2,3}` |
| Field pretrain weight | `checkpoints/M4_Combined_field_pretrain` (independent fourth run; used by field scripts) |

Verified from packaged JSON (test Peak RMSE for M4-Combined seeds): 5.779 / 5.259 / 5.615 mm → mean **5.551 mm** (matches the paper).

## Quick start

```bash
pip install -r requirements.txt
# optional overrides:
# set CPENG_DATA_DIR=...  CPENG_HYPERPARAMS=...  CPENG_FIELD_NPZ=...
```

Evaluate packaged weights with your own loader, or retrain, for example:

```bash
python code/train/train_m4_physics_combined.py --seed 1
```

Field scripts default to `data/field/transfer_dataset_v1.npz` and `checkpoints/M4_Combined_field_pretrain/best_model.pth`.

## Notes

1. **M3 (k=5)** paper numbers come from the residual checkpoint in `checkpoints/M3_k5`. Do not confuse with any older non-residual run.
2. **M3 (k=3)** historically had no separate train file in the working repo; this release adds `code/train/train_m3_cnn_attention_residual_k3.py` using `CNNAttnLSTM_Residual_Version_K3`.
3. OpenSees materials here are a **representative case** for reproducibility of §3.1 parameters. Full motion-suite case trees are large; regenerating the full numerical corpus requires the Ex4 motion set and OpenSees workflow described in the paper.
4. Raw CESMD waveforms are not redistributed; users should obtain station 89324 records from CESMD and/or use the prepared `transfer_dataset_v1.npz`.

## What was intentionally excluded

- Manuscript / response-to-reviewers / editorial emails
- Internal audit notes and agent chat logs
- Unrelated ablation branches (Mamba, exploratory folders)
- The non-paper `ContinuousGirderBridge4Span` example model

## Citation

Please cite the published ASCE paper (CPENG-8450). Update this README with the Zenodo DOI after deposit.
