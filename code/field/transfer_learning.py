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
import argparse
import copy
import json
from pathlib import Path
from typing import Dict, Tuple
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from scipy.stats import pearsonr
from sklearn.metrics import r2_score
from torch.utils.data import DataLoader, TensorDataset


SCRIPT_DIR = Path(__file__).resolve().parent
_TRAIN_DIR = REPO_ROOT / "code" / "train"
if str(_TRAIN_DIR) not in sys.path:
    sys.path.insert(0, str(_TRAIN_DIR))

from attention_module import ModelM4_PhysicsPure  # type: ignore
from train_m4_physics_combined import CombinedLoss  # type: ignore


def set_seed(seed: int) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_hyperparams() -> Dict[str, object]:
    hp_file = hyperparams_path()
    if hp_file.exists():
        payload = json.loads(hp_file.read_text(encoding="utf-8"))
        return payload.get("best_hyperparameters", payload)
    tr_file = REPO_ROOT / "checkpoints" / "M4_Combined_field_pretrain" / "training_results.json"
    if tr_file.exists():
        payload = json.loads(tr_file.read_text(encoding="utf-8"))
        mp = payload.get("model_params", {})
        if mp:
            return {
                "hidden_dim": int(mp.get("hidden_dim", 128)),
                "num_layers": int(mp.get("num_layers", 3)),
                "dropout": float(mp.get("dropout", 0.3)),
                "bidirectional": bool(mp.get("bidirectional", False)),
            }
    return {"hidden_dim": 128, "num_layers": 3, "dropout": 0.3, "bidirectional": False}


def build_model(device: torch.device) -> nn.Module:
    hp = load_hyperparams()
    return ModelM4_PhysicsPure(
        input_dim=3,
        hidden_dim=int(hp["hidden_dim"]),
        num_layers=int(hp["num_layers"]),
        output_dim=1,
        dropout=float(hp["dropout"]),
        bidirectional=bool(hp["bidirectional"]),
    ).to(device)


def maybe_load_pretrained(model: nn.Module, pretrained_path: Path) -> bool:
    if not pretrained_path.exists():
        return False
    state = torch.load(pretrained_path, map_location="cpu")
    model.load_state_dict(state, strict=True)
    return True


def compute_peak_indices(batch_x: torch.Tensor) -> torch.Tensor:
    return torch.argmax(torch.abs(batch_x[:, :, 0]), dim=1).long()


def train_model(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: optim.Optimizer,
    device: torch.device,
    max_epochs: int,
    patience: int,
    min_delta: float = 1e-6,
) -> Tuple[nn.Module, list]:
    best_state = copy.deepcopy(model.state_dict())
    best_loss = np.inf
    wait = 0
    history = []
    for _ in range(max_epochs):
        model.train()
        running = 0.0
        for bx, by in loader:
            bx, by = bx.to(device), by.to(device)
            optimizer.zero_grad()
            pred = model(bx, peak_indices=compute_peak_indices(bx))
            loss = criterion(pred, by)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            running += float(loss.item())
        train_loss = running / max(1, len(loader))
        history.append(train_loss)
        if train_loss < best_loss - min_delta:
            best_loss = train_loss
            best_state = copy.deepcopy(model.state_dict())
            wait = 0
        else:
            wait += 1
            if wait >= patience:
                break
    model.load_state_dict(best_state)
    return model, history


@torch.no_grad()
def predict(model: nn.Module, x: np.ndarray, device: torch.device) -> np.ndarray:
    model.eval()
    xt = torch.from_numpy(x).float().to(device)
    return model(xt, peak_indices=compute_peak_indices(xt)).cpu().numpy()


def inverse_transform(y_norm: np.ndarray, y_mean: np.ndarray, y_std: np.ndarray) -> np.ndarray:
    return y_norm * y_std + y_mean


