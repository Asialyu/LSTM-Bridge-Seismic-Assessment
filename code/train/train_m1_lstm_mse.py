#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
改进版 LSTM 模型训练脚本 - 纯 MSE 损失版本
与 train_lstm_improved.py 结构保持一致，仅将损失函数改为 nn.MSELoss，
并将输出目录改为 results_mse_v2，方便与 CombinedLoss 版本对比。
"""
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from pathlib import Path
import matplotlib.pyplot as plt
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from scipy.stats import pearsonr
import time
import json
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


# 设置随机种子
def set_seed(seed=42):
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


set_seed(42)

# 设备配置
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"使用设备: {device}")


# ==================== 数据加载 ====================
class SeismicDataset(Dataset):
    """地震响应数据集"""

    def __init__(self, x_dir, y_dir, normalize=True):
        self.x_dir = Path(x_dir)
        self.y_dir = Path(y_dir)

        # 获取所有文件
        x_files = sorted(list(self.x_dir.glob("*_X.txt")))
        y_files = sorted(list(self.y_dir.glob("*_Y.txt")))

        # 确保X和Y文件匹配
        self.samples = []
        for x_file in x_files:
            base_name = x_file.stem.replace('_X', '')
            y_file = self.y_dir / f"{base_name}_Y.txt"
            if y_file.exists():
                self.samples.append((x_file, y_file))

        print(f"加载了 {len(self.samples)} 个样本")

        # 计算归一化参数（使用训练集）
        if normalize:
            self._compute_normalization()
        else:
            self.x_mean = self.x_std = None
            self.y_mean = self.y_std = None

    def _compute_normalization(self):
        """计算归一化参数"""
        print("计算归一化参数...")
        all_x = []
        all_y = []

        for x_file, y_file in self.samples[:200]:  # 增加到200个样本计算（考虑增强数据）
            x_data = np.loadtxt(x_file).flatten()
            y_data = np.loadtxt(y_file).flatten()
            all_x.append(x_data)
            all_y.append(y_data)

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

        # 读取数据
        x = np.loadtxt(x_file).astype(np.float32)
        y = np.loadtxt(y_file).astype(np.float32)

        # 归一化
        if self.x_mean is not None:
            x = (x - self.x_mean) / self.x_std
            y = (y - self.y_mean) / self.y_std

        # 转换为tensor并添加特征维度
        x = torch.from_numpy(x).unsqueeze(-1)  # (seq_len, 1)
        y = torch.from_numpy(y).unsqueeze(-1)  # (seq_len, 1)

        return x, y


# ==================== 改进LSTM模型 ====================
class ImprovedLSTM(nn.Module):
    """改进版 LSTM 模型 - 支持双向LSTM和更大容量"""

    def __init__(self, input_dim=1, hidden_dim=32, num_layers=1, output_dim=1,
                 dropout=0.3, bidirectional=False):
        super(ImprovedLSTM, self).__init__()

        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.bidirectional = bidirectional

        # LSTM层
        self.lstm = nn.LSTM(
            input_dim,
            hidden_dim,
            num_layers,
            batch_first=True,
            dropout=0 if num_layers == 1 else dropout,
            bidirectional=bidirectional
        )

        # 计算LSTM输出维度
        lstm_output_dim = hidden_dim * 2 if bidirectional else hidden_dim

        # 全连接输出层
        self.fc = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(lstm_output_dim, output_dim)
        )

    def forward(self, x):
        # x: (batch, seq_len, input_dim)
        lstm_out, _ = self.lstm(x)  # lstm_out: (batch, seq_len, hidden_dim)
        output = self.fc(lstm_out)  # (batch, seq_len, output_dim)
        return output


# ==================== 训练和评估 ====================
def train_epoch(model, dataloader, criterion, optimizer, device, base_dataset):
    """训练一个epoch"""
    model.train()
    total_loss = 0

    for batch_x, batch_y in dataloader:
        batch_x = batch_x.to(device)
        batch_y = batch_y.to(device)

        # 前向传播
        optimizer.zero_grad()
        output = model(batch_x)

        # 计算损失（纯 MSE）
        loss = criterion(output, batch_y)

        # 反向传播
        loss.backward()

        # 梯度裁剪
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

        optimizer.step()

        total_loss += loss.item()

    avg_loss = total_loss / len(dataloader)
    return avg_loss


def evaluate(model, dataloader, criterion, device, base_dataset):
    """评估模型"""
    model.eval()
    total_loss = 0

    all_y_true = []
    all_y_pred = []

    with torch.no_grad():
        for batch_x, batch_y in dataloader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)

            # 前向传播
            output = model(batch_x)

            # 计算损失（用于监控）
            loss = criterion(output, batch_y)
            total_loss += loss.item()

            # 收集预测和真实值
            all_y_true.append(batch_y.cpu().numpy())
            all_y_pred.append(output.cpu().numpy())

    avg_loss = total_loss / len(dataloader)

    # 合并所有batch
    y_true = np.concatenate(all_y_true, axis=0).flatten()
    y_pred = np.concatenate(all_y_pred, axis=0).flatten()

    # 反归一化
    y_mean = base_dataset.y_mean
    y_std = base_dataset.y_std

    y_true_denorm = y_true * y_std + y_mean
    y_pred_denorm = y_pred * y_std + y_mean

    # 计算指标
    mse = mean_squared_error(y_true_denorm, y_pred_denorm)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_true_denorm, y_pred_denorm)
    r2 = r2_score(y_true_denorm, y_pred_denorm)

    # 计算CI (Correlation Index)
    if len(y_true_denorm) > 1:
        ci_corr, _ = pearsonr(y_true_denorm, y_pred_denorm)
        ci = float(ci_corr)
    else:
        ci = 0.0

    # ==================== 计算峰值指标 ====================
    # 重新组织数据为样本级别（保持batch结构）
    y_true_samples = np.concatenate(all_y_true, axis=0)  # (num_samples, seq_len, 1)
    y_pred_samples = np.concatenate(all_y_pred, axis=0)  # (num_samples, seq_len, 1)
    
    # 反归一化每个样本
    y_true_samples_denorm = y_true_samples * base_dataset.y_std + base_dataset.y_mean  # (num_samples, seq_len, 1)
    y_pred_samples_denorm = y_pred_samples * base_dataset.y_std + base_dataset.y_mean  # (num_samples, seq_len, 1)
    
    # 计算每个样本的峰值（绝对值最大，转换为mm）
    peak_true = []
    peak_pred = []
    
    for i in range(y_true_samples_denorm.shape[0]):
        # 计算每个样本的峰值（绝对值最大）
        peak_t = np.abs(y_true_samples_denorm[i]).max() * 1000  # 转换为mm
        peak_p = np.abs(y_pred_samples_denorm[i]).max() * 1000  # 转换为mm
        peak_true.append(peak_t)
        peak_pred.append(peak_p)
    
    # 计算峰值RMSE
    if len(peak_true) > 1:
        peak_rmse = np.sqrt(np.mean((np.array(peak_true) - np.array(peak_pred))**2))
    else:
        peak_rmse = 0.0

    metrics = {
        'loss': avg_loss,
        'mse': mse,
        'rmse': rmse,
        'mae': mae,
        'r2': r2,
        'ci': ci,
        'peak_rmse_mm': peak_rmse
    }

    return metrics


# ==================== 主训练流程 ====================
def main():
    print("\n" + "=" * 60)
    print("改进版 LSTM 模型训练 - 纯 MSE 版本")
    print("=" * 60)

    # 数据路径（使用增强后的数据）
    data_dir = data_augmented_dir()

    # 如果增强数据不存在，使用原始数据
    if not data_dir.exists():
        print(f"警告: 增强数据目录不存在，使用原始数据")
        data_dir = data_augmented_dir()  # fixed2000 fallback removed in release; use CPENG_DATA_DIR

    train_x_dir = data_dir / 'train' / 'X'
    train_y_dir = data_dir / 'train' / 'Y'
    test_x_dir = data_dir / 'test' / 'X'
    test_y_dir = data_dir / 'test' / 'Y'

    # 输出目录（MSE 专用）
    current_dir = Path(__file__).parent
    output_dir = REPO_ROOT / 'checkpoints' / 'M1'
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n输出目录: {output_dir}")

    # 先加载所有训练数据
    full_train_dataset = SeismicDataset(train_x_dir, train_y_dir, normalize=True)
    test_dataset = SeismicDataset(test_x_dir, test_y_dir, normalize=True)

    # 使用训练集的归一化参数来归一化测试集
    test_dataset.x_mean = full_train_dataset.x_mean
    test_dataset.x_std = full_train_dataset.x_std
    test_dataset.y_mean = full_train_dataset.y_mean
    test_dataset.y_std = full_train_dataset.y_std

    # 按地震动名称分组划分训练集和验证集
    print("\n按地震动分组划分训练集和验证集...")

    def extract_motion_name(file_path):
        """从文件路径提取地震动名称"""
        name = file_path.stem.replace('_X', '').replace('_time', '')
        if '_aug' in name:
            name = name.split('_aug')[0]
        if '_0p' in name:
            return name.split('_0p')[0]
        return None

    # 按地震动分组
    motion_groups = defaultdict(list)
    for i, (x_file, y_file) in enumerate(full_train_dataset.samples):
        motion_name = extract_motion_name(x_file)
        if motion_name:
            motion_groups[motion_name].append(i)

    # 列出所有地震动（排除增强样本）
    all_motions = sorted([m for m in motion_groups.keys() if m and not m.startswith('aug')])
    print(f"  训练集中共有 {len(all_motions)} 个地震动（原始）")

    # 选择验证集地震动（从前4个）
    val_motions = all_motions[:4]
    train_motions = all_motions[4:]

    print(f"  验证集地震动 ({len(val_motions)} 个): {val_motions}")
    print(f"  训练集地震动 ({len(train_motions)} 个): {train_motions}")

    # 创建训练集和验证集的索引
    train_indices = []
    val_indices = []

    for motion_name in train_motions:
        train_indices.extend(motion_groups[motion_name])

    for motion_name in val_motions:
        val_indices.extend(motion_groups[motion_name])

    print(f"\n  最终划分:")
    print(f"    训练集样本数: {len(train_indices)} 个")
    print(f"    验证集样本数: {len(val_indices)} 个")
    print(f"    测试集样本数: {len(test_dataset)} 个")

    # 创建子数据集
    train_dataset = torch.utils.data.Subset(full_train_dataset, train_indices)
    val_dataset = torch.utils.data.Subset(full_train_dataset, val_indices)

    # 创建数据加载器
    train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=8, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_dataset, batch_size=8, shuffle=False, num_workers=0)

    # 读取最佳超参数
    hyperopt_dir = hyperparams_path().parent
    if not (hyperopt_dir / 'best_hyperparameters.json').exists():
        raise FileNotFoundError(
            f"\n未找到最佳超参数文件: {hyperopt_dir / 'best_hyperparameters.json'}\n"
            f"请先准备超参数文件，或在脚本中手动设置 best_hyperparams 后再运行。"
        )

    print("\n读取超参数调优得到的最佳超参数...")
    with open(hyperopt_dir / 'best_hyperparameters.json', 'r', encoding='utf-8') as f:
        best_config = json.load(f)
    best_hyperparams = best_config['best_hyperparameters']
    print("  已加载最佳超参数")

    # 创建模型（使用最佳超参数）
    print("\n创建改进版LSTM模型（使用最佳超参数，纯 MSE 版本）...")
    print(f"  超参数: hidden_dim={best_hyperparams['hidden_dim']}, "
          f"num_layers={best_hyperparams['num_layers']}, "
          f"dropout={best_hyperparams['dropout']}, "
          f"bidirectional={best_hyperparams['bidirectional']}")
    model = ImprovedLSTM(
        input_dim=1,
        hidden_dim=best_hyperparams['hidden_dim'],
        num_layers=best_hyperparams['num_layers'],
        output_dim=1,
        dropout=best_hyperparams['dropout'],
        bidirectional=best_hyperparams['bidirectional']
    ).to(device)

    # 计算模型参数量
    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"模型参数量: {total_params:,} 个")
    print(f"参数/样本比: {total_params / len(train_indices):.1f}:1")

    # 使用纯 MSE 损失
    print("\n使用纯 MSE 损失函数 (nn.MSELoss)...")
    criterion = nn.MSELoss()

    # 损失函数和优化器（使用最佳超参数）
    optimizer = optim.Adam(
        model.parameters(),
        lr=best_hyperparams['learning_rate'],
        weight_decay=best_hyperparams['weight_decay']
    )

    # 学习率调度器（仍然基于 CI）
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode='max',
        factor=0.7,
        patience=30,
        verbose=True
    )

    # 训练循环
    print("\n开始训练...")
    print("优化策略：")
    print("  - 使用CI作为early stopping依据，patience=90，目标CI>0.9")
    print("  - 学习率调度基于CI（而不是loss），当CI不再提升时降低学习率")
    print("  - 学习率衰减更温和（factor=0.7, patience=30）")
    num_epochs = 2000
    best_val_ci = -float('inf')
    best_val_loss = float('inf')
    patience = 90
    patience_counter = 0

    train_losses = []
    val_losses = []
    test_losses = []
    val_r2_scores = []
    test_r2_scores = []
    val_ci_scores = []
    test_ci_scores = []
    val_peak_rmse_scores = []
    test_peak_rmse_scores = []

    start_time = time.time()

    for epoch in range(num_epochs):
        # 训练
        train_loss = train_epoch(model, train_loader, criterion, optimizer, device, full_train_dataset)

        # 验证
        val_metrics = evaluate(model, val_loader, criterion, device, full_train_dataset)

        # 测试
        test_metrics = evaluate(model, test_loader, criterion, device, full_train_dataset)

        # 记录
        train_losses.append(train_loss)
        val_losses.append(val_metrics['loss'])
        test_losses.append(test_metrics['loss'])
        val_r2_scores.append(val_metrics['r2'])
        test_r2_scores.append(test_metrics['r2'])
        val_ci_scores.append(val_metrics['ci'])
        test_ci_scores.append(test_metrics['ci'])
        val_peak_rmse_scores.append(val_metrics['peak_rmse_mm'])
        test_peak_rmse_scores.append(test_metrics['peak_rmse_mm'])

        # 学习率调度（基于 CI）
        scheduler.step(val_metrics['ci'])

        # 打印进度
        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"\nEpoch [{epoch + 1}/{num_epochs}]")
            print(f"  Train Loss: {train_loss:.6f}")
            print(f"  Val Loss: {val_metrics['loss']:.6f} | R2: {val_metrics['r2']:.6f} | CI: {val_metrics['ci']:.6f} | RMSE: {val_metrics['rmse']:.4f} mm | MAE: {val_metrics['mae']:.4f} mm")
            print(f"  Val Peak RMSE: {val_metrics['peak_rmse_mm']:.2f} mm")
            print(f"  Test Loss: {test_metrics['loss']:.6f} | R2: {test_metrics['r2']:.6f} | CI: {test_metrics['ci']:.6f} | RMSE: {test_metrics['rmse']:.4f} mm | MAE: {test_metrics['mae']:.4f} mm")
            print(f"  Test Peak RMSE: {test_metrics['peak_rmse_mm']:.2f} mm")
            print(f"  当前LR: {optimizer.param_groups[0]['lr']:.2e}")

        # 保存最佳模型（使用 CI）
        if val_metrics['ci'] > best_val_ci:
            best_val_ci = val_metrics['ci']
            best_val_loss = val_metrics['loss']
            torch.save(model.state_dict(), output_dir / 'best_model.pth')
            patience_counter = 0
            print(f"  -> 保存最佳模型 (val_ci={best_val_ci:.6f}, val_loss={best_val_loss:.6f})")
        else:
            patience_counter += 1

        # Early stopping
        if patience_counter >= patience:
            print(f"\nEarly stopping at epoch {epoch + 1} (CI未提升已{patience}个epoch)")
            print(f"  最佳验证集CI: {best_val_ci:.6f}")
            break

    train_time = time.time() - start_time
    print(f"\n训练完成！总耗时: {train_time:.1f} 秒")

    # 加载最佳模型并最终评估
    print("\n加载最佳模型进行最终评估...")
    model.load_state_dict(torch.load(output_dir / 'best_model.pth', weights_only=False))

    final_val_metrics = evaluate(model, val_loader, criterion, device, full_train_dataset)
    final_test_metrics = evaluate(model, test_loader, criterion, device, full_train_dataset)

    print("\n" + "=" * 60)
    print("最终评估结果:")
    print("=" * 60)
    print(f"\n验证集:")
    print(f"  Loss: {final_val_metrics['loss']:.6f}")
    print(f"  RMSE: {final_val_metrics['rmse']:.4f} mm")
    print(f"  MAE: {final_val_metrics['mae']:.4f} mm")
    print(f"  R2: {final_val_metrics['r2']:.6f}")
    print(f"  CI: {final_val_metrics['ci']:.6f}")
    print(f"  Peak RMSE: {final_val_metrics['peak_rmse_mm']:.2f} mm")

    print(f"\n测试集:")
    print(f"  Loss: {final_test_metrics['loss']:.6f}")
    print(f"  RMSE: {final_test_metrics['rmse']:.4f} mm")
    print(f"  MAE: {final_test_metrics['mae']:.4f} mm")
    print(f"  R2: {final_test_metrics['r2']:.6f}")
    print(f"  CI: {final_test_metrics['ci']:.6f}")
    print(f"  Peak RMSE: {final_test_metrics['peak_rmse_mm']:.2f} mm")

    # 保存训练结果
    actual_hidden_dim = getattr(model.lstm, 'hidden_size', None)
    actual_num_layers = getattr(model.lstm, 'num_layers', None)
    actual_bidirectional = getattr(model.lstm, 'bidirectional', None)
    actual_dropout = None
    if isinstance(model.fc, nn.Sequential) and len(model.fc) > 0 and isinstance(model.fc[0], nn.Dropout):
        actual_dropout = model.fc[0].p
    elif hasattr(model, 'dropout'):
        actual_dropout = getattr(model, 'dropout')

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
            'hidden_dim': int(actual_hidden_dim) if actual_hidden_dim is not None else None,
            'num_layers': int(actual_num_layers) if actual_num_layers is not None else None,
            'dropout': float(actual_dropout) if actual_dropout is not None else None,
            'bidirectional': bool(actual_bidirectional) if actual_bidirectional is not None else None,
            'total_params': total_params
        },
        'loss_config': {
            'type': 'mse',
            'mse_weight': 1.0
        },
        'hyperparameters_used': best_hyperparams,
        'normalization': {
            'x_mean': float(full_train_dataset.x_mean),
            'x_std': float(full_train_dataset.x_std),
            'y_mean': float(full_train_dataset.y_mean),
            'y_std': float(full_train_dataset.y_std)
        },
        'training_time_seconds': train_time
    }

    with open(output_dir / 'training_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # 绘制训练曲线
    fig, axes = plt.subplots(3, 2, figsize=(16, 15))

    # Loss曲线
    ax1 = axes[0, 0]
    ax1.plot(train_losses, label='Train Loss', linewidth=2)
    ax1.plot(val_losses, label='Val Loss', linewidth=2)
    ax1.plot(test_losses, label='Test Loss', linewidth=2)
    ax1.set_xlabel('Epoch')
    ax1.set_ylabel('Loss')
    ax1.set_title('Training, Validation and Test Loss')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # R2曲线
    ax2 = axes[0, 1]
    ax2.plot(val_r2_scores, label='Val R2 Score', linewidth=2)
    ax2.plot(test_r2_scores, label='Test R2 Score', linewidth=2)
    ax2.set_xlabel('Epoch')
    ax2.set_ylabel('R2 Score')
    ax2.set_title('Validation and Test R2 Score')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # CI曲线
    ax3 = axes[1, 0]
    ax3.plot(val_ci_scores, label='Val CI Score', linewidth=2, color='green')
    ax3.plot(test_ci_scores, label='Test CI Score', linewidth=2, color='orange')
    ax3.set_xlabel('Epoch')
    ax3.set_ylabel('CI (Correlation Index)')
    ax3.set_title('Validation and Test CI Score')
    ax3.axhline(y=0, color='black', linestyle='--', linewidth=0.8, alpha=0.5)
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # Peak RMSE曲线
    ax4 = axes[1, 1]
    ax4.plot(val_peak_rmse_scores, label='Val Peak RMSE', linewidth=2, color='purple')
    ax4.plot(test_peak_rmse_scores, label='Test Peak RMSE', linewidth=2, color='brown')
    ax4.set_xlabel('Epoch')
    ax4.set_ylabel('Peak RMSE (mm)')
    ax4.set_title('Validation and Test Peak RMSE')
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    # R2 vs CI 对比
    ax5 = axes[2, 0]
    ax5.plot(val_r2_scores, val_ci_scores, label='Val', marker='o', markersize=2, linewidth=1, alpha=0.6)
    ax5.plot(test_r2_scores, test_ci_scores, label='Test', marker='s', markersize=2, linewidth=1, alpha=0.6)
    ax5.set_xlabel('R2 Score')
    ax5.set_ylabel('CI Score')
    ax5.set_title('R2 vs CI Relationship')
    ax5.legend()
    ax5.grid(True, alpha=0.3)

    # 空白（保留布局）
    ax6 = axes[2, 1]
    ax6.axis('off')

    plt.tight_layout()
    plt.savefig(output_dir / 'training_curves.png', dpi=300, bbox_inches='tight')
    print(f"\n训练曲线已保存: {output_dir / 'training_curves.png'}")

    print(f"训练结果已保存: {output_dir / 'training_results.json'}")
    print(f"最佳模型已保存: {output_dir / 'best_model.pth'}")

    print("\n训练完成！")


if __name__ == "__main__":
    main()


