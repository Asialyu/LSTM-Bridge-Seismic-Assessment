#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M4 (Physics, Combined Loss): The Proposed Model (Final SOTA Version)

目的：
- 冲击论文的最高性能指标。
- 证明 "物理输入(Architecture) + 物理约束(Loss) = 最佳峰值预测"。

配置：
- 模型：ModelM4_PhysicsPure (无CNN, 物理残差)
- 损失：CombinedLoss (加权MSE + 峰值损失 + 梯度损失 + 相关性损失)
  - 重点强化 Peak Weight 和 Correlation Weight 以对抗漂移。
- 输出目录：results_m4_final_combined/ (独立，不与其他版本冲突)
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

# 引用你已经有的 M4 模型类
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

def _json_default(obj):
    """Make numpy / torch scalars JSON-serializable."""
    try:
        import numpy as _np
        if isinstance(obj, (_np.floating, _np.integer)):
            return obj.item()
        if isinstance(obj, _np.ndarray):
            return obj.tolist()
    except Exception:
        pass
    # torch scalar
    if isinstance(obj, torch.Tensor) and obj.numel() == 1:
        return obj.detach().cpu().item()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

# ==================== 1. 损失函数 (Combined Loss) ====================
class CombinedLoss(nn.Module):
    """
    终极物理约束损失函数
    策略：
    1. Correlation (3.0): 强行拉齐相位，死死按住积分漂移。
    2. Peak (2.0): 强迫模型去拟合那些尖锐的极值点。
    3. Gradient (1.5): 保证波形的光滑度，模拟真实的物理运动。
    """
    def __init__(self, mse_weight=1.0, peak_weight=2.0, gradient_weight=1.5, 
                 correlation_weight=3.0, peak_threshold=0.7):
        super(CombinedLoss, self).__init__()
        self.mse_weight = mse_weight
        self.peak_weight = peak_weight
        self.gradient_weight = gradient_weight
        self.correlation_weight = correlation_weight
        self.peak_threshold = peak_threshold
        self.mse_criterion = nn.MSELoss()
        self.l1_criterion = nn.L1Loss()

    def forward(self, y_pred, y_true):
        # 1. 基础 MSE
        mse_loss = self.mse_criterion(y_pred, y_true)
        
        # 2. 峰值损失 (Peak Loss)
        # 只计算真实值绝对值超过阈值(0.7 max)的部分
        # 注意：这里按 Batch 内的最大值动态计算阈值
        batch_max = torch.max(torch.abs(y_true))
        peak_mask = torch.abs(y_true) > (self.peak_threshold * batch_max)
        
        if peak_mask.sum() > 0:
            peak_loss = self.mse_criterion(y_pred[peak_mask], y_true[peak_mask])
        else:
            peak_loss = torch.tensor(0.0, device=y_pred.device)

        # 3. 梯度损失 (Gradient Loss) - 物理平滑约束
        dy_true = y_true[:, 1:] - y_true[:, :-1]
        dy_pred = y_pred[:, 1:] - y_pred[:, :-1]
        grad_loss = self.l1_criterion(dy_pred, dy_true)

        # 4. 相关性损失 (Correlation Loss) - 抗漂移核心
        vx = y_pred - torch.mean(y_pred, dim=1, keepdim=True)
        vy = y_true - torch.mean(y_true, dim=1, keepdim=True)
        # 按样本计算相关系数，然后取平均
        cov = torch.sum(vx * vy, dim=1)
        var_x = torch.sqrt(torch.sum(vx ** 2, dim=1))
        var_y = torch.sqrt(torch.sum(vy ** 2, dim=1))
        # 避免除零
        cost = cov / (var_x * var_y + 1e-8)
        corr_loss = torch.mean(1 - cost)

        # 总损失
        total_loss = (self.mse_weight * mse_loss + 
                      self.peak_weight * peak_loss + 
                      self.gradient_weight * grad_loss + 
                      self.correlation_weight * corr_loss)
        return total_loss