def evaluate_metrics(y_true_m: np.ndarray, y_pred_m: np.ndarray) -> Dict[str, float]:
    yt = y_true_m.reshape(-1)
    yp = y_pred_m.reshape(-1)
    err = yp - yt
    rmse_m = float(np.sqrt(np.mean(err**2)))
    mae_m = float(np.mean(np.abs(err)))
    r2 = float(r2_score(yt, yp))
    ci = float(pearsonr(yt, yp)[0]) if len(yt) > 1 else 0.0
    peak_true_mm = np.max(np.abs(y_true_m), axis=1).reshape(-1) * 1000.0
    peak_pred_mm = np.max(np.abs(y_pred_m), axis=1).reshape(-1) * 1000.0
    peak_rmse_mm = float(np.sqrt(np.mean((peak_pred_mm - peak_true_mm) ** 2)))
    return {
        "RMSE_mm": rmse_m * 1000.0,
        "MAE_mm": mae_m * 1000.0,
        "R2": r2,
        "CI": ci,
        "Peak_RMSE_mm": peak_rmse_mm,
    }


def freeze_for_finetune(model: nn.Module) -> None:
    for p in model.parameters():
        p.requires_grad = False
    # M4 has no CNN module; encoder stays frozen naturally.
    if hasattr(model, "decoder"):
        for p in model.decoder.parameters():
            p.requires_grad = True
    if hasattr(model, "attn_fc"):
        for p in model.attn_fc.parameters():
            p.requires_grad = True
    if hasattr(model, "query_fc"):
        for p in model.query_fc.parameters():
            p.requires_grad = True
    if hasattr(model, "delta_predictor"):
        for p in model.delta_predictor.parameters():
            p.requires_grad = True
    if hasattr(model, "phys_scale"):
        model.phys_scale.requires_grad = True
    if hasattr(model, "phys_bias"):
        model.phys_bias.requires_grad = True


def print_metrics_table(rows: Dict[str, Dict[str, float]]) -> None:
    headers = ["Group", "RMSE(mm)", "MAE(mm)", "R2", "CI", "Peak RMSE(mm)"]
    print("\n" + "=" * 86)
    print(f"{headers[0]:<26}{headers[1]:>12}{headers[2]:>12}{headers[3]:>10}{headers[4]:>10}{headers[5]:>16}")
    print("-" * 86)
    for k, m in rows.items():
        print(
            f"{k:<26}{m['RMSE_mm']:>12.3f}{m['MAE_mm']:>12.3f}{m['R2']:>10.4f}{m['CI']:>10.4f}{m['Peak_RMSE_mm']:>16.3f}"
        )
    print("=" * 86)


