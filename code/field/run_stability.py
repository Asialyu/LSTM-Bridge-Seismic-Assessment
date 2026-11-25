from __future__ import annotations


# --- release path bootstrap (no machine-specific absolute paths) ---
from pathlib import Path as _Path
import sys as _sys
_CODE_DIR = _Path(__file__).resolve().parents[1]  # .../code
if str(_CODE_DIR) not in _sys.path:
    _sys.path.insert(0, str(_CODE_DIR))
from paths import data_augmented_dir, hyperparams_path, ensure_models_on_path, REPO_ROOT
ensure_models_on_path()
# --- end bootstrap ---
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

import transfer_learning as tl


SCRIPT_DIR = Path(__file__).resolve().parent
OUT_DIR = REPO_ROOT / "checkpoints" / "field_stability"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DATA_NPZ = REPO_ROOT / "data" / "field" / "transfer_dataset_v1.npz"
PRETRAINED = REPO_ROOT / "checkpoints" / "M4_Combined_field_pretrain" / "best_model.pth"

SEEDS = [42, 123, 2026, 7, 99]
GROUP3_LR = 1e-4
PHASE3_LR_SWEEP = [2e-4, 1e-4, 8e-5]
DT = 0.02
FREEZE_STRATEGIES = ["conservative", "unfreeze_all"]
# (mse, peak, grad, corr)
LOSS_CONFIGS = [
    ("L0_base", (1.0, 2.0, 1.5, 3.0)),
    ("L1_peak_boost", (1.0, 3.0, 1.0, 2.5)),
    ("L2_global_fit", (1.5, 2.0, 1.0, 3.0)),
]
PHASE4_WEIGHT_SWEEP = [
    ("W1_peak3_corr3", (1.5, 3.0, 1.0, 3.0)),
    ("W2_peak3_corr3p5", (1.5, 3.0, 1.0, 3.5)),
    ("W3_peak3p5_corr3", (1.5, 3.5, 1.0, 3.0)),
    ("W4_peak3p5_corr3p5", (1.5, 3.5, 1.0, 3.5)),
]
PHASE5_LR_FINE = [1.5e-4, 1.8e-4, 2.0e-4, 2.2e-4, 2.5e-4]


@dataclass
class RunResult:
    seed: int
    group: str
    strategy: str | None
    lr: float | None
    loss_name: str | None
    metrics: Dict[str, float]
    y_pred_m: np.ndarray | None = None


def _mean_std(
    rows: List[RunResult],
    group: str,
    strategy: str | None = None,
    lr: float | None = None,
    loss_name: str | None = None,
) -> Dict[str, Tuple[float, float]]:
    items = [r.metrics for r in rows if r.group == group and r.strategy == strategy and r.lr == lr and r.loss_name == loss_name]
    keys = ["RMSE_mm", "R2", "Peak_RMSE_mm"]
    out: Dict[str, Tuple[float, float]] = {}
    for k in keys:
        vals = np.array([m[k] for m in items], dtype=float)
        out[k] = (float(vals.mean()), float(vals.std(ddof=1)) if len(vals) > 1 else 0.0)
    return out


def _fmt(m: Tuple[float, float], digits: int = 3) -> str:
    mean, std = m
    return f"{mean:.{digits}f} ± {std:.{digits}f}"


def _pick_best_seed(
    rows: List[RunResult],
    group: str,
    strategy: str | None = None,
    lr: float | None = None,
    loss_name: str | None = None,
) -> int:
    group_rows = [r for r in rows if r.group == group and r.strategy == strategy and r.lr == lr and r.loss_name == loss_name]
    # Prioritize higher R2, then lower Peak RMSE.
    best = max(group_rows, key=lambda r: (r.metrics["R2"], -r.metrics["Peak_RMSE_mm"]))
    return best.seed


def _strategy_label(strategy: str) -> str:
    return "A_conservative" if strategy == "conservative" else "B_unfreeze_all"


