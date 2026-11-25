#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M4 (Physics, MSE): Physics-Informed Residual LSTM without CNN (for ablation fairness)

目的：
- 确保与 M1/M2/M3 的 “纯 MSE” 消融一致：只比较结构/输入，不引入组合损失带来的额外训练信号。

输入：
- (batch, seq_len, 3) = [ü_g, u̇_g, u_g]
  其中 u̇_g / u_g 由基底输入加速度 ü_g 数值积分得到（ground-motion-derived prior，不引入 CNN）。

模型：
- ModelM4_PhysicsPure（定义在 attention_module.py）
  Output = Prior_Projected + Delta_Y
  其中 Prior_Projected 对积分得到的 u_g 通道做可学习仿射对齐（scale, bias）。

损失：
- nn.MSELoss()
"""

import argparse
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from scipy.stats import pearsonr
import time
import json
import sys
from collections import defaultdict

# --- release path bootstrap (no machine-specific absolute paths) ---
from pathlib import Path as _Path
import sys as _sys
_CODE_DIR = _Path(__file__).resolve().parents[1]  # .../code
if str(_CODE_DIR) not in _sys.path:
    _sys.path.insert(0, str(_CODE_DIR))
from paths import data_augmented_dir, hyperparams_path, ensure_models_on_path, REPO_ROOT
ensure_models_on_path()
# --- end bootstrap ---

current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))
sys.path.insert(0, str(current_dir))

from attention_module import ModelM4_PhysicsPure


def set_seed(seed=42):
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


DEFAULT_SEED = 42
set_seed(DEFAULT_SEED)
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"使用设备: {device}")


def compute_physics_inputs(acceleration: np.ndarray, dt: float = 0.02):
    """
    对基底输入加速度做数值积分，得到 ground-motion-derived kinematic prior：
      v_g(t) = ∫ ü_g dt
      u_g(t) = ∫ v_g dt

    注意：这里的 (v_g, u_g) 是由输入地震动构造的先验特征，并非桥面/跨中响应的速度/位移。
    """
    vel = np.cumsum(acceleration) * dt
    disp = np.cumsum(vel) * dt
    return vel.astype(np.float32), disp.astype(np.float32)


class SeismicDatasetPhysics(Dataset):
    def __init__(self, x_dir, y_dir, normalize=True, dt=0.02):
        self.x_dir = Path(x_dir)
        self.y_dir = Path(y_dir)
        self.dt = dt
        x_files = sorted(list(self.x_dir.glob("*_X.txt")))
        self.samples = []
        for x_file in x_files:
            base_name = x_file.stem.replace('_X', '')
            y_file = self.y_dir / f"{base_name}_Y.txt"
            if y_file.exists():
                self.samples.append((x_file, y_file))
        print(f"加载了 {len(self.samples)} 个样本")

        if normalize:
            self._compute_normalization()
        else:
            self.acc_mean = self.acc_std = None
            self.vel_mean = self.vel_std = None
            self.disp_mean = self.disp_std = None
            self.y_mean = self.y_std = None

    def _compute_normalization(self):
        print("计算归一化参数（Acc/Vel/Disp/Target）...")
        all_acc, all_vel, all_disp, all_y = [], [], [], []
        for x_file, y_file in self.samples[:200]:
            acc = np.loadtxt(x_file).flatten().astype(np.float32)
            vel, disp = compute_physics_inputs(acc, self.dt)
            y = np.loadtxt(y_file).flatten().astype(np.float32)
            all_acc.append(acc)
            all_vel.append(vel)
            all_disp.append(disp)
            all_y.append(y)

        all_acc = np.concatenate(all_acc)
        all_vel = np.concatenate(all_vel)
        all_disp = np.concatenate(all_disp)
        all_y = np.concatenate(all_y)

        self.acc_mean = float(np.mean(all_acc))
        self.acc_std = float(np.std(all_acc) + 1e-8)
        self.vel_mean = float(np.mean(all_vel))
        self.vel_std = float(np.std(all_vel) + 1e-8)
        self.disp_mean = float(np.mean(all_disp))
        self.disp_std = float(np.std(all_disp) + 1e-8)
        self.y_mean = float(np.mean(all_y))
        self.y_std = float(np.std(all_y) + 1e-8)

        print(f"  Acc:  mean={self.acc_mean:.6f}, std={self.acc_std:.6f}")
        print(f"  Vel:  mean={self.vel_mean:.6f}, std={self.vel_std:.6f}")
        print(f"  Disp: mean={self.disp_mean:.6f}, std={self.disp_std:.6f}")
        print(f"  Y:    mean={self.y_mean:.6f}, std={self.y_std:.6f}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        x_file, y_file = self.samples[idx]
        acc = np.loadtxt(x_file).astype(np.float32)
        y = np.loadtxt(y_file).astype(np.float32)
        vel, disp = compute_physics_inputs(acc, self.dt)

        if self.acc_mean is not None:
            acc = (acc - self.acc_mean) / self.acc_std
            vel = (vel - self.vel_mean) / self.vel_std
            disp = (disp - self.disp_mean) / self.disp_std
            y = (y - self.y_mean) / self.y_std

        x_3ch = np.stack([acc, vel, disp], axis=-1).astype(np.float32)  # (seq, 3)
        return torch.from_numpy(x_3ch), torch.from_numpy(y).unsqueeze(-1)


def compute_peak_indices(batch_x: torch.Tensor) -> torch.Tensor:
    # 用加速度通道找峰值
    abs_x = torch.abs(batch_x[:, :, 0])
    return torch.argmax(abs_x, dim=1).long()


def train_epoch(model, dataloader, criterion, optimizer):
    model.train()
    total = 0.0
    for batch_x, batch_y in dataloader:
        batch_x = batch_x.to(device)
        batch_y = batch_y.to(device)
        optimizer.zero_grad()
        peak_indices = compute_peak_indices(batch_x)
        pred = model(batch_x, peak_indices=peak_indices)
        loss = criterion(pred, batch_y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        total += float(loss.item())
    return total / len(dataloader)


@torch.no_grad()
def evaluate(model, dataloader, criterion, base_dataset):
    model.eval()
    total = 0.0
    all_y_true, all_y_pred = [], []
    for batch_x, batch_y in dataloader:
        batch_x = batch_x.to(device)
        batch_y = batch_y.to(device)
        peak_indices = compute_peak_indices(batch_x)
        pred = model(batch_x, peak_indices=peak_indices)
        loss = criterion(pred, batch_y)
        total += float(loss.item())
        all_y_true.append(batch_y.cpu().numpy())
        all_y_pred.append(pred.cpu().numpy())

    avg_loss = total / len(dataloader)
    y_true = np.concatenate(all_y_true, axis=0).flatten()
    y_pred = np.concatenate(all_y_pred, axis=0).flatten()

    # 反归一化到物理量（与既有脚本保持一致）
    y_true_denorm = y_true * base_dataset.y_std + base_dataset.y_mean
    y_pred_denorm = y_pred * base_dataset.y_std + base_dataset.y_mean

    mse = mean_squared_error(y_true_denorm, y_pred_denorm)
    rmse = float(np.sqrt(mse))
    mae = float(mean_absolute_error(y_true_denorm, y_pred_denorm))
    r2 = float(r2_score(y_true_denorm, y_pred_denorm))
    ci = float(pearsonr(y_true_denorm, y_pred_denorm)[0]) if len(y_true_denorm) > 1 else 0.0

    # Peak RMSE（每条样本取最大绝对值，单位 mm）
    y_true_samples = np.concatenate(all_y_true, axis=0) * base_dataset.y_std + base_dataset.y_mean
    y_pred_samples = np.concatenate(all_y_pred, axis=0) * base_dataset.y_std + base_dataset.y_mean
    peak_true = np.max(np.abs(y_true_samples), axis=1) * 1000.0
    peak_pred = np.max(np.abs(y_pred_samples), axis=1) * 1000.0
    peak_rmse = float(np.sqrt(np.mean((peak_true - peak_pred) ** 2))) if len(peak_true) > 1 else 0.0

    return {
        "loss": avg_loss,
        "mse": float(mse),
        "rmse": rmse,
        "mae": mae,
        "r2": r2,
        "ci": ci,
        "peak_rmse_mm": peak_rmse,
    }


def main():
    print("\n" + "=" * 60)
    print("M4 (Physics, MSE) - 消融公平对比版")
    print("=" * 60)

    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--output_dir",
        type=str,
        default="",
        help="Override output directory (default: results_ablation_mse_m4_physics_pure).",
    )
    args = parser.parse_args()
    set_seed(args.seed)

    data_dir = data_augmented_dir()
    if not data_dir.exists():
        print("警告: 增强数据目录不存在，使用原始数据")
        data_dir = data_augmented_dir()  # fixed2000 fallback removed in release; use CPENG_DATA_DIR

    train_x_dir = data_dir / "train" / "X"
    train_y_dir = data_dir / "train" / "Y"
    test_x_dir = data_dir / "test" / "X"
    test_y_dir = data_dir / "test" / "Y"

    output_dir = Path(args.output_dir) if args.output_dir else (current_dir / "results_ablation_mse_m4_physics_pure")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n输出目录: {output_dir}")

    full_train_dataset = SeismicDatasetPhysics(train_x_dir, train_y_dir, normalize=True, dt=0.02)
    test_dataset = SeismicDatasetPhysics(test_x_dir, test_y_dir, normalize=True, dt=0.02)

    # 统一归一化参数（按训练集）
    test_dataset.acc_mean, test_dataset.acc_std = full_train_dataset.acc_mean, full_train_dataset.acc_std
    test_dataset.vel_mean, test_dataset.vel_std = full_train_dataset.vel_mean, full_train_dataset.vel_std
    test_dataset.disp_mean, test_dataset.disp_std = full_train_dataset.disp_mean, full_train_dataset.disp_std
    test_dataset.y_mean, test_dataset.y_std = full_train_dataset.y_mean, full_train_dataset.y_std

    print("\n按地震动分组划分训练/验证（与其它脚本一致）...")

    def extract_motion_name(file_path: Path):
        name = file_path.stem.replace("_X", "").replace("_time", "")
        if "_aug" in name:
            name = name.split("_aug")[0]
        if "_0p" in name:
            return name.split("_0p")[0]
        return None

    motion_groups = defaultdict(list)
    for i, (x_file, _) in enumerate(full_train_dataset.samples):
        name = extract_motion_name(x_file)
        if name:
            motion_groups[name].append(i)

    all_motions = sorted([m for m in motion_groups.keys() if m and not m.startswith("aug")])
    val_motions = all_motions[:4]
    train_motions = all_motions[4:]

    train_indices, val_indices = [], []
    for m in train_motions:
        train_indices.extend(motion_groups[m])
    for m in val_motions:
        val_indices.extend(motion_groups[m])

    print(f"  验证集地震动: {val_motions}")
    print(f"  训练集样本数: {len(train_indices)} | 验证集样本数: {len(val_indices)} | 测试集样本数: {len(test_dataset)}")

    train_dataset = torch.utils.data.Subset(full_train_dataset, train_indices)
    val_dataset = torch.utils.data.Subset(full_train_dataset, val_indices)

    train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=8, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_dataset, batch_size=8, shuffle=False, num_workers=0)

    # 超参数（与其它 MSE 脚本保持一致：来自 hyperopt）
    hyperopt_dir = hyperparams_path().parent
    if not (hyperopt_dir / "best_hyperparameters.json").exists():
        raise FileNotFoundError(f"未找到超参数文件：{hyperopt_dir / 'best_hyperparameters.json'}")
    with open(hyperopt_dir / "best_hyperparameters.json", "r", encoding="utf-8") as f:
        best_hyperparams = json.load(f)["best_hyperparameters"]

    print("\n创建模型 ModelM4_PhysicsPure（No CNN + Phys Residual）...")
    model = ModelM4_PhysicsPure(
        input_dim=3,
        hidden_dim=best_hyperparams["hidden_dim"],
        num_layers=best_hyperparams["num_layers"],
        output_dim=1,
        dropout=best_hyperparams["dropout"],
        bidirectional=best_hyperparams["bidirectional"],
        dt=0.02,
    ).to(device)

    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"模型参数量: {total_params:,}")

    criterion = nn.MSELoss()
    optimizer = optim.Adam(
        model.parameters(),
        lr=best_hyperparams["learning_rate"],
        weight_decay=best_hyperparams["weight_decay"],
    )
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="max", factor=0.7, patience=30, verbose=True)

    num_epochs = 2000
    patience = 90
    best_val_ci = -1e9
    patience_counter = 0

    train_losses, val_losses, test_losses = [], [], []
    val_r2_scores, test_r2_scores = [], []
    val_ci_scores, test_ci_scores = [], []
    val_peak_rmse_scores, test_peak_rmse_scores = [], []

    print(f"\n开始训练（纯 MSE；CI 监控 EarlyStopping patience={patience}）...")
    start_time = time.time()

    for epoch in range(num_epochs):
        train_loss = train_epoch(model, train_loader, criterion, optimizer)
        val_metrics = evaluate(model, val_loader, criterion, full_train_dataset)
        test_metrics = evaluate(model, test_loader, criterion, full_train_dataset)

        train_losses.append(train_loss)
        val_losses.append(val_metrics["loss"])
        test_losses.append(test_metrics["loss"])
        val_r2_scores.append(val_metrics["r2"])
        test_r2_scores.append(test_metrics["r2"])
        val_ci_scores.append(val_metrics["ci"])
        test_ci_scores.append(test_metrics["ci"])
        val_peak_rmse_scores.append(val_metrics["peak_rmse_mm"])
        test_peak_rmse_scores.append(test_metrics["peak_rmse_mm"])

        scheduler.step(val_metrics["ci"])

        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"\nEpoch [{epoch+1}/{num_epochs}]")
            print(f"  Train Loss: {train_loss:.6f}")
            print(f"  Val  | Loss: {val_metrics['loss']:.6f} | R2: {val_metrics['r2']:.6f} | CI: {val_metrics['ci']:.6f} | RMSE: {val_metrics['rmse']:.4f} mm | MAE: {val_metrics['mae']:.4f} mm | PeakRMSE: {val_metrics['peak_rmse_mm']:.2f} mm")
            print(f"  Test | Loss: {test_metrics['loss']:.6f} | R2: {test_metrics['r2']:.6f} | CI: {test_metrics['ci']:.6f} | RMSE: {test_metrics['rmse']:.4f} mm | MAE: {test_metrics['mae']:.4f} mm | PeakRMSE: {test_metrics['peak_rmse_mm']:.2f} mm")

        if val_metrics["ci"] > best_val_ci:
            best_val_ci = val_metrics["ci"]
            torch.save(model.state_dict(), output_dir / "best_model.pth")
            patience_counter = 0
            print(f"  -> 保存最佳模型 (val_ci={best_val_ci:.6f})")
        else:
            patience_counter += 1

        if patience_counter >= patience:
            print(f"\nEarly stopping at epoch {epoch+1} (CI未提升已{patience}个epoch)")
            print(f"  最佳验证集CI: {best_val_ci:.6f}")
            break

    train_time = time.time() - start_time
    print(f"\n训练完成！总耗时: {train_time:.1f} 秒")

    print("\n加载最佳模型进行最终评估...")
    # 避免 PyTorch FutureWarning（仅加载权重；不影响结果）
    model.load_state_dict(torch.load(output_dir / "best_model.pth", map_location=device, weights_only=True))
    final_val_metrics = evaluate(model, val_loader, criterion, full_train_dataset)
    final_test_metrics = evaluate(model, test_loader, criterion, full_train_dataset)

    print("\n" + "=" * 60)
    print("最终评估结果:")
    print("=" * 60)
    print("\n验证集:")
    print(f"  Loss: {final_val_metrics['loss']:.6f}")
    print(f"  RMSE: {final_val_metrics['rmse']:.6f} mm")
    print(f"  MAE: {final_val_metrics['mae']:.6f} mm")
    print(f"  R2: {final_val_metrics['r2']:.6f}")
    print(f"  CI: {final_val_metrics['ci']:.6f}")
    print(f"  Peak RMSE: {final_val_metrics['peak_rmse_mm']:.2f} mm")
    print("\n测试集:")
    print(f"  Loss: {final_test_metrics['loss']:.6f}")
    print(f"  RMSE: {final_test_metrics['rmse']:.6f} mm")
    print(f"  MAE: {final_test_metrics['mae']:.6f} mm")
    print(f"  R2: {final_test_metrics['r2']:.6f}")
    print(f"  CI: {final_test_metrics['ci']:.6f}")
    print(f"  Peak RMSE: {final_test_metrics['peak_rmse_mm']:.2f} mm")

    results = {
        "train_losses": train_losses,
        "val_losses": val_losses,
        "test_losses": test_losses,
        "val_r2_scores": val_r2_scores,
        "test_r2_scores": test_r2_scores,
        "val_ci_scores": val_ci_scores,
        "test_ci_scores": test_ci_scores,
        "val_peak_rmse_scores": val_peak_rmse_scores,
        "test_peak_rmse_scores": test_peak_rmse_scores,
        "final_val_metrics": final_val_metrics,
        "final_test_metrics": final_test_metrics,
        "model_params": {
            "input_dim": 3,
            "hidden_dim": best_hyperparams["hidden_dim"],
            "num_layers": best_hyperparams["num_layers"],
            "dropout": best_hyperparams["dropout"],
            "bidirectional": best_hyperparams["bidirectional"],
            "total_params": total_params,
        },
        "loss_config": {"loss_function": "MSE"},
        "training_time_seconds": train_time,
        "ablation_study_note": "M4 (Physics, MSE): No CNN, physics residual baseline + data-driven delta. For fair MSE ablation.",
    }

    with open(output_dir / "training_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # 曲线图（简版）
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    epochs = range(1, len(train_losses) + 1)

    axes[0, 0].plot(epochs, train_losses, label="Train")
    axes[0, 0].plot(epochs, val_losses, label="Val")
    axes[0, 0].plot(epochs, test_losses, label="Test")
    axes[0, 0].set_title("Loss")
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].legend()

    axes[0, 1].plot(epochs, val_ci_scores, label="Val")
    axes[0, 1].plot(epochs, test_ci_scores, label="Test")
    axes[0, 1].set_title("CI")
    axes[0, 1].grid(True, alpha=0.3)
    axes[0, 1].legend()

    axes[1, 0].plot(epochs, val_r2_scores, label="Val")
    axes[1, 0].plot(epochs, test_r2_scores, label="Test")
    axes[1, 0].set_title("R²")
    axes[1, 0].grid(True, alpha=0.3)
    axes[1, 0].legend()

    axes[1, 1].plot(epochs, val_peak_rmse_scores, label="Val")
    axes[1, 1].plot(epochs, test_peak_rmse_scores, label="Test")
    axes[1, 1].set_title("Peak RMSE (mm)")
    axes[1, 1].grid(True, alpha=0.3)
    axes[1, 1].legend()

    plt.tight_layout()
    plt.savefig(output_dir / "training_curves.png", dpi=300, bbox_inches="tight")
    plt.close()

    print(f"\n结果已保存到: {output_dir}")


if __name__ == "__main__":
    main()


