#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据增强脚本 - 用于增加训练样本数量
包含：时间平移、幅值缩放、添加噪声
"""
import numpy as np
from pathlib import Path
import pandas as pd
import shutil


# --- release path bootstrap (no machine-specific absolute paths) ---
from pathlib import Path as _Path
import sys as _sys
_CODE_DIR = _Path(__file__).resolve().parents[1]  # .../code
if str(_CODE_DIR) not in _sys.path:
    _sys.path.insert(0, str(_CODE_DIR))
from paths import data_augmented_dir, hyperparams_path, ensure_models_on_path, REPO_ROOT
ensure_models_on_path()
# --- end bootstrap ---
def time_shift(data, shift_steps):
    """
    时间平移：将数据前后平移
    
    Args:
        data: 1D numpy array, 时间序列数据
        shift_steps: 平移步数（正数向后，负数向前）
    
    Returns:
        平移后的数据（补零填充）
    """
    if shift_steps == 0:
        return data.copy()
    
    shifted = np.zeros_like(data)
    if shift_steps > 0:
        # 向后平移
        shifted[shift_steps:] = data[:-shift_steps]
    else:
        # 向前平移
        shifted[:shift_steps] = data[-shift_steps:]
    
    return shifted

def amplitude_scale(data, scale_factor):
    """
    幅值缩放：将数据乘以缩放因子
    
    Args:
        data: 1D numpy array
        scale_factor: 缩放因子（如1.05表示放大5%）
    
    Returns:
        缩放后的数据
    """
    return data * scale_factor

def add_noise(data, noise_level=0.02):
    """
    添加高斯噪声
    
    Args:
        data: 1D numpy array
        noise_level: 噪声水平（相对于数据标准差的比例）
    
    Returns:
        添加噪声后的数据
    """
    std = np.std(data)
    noise = np.random.normal(0, std * noise_level, size=data.shape)
    return data + noise

def augment_sample(x_data, y_data, augment_config):
    """
    对单个样本进行增强
    
    Args:
        x_data: 输入地震动数据 (1D array)
        y_data: 输出位移数据 (1D array)
        augment_config: 增强配置字典
    
    Returns:
        (augmented_x, augmented_y, augmentation_info)
    """
    aug_x = x_data.copy()
    aug_y = y_data.copy()
    
    aug_info = []
    
    # 1. 时间平移
    if augment_config.get('time_shift', False):
        # 随机平移 -50到50步（-1秒到1秒）
        shift_steps = np.random.randint(-50, 51)
        if shift_steps != 0:
            aug_x = time_shift(aug_x, shift_steps)
            aug_y = time_shift(aug_y, shift_steps)
            aug_info.append(f"shift_{shift_steps}")
    
    # 2. 幅值缩放
    if augment_config.get('amplitude_scale', False):
        # 随机缩放 ±5-10%
        scale_factor = np.random.uniform(0.90, 1.10)
        aug_x = amplitude_scale(aug_x, scale_factor)
        aug_y = amplitude_scale(aug_y, scale_factor)
        aug_info.append(f"scale_{scale_factor:.3f}")
    
    # 3. 添加噪声
    if augment_config.get('add_noise', False):
        # 噪声水平：1-3%
        noise_level = np.random.uniform(0.01, 0.03)
        aug_x = add_noise(aug_x, noise_level)
        aug_y = add_noise(aug_y, noise_level)
        aug_info.append(f"noise_{noise_level:.3f}")
    
    aug_info_str = "_".join(aug_info) if aug_info else "original"
    
    return aug_x, aug_y, aug_info_str

def augment_dataset(input_dir, output_dir, augment_config, augment_factor=3):
    """
    对整个数据集进行增强
    
    Args:
        input_dir: 输入数据目录（包含train/X, train/Y, test/X, test/Y）
        output_dir: 输出数据目录
        augment_config: 增强配置
        augment_factor: 每个原始样本生成多少个增强样本
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    
    # 只增强训练集，不增强测试集
    train_x_dir = input_dir / 'train' / 'X'
    train_y_dir = input_dir / 'train' / 'Y'
    test_x_dir = input_dir / 'test' / 'X'
    test_y_dir = input_dir / 'test' / 'Y'
    
    # 输出目录
    output_train_x_dir = output_dir / 'train' / 'X'
    output_train_y_dir = output_dir / 'train' / 'Y'
    output_test_x_dir = output_dir / 'test' / 'X'
    output_test_y_dir = output_dir / 'test' / 'Y'
    
    # 创建输出目录
    output_train_x_dir.mkdir(parents=True, exist_ok=True)
    output_train_y_dir.mkdir(parents=True, exist_ok=True)
    output_test_x_dir.mkdir(parents=True, exist_ok=True)
    output_test_y_dir.mkdir(parents=True, exist_ok=True)
    
    # 加载训练集元数据
    train_meta_path = input_dir / 'train_metadata.csv'
    if train_meta_path.exists():
        train_meta = pd.read_csv(train_meta_path)
    else:
        train_meta = None
    
    # 处理训练集
    print("处理训练集...")
    x_files = sorted(list(train_x_dir.glob("*_X.txt")))
    
    augmented_meta = []
    augmented_count = 0
    
    for x_file in x_files:
        base_name = x_file.stem.replace('_X', '')
        y_file = train_y_dir / f"{base_name}_Y.txt"
        
        if not y_file.exists():
            continue
        
        # 读取原始数据
        x_data = np.loadtxt(x_file).astype(np.float32)
        y_data = np.loadtxt(y_file).astype(np.float32)
        
        # 保存原始样本（不增强）
        shutil.copy(x_file, output_train_x_dir / f"{base_name}_X.txt")
        shutil.copy(y_file, output_train_y_dir / f"{base_name}_Y.txt")
        
        if train_meta is not None:
            orig_row = train_meta[train_meta['case_id'] == base_name]
            if not orig_row.empty:
                augmented_meta.append(orig_row.iloc[0].to_dict())
        
        # 生成增强样本
        for aug_idx in range(augment_factor):
            aug_x, aug_y, aug_info = augment_sample(x_data, y_data, augment_config)
            
            aug_name = f"{base_name}_aug{aug_idx+1}_{aug_info}"
            
            # 保存增强样本
            np.savetxt(output_train_x_dir / f"{aug_name}_X.txt", aug_x, fmt='%.8g')
            np.savetxt(output_train_y_dir / f"{aug_name}_Y.txt", aug_y, fmt='%.8g')
            
            # 记录元数据
            if train_meta is not None:
                aug_row = orig_row.iloc[0].copy() if not orig_row.empty else {}
                aug_row['case_id'] = aug_name
                aug_row['augmentation'] = aug_info
                augmented_meta.append(aug_row)
            
            augmented_count += 1
        
        if (len(x_files) > 0) and ((x_files.index(x_file) + 1) % 10 == 0):
            print(f"  已处理 {x_files.index(x_file) + 1}/{len(x_files)} 个原始样本...")
    
    print(f"训练集增强完成：原始 {len(x_files)} 个样本 → 增强后 {len(x_files) + augmented_count} 个样本")
    
    # 保存增强后的元数据
    if train_meta is not None and augmented_meta:
        aug_meta_df = pd.DataFrame(augmented_meta)
        aug_meta_df.to_csv(output_dir / 'train_metadata_augmented.csv', index=False)
        print(f"增强元数据已保存: {output_dir / 'train_metadata_augmented.csv'}")
    
    # 复制测试集（不增强）
    print("\n复制测试集（不增强）...")
    test_x_files = sorted(list(test_x_dir.glob("*_X.txt")))
    test_count = 0
    
    for x_file in test_x_files:
        base_name = x_file.stem.replace('_X', '')
        y_file = test_y_dir / f"{base_name}_Y.txt"
        
        if y_file.exists():
            shutil.copy(x_file, output_test_x_dir / f"{base_name}_X.txt")
            shutil.copy(y_file, output_test_y_dir / f"{base_name}_Y.txt")
            test_count += 1
    
    print(f"测试集复制完成：{test_count} 个样本")
    
    # 复制测试集元数据
    test_meta_path = input_dir / 'test_metadata.csv'
    if test_meta_path.exists():
        shutil.copy(test_meta_path, output_dir / 'test_metadata.csv')
        print(f"测试集元数据已复制")
    
    print("\n数据增强完成！")
    print(f"输出目录: {output_dir}")
    print(f"训练集: {len(x_files)} 原始 + {augmented_count} 增强 = {len(x_files) + augmented_count} 个样本")
    print(f"测试集: {test_count} 个样本")