# ==================== 2. 数据处理与积分先验（ground-motion-derived） ====================
def compute_physics_inputs(acceleration: np.ndarray, dt: float = 0.02):
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
        print("计算归一化参数...")
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
        x_3ch = np.stack([acc, vel, disp], axis=-1).astype(np.float32)
        return torch.from_numpy(x_3ch), torch.from_numpy(y).unsqueeze(-1)

# ==================== 3. 训练与评估流程 ====================
def compute_peak_indices(batch_x):
    return torch.argmax(torch.abs(batch_x[:, :, 0]), dim=1).long()

def train_epoch(model, dataloader, criterion, optimizer):
    model.train()
    total = 0.0
    for batch_x, batch_y in dataloader:
        batch_x, batch_y = batch_x.to(device), batch_y.to(device)
        optimizer.zero_grad()
        peak_indices = compute_peak_indices(batch_x)
        pred = model(batch_x, peak_indices=peak_indices)
        loss = criterion(pred, batch_y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        total += loss.item()
    return total / len(dataloader)

@torch.no_grad()
def evaluate(model, dataloader, criterion, base_dataset):
    model.eval()
    total_loss = 0.0
    all_y_true, all_y_pred = [], []
    for batch_x, batch_y in dataloader:
        batch_x, batch_y = batch_x.to(device), batch_y.to(device)
        peak_indices = compute_peak_indices(batch_x)
        pred = model(batch_x, peak_indices=peak_indices)
        loss = criterion(pred, batch_y)
        total_loss += loss.item()
        all_y_true.append(batch_y.cpu().numpy())
        all_y_pred.append(pred.cpu().numpy())

    avg_loss = total_loss / len(dataloader)
    y_true = np.concatenate(all_y_true, axis=0).flatten()
    y_pred = np.concatenate(all_y_pred, axis=0).flatten()
    y_true_dn = y_true * base_dataset.y_std + base_dataset.y_mean
    y_pred_dn = y_pred * base_dataset.y_std + base_dataset.y_mean

    mse = mean_squared_error(y_true_dn, y_pred_dn)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_true_dn, y_pred_dn)
    r2 = r2_score(y_true_dn, y_pred_dn)
    ci = pearsonr(y_true_dn, y_pred_dn)[0] if len(y_true_dn) > 1 else 0.0

    # Peak RMSE
    y_t_samp = np.concatenate(all_y_true, axis=0) * base_dataset.y_std + base_dataset.y_mean
    y_p_samp = np.concatenate(all_y_pred, axis=0) * base_dataset.y_std + base_dataset.y_mean
    peak_t = np.max(np.abs(y_t_samp), axis=1) * 1000.0
    peak_p = np.max(np.abs(y_p_samp), axis=1) * 1000.0
    peak_rmse = np.sqrt(np.mean((peak_t - peak_p)**2)) if len(peak_t) > 1 else 0.0

    return {
        'loss': avg_loss, 
        'rmse': rmse, 
        'mae': mae,
        'r2': r2, 
        'ci': ci, 
        'peak_rmse_mm': peak_rmse
    }