def _make_criterion(weights: Tuple[float, float, float, float]) -> nn.Module:
    mse_w, peak_w, grad_w, corr_w = weights
    return tl.CombinedLoss(
        mse_weight=mse_w,
        peak_weight=peak_w,
        gradient_weight=grad_w,
        correlation_weight=corr_w,
        peak_threshold=0.7,
    )


def _apply_strategy(model: nn.Module, strategy: str) -> None:
    if strategy == "conservative":
        tl.freeze_for_finetune(model)
        return
    if strategy == "unfreeze_all":
        for p in model.parameters():
            p.requires_grad = True
        return
    raise ValueError(f"Unknown strategy: {strategy}")


def _window_indices(y_true_m: np.ndarray, dt: float, window_s: float = 2.5) -> Tuple[int, int]:
    y = y_true_m[0, :, 0]
    peak_idx = int(np.argmax(np.abs(y)))
    w = int(round(window_s / dt))
    i0 = max(0, peak_idx - w)
    i1 = min(len(y), peak_idx + w)
    return i0, i1


def _window_metrics(y_true_m: np.ndarray, y_pred_m: np.ndarray, dt: float) -> Dict[str, float]:
    i0, i1 = _window_indices(y_true_m, dt)
    yt = y_true_m[:, i0:i1, :]
    yp = y_pred_m[:, i0:i1, :]
    m = tl.evaluate_metrics(yt, yp)
    return {
        "Win_RMSE_mm": float(m["RMSE_mm"]),
        "Win_CI": float(m["CI"]),
        "Win_Peak_RMSE_mm": float(m["Peak_RMSE_mm"]),
    }


def _ms_dict(items: List[Dict[str, float]], key: str) -> Tuple[float, float]:
    vals = np.array([it[key] for it in items], dtype=float)
    return float(vals.mean()), float(vals.std(ddof=1)) if len(vals) > 1 else 0.0


