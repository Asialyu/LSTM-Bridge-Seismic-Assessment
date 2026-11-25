#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M3 residual CNN-Attention-LSTM with kernel_size=3 (paper Table 5).

Uses CNNAttnLSTM_Residual_Version_K3 from attention_module.py.
Paper checkpoint: checkpoints/M3_k3/
"""
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

from attention_module import CNNAttnLSTM_Residual_Version_K3


def set_seed(seed=42):
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

set_seed(42)
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"使用设备: {device}")


class SeismicDataset(Dataset):
    def __init__(self, x_dir, y_dir, normalize=True):
        self.x_dir = Path(x_dir)
        self.y_dir = Path(y_dir)
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
            self.x_mean = self.x_std = None
            self.y_mean = self.y_std = None

    def _compute_normalization(self):
        print("计算归一化参数...")
        all_x, all_y = [], []
        for x_file, y_file in self.samples[:200]:
            all_x.append(np.loadtxt(x_file).flatten())
            all_y.append(np.loadtxt(y_file).flatten())
        all_x = np.concatenate(all_x)
        all_y = np.concatenate(all_y)
        self.x_mean = np.mean(all_x)
        self.x_std = np.std(all_x) + 1e-8
        self.y_mean = np.mean(all_y)
        self.y_std = np.std(all_y) + 1e-8
        print(f"  X: mean={self.x_mean:.6f}, std={self.x_std:.6f}")
        print(f"  Y: mean={self.y_mean:.6f}, std={self.y_std:.6f}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        x_file, y_file = self.samples[idx]
        x = np.loadtxt(x_file).astype(np.float32)
        y = np.loadtxt(y_file).astype(np.float32)
        if self.x_mean is not None:
            x = (x - self.x_mean) / self.x_std
            y = (y - self.y_mean) / self.y_std
        x = torch.from_numpy(x).unsqueeze(-1)
        y = torch.from_numpy(y).unsqueeze(-1)
        return x, y


def compute_peak_indices(batch_x: torch.Tensor) -> torch.Tensor:
    abs_x = torch.abs(batch_x.squeeze(-1))
    peak_indices = torch.argmax(abs_x, dim=1)
    return peak_indices.long()


def train_epoch(model, dataloader, criterion, optimizer, device, base_dataset):
    model.train()
    total_loss = 0.0
    for batch_x, batch_y in dataloader:
        batch_x = batch_x.to(device)
        batch_y = batch_y.to(device)
        optimizer.zero_grad()
        peak_indices = compute_peak_indices(batch_x)
        output = model(batch_x, peak_indices=peak_indices)
        loss = criterion(output, batch_y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        total_loss += loss.item()
    return total_loss / len(dataloader)


@torch.no_grad()
def evaluate(model, dataloader, criterion, device, base_dataset):
    model.eval()
    total_loss = 0.0
    all_y_true, all_y_pred = [], []
    for batch_x, batch_y in dataloader:
        batch_x = batch_x.to(device)
        batch_y = batch_y.to(device)
        peak_indices = compute_peak_indices(batch_x)
        output = model(batch_x, peak_indices=peak_indices)
        loss = criterion(output, batch_y)
        total_loss += loss.item()
        all_y_true.append(batch_y.cpu().numpy())
        all_y_pred.append(output.cpu().numpy())
    avg_loss = total_loss / len(dataloader)
    y_true = np.concatenate(all_y_true, axis=0).flatten()
    y_pred = np.concatenate(all_y_pred, axis=0).flatten()
    y_true_denorm = y_true * base_dataset.y_std + base_dataset.y_mean
    y_pred_denorm = y_pred * base_dataset.y_std + base_dataset.y_mean
    mse = mean_squared_error(y_true_denorm, y_pred_denorm)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_true_denorm, y_pred_denorm)
    r2 = r2_score(y_true_denorm, y_pred_denorm)
    ci = float(pearsonr(y_true_denorm, y_pred_denorm)[0]) if len(y_true_denorm) > 1 else 0.0

    y_true_samples = np.concatenate(all_y_true, axis=0)
    y_pred_samples = np.concatenate(all_y_pred, axis=0)
    y_true_samples_denorm = y_true_samples * base_dataset.y_std + base_dataset.y_mean
    y_pred_samples_denorm = y_pred_samples * base_dataset.y_std + base_dataset.y_mean

    peak_true, peak_pred = [], []
    for i in range(y_true_samples_denorm.shape[0]):
        peak_t = np.abs(y_true_samples_denorm[i]).max() * 1000
        peak_p = np.abs(y_pred_samples_denorm[i]).max() * 1000
        peak_true.append(peak_t)
        peak_pred.append(peak_p)
    if len(peak_true) > 1:
        peak_rmse = np.sqrt(np.mean((np.array(peak_true) - np.array(peak_pred))**2))
    else:
        peak_rmse = 0.0

    return {
        'loss': avg_loss,
        'mse': mse,
        'rmse': rmse,
        'mae': mae,
        'r2': r2,
        'ci': ci,
        'peak_rmse_mm': peak_rmse
    }


def main():
    print("\n" + "=" * 60)
    print("CNN-Attention-LSTM (CAL-Net) MSE版本")
    print("=" * 60)

    data_dir = data_augmented_dir()
    if not data_dir.exists():
        print("警告: 增强数据目录不存在，使用原始数据")
        data_dir = data_augmented_dir()  # fixed2000 fallback removed in release; use CPENG_DATA_DIR
    train_x_dir = data_dir / 'train' / 'X'
    train_y_dir = data_dir / 'train' / 'Y'
    test_x_dir = data_dir / 'test' / 'X'
    test_y_dir = data_dir / 'test' / 'Y'

    output_dir = REPO_ROOT / 'checkpoints' / 'M3_k3'
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n输出目录: {output_dir}（CNN-Attention-LSTM MSE版本）")

    full_train_dataset = SeismicDataset(train_x_dir, train_y_dir, normalize=True)
    test_dataset = SeismicDataset(test_x_dir, test_y_dir, normalize=True)
    test_dataset.x_mean = full_train_dataset.x_mean
    test_dataset.x_std = full_train_dataset.x_std
    test_dataset.y_mean = full_train_dataset.y_mean
    test_dataset.y_std = full_train_dataset.y_std

    print("\n按地震动分组划分训练集和验证集...")
    def extract_motion_name(file_path):
        name = file_path.stem.replace('_X', '').replace('_time', '')
        if '_aug' in name:
            name = name.split('_aug')[0]
        if '_0p' in name:
            return name.split('_0p')[0]
        return None

    motion_groups = defaultdict(list)
    for i, (x_file, y_file) in enumerate(full_train_dataset.samples):
        name = extract_motion_name(x_file)
        if name:
            motion_groups[name].append(i)
    all_motions = sorted([m for m in motion_groups.keys() if m and not m.startswith('aug')])
    print(f"  训练集中共有 {len(all_motions)} 个地震动（原始）")
    val_motions = all_motions[:4]
    train_motions = all_motions[4:]
    print(f"  验证集地震动 ({len(val_motions)} 个): {val_motions}")
    print(f"  训练集地震动 ({len(train_motions)} 个): {train_motions}")

    train_indices, val_indices = [], []
    for m in train_motions:
        train_indices.extend(motion_groups[m])
    for m in val_motions:
        val_indices.extend(motion_groups[m])
    print(f"\n  最终划分:\n    训练集样本数: {len(train_indices)} 个\n    验证集样本数: {len(val_indices)} 个\n    测试集样本数: {len(test_dataset)} 个")

    train_dataset = torch.utils.data.Subset(full_train_dataset, train_indices)
    val_dataset = torch.utils.data.Subset(full_train_dataset, val_indices)
    train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=8, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_dataset, batch_size=8, shuffle=False, num_workers=0)

    hyperopt_dir = hyperparams_path().parent
    if (hyperopt_dir / 'best_hyperparameters.json').exists():
        print("\n读取超参数调优得到的最佳超参数...")
        with open(hyperopt_dir / 'best_hyperparameters.json', 'r', encoding='utf-8') as f:
            best_hyperparams = json.load(f)['best_hyperparameters']
        print("  已加载最佳超参数（与Baseline一致）")
    else:
        raise FileNotFoundError(f"未找到超参数文件：{hyperopt_dir / 'best_hyperparameters.json'}")

    print("\n创建 CNN-Attention-LSTM residual model (k=3)...")
    print(f"  CNN: cnn_channels=16, kernel_size=3")
    print(f"  LSTM Encoder: hidden_dim={best_hyperparams['hidden_dim']}, num_layers={best_hyperparams['num_layers']}, dropout={best_hyperparams['dropout']}, bidirectional={best_hyperparams['bidirectional']}")
    model = CNNAttnLSTM_Residual_Version_K3(
        input_dim=1,
        cnn_channels=16,
        hidden_dim=best_hyperparams['hidden_dim'],
        num_layers=best_hyperparams['num_layers'],
        output_dim=1,
        dropout=best_hyperparams['dropout'],
        bidirectional=best_hyperparams['bidirectional']
    ).to(device)
    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"模型参数量: {total_params:,} 个")

    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=best_hyperparams['learning_rate'], weight_decay=best_hyperparams['weight_decay'])
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='max', factor=0.7, patience=30, verbose=True)

    print("\n开始训练（CI 作为监控指标，EarlyStopping patience=90，与Baseline一致）...")
    num_epochs = 2000
    best_val_ci = -1e9
    patience = 90
    patience_counter = 0
    train_losses, val_losses, test_losses = [], [], []
    val_r2_scores, test_r2_scores = [], []
    val_ci_scores, test_ci_scores = [], []
    val_peak_rmse_scores, test_peak_rmse_scores = [], []
    start_time = time.time()

    for epoch in range(num_epochs):
        train_loss = train_epoch(model, train_loader, criterion, optimizer, device, full_train_dataset)
        val_metrics = evaluate(model, val_loader, criterion, device, full_train_dataset)
        test_metrics = evaluate(model, test_loader, criterion, device, full_train_dataset)
        train_losses.append(train_loss)
        val_losses.append(val_metrics['loss'])
        test_losses.append(test_metrics['loss'])
        val_r2_scores.append(val_metrics['r2'])
        test_r2_scores.append(test_metrics['r2'])
        val_ci_scores.append(val_metrics['ci'])
        test_ci_scores.append(test_metrics['ci'])
        val_peak_rmse_scores.append(val_metrics['peak_rmse_mm'])
        test_peak_rmse_scores.append(test_metrics['peak_rmse_mm'])
        scheduler.step(val_metrics['ci'])

        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"\nEpoch [{epoch+1}/{num_epochs}]")
            print(f"  Train Loss: {train_loss:.6f}")
            print(f"  Val Loss: {val_metrics['loss']:.6f} | R2: {val_metrics['r2']:.6f} | CI: {val_metrics['ci']:.6f} | RMSE: {val_metrics['rmse']:.4f} mm | MAE: {val_metrics['mae']:.4f} mm")
            print(f"  Val Peak RMSE: {val_metrics['peak_rmse_mm']:.2f} mm")
            print(f"  Test Loss: {test_metrics['loss']:.6f} | R2: {test_metrics['r2']:.6f} | CI: {test_metrics['ci']:.6f} | RMSE: {test_metrics['rmse']:.4f} mm | MAE: {test_metrics['mae']:.4f} mm")
            print(f"  Test Peak RMSE: {test_metrics['peak_rmse_mm']:.2f} mm")
            print(f"  当前LR: {optimizer.param_groups[0]['lr']:.2e}")

        if val_metrics['ci'] > best_val_ci:
            best_val_ci = val_metrics['ci']
            torch.save(model.state_dict(), output_dir / 'best_model.pth')
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
    model.load_state_dict(torch.load(output_dir / 'best_model.pth', weights_only=False))
    final_val_metrics = evaluate(model, val_loader, criterion, device, full_train_dataset)
    final_test_metrics = evaluate(model, test_loader, criterion, device, full_train_dataset)

    print("\n" + "="*60)
    print("最终评估结果（CNN-Attention-LSTM MSE版本）:")
    print("="*60)
    print(f"\n验证集: Loss={final_val_metrics['loss']:.6f} | RMSE={final_val_metrics['rmse']:.4f} | MAE={final_val_metrics['mae']:.4f} | R2={final_val_metrics['r2']:.6f} | CI={final_val_metrics['ci']:.6f}")
    print(f"  Peak RMSE: {final_val_metrics['peak_rmse_mm']:.2f} mm")
    print(f"\n测试集: Loss={final_test_metrics['loss']:.6f} | RMSE={final_test_metrics['rmse']:.4f} | MAE={final_test_metrics['mae']:.4f} | R2={final_test_metrics['r2']:.6f} | CI={final_test_metrics['ci']:.6f}")
    print(f"  Peak RMSE: {final_test_metrics['peak_rmse_mm']:.2f} mm")

    results = {
        'train_losses': train_losses,
        'val_losses': val_losses,
        'test_losses': test_losses,
        'val_r2_scores': val_r2_scores,
        'test_r2_scores': test_r2_scores,
        'val_ci_scores': val_ci_scores,
        'test_ci_scores': test_ci_scores,
        'val_peak_rmse_scores': val_peak_rmse_scores,
        'test_peak_rmse_scores': test_peak_rmse_scores,
        'final_val_metrics': final_val_metrics,
        'final_test_metrics': final_test_metrics,
        'model_params': {
            'cnn_channels': 16,
            'hidden_dim': int(model.encoder.hidden_size),
            'num_layers': int(model.encoder.num_layers),
            'dropout': float(model.fc[0].p) if isinstance(model.fc, nn.Sequential) and isinstance(model.fc[0], nn.Dropout) else None,
            'bidirectional': bool(model.encoder.bidirectional),
            'total_params': sum(p.numel() for p in model.parameters() if p.requires_grad)
        },
        'attention_config': {
            'type': 'ResCNN_EncoderDecoderGlobalAttention',
            'cnn_channels': 16,
            'note': 'Residual Raw+CNN feature fusion + Encoder-Decoder Global Attention'
        },
        'loss_config': {
            'loss_function': 'MSE',
            'note': 'Residual CNN-Attention-LSTM (Res-CAL-Net) MSE version'
        },
        'hyperparameters_used': best_hyperparams,
        'normalization': {
            'x_mean': float(full_train_dataset.x_mean),
            'x_std': float(full_train_dataset.x_std),
            'y_mean': float(full_train_dataset.y_mean),
            'y_std': float(full_train_dataset.y_std)
        },
        'training_time_seconds': train_time,
        'ablation_study_note': 'This is the Residual CNN-Attention-LSTM (Res-CAL-Net) MSE version with lightweight CNN feature extraction.'
    }
    with open(output_dir / 'training_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    fig, axes = plt.subplots(3, 2, figsize=(16, 15))
    ax1 = axes[0, 0]
    ax1.plot(train_losses, label='Train Loss', linewidth=2)
    ax1.plot(val_losses, label='Val Loss', linewidth=2)
    ax1.plot(test_losses, label='Test Loss', linewidth=2)
    ax1.set_xlabel('Epoch'); ax1.set_ylabel('Loss'); ax1.set_title('Training/Validation/Test Loss (MSE)'); ax1.legend(); ax1.grid(True, alpha=0.3)

    ax2 = axes[0, 1]
    ax2.plot(val_r2_scores, label='Val R2', linewidth=2)
    ax2.plot(test_r2_scores, label='Test R2', linewidth=2)
    ax2.set_xlabel('Epoch'); ax2.set_ylabel('R2'); ax2.set_title('R2 Curves'); ax2.legend(); ax2.grid(True, alpha=0.3)

    ax3 = axes[1, 0]
    ax3.plot(val_ci_scores, label='Val CI', linewidth=2, color='green')
    ax3.plot(test_ci_scores, label='Test CI', linewidth=2, color='orange')
    ax3.set_xlabel('Epoch'); ax3.set_ylabel('CI'); ax3.set_title('CI Curves'); ax3.legend(); ax3.grid(True, alpha=0.3)

    ax4 = axes[1, 1]
    ax4.plot(val_peak_rmse_scores, label='Val Peak RMSE', linewidth=2, color='purple')
    ax4.plot(test_peak_rmse_scores, label='Test Peak RMSE', linewidth=2, color='brown')
    ax4.set_xlabel('Epoch'); ax4.set_ylabel('Peak RMSE (mm)'); ax4.set_title('Peak RMSE Curves'); ax4.legend(); ax4.grid(True, alpha=0.3)

    ax5 = axes[2, 0]
    ax5.axis('off')

    ax6 = axes[2, 1]
    ax6.plot(val_r2_scores, val_ci_scores, label='Val', marker='o', markersize=2, linewidth=1, alpha=0.6)
    ax6.plot(test_r2_scores, test_ci_scores, label='Test', marker='s', markersize=2, linewidth=1, alpha=0.6)
    ax6.set_xlabel('R2'); ax6.set_ylabel('CI'); ax6.set_title('R2 vs CI'); ax6.legend(); ax6.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / 'training_curves.png', dpi=300, bbox_inches='tight')
    print(f"\n训练曲线已保存: {output_dir / 'training_curves.png'}")
    print(f"训练结果已保存: {output_dir / 'training_results.json'}")
    print(f"最佳模型已保存: {output_dir / 'best_model.pth'}")
    print("\n训练完成！（Residual CNN-Attention-LSTM MSE版本）")


if __name__ == "__main__":
    main()

