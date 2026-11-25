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
from pathlib import Path
from typing import Dict, Tuple
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import resample_poly

# Reuse parser implementation from stable workspace.
LEGACY_DIR = Path(r"d:\cursor_project\LSTM\ablation_experiments\新第五章-实例验证数据\20744789-1777128708P")
if str(LEGACY_DIR) not in sys.path:
    sys.path.append(str(LEGACY_DIR))
from parse_v2_file import parse_v2_file  # type: ignore


BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "prepared_transfer_data"
OUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_ROOT = BASE_DIR

# Third dataset split (4-shot + 1 test).
TEST_EVENT = "nc73201181_ce89324p"
TRAIN_EVENTS = [
    "nc73821046_ce89324p",
    "nc73943821_ce89324p",
    "nc73925281_ce89324p",
    "nc73947830_ce89324p",
]

TARGET_DT = 0.02
TARGET_LEN = 2000
PRE_SAMPLES = 500
POST_SAMPLES = 1500
PRIMARY_ACC_CHANNEL = "003"
PRIMARY_DISP_CHANNEL = "007"


def _resolve_event_dir(event_name: str) -> Path:
    direct = DATA_ROOT / event_name
    if direct.exists():
        return direct
    raise FileNotFoundError(f"Event folder not found for {event_name} under {DATA_ROOT}")


def _find_channel_file(event_dir: Path, channel: str) -> Path:
    candidates = [
        f"chan{channel}.v2",
        f"CHAN{channel}.V2",
        f"chan{channel}.V2",
        f"CHAN{channel}.v2",
    ]
    for name in candidates:
        p = event_dir / name
        if p.exists():
            return p
    for p in event_dir.iterdir():
        if p.is_file() and p.suffix.lower() == ".v2" and p.stem.lower() == f"chan{channel}":
            return p
    raise FileNotFoundError(f"Cannot find chan{channel}.v2 in {event_dir}")


def _resample_to_target_dt(sig: np.ndarray, old_dt: float, new_dt: float) -> np.ndarray:
    ratio = new_dt / old_dt
    if np.isclose(ratio, 2.0):
        return resample_poly(sig, up=1, down=2)
    inv = old_dt / new_dt
    if np.isclose(inv, round(inv)) and round(inv) > 0:
        return resample_poly(sig, up=int(round(inv)), down=1)
    if np.isclose(ratio, round(ratio)) and round(ratio) > 0:
        return resample_poly(sig, up=1, down=int(round(ratio)))
    return resample_poly(sig, up=1, down=2)


def _slice_around_peak_with_padding(acc: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray, int]:
    idx_peak = int(np.argmax(np.abs(acc)))
    start = idx_peak - PRE_SAMPLES
    end = idx_peak + POST_SAMPLES

    acc_out = np.zeros(TARGET_LEN, dtype=np.float64)
    y_out = np.zeros(TARGET_LEN, dtype=np.float64)
    src_start = max(0, start)
    src_end = min(len(acc), end)
    dst_start = src_start - start
    dst_end = dst_start + (src_end - src_start)
    if src_end > src_start:
        acc_out[dst_start:dst_end] = acc[src_start:src_end]
        y_out[dst_start:dst_end] = y[src_start:src_end]
    return acc_out, y_out, idx_peak


def _build_kinematic_priors(acc: np.ndarray, dt: float) -> Tuple[np.ndarray, np.ndarray]:
    v = np.zeros_like(acc, dtype=np.float64)
    d = np.zeros_like(acc, dtype=np.float64)
    for i in range(1, len(acc)):
        v[i] = v[i - 1] + acc[i] * dt
        d[i] = d[i - 1] + v[i] * dt
    return v, d


def _process_event(event_name: str) -> Dict[str, np.ndarray]:
    event_dir = _resolve_event_dir(event_name)
    f_acc = _find_channel_file(event_dir, PRIMARY_ACC_CHANNEL)
    f_disp = _find_channel_file(event_dir, PRIMARY_DISP_CHANNEL)
    used_channels = f"{PRIMARY_ACC_CHANNEL}/{PRIMARY_DISP_CHANNEL}"
    dt_a, acc_cmss, _ = parse_v2_file(str(f_acc))
    dt_y, _, disp_cm = parse_v2_file(str(f_disp))
    if not np.isclose(dt_a, dt_y, atol=1e-9):
        raise ValueError(f"dt mismatch in event {event_name}: {dt_a} vs {dt_y}")

    acc_mss = np.asarray(acc_cmss, dtype=np.float64) / 100.0
    disp_m = np.asarray(disp_cm, dtype=np.float64) / 100.0
    n = min(len(acc_mss), len(disp_m))
    acc_mss = acc_mss[:n]
    disp_m = disp_m[:n]

    acc_ds = _resample_to_target_dt(acc_mss, dt_a, TARGET_DT)
    disp_ds = _resample_to_target_dt(disp_m, dt_a, TARGET_DT)
    n2 = min(len(acc_ds), len(disp_ds))
    acc_ds = acc_ds[:n2]
    disp_ds = disp_ds[:n2]

    a_win, y_win, idx_peak = _slice_around_peak_with_padding(acc_ds, disp_ds)
    v_win, d_win = _build_kinematic_priors(a_win, TARGET_DT)
    X = np.stack([a_win, v_win, d_win], axis=-1)
    Y = y_win[:, None]
    return {
        "event": np.array(event_name),
        "event_dir": np.array(event_dir.name),
        "used_channels": np.array(used_channels),
        "X_raw": X,
        "Y_raw": Y,
        "idx_peak_ds": np.array(idx_peak),
    }