# ==================== 4. 主程序 ====================
def main():
    print("\n" + "="*60)
    print("M4 (Physics, Combined Loss) - 终极 SOTA 模型")
    print("="*60)

    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--output_dir",
        type=str,
        default="",
        help="Override output directory (default: results_m4_final_combined).",
    )
    args = parser.parse_args()
    set_seed(args.seed)

    # 路径配置
    data_dir = data_augmented_dir()
    if not data_dir.exists():
        data_dir = data_augmented_dir()  # fixed2000 fallback removed in release; use CPENG_DATA_DIR

    output_dir = Path(args.output_dir) if args.output_dir else (REPO_ROOT / 'checkpoints' / 'M4_Combined_seed1')
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n输出目录: {output_dir}")

    # 加载数据
    full_ds = SeismicDatasetPhysics(data_dir/'train'/'X', data_dir/'train'/'Y', normalize=True, dt=0.02)
    test_ds = SeismicDatasetPhysics(data_dir/'test'/'X', data_dir/'test'/'Y', normalize=True, dt=0.02)
    
    # 传递归一化参数
    for attr in ['acc_mean', 'acc_std', 'vel_mean', 'vel_std', 'disp_mean', 'disp_std', 'y_mean', 'y_std']:
        setattr(test_ds, attr, getattr(full_ds, attr))

    # 数据集划分
    def get_name(p):
        n = p.stem.replace('_X', '').replace('_time', '')
        if '_aug' in n:
            n = n.split('_aug')[0]
        if '_0p' in n:
            return n.split('_0p')[0]
        return None

    groups = defaultdict(list)
    for i, (xf, _) in enumerate(full_ds.samples):
        name = get_name(xf)
        if name: groups[name].append(i)
    
    motions = sorted([m for m in groups.keys() if not m.startswith('aug')])
    train_idx = []
    val_idx = []
    for m in motions[4:]: 
        train_idx.extend(groups[m])  # 后面的做训练
    for m in motions[:4]: 
        val_idx.extend(groups[m])    # 前4个做验证

    train_loader = DataLoader(torch.utils.data.Subset(full_ds, train_idx), batch_size=8, shuffle=True)
    val_loader = DataLoader(torch.utils.data.Subset(full_ds, val_idx), batch_size=8, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=8, shuffle=False)

    # 超参数
    hp_path = hyperparams_path()
    with open(hp_path, encoding='utf-8') as f: 
        hp = json.load(f)['best_hyperparameters']

    # 模型与优化
    model = ModelM4_PhysicsPure(
        input_dim=3, 
        hidden_dim=hp['hidden_dim'], 
        num_layers=hp['num_layers'],
        output_dim=1, 
        dropout=hp['dropout'], 
        bidirectional=hp['bidirectional']
    ).to(device)
    
    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\n模型参数量: {total_params:,}")
    
    criterion = CombinedLoss()  # 使用默认的强力权重
    optimizer = optim.Adam(model.parameters(), lr=hp['learning_rate'], weight_decay=hp['weight_decay'])
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='max', factor=0.7, patience=30, verbose=True)

    # 训练循环
    best_ci = -999
    patience = 90
    counter = 0
    history = defaultdict(list)

    print("\n开始训练 (Target: Peak RMSE < 8.0)...")
    t0 = time.time()
    for epoch in range(2000):
        t_loss = train_epoch(model, train_loader, criterion, optimizer)
        v_met = evaluate(model, val_loader, criterion, full_ds)
        t_met = evaluate(model, test_loader, criterion, full_ds)

        # 记录
        history['train_loss'].append(t_loss)
        history['val_loss'].append(v_met['loss'])
        history['val_r2'].append(v_met['r2'])
        history['val_ci'].append(v_met['ci'])
        history['test_r2'].append(t_met['r2'])
        history['test_ci'].append(t_met['ci'])
        history['val_peak'].append(v_met['peak_rmse_mm'])
        history['test_peak'].append(t_met['peak_rmse_mm'])

        scheduler.step(v_met['ci'])

        if (epoch+1) % 10 == 0 or epoch == 0:
            print(f"\nEpoch [{epoch+1}/2000]")
            print(f"  Train Loss: {t_loss:.6f}")
            print(f"  Val  | Loss: {v_met['loss']:.6f} | R2: {v_met['r2']:.6f} | CI: {v_met['ci']:.6f} | RMSE: {v_met['rmse']:.4f} mm | MAE: {v_met['mae']:.4f} mm | PeakRMSE: {v_met['peak_rmse_mm']:.2f} mm")
            print(f"  Test | Loss: {t_met['loss']:.6f} | R2: {t_met['r2']:.6f} | CI: {t_met['ci']:.6f} | RMSE: {t_met['rmse']:.4f} mm | MAE: {t_met['mae']:.4f} mm | PeakRMSE: {t_met['peak_rmse_mm']:.2f} mm")

        if v_met['ci'] > best_ci:
            best_ci = v_met['ci']
            torch.save(model.state_dict(), output_dir / 'best_model.pth')
            counter = 0
            print(f"  -> 保存最佳模型 (val_ci={best_ci:.6f})")
        else:
            counter += 1
            if counter >= patience:
                print(f"\nEarly stopping at epoch {epoch+1} (CI未提升已{patience}个epoch)")
                print(f"  最佳验证集CI: {best_ci:.6f}")
                break

    train_time = time.time() - t0
    print(f"\n训练完成！总耗时: {train_time:.1f} 秒")

    # 最终结果
    print("\n加载最佳模型进行最终评估...")
    model.load_state_dict(torch.load(output_dir / 'best_model.pth', map_location=device, weights_only=True))
    final_val_metrics = evaluate(model, val_loader, criterion, full_ds)
    final_test_metrics = evaluate(model, test_loader, criterion, full_ds)
    
    print("\n" + "="*60)
    print("最终评估结果:")
    print("="*60)
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
    
    print(f"\n结果已保存到: {output_dir}")

    # 保存结果
    results = {
        "train_losses": history['train_loss'],
        "val_losses": history['val_loss'],
        "val_r2_scores": history['val_r2'],
        "val_ci_scores": history['val_ci'],
        "test_r2_scores": history['test_r2'],
        "test_ci_scores": history['test_ci'],
        "val_peak_rmse_scores": history['val_peak'],
        "test_peak_rmse_scores": history['test_peak'],
        "final_val_metrics": final_val_metrics,
        "final_test_metrics": final_test_metrics,
        "model_params": {
            "input_dim": 3,
            "hidden_dim": hp['hidden_dim'],
            "num_layers": hp['num_layers'],
            "dropout": hp['dropout'],
            "bidirectional": hp['bidirectional'],
            "total_params": total_params,
        },
        "loss_config": {
            "mse_weight": 1.0,
            "peak_weight": 2.0,
            "gradient_weight": 1.5,
            "correlation_weight": 3.0,
            "peak_threshold": 0.7
        }
    }
    
    with open(output_dir / 'training_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=_json_default)
    
    # 绘制训练曲线
    plt.figure(figsize=(15, 10))
    
    plt.subplot(2, 3, 1)
    plt.plot(history['train_loss'], label='Train Loss')
    plt.plot(history['val_loss'], label='Val Loss')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.legend()
    plt.title('Training Loss')
    plt.grid(True)
    
    plt.subplot(2, 3, 2)
    plt.plot(history['val_r2'], label='Val R²')
    plt.plot(history['test_r2'], label='Test R²')
    plt.xlabel('Epoch')
    plt.ylabel('R²')
    plt.legend()
    plt.title('R² Score')
    plt.grid(True)
    
    plt.subplot(2, 3, 3)
    plt.plot(history['val_ci'], label='Val CI')
    plt.plot(history['test_ci'], label='Test CI')
    plt.xlabel('Epoch')
    plt.ylabel('CI')
    plt.legend()
    plt.title('Correlation Index')
    plt.grid(True)
    
    plt.subplot(2, 3, 4)
    plt.plot(history['val_peak'], label='Val Peak RMSE')
    plt.plot(history['test_peak'], label='Test Peak RMSE')
    plt.xlabel('Epoch')
    plt.ylabel('Peak RMSE (mm)')
    plt.legend()
    plt.title('Peak RMSE')
    plt.grid(True)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'training_curves.png', dpi=300, bbox_inches='tight')
    print(f"\n训练曲线已保存: {output_dir / 'training_curves.png'}")

if __name__ == '__main__':
    main()

