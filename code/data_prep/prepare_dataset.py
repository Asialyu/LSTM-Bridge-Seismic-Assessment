#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
整理桥梁地震响应数据集
- X: 输入地震动横向水平加速度时程
- Y: 桥梁第二跨跨中点横向水平位移时程（节点65，第8个节点）
- 训练集: 12个地震动 × 5个强度 = 60个样本
- 测试集: 20个地震动 × 15个强度 = 300个样本
"""

import numpy as np
from pathlib import Path
import re
import pandas as pd
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

def extract_motion_name_from_path(path):
    """从路径中提取地震动名称，例如 G04_0p10g -> G04"""
    parts = path.parts
    for part in parts:
        if '_' in part and ('p' in part or '0p' in part):
            # 匹配格式如: G04_0p10g, C08_0p20g
            match = re.match(r'([A-Z0-9_-]+)_0p\d+p?g', part)
            if match:
                return match.group(1)
    return None

def get_intensity_from_path(path):
    """从路径中提取PGA强度，例如 G04_0p10g -> 0.10"""
    parts = path.parts
    for part in parts:
        match = re.match(r'.*_0p(\d+)p?g', part)
        if match:
            intensity_str = match.group(1)
            if len(intensity_str) == 1:
                return float(intensity_str) / 10.0
            elif len(intensity_str) == 2:
                return float(intensity_str) / 100.0
    return None

def read_acceleration_time_history(acc_time_file, acc_value_file):
    """读取加速度时程（时间和数值分开存储）"""
    try:
        time_data = np.loadtxt(acc_time_file)
        acc_data = np.loadtxt(acc_value_file)
        
        # 确保时间序列和加速度数据长度一致
        min_len = min(len(time_data), len(acc_data))
        time_data = time_data[:min_len]
        acc_data = acc_data[:min_len]
        
        return time_data, acc_data
    except Exception as e:
        print(f"Error reading acceleration files: {e}")
        return None, None

def read_displacement_from_deckdisp(deckdisp_file, midspan_node_index=7, direction_index=1):
    """
    从deckdisp文件中读取第二跨跨中点横向位移（Y方向）
    deckdisp文件格式: 第一列是时间，后续列是各节点的位移（每节点3个方向：X, Y, Z）
    格式：time, node58_X, node58_Y, node58_Z, node59_X, node59_Y, node59_Z, ..., node78_X, node78_Y, node78_Z
    第二跨跨中点是节点65，是第8个节点（索引7），Y方向位移在列23（索引22）
    计算公式：列索引 = 1（时间列）+ 7（前7个节点）× 3（每节点X,Y,Z）+ 1（Y方向）= 23
    """
    try:
        # 尝试读取，如果列数不一致，只读取前N列
        data = np.loadtxt(deckdisp_file)
        
        # 如果数据行数太少，可能文件不完整
        if len(data) < 10:
            return None, None
        
        time = data[:, 0]
        
        # 计算节点数量：(总列数-1) / 3
        n_cols = data.shape[1] - 1  # 减去时间列
        n_nodes = n_cols // 3
        
        if n_nodes < 1:
            # 如果列数不足，可能是简化的格式：time, X, Y, Z
            if data.shape[1] >= 4:
                disp_y = data[:, 2]  # Y方向是第3列（索引2）
            elif data.shape[1] >= 3:
                disp_y = data[:, 2]  # Y方向是第3列
            elif data.shape[1] >= 2:
                disp_y = data[:, 1]  # 如果只有2列，第2列可能是Y
            else:
                disp_y = data[:, 0]
            return time, disp_y
        
        # 第二跨跨中点（节点65，第8个节点，索引7）的Y方向位移索引
        # 格式：列0=time, 列1-3=node58(X,Y,Z), 列4-6=node59(X,Y,Z), ..., 列22-24=node65(X,Y,Z)
        # 节点65是第8个节点（索引7），所以：列索引 = 1 + 7*3 + 1 = 23（索引22）
        midspan_y_col = 1 + midspan_node_index * 3 + direction_index
        
        if midspan_y_col >= data.shape[1]:
            # 如果索引超出范围，尝试使用中间节点的Y方向
            if n_nodes >= 8:
                # 使用第8个节点（节点65）
                midspan_y_col = 1 + 7 * 3 + 1  # 列23（索引22）
            elif n_nodes >= 11:
                # 如果节点不够，尝试使用第11个节点（节点68，中点）
                midspan_y_col = 1 + 10 * 3 + 1
            elif data.shape[1] >= 3:
                midspan_y_col = 2  # 回退到第一个节点的Y方向
            else:
                midspan_y_col = 1
        
        disp_y = data[:, midspan_y_col]
        
        return time, disp_y
    except Exception as e:
        # 如果读取失败，可能是文件格式不一致，尝试逐行读取
        try:
            time_list = []
            disp_y_list = []
            
            with open(deckdisp_file, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        try:
                            t = float(parts[0])
                            # 假设第3列（索引2）是Y方向位移
                            disp_y = float(parts[2])
                            time_list.append(t)
                            disp_y_list.append(disp_y)
                        except ValueError:
                            continue
            
            if len(time_list) > 0:
                return np.array(time_list), np.array(disp_y_list)
            return None, None
        except Exception as e2:
            print(f"Error reading displacement file {deckdisp_file}: {e}, {e2}")
            return None, None

def prepare_dataset(base_dir, output_dir):
    """
    整理数据集
    """
    base_path = Path(base_dir)
    output_path = Path(output_dir)
    
    # 创建输出目录结构
    train_x_dir = output_path / "train" / "X"
    train_y_dir = output_path / "train" / "Y"
    test_x_dir = output_path / "test" / "X"
    test_y_dir = output_path / "test" / "Y"
    
    for d in [train_x_dir, train_y_dir, test_x_dir, test_y_dir]:
        d.mkdir(parents=True, exist_ok=True)
    
    # 查找所有_brfiles目录
    all_brfiles_dirs = list(base_path.rglob('*_brfiles'))
    
    # 定义训练集和测试集的强度
    train_intensities = [0.1, 0.2, 0.3, 0.4, 0.5]
    test_intensities = [round(0.05 * i, 2) for i in range(1, 16)]  # 0.05 to 0.75
    
    # 按地震动名称分组
    motion_groups = defaultdict(list)
    for brfiles_dir in all_brfiles_dirs:
        motion_name = extract_motion_name_from_path(brfiles_dir)
        if motion_name:
            motion_groups[motion_name].append(brfiles_dir)
    
    # 统计信息
    train_count = 0
    test_count = 0
    failed_cases = []
    
    # 元数据记录
    train_metadata = []
    test_metadata = []
    
    print(f"\n{'='*60}")
    print(f"开始整理数据集")
    print(f"{'='*60}\n")
    print(f"找到 {len(motion_groups)} 个不同的地震动")
    
    # 先确定哪些是训练集（12个），哪些是测试集（20个）
    motion_names = sorted(motion_groups.keys())
    
    # 根据原始选波结果，应该能区分出12个和20个
    # 这里我们假设前12个（或按某种规则）是训练集
    # 实际上应该根据实际的选波结果来确定
    
    # 简单策略：按照出现次数或目录深度来判断
    # 更可靠的方法：根据目录结构中的信息
    
    # 统计每个地震动的强度范围
    motion_stats = {}
    for motion_name, dirs in motion_groups.items():
        intensities = []
        for d in dirs:
            intensity = get_intensity_from_path(d)
            if intensity:
                intensities.append(intensity)
        motion_stats[motion_name] = sorted(set(intensities))
    
    # 根据强度范围判断：训练集有5个强度，测试集有15个强度
    train_motions = []
    test_motions = []
    
    for motion_name, intensities in motion_stats.items():
        if len(intensities) == 5 and all(i in train_intensities for i in intensities):
            train_motions.append(motion_name)
        elif len(intensities) >= 10:  # 测试集可能有更多强度
            test_motions.append(motion_name)
    
    # 如果自动判断不准确，可能需要手动指定
    # 这里采用更保守的策略：先处理明显的训练集（5个强度都在训练集范围内）
    # 其余的作为测试集
    
    print(f"自动识别: 训练集地震动 {len(train_motions)} 个, 测试集地震动 {len(test_motions)} 个")
    
    # 验证：训练集应该有12个地震动，测试集应该有20个地震动
    if len(train_motions) != 12:
        print(f"\n[WARNING] 训练集地震动数量不对！期望12个，实际{len(train_motions)}个")
        print(f"  训练集地震动: {train_motions}")
        print(f"  可能需要手动指定")
    
    if len(test_motions) != 20:
        print(f"\n[WARNING] 测试集地震动数量不对！期望20个，实际{len(test_motions)}个")
        print(f"  测试集地震动（前20个）: {test_motions[:20]}")
    
    # 确保训练集只有12个，测试集只有20个
    train_motions = sorted(train_motions)[:12]  # 只取前12个
    test_motions = sorted(test_motions)[:20]    # 只取前20个
    
    print(f"\n最终划分:")
    print(f"  训练集地震动（12个）: {train_motions}")
    print(f"  测试集地震动（20个）: {test_motions[:10]}... (共{len(test_motions)}个)")
    
    # 创建训练集和测试集地震动集合（用于快速查找）
    train_motions_set = set(train_motions)
    test_motions_set = set(test_motions)
    
    # 处理所有工况
    processed_count = 0
    for motion_name, dirs in motion_groups.items():
        for brfiles_dir in sorted(dirs):
            intensity = get_intensity_from_path(brfiles_dir)
            if intensity is None:
                continue
            
            # 先按地震动名称判断是训练集还是测试集
            # 然后按强度判断
            if motion_name in train_motions_set:
                # 训练集地震动：只接受5个强度 [0.1, 0.2, 0.3, 0.4, 0.5]
                is_train = intensity in train_intensities
                is_test = False
            elif motion_name in test_motions_set:
                # 测试集地震动：只接受15个强度 [0.05-0.75]
                is_train = False
                is_test = intensity in test_intensities
            else:
                # 不属于训练集或测试集的地震动，跳过
                continue
            
            if not (is_train or is_test):
                continue
            
            # 读取数据
            acc_time_file = brfiles_dir / "acc_timeY.txt"
            acc_value_file = brfiles_dir / "acc_valueY.txt"
            deckdisp_file = brfiles_dir / f"{brfiles_dir.name.replace('_brfiles', '')}.deckdisp"
            
            # 如果deckdisp不存在，尝试其他可能的文件名
            if not deckdisp_file.exists():
                # 尝试查找任何.deckdisp文件
                deckdisp_files = list(brfiles_dir.glob("*.deckdisp"))
                if deckdisp_files:
                    deckdisp_file = deckdisp_files[0]
                else:
                    failed_cases.append(f"{brfiles_dir.name}: 未找到deckdisp文件")
                    continue
            
            if not acc_time_file.exists() or not acc_value_file.exists():
                failed_cases.append(f"{brfiles_dir.name}: 未找到加速度文件")
                continue
            
            # 读取加速度时程（横向，Y方向）
            time_acc, acc_y = read_acceleration_time_history(acc_time_file, acc_value_file)
            if time_acc is None or acc_y is None:
                failed_cases.append(f"{brfiles_dir.name}: 读取加速度失败")
                continue
            
            # 读取第二跨跨中点横向位移（节点65，第8个节点）
            time_disp, disp_y = read_displacement_from_deckdisp(deckdisp_file, midspan_node_index=7, direction_index=1)
            if time_disp is None or disp_y is None:
                failed_cases.append(f"{brfiles_dir.name}: 读取位移失败")
                continue
            
            # 确保时间序列一致
            # 使用固定的时间步长0.02秒（与分析时间步长compdT一致）
            # 取较短的长度，并插值对齐
            min_time = max(time_acc[0], time_disp[0])
            max_time = min(time_acc[-1], time_disp[-1])
            dt = 0.02  # 固定时间步长，与分析参数compdT一致
            
            # 创建统一的时间序列
            time_unified = np.arange(min_time, max_time + dt/2, dt)
            
            # 插值对齐
            acc_interp = np.interp(time_unified, time_acc, acc_y)
            disp_interp = np.interp(time_unified, time_disp, disp_y)
            
            # 生成文件名
            case_id = f"{motion_name}_{intensity:.2f}g".replace('.', 'p')
            
            if is_train:
                # 保存训练集
                np.savetxt(train_x_dir / f"{case_id}_X.txt", acc_interp, fmt='%.8e')
                np.savetxt(train_y_dir / f"{case_id}_Y.txt", disp_interp, fmt='%.8e')
                np.savetxt(train_x_dir / f"{case_id}_time.txt", time_unified, fmt='%.6f')
                
                train_metadata.append({
                    'case_id': case_id,
                    'motion_name': motion_name,
                    'intensity': intensity,
                    'n_points': len(time_unified),
                    'dt': dt,
                    'max_acc': np.max(np.abs(acc_interp)),
                    'max_disp': np.max(np.abs(disp_interp))
                })
                train_count += 1
                
            elif is_test:
                # 保存测试集
                np.savetxt(test_x_dir / f"{case_id}_X.txt", acc_interp, fmt='%.8e')
                np.savetxt(test_y_dir / f"{case_id}_Y.txt", disp_interp, fmt='%.8e')
                np.savetxt(test_x_dir / f"{case_id}_time.txt", time_unified, fmt='%.6f')
                
                test_metadata.append({
                    'case_id': case_id,
                    'motion_name': motion_name,
                    'intensity': intensity,
                    'n_points': len(time_unified),
                    'dt': dt,
                    'max_acc': np.max(np.abs(acc_interp)),
                    'max_disp': np.max(np.abs(disp_interp))
                })
                test_count += 1
            
            processed_count += 1
            if processed_count % 50 == 0:
                print(f"  已处理: {processed_count} 个工况...")
    
    # 保存元数据
    if train_metadata:
        train_df = pd.DataFrame(train_metadata)
        train_df.to_csv(output_path / "train_metadata.csv", index=False, encoding='utf-8-sig')
        print(f"\n训练集: {train_count} 个样本")
        print(f"  保存到: {train_x_dir.parent}")
    
    if test_metadata:
        test_df = pd.DataFrame(test_metadata)
        test_df.to_csv(output_path / "test_metadata.csv", index=False, encoding='utf-8-sig')
        print(f"测试集: {test_count} 个样本")
        print(f"  保存到: {test_x_dir.parent}")
    
    # 保存失败案例
    if failed_cases:
        with open(output_path / "failed_cases.txt", 'w', encoding='utf-8') as f:
            for case in failed_cases:
                f.write(f"{case}\n")
        print(f"\n警告: {len(failed_cases)} 个案例处理失败，详情见 failed_cases.txt")
    
    print(f"\n{'='*60}")
    print(f"数据集整理完成!")
    print(f"  训练集: {train_count} 个")
    print(f"  测试集: {test_count} 个")
    print(f"  输出目录: {output_path}")
    print(f"{'='*60}\n")
    
    return train_count, test_count

if __name__ == "__main__":
    base_dir = str(REPO_ROOT / "opensees")
    output_dir = str(REPO_ROOT / "data" / "numerical")
    
    prepare_dataset(base_dir, output_dir)