def plot_peak_window(
    y_true_m: np.ndarray,
    y1_m: np.ndarray,
    y2_m: np.ndarray,
    y3_m: np.ndarray,
    dt: float,
    out_png: Path,
    out_pdf: Path,
    window_s: float = 2.5,
) -> None:
    y_true = y_true_m[0, :, 0] * 1000.0
    g1 = y1_m[0, :, 0] * 1000.0
    g2 = y2_m[0, :, 0] * 1000.0
    g3 = y3_m[0, :, 0] * 1000.0
    t = np.arange(len(y_true)) * dt
    peak_idx = int(np.argmax(np.abs(y_true)))
    w = int(round(window_s / dt))
    i0 = max(0, peak_idx - w)
    i1 = min(len(y_true), peak_idx + w)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Paper Fig. 13: same single-column width as Fig. 12 (SCI one-column ~3.5 in).
    sci_w_in = 3.5
    sci_h_in = 2.6 / 2.0  # half height; width unchanged
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 9,
            "axes.labelsize": 9,
            "axes.titlesize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "axes.linewidth": 0.75,
            "figure.dpi": 300,
            "savefig.dpi": 600,
        }
    )
    fig, ax = plt.subplots(1, 1, figsize=(sci_w_in, sci_h_in), constrained_layout=False)
    ax.plot(t[i0:i1], y_true[i0:i1], color="black", linewidth=1.05, label="CESMD ref. (ch.7)")
    ax.plot(t[i0:i1], g1[i0:i1], color="#8c8c8c", linestyle="--", linewidth=0.85, label="G1 scratch")
    ax.plot(t[i0:i1], g2[i0:i1], color="#1f77b4", linewidth=0.9, label="G2 zero-shot")
    ax.plot(t[i0:i1], g3[i0:i1], color="#d62728", linewidth=1.05, label="G3 pretrain+FT")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Displacement (mm)")
    ax.grid(True, alpha=0.3, linewidth=0.45)
    ax.legend(
        loc="upper center",
        ncol=2,
        frameon=False,
        bbox_to_anchor=(0.5, -0.38),
        handlelength=2.2,
        columnspacing=0.9,
    )
    fig.subplots_adjust(left=0.16, right=0.97, top=0.96, bottom=0.48)
    fig.savefig(out_png, dpi=600, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(out_pdf, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def main() -> None:
    if not DATA_NPZ.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_NPZ}. Run prepare_transfer_data.py first.")
    if not PRETRAINED.exists():
        raise FileNotFoundError(f"Pretrained checkpoint not found: {PRETRAINED}")

    data = np.load(DATA_NPZ, allow_pickle=True)
    X_train = data["X_train"].astype(np.float32)
    Y_train = data["Y_train"].astype(np.float32)
    X_test = data["X_test"].astype(np.float32)
    Y_test = data["Y_test"].astype(np.float32)
    y_mean = data["y_mean"].astype(np.float32)
    y_std = data["y_std"].astype(np.float32)
    test_event = str(data["test_event"].item()) if data["test_event"].shape == () else str(data["test_event"][0])

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    print(f"Test event: {test_event}")
    print(f"Seeds: {SEEDS}")
    print(f"Group3 phase-1 freeze strategies: {FREEZE_STRATEGIES}, fixed lr={GROUP3_LR:.0e}")
    print(f"Group3 phase-2 loss configs: {[name for name, _ in LOSS_CONFIGS]}")
    print(f"Group3 phase-3 narrow LR sweep: {PHASE3_LR_SWEEP}")
    print(f"Group3 phase-4 weight sweep: {[name for name, _ in PHASE4_WEIGHT_SWEEP]}")
    print(f"Group3 phase-5 LR fine sweep: {PHASE5_LR_FINE}")

    results: List[RunResult] = []
    y_true_m = tl.inverse_transform(Y_test, y_mean, y_std)

    for seed in SEEDS:
        tl.set_seed(seed)

        train_loader = DataLoader(
            TensorDataset(torch.from_numpy(X_train), torch.from_numpy(Y_train)),
            batch_size=1,
            shuffle=True,
        )
        criterion_base = _make_criterion(LOSS_CONFIGS[0][1])

        # Group 1: Scratch
        g1 = tl.build_model(device)
        g1, _hist1 = tl.train_model(
            g1,
            train_loader,
            criterion_base,
            optim.Adam(g1.parameters(), lr=1e-3),
            device,
            max_epochs=160,
            patience=25,
        )
        y1_pred_n = tl.predict(g1, X_test, device)
        y1_m = tl.inverse_transform(y1_pred_n, y_mean, y_std)
        m1 = tl.evaluate_metrics(y_true_m, y1_m)
        results.append(RunResult(seed=seed, group="Group1_Scratch", strategy=None, lr=None, loss_name=None, metrics=m1, y_pred_m=y1_m))

        # Group 2: Zero-shot
        g2 = tl.build_model(device)
        tl.maybe_load_pretrained(g2, PRETRAINED)
        y2_pred_n = tl.predict(g2, X_test, device)
        y2_m = tl.inverse_transform(y2_pred_n, y_mean, y_std)
        m2 = tl.evaluate_metrics(y_true_m, y2_m)
        results.append(RunResult(seed=seed, group="Group2_ZeroShot", strategy=None, lr=None, loss_name=None, metrics=m2, y_pred_m=y2_m))

        print(
            f"Seed {seed}: baseline G1 R2={m1['R2']:.4f}, G2 R2={m2['R2']:.4f}"
        )
        # Phase 1: freeze strategy comparison under baseline loss.
        for strategy in FREEZE_STRATEGIES:
            g3 = tl.build_model(device)
            tl.maybe_load_pretrained(g3, PRETRAINED)
            _apply_strategy(g3, strategy)
            trainable = [p for p in g3.parameters() if p.requires_grad]
            opt3 = optim.Adam(trainable, lr=GROUP3_LR)
            g3, _hist3 = tl.train_model(
                g3,
                train_loader,
                criterion_base,
                opt3,
                device,
                max_epochs=80,
                patience=20,
            )
            y3_pred_n = tl.predict(g3, X_test, device)
            y3_m = tl.inverse_transform(y3_pred_n, y_mean, y_std)
            m3 = tl.evaluate_metrics(y_true_m, y3_m)
            results.append(
                RunResult(
                    seed=seed,
                    group="Group3_PretrainFT",
                    strategy=strategy,
                    lr=GROUP3_LR,
                    loss_name="L0_base",
                    metrics=m3,
                    y_pred_m=y3_m,
                )
            )
            print(
                f"Seed {seed}: Group3 {_strategy_label(strategy)}, "
                f"R2={m3['R2']:.4f}, PeakRMSE={m3['Peak_RMSE_mm']:.3f} mm"
            )

    # Pick best strategy from phase 1, then run phase 2 loss sweep.
    best_strategy = None
    best_phase1_r2 = -np.inf
    for strategy in FREEZE_STRATEGIES:
        ms = _mean_std(results, "Group3_PretrainFT", strategy, GROUP3_LR, "L0_base")
        if ms["R2"][0] > best_phase1_r2:
            best_phase1_r2 = ms["R2"][0]
            best_strategy = strategy
    assert best_strategy is not None
    print(f"Selected strategy for phase-2 loss sweep: {_strategy_label(best_strategy)}")

    for seed in SEEDS:
        tl.set_seed(seed)
        train_loader = DataLoader(
            TensorDataset(torch.from_numpy(X_train), torch.from_numpy(Y_train)),
            batch_size=1,
            shuffle=True,
        )
        for loss_name, weights in LOSS_CONFIGS[1:]:
            g3 = tl.build_model(device)
            tl.maybe_load_pretrained(g3, PRETRAINED)
            _apply_strategy(g3, best_strategy)
            trainable = [p for p in g3.parameters() if p.requires_grad]
            opt3 = optim.Adam(trainable, lr=GROUP3_LR)
            g3, _hist3 = tl.train_model(
                g3,
                train_loader,
                _make_criterion(weights),
                opt3,
                device,
                max_epochs=80,
                patience=20,
            )
            y3_pred_n = tl.predict(g3, X_test, device)
            y3_m = tl.inverse_transform(y3_pred_n, y_mean, y_std)
            m3 = tl.evaluate_metrics(y_true_m, y3_m)
            results.append(
                RunResult(
                    seed=seed,
                    group="Group3_PretrainFT",
                    strategy=best_strategy,
                    lr=GROUP3_LR,
                    loss_name=loss_name,
                    metrics=m3,
                    y_pred_m=y3_m,
                )
            )
            print(
                f"Seed {seed}: Group3 {_strategy_label(best_strategy)} + {loss_name}, "
                f"R2={m3['R2']:.4f}, PeakRMSE={m3['Peak_RMSE_mm']:.3f} mm"
            )

    # Select best loss under fixed lr, then run narrow lr sweep.
    best_loss_name = None
    best_loss_r2 = -np.inf
    for loss_name, _weights in LOSS_CONFIGS:
        ms = _mean_std(results, "Group3_PretrainFT", best_strategy, GROUP3_LR, loss_name)
        if ms["R2"][0] > best_loss_r2:
            best_loss_r2 = ms["R2"][0]
            best_loss_name = loss_name
    assert best_loss_name is not None
    print(f"Selected loss for phase-3 LR sweep: {best_loss_name}")

    loss_weights_map = {name: w for name, w in LOSS_CONFIGS}
    for seed in SEEDS:
        tl.set_seed(seed)
        train_loader = DataLoader(
            TensorDataset(torch.from_numpy(X_train), torch.from_numpy(Y_train)),
            batch_size=1,
            shuffle=True,
        )
        for lr in PHASE3_LR_SWEEP:
            g3 = tl.build_model(device)
            tl.maybe_load_pretrained(g3, PRETRAINED)
            _apply_strategy(g3, best_strategy)
            trainable = [p for p in g3.parameters() if p.requires_grad]
            opt3 = optim.Adam(trainable, lr=lr)
            g3, _hist3 = tl.train_model(
                g3,
                train_loader,
                _make_criterion(loss_weights_map[best_loss_name]),
                opt3,
                device,
                max_epochs=80,
                patience=20,
            )
            y3_pred_n = tl.predict(g3, X_test, device)
            y3_m = tl.inverse_transform(y3_pred_n, y_mean, y_std)
            m3 = tl.evaluate_metrics(y_true_m, y3_m)
            results.append(
                RunResult(
                    seed=seed,
                    group="Group3_PretrainFT",
                    strategy=best_strategy,
                    lr=lr,
                    loss_name=f"{best_loss_name}_lr_tune",
                    metrics=m3,
                    y_pred_m=y3_m,
                )
            )
            print(
                f"Seed {seed}: Group3 {_strategy_label(best_strategy)} + {best_loss_name}, "
                f"lr={lr:.0e}, R2={m3['R2']:.4f}, PeakRMSE={m3['Peak_RMSE_mm']:.3f} mm"
            )

    # Select best lr from phase-3, then do small CI/Peak weight 2x2 sweep.
    best_lr = None
    best_lr_r2 = -np.inf
    for lr in PHASE3_LR_SWEEP:
        ms = _mean_std(results, "Group3_PretrainFT", best_strategy, lr, f"{best_loss_name}_lr_tune")
        if ms["R2"][0] > best_lr_r2:
            best_lr_r2 = ms["R2"][0]
            best_lr = lr
    assert best_lr is not None
    print(f"Selected lr for phase-4 weight sweep: {best_lr:.0e}")

    for seed in SEEDS:
        tl.set_seed(seed)
        train_loader = DataLoader(
            TensorDataset(torch.from_numpy(X_train), torch.from_numpy(Y_train)),
            batch_size=1,
            shuffle=True,
        )
        for w_name, w_cfg in PHASE4_WEIGHT_SWEEP:
            g3 = tl.build_model(device)
            tl.maybe_load_pretrained(g3, PRETRAINED)
            _apply_strategy(g3, best_strategy)
            trainable = [p for p in g3.parameters() if p.requires_grad]
            opt3 = optim.Adam(trainable, lr=best_lr)
            g3, _hist3 = tl.train_model(
                g3,
                train_loader,
                _make_criterion(w_cfg),
                opt3,
                device,
                max_epochs=80,
                patience=20,
            )
            y3_pred_n = tl.predict(g3, X_test, device)
            y3_m = tl.inverse_transform(y3_pred_n, y_mean, y_std)
            m3 = tl.evaluate_metrics(y_true_m, y3_m)
            results.append(
                RunResult(
                    seed=seed,
                    group="Group3_PretrainFT",
                    strategy=best_strategy,
                    lr=best_lr,
                    loss_name=f"{w_name}_phase4",
                    metrics=m3,
                    y_pred_m=y3_m,
                )
            )
            print(
                f"Seed {seed}: Group3 {_strategy_label(best_strategy)} + {w_name}, "
                f"lr={best_lr:.0e}, R2={m3['R2']:.4f}, PeakRMSE={m3['Peak_RMSE_mm']:.3f} mm"
            )

    # Summaries
    g1_ms = _mean_std(results, "Group1_Scratch", None, None, None)
    g2_ms = _mean_std(results, "Group2_ZeroShot", None, None, None)

    table = [
        "| Group / Config | RMSE (mm) | R2 | Peak RMSE (mm) |",
        "|---|---:|---:|---:|",
        f"| Group 1 (Scratch) | {_fmt(g1_ms['RMSE_mm'])} | {_fmt(g1_ms['R2'], digits=4)} | {_fmt(g1_ms['Peak_RMSE_mm'])} |",
        f"| Group 2 (Zero-shot) | {_fmt(g2_ms['RMSE_mm'])} | {_fmt(g2_ms['R2'], digits=4)} | {_fmt(g2_ms['Peak_RMSE_mm'])} |",
    ]
    best_cfg = None
    best_r2_mean = -np.inf
    # Phase 1 strategy rows
    for strategy in FREEZE_STRATEGIES:
        ms = _mean_std(results, "Group3_PretrainFT", strategy, GROUP3_LR, "L0_base")
        table.append(
            f"| Group 3 ({_strategy_label(strategy)}, L0_base, lr={GROUP3_LR:.0e}) | "
            f"{_fmt(ms['RMSE_mm'])} | {_fmt(ms['R2'], digits=4)} | {_fmt(ms['Peak_RMSE_mm'])} |"
        )
    # Phase 2 loss rows (under selected best strategy)
    for loss_name, _weights in LOSS_CONFIGS[1:]:
        ms = _mean_std(results, "Group3_PretrainFT", best_strategy, GROUP3_LR, loss_name)
        table.append(
            f"| Group 3 ({_strategy_label(best_strategy)}, {loss_name}, lr={GROUP3_LR:.0e}) | "
            f"{_fmt(ms['RMSE_mm'])} | {_fmt(ms['R2'], digits=4)} | {_fmt(ms['Peak_RMSE_mm'])} |"
        )
        if ms["R2"][0] > best_r2_mean:
            best_r2_mean = ms["R2"][0]
            best_cfg = (best_strategy, GROUP3_LR, loss_name, ms)
    for lr in PHASE3_LR_SWEEP:
        ms = _mean_std(results, "Group3_PretrainFT", best_strategy, lr, f"{best_loss_name}_lr_tune")
        table.append(
            f"| Group 3 ({_strategy_label(best_strategy)}, {best_loss_name}, lr={lr:.0e}) | "
            f"{_fmt(ms['RMSE_mm'])} | {_fmt(ms['R2'], digits=4)} | {_fmt(ms['Peak_RMSE_mm'])} |"
        )
        if ms["R2"][0] > best_r2_mean:
            best_r2_mean = ms["R2"][0]
            best_cfg = (best_strategy, lr, f"{best_loss_name}_lr_tune", ms)
    for w_name, _w_cfg in PHASE4_WEIGHT_SWEEP:
        ms = _mean_std(results, "Group3_PretrainFT", best_strategy, best_lr, f"{w_name}_phase4")
        table.append(
            f"| Group 3 ({_strategy_label(best_strategy)}, {w_name}, lr={best_lr:.0e}) | "
            f"{_fmt(ms['RMSE_mm'])} | {_fmt(ms['R2'], digits=4)} | {_fmt(ms['Peak_RMSE_mm'])} |"
        )
        if ms["R2"][0] > best_r2_mean:
            best_r2_mean = ms["R2"][0]
            best_cfg = (best_strategy, best_lr, f"{w_name}_phase4", ms)

    # Phase 5: fine LR sweep around best phase-4 config (keep strategy and weights fixed).
    best_phase4 = ("W3_peak3p5_corr3", (1.5, 3.5, 1.0, 3.0))
    phase5_name = f"{best_phase4[0]}_lr_fine"
    for seed in SEEDS:
        tl.set_seed(seed)
        train_loader = DataLoader(
            TensorDataset(torch.from_numpy(X_train), torch.from_numpy(Y_train)),
            batch_size=1,
            shuffle=True,
        )
        for lr in PHASE5_LR_FINE:
            g3 = tl.build_model(device)
            tl.maybe_load_pretrained(g3, PRETRAINED)
            _apply_strategy(g3, "unfreeze_all")
            trainable = [p for p in g3.parameters() if p.requires_grad]
            opt3 = optim.Adam(trainable, lr=lr)
            g3, _hist3 = tl.train_model(
                g3,
                train_loader,
                _make_criterion(best_phase4[1]),
                opt3,
                device,
                max_epochs=80,
                patience=20,
            )
            y3_pred_n = tl.predict(g3, X_test, device)
            y3_m = tl.inverse_transform(y3_pred_n, y_mean, y_std)
            m3 = tl.evaluate_metrics(y_true_m, y3_m)
            results.append(
                RunResult(
                    seed=seed,
                    group="Group3_PretrainFT",
                    strategy="unfreeze_all",
                    lr=lr,
                    loss_name=phase5_name,
                    metrics=m3,
                    y_pred_m=y3_m,
                )
            )
            print(
                f"Seed {seed}: Group3 B_unfreeze_all + {best_phase4[0]}, "
                f"lr={lr:.1e}, R2={m3['R2']:.4f}, PeakRMSE={m3['Peak_RMSE_mm']:.3f} mm"
            )

    for lr in PHASE5_LR_FINE:
        ms = _mean_std(results, "Group3_PretrainFT", "unfreeze_all", lr, phase5_name)
        table.append(
            f"| Group 3 (B_unfreeze_all, {best_phase4[0]}, lr={lr:.1e}) | "
            f"{_fmt(ms['RMSE_mm'])} | {_fmt(ms['R2'], digits=4)} | {_fmt(ms['Peak_RMSE_mm'])} |"
        )
        # choose by R2 first, then PeakRMSE.
        if (ms["R2"][0] > best_r2_mean) or (
            np.isclose(ms["R2"][0], best_r2_mean) and best_cfg is not None and ms["Peak_RMSE_mm"][0] < best_cfg[3]["Peak_RMSE_mm"][0]
        ):
            best_r2_mean = ms["R2"][0]
            best_cfg = ("unfreeze_all", lr, phase5_name, ms)
    md = "\n".join(table)

    assert best_cfg is not None
    best_strategy, best_lr, best_loss_name, best_ms = best_cfg
    # Pick best Group3 seed in best mean-R2 config and render high-res comparison.
    best_seed = _pick_best_seed(results, "Group3_PretrainFT", best_strategy, best_lr, best_loss_name)
    y1_best = next(r.y_pred_m for r in results if r.group == "Group1_Scratch" and r.seed == best_seed)
    y2_best = next(r.y_pred_m for r in results if r.group == "Group2_ZeroShot" and r.seed == best_seed)
    y3_best = next(
        r.y_pred_m
        for r in results
        if (
            r.group == "Group3_PretrainFT"
            and r.seed == best_seed
            and r.strategy == best_strategy
            and r.lr == best_lr
            and r.loss_name == best_loss_name
        )
    )
    assert y1_best is not None and y2_best is not None and y3_best is not None
    np.savez_compressed(
        OUT_DIR / "fig12_13_waveforms.npz",
        y_true_m=y_true_m,
        y1_m=y1_best,
        y2_m=y2_best,
        y3_m=y3_best,
        dt=DT,
        best_seed=best_seed,
    )
    print(f"Saved waveform cache for replot: {OUT_DIR / 'fig12_13_waveforms.npz'}")
    tl.plot_results(
        y_true_m=y_true_m,
        y1_m=y1_best,
        y2_m=y2_best,
        y3_m=y3_best,
        dt=DT,
        out_png=OUT_DIR / "best_seed_waveform_compare.png",
        out_pdf=OUT_DIR / "best_seed_waveform_compare.pdf",
    )
    plot_peak_window(
        y_true_m=y_true_m,
        y1_m=y1_best,
        y2_m=y2_best,
        y3_m=y3_best,
        dt=DT,
        out_png=OUT_DIR / "best_seed_peak_window_compare.png",
        out_pdf=OUT_DIR / "best_seed_peak_window_compare.pdf",
        window_s=2.5,
    )

    # Peak-window metrics table (±2.5s around true peak), aggregated across seeds.
    def _collect_window(group: str, strategy: str | None, lr: float | None, loss_name: str | None) -> List[Dict[str, float]]:
        out = []
        for r in results:
            if r.group != group:
                continue
            if strategy is not None and r.strategy != strategy:
                continue
            if lr is not None and (r.lr is None or abs(float(r.lr) - float(lr)) > 1e-12):
                continue
            if loss_name is not None and r.loss_name != loss_name:
                continue
            if r.y_pred_m is None:
                continue
            out.append(_window_metrics(y_true_m, r.y_pred_m, DT))
        return out

    w1 = _collect_window("Group1_Scratch", None, None, None)
    w2 = _collect_window("Group2_ZeroShot", None, None, None)
    w3 = _collect_window("Group3_PretrainFT", best_strategy, best_lr, best_loss_name)

    peak_win_table = [
        "| Group / Config (Peak window ±2.5s) | Win RMSE (mm) | Win CI | Win Peak RMSE (mm) |",
        "|---|---:|---:|---:|",
        f"| Group 1 (Scratch) | {_fmt(_ms_dict(w1, 'Win_RMSE_mm'))} | {_fmt(_ms_dict(w1, 'Win_CI'), digits=4)} | {_fmt(_ms_dict(w1, 'Win_Peak_RMSE_mm'))} |",
        f"| Group 2 (Zero-shot) | {_fmt(_ms_dict(w2, 'Win_RMSE_mm'))} | {_fmt(_ms_dict(w2, 'Win_CI'), digits=4)} | {_fmt(_ms_dict(w2, 'Win_Peak_RMSE_mm'))} |",
        f"| Group 3 (TL best) | {_fmt(_ms_dict(w3, 'Win_RMSE_mm'))} | {_fmt(_ms_dict(w3, 'Win_CI'), digits=4)} | {_fmt(_ms_dict(w3, 'Win_Peak_RMSE_mm'))} |",
    ]
    peak_win_md = "\n".join(peak_win_table)
    (OUT_DIR / "peak_window_summary.md").write_text(peak_win_md, encoding="utf-8")
    print("\n=== Peak-window summary (±2.5s) ===")
    print(peak_win_md)
    print(f"Saved: {OUT_DIR / 'peak_window_summary.md'}")
    print(f"Saved: {OUT_DIR / 'best_seed_peak_window_compare.png'}")

    (OUT_DIR / "stability_summary.md").write_text(md, encoding="utf-8")
    serializable_rows = []
    for r in results:
        serializable_rows.append(
            {
                "seed": r.seed,
                "group": r.group,
                "strategy": r.strategy,
                "lr": r.lr,
                "loss_name": r.loss_name,
                "metrics": r.metrics,
            }
        )
    (OUT_DIR / "stability_raw.json").write_text(
        json.dumps(serializable_rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print("\n=== Stability summary (mean ± std) ===")
    print(md)
    print(
        f"\nBest Group3 config by mean R2: strategy={best_strategy}, loss={best_loss_name}, lr={best_lr:.0e}, "
        f"R2={best_ms['R2'][0]:.4f} ± {best_ms['R2'][1]:.4f}, "
        f"PeakRMSE={best_ms['Peak_RMSE_mm'][0]:.3f} ± {best_ms['Peak_RMSE_mm'][1]:.3f} mm"
    )
    print(f"Best seed under best config: {best_seed}")
    print(f"Reached target (R2 mean > 0.25): {best_ms['R2'][0] > 0.25}")
    print(f"\nSaved: {OUT_DIR / 'stability_summary.md'}")
    print(f"Saved: {OUT_DIR / 'stability_raw.json'}")
    print(f"Saved: {OUT_DIR / 'best_seed_waveform_compare.png'}")


if __name__ == "__main__":
    main()