def _zscore_fit(X_train: np.ndarray, Y_train: np.ndarray) -> Dict[str, np.ndarray]:
    x_mean = X_train.mean(axis=(0, 1), keepdims=True)
    x_std = X_train.std(axis=(0, 1), keepdims=True)
    y_mean = Y_train.mean(axis=(0, 1), keepdims=True)
    y_std = Y_train.std(axis=(0, 1), keepdims=True)
    eps = 1e-12
    x_std = np.where(x_std < eps, 1.0, x_std)
    y_std = np.where(y_std < eps, 1.0, y_std)
    return {"x_mean": x_mean, "x_std": x_std, "y_mean": y_mean, "y_std": y_std}


def _zscore_apply(X: np.ndarray, Y: np.ndarray, stats: Dict[str, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
    Xn = (X - stats["x_mean"]) / stats["x_std"]
    Yn = (Y - stats["y_mean"]) / stats["y_std"]
    return Xn, Yn


def main() -> None:
    train_items = [_process_event(ev) for ev in TRAIN_EVENTS]
    X_train_raw = np.stack([it["X_raw"] for it in train_items], axis=0)
    Y_train_raw = np.stack([it["Y_raw"] for it in train_items], axis=0)

    test_item = _process_event(TEST_EVENT)
    X_test_raw = test_item["X_raw"][None, ...]
    Y_test_raw = test_item["Y_raw"][None, ...]

    stats = _zscore_fit(X_train_raw, Y_train_raw)
    X_train, Y_train = _zscore_apply(X_train_raw, Y_train_raw, stats)
    X_test, Y_test = _zscore_apply(X_test_raw, Y_test_raw, stats)

    out_npz = OUT_DIR / "transfer_dataset_v1.npz"
    np.savez_compressed(
        out_npz,
        train_events=np.array(TRAIN_EVENTS),
        test_event=np.array(TEST_EVENT),
        train_event_dirs=np.array([it["event_dir"] for it in train_items]),
        train_used_channels=np.array([it["used_channels"] for it in train_items]),
        test_event_dir=np.array(test_item["event_dir"]),
        test_used_channels=np.array(test_item["used_channels"]),
        X_train=X_train.astype(np.float32),
        Y_train=Y_train.astype(np.float32),
        X_test=X_test.astype(np.float32),
        Y_test=Y_test.astype(np.float32),
        X_train_raw=X_train_raw.astype(np.float32),
        Y_train_raw=Y_train_raw.astype(np.float32),
        X_test_raw=X_test_raw.astype(np.float32),
        Y_test_raw=Y_test_raw.astype(np.float32),
        x_mean=stats["x_mean"].astype(np.float32),
        x_std=stats["x_std"].astype(np.float32),
        y_mean=stats["y_mean"].astype(np.float32),
        y_std=stats["y_std"].astype(np.float32),
    )

    t = np.arange(TARGET_LEN, dtype=float) * TARGET_DT
    fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True, gridspec_kw={"hspace": 0.08})
    axes[0].plot(t, X_test_raw[0, :, 0], color="#1f77b4", linewidth=1.0)
    axes[0].set_ylabel("a(t) [m/s^2]")
    axes[0].set_title("Test raw: acceleration / prior displacement / true displacement")
    axes[0].grid(True, alpha=0.3)
    axes[1].plot(t, X_test_raw[0, :, 2], color="#ff7f0e", linewidth=1.0)
    axes[1].set_ylabel("d_prior(t) [m]")
    axes[1].grid(True, alpha=0.3)
    axes[2].plot(t, Y_test_raw[0, :, 0], color="#2ca02c", linewidth=1.0)
    axes[2].set_ylabel("u_true(t) [m]")
    axes[2].set_xlabel("Time [s]")
    axes[2].grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "test_raw_a_prior_true_check.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT_DIR / "test_raw_a_prior_true_check.pdf", bbox_inches="tight")
    plt.close(fig)

    print("=== Transfer Data Prepared (Third-dataset Z-score) ===")
    print(f"Data root  : {DATA_ROOT}")
    print(f"Train events: {TRAIN_EVENTS}")
    print(f"Test event : {TEST_EVENT}")
    print(f"Train dirs : {[str(it['event_dir']) for it in train_items]}")
    print(f"Train chns : {[str(it['used_channels']) for it in train_items]}")
    print(f"Test dir   : {test_item['event_dir']}")
    print(f"Test chns  : {test_item['used_channels']}")
    print(f"X_train shape: {X_train.shape}, Y_train shape: {Y_train.shape}")
    print(f"X_test shape : {X_test.shape}, Y_test shape : {Y_test.shape}")
    print(f"Saved dataset: {out_npz}")


if __name__ == "__main__":
    main()