def main():
    """主函数"""
    print("="*80)
    print("数据增强脚本")
    print("="*80)
    
    # 配置
    input_dir = data_augmented_dir()  # fixed2000 fallback removed in release; use CPENG_DATA_DIR
    output_dir = data_augmented_dir()
    
    # 增强配置
    augment_config = {
        'time_shift': True,      # 启用时间平移
        'amplitude_scale': True,  # 启用幅值缩放
        'add_noise': True        # 启用噪声添加
    }
    
    # 每个原始样本生成3个增强样本
    augment_factor = 3
    
    print(f"\n输入目录: {input_dir}")
    print(f"输出目录: {output_dir}")
    print(f"\n增强配置:")
    print(f"  时间平移: {augment_config['time_shift']}")
    print(f"  幅值缩放: {augment_config['amplitude_scale']}")
    print(f"  添加噪声: {augment_config['add_noise']}")
    print(f"  增强倍数: {augment_factor} (每个原始样本生成 {augment_factor} 个增强样本)")
    print(f"\n预期结果: 40 个训练样本 → {40 * (1 + augment_factor)} = {40 * (1 + augment_factor)} 个样本")
    
    # 执行增强
    augment_dataset(input_dir, output_dir, augment_config, augment_factor)
    
    print("\n" + "="*80)
    print("数据增强完成！可以开始训练改进的模型了")
    print("="*80)

if __name__ == "__main__":
    main()