def plot_results(y_true_m: np.ndarray, y1_m: np.ndarray, y2_m: np.ndarray, y3_m: np.ndarray, dt: float, out_png: Path, out_pdf: Path) -> None:
    """Paper Fig. 12 style: single-column (~3.5 in) for typical SCI/ASCE layouts."""
    y_true = y_true_m[0, :, 0] * 1000.0
    g1 = y1_m[0, :, 0] * 1000.0
    g2 = y2_m[0, :, 0] * 1000.0
    g3 = y3_m[0, :, 0] * 1000.0
    t = np.arange(len(y_true)) * dt
    sci_w_in = 3.5
    sci_h_in = 2.75 / 2.0  # half height vs earlier SCI draft; width unchanged
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
    ax.plot(t, y_true, color="black", linewidth=1.05, label="CESMD ref. (ch.7)")
    ax.plot(t, g1, color="#8c8c8c", linestyle="--", linewidth=0.85, label="G1 scratch")
    ax.plot(t, g2, color="#1f77b4", linewidth=0.9, label="G2 zero-shot")
    ax.plot(t, g3, color="#d62728", linewidth=1.05, label="G3 pretrain+FT")
    ax.set_xlim(0, 40)
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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data_npz",
        type=str,
        default=str(REPO_ROOT / "data" / "field" / "transfer_dataset_v1.npz"),
    )
    parser.add_argument(
        "--pretrained_path",
        type=str,
        default=str(REPO_ROOT / "checkpoints" / "M4_Combined_field_pretrain" / "best_model.pth"),
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs_scratch", type=int, default=160)
    parser.add_argument("--epochs_finetune", type=int, default=80)
    parser.add_argument("--patience_scratch", type=int, default=25)
    parser.add_argument("--patience_finetune", type=int, default=20)
    parser.add_argument("--batch_size", type=int, default=1)
    args = parser.parse_args()

    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    out_dir = SCRIPT_DIR / "results_transfer_learning"
    out_dir.mkdir(parents=True, exist_ok=True)

    data = np.load(args.data_npz, allow_pickle=True)
    X_train = data["X_train"].astype(np.float32)
    Y_train = data["Y_train"].astype(np.float32)
    X_test = data["X_test"].astype(np.float32)
    Y_test = data["Y_test"].astype(np.float32)
    y_mean = data["y_mean"].astype(np.float32)
    y_std = data["y_std"].astype(np.float32)

    train_loader = DataLoader(TensorDataset(torch.from_numpy(X_train), torch.from_numpy(Y_train)), batch_size=args.batch_size, shuffle=True)
    criterion = CombinedLoss(mse_weight=1.0, peak_weight=2.0, gradient_weight=1.5, correlation_weight=3.0, peak_threshold=0.7)

    pretrained_path = Path(args.pretrained_path)
    print(f"Pretrained path: {pretrained_path}")

    # Group 1
    g1 = build_model(device)
    g1, hist1 = train_model(g1, train_loader, criterion, optim.Adam(g1.parameters(), lr=1e-3), device, args.epochs_scratch, args.patience_scratch)
    y1_pred_n = predict(g1, X_test, device)

    # Group 2
    g2 = build_model(device)
    loaded_g2 = maybe_load_pretrained(g2, pretrained_path)
    print(f"Group2 pretrained loaded: {loaded_g2}")
    y2_pred_n = predict(g2, X_test, device)

    # Group 3
    g3 = build_model(device)
    loaded_g3 = maybe_load_pretrained(g3, pretrained_path)
    print(f"Group3 pretrained loaded: {loaded_g3}")
    freeze_for_finetune(g3)
    print(f"Group3 trainable params after freezing: {sum(p.numel() for p in g3.parameters() if p.requires_grad):,}")
    g3, hist3 = train_model(
        g3,
        train_loader,
        criterion,
        optim.Adam([p for p in g3.parameters() if p.requires_grad], lr=5e-5),
        device,
        args.epochs_finetune,
        args.patience_finetune,
    )
    y3_pred_n = predict(g3, X_test, device)

    y_true_m = inverse_transform(Y_test, y_mean, y_std)
    y1_m = inverse_transform(y1_pred_n, y_mean, y_std)
    y2_m = inverse_transform(y2_pred_n, y_mean, y_std)
    y3_m = inverse_transform(y3_pred_n, y_mean, y_std)

    m1 = evaluate_metrics(y_true_m, y1_m)
    m2 = evaluate_metrics(y_true_m, y2_m)
    m3 = evaluate_metrics(y_true_m, y3_m)
    metrics = {"Group 1 (Scratch)": m1, "Group 2 (Zero-shot)": m2, "Group 3 (Pretrain+FT)": m3}
    print_metrics_table(metrics)

    fig_png = out_dir / "fig_transfer_timeseries_compare.png"
    fig_pdf = out_dir / "fig_transfer_timeseries_compare.pdf"
    plot_results(y_true_m, y1_m, y2_m, y3_m, dt=0.02, out_png=fig_png, out_pdf=fig_pdf)

    np.save(out_dir / "y_test_true_m.npy", y_true_m)
    np.save(out_dir / "y_pred_group1_m.npy", y1_m)
    np.save(out_dir / "y_pred_group2_m.npy", y2_m)
    np.save(out_dir / "y_pred_group3_m.npy", y3_m)
    with open(out_dir / "transfer_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    with open(out_dir / "training_history.json", "w", encoding="utf-8") as f:
        json.dump({"group1_train_loss": hist1, "group3_train_loss": hist3}, f, indent=2, ensure_ascii=False)

    print(f"\nSaved figure: {fig_png}")
    print(f"Saved metrics: {out_dir / 'transfer_metrics.json'}")


if __name__ == "__main__":
    main()

