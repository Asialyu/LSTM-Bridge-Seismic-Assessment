#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
时间注意力模块（Bahdanau Attention）
聚焦地震加速度时程中对跨中位移影响最大的时间步（如地震峰值段）
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np


class SelfAttentionLayer(nn.Module):
    """
    自注意力层 (Self-Attention)
    允许序列中的每个时间步关注序列中的其他所有时间步
    """
    def __init__(self, hidden_dim, num_heads: int = 4, dropout: float = 0.1):
        super(SelfAttentionLayer, self).__init__()
        self.hidden_dim = hidden_dim
        self.num_heads = num_heads

        # PyTorch MultiheadAttention：输入形状 (seq_len, batch, embed_dim)
        self.multihead_attn = nn.MultiheadAttention(
            embed_dim=hidden_dim,
            num_heads=num_heads,
            dropout=dropout,
            batch_first=False  # 使用默认 (seq_len, batch, dim)
        )

        # 残差 + LayerNorm（Transformer 标准配置）
        self.layer_norm = nn.LayerNorm(hidden_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(self, lstm_output: torch.Tensor) -> torch.Tensor:
        """
        Args:
            lstm_output: (batch, seq_len, hidden_dim)
        Returns:
            output: (batch, seq_len, hidden_dim)
        """
        # 调整维度以适配 MultiheadAttention: (seq_len, batch, hidden_dim)
        lstm_output_permuted = lstm_output.permute(1, 0, 2)

        # Self-Attention：Query = Key = Value = lstm_output
        # attn_output: (seq_len, batch, hidden_dim)
        attn_output, attn_weights = self.multihead_attn(
            query=lstm_output_permuted,
            key=lstm_output_permuted,
            value=lstm_output_permuted
        )

        # 残差 + LayerNorm
        attn_output = self.dropout(attn_output)
        # 与输入做残差（同一形状）
        attn_output = self.layer_norm(lstm_output_permuted + attn_output)

        # 调回 (batch, seq_len, hidden_dim)
        output = attn_output.permute(1, 0, 2)
        return output


class ImprovedLSTMWithSelfAttention(nn.Module):
    """
    增强版LSTM模型 - LSTM + Self-Attention
    用自注意力在整个时程上做“上下文聚合”，更加适合 Seq2Seq 全时程回归任务。
    """
    def __init__(self, input_dim=1, hidden_dim=128, num_layers=3, output_dim=1,
                 dropout=0.3, bidirectional=False):
        super(ImprovedLSTMWithSelfAttention, self).__init__()

        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.bidirectional = bidirectional

        # 1. LSTM 编码器（参数与 baseline 一致）
        self.lstm = nn.LSTM(
            input_dim,
            hidden_dim,
            num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=bidirectional
        )

        lstm_output_dim = hidden_dim * 2 if bidirectional else hidden_dim

        # 2. 自注意力层（替代原来的 TimeAttention）
        # num_heads=4：让模型从 4 个“子空间视角”理解时程关系
        self.self_attention = SelfAttentionLayer(
            hidden_dim=lstm_output_dim,
            num_heads=4,
            dropout=dropout
        )

        # 3. 输出层（与 baseline 形状保持一致）
        self.fc = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(lstm_output_dim, output_dim)
        )

    def forward(self, x, peak_indices=None):
        """
        Args:
            x: (batch, seq_len, input_dim) 输入地震动加速度时程
            peak_indices: 为兼容旧接口保留，但在 Self-Attention 版本中不再使用
        Returns:
            output: (batch, seq_len, output_dim) 预测位移时程
        """
        # 1. LSTM 前向
        lstm_out, _ = self.lstm(x)  # (batch, seq_len, hidden_dim)

        # 2. Self-Attention：每个时间步都从整个时程中聚合自己需要的上下文
        attn_out = self.self_attention(lstm_out)  # (batch, seq_len, hidden_dim)

        # 3. 输出预测序列
        output = self.fc(attn_out)  # (batch, seq_len, output_dim)
        return output


class TimeAttention(nn.Module):
    """
    时间注意力机制（Bahdanau Attention）
    关注哪些时间步对位移预测最重要（如地震峰值段）
    
    核心思想：
    - 计算每个时间步的注意力权重（基于LSTM隐藏态与查询向量的相似度）
    - 加权求和得到注意力输出
    - 解决普通LSTM对长时序"均等加权"的缺陷，强化地震峰值等关键时段的特征捕捉
    """
    def __init__(self, hidden_dim):
        """
        Args:
            hidden_dim: LSTM输出隐藏层维度
        """
        super(TimeAttention, self).__init__()
        self.hidden_dim = hidden_dim
        
        # 查询向量（可学习的上下文向量）
        # 用于计算每个时间步的重要性
        self.context_vector = nn.Linear(hidden_dim, hidden_dim, bias=False)
        
        # 注意力分数计算层
        # 将LSTM输出和查询向量结合，计算注意力分数
        self.attention = nn.Linear(hidden_dim, 1, bias=False)
        
        # 可选的：添加tanh激活
        self.tanh = nn.Tanh()
        
    def forward(self, lstm_output, hidden_state=None, peak_indices=None, temperature: float = 1.0):
        """
        计算时间注意力权重，并返回加权后的输出
        
        Args:
            lstm_output: (batch, seq_len, hidden_dim) LSTM所有时间步的输出
            hidden_state: (batch, hidden_dim) 可选的查询向量（默认使用最后一个隐藏态）
        
        Returns:
            output: (batch, seq_len, hidden_dim) 时间步加权后的输出序列
            attention_weights: (batch, seq_len) 每个时间步的注意力权重
        """
        batch_size, seq_len, hidden_dim = lstm_output.size()
        
        # 选择查询向量：
        # 优先使用峰值位置隐藏态（若提供peak_indices），否则使用传入的hidden_state，
        # 若仍为空，则回退为最后一个时间步的隐藏态
        if peak_indices is not None:
            # 使用每个样本峰值时间步的隐藏态作为查询
            batch_indices = torch.arange(batch_size, device=lstm_output.device)
            hidden_state = lstm_output[batch_indices, peak_indices, :]  # (batch, hidden_dim)
        elif hidden_state is None:
            hidden_state = lstm_output[:, -1, :]  # (batch, hidden_dim)
        
        # 计算查询向量（上下文向量）
        query = self.context_vector(hidden_state)  # (batch, hidden_dim)
        query = query.unsqueeze(1)  # (batch, 1, hidden_dim)
        
        # 计算注意力分数
        # 方式1：使用查询向量与LSTM输出的点积（Bahdanau风格）
        # 将查询向量扩展到所有时间步
        query_expanded = query.expand(-1, seq_len, -1)  # (batch, seq_len, hidden_dim)
        
        # 计算相似度分数
        # 使用加法注意力（Additive Attention / Bahdanau Attention）
        combined = lstm_output + query_expanded  # (batch, seq_len, hidden_dim)
        combined = self.tanh(combined)  # 激活
        scores = self.attention(combined)  # (batch, seq_len, 1)
        scores = scores.squeeze(-1)  # (batch, seq_len)
        
        # Softmax归一化得到注意力权重，加入温度系数（temperature<1提升对比度）
        scores_scaled = scores / max(temperature, 1e-6)
        attention_weights = F.softmax(scores_scaled, dim=1)  # (batch, seq_len)
        
        # 应用注意力权重到LSTM输出
        # attention_weights: (batch, seq_len) -> (batch, seq_len, 1)
        attention_weights_expanded = attention_weights.unsqueeze(-1)  # (batch, seq_len, 1)
        
        # 时间步加权：每个时间步的输出乘以对应的注意力权重
        output = lstm_output * attention_weights_expanded  # (batch, seq_len, hidden_dim)
        
        return output, attention_weights


class ImprovedLSTMWithAttention(nn.Module):
    """
    增强版LSTM模型 - 带时间注意力机制（Bahdanau Attention）
    LSTM参数与baseline一致：hidden_dim=128, num_layers=3, dropout=0.3
    
    时间注意力（Time Attention）：
    - 聚焦地震加速度时程中对跨中位移影响最大的时间步（如地震峰值段）
    - 计算每个时间步的注意力权重（基于LSTM隐藏态与查询向量的相似度）
    - 加权求和得到注意力输出
    - 解决普通LSTM对长时序"均等加权"的缺陷，强化地震峰值等关键时段的特征捕捉
    """
    def __init__(self, input_dim=1, hidden_dim=128, num_layers=3, output_dim=1, 
                 dropout=0.3, bidirectional=False):
        """
        原始 2-1 版本：Encoder 直接输出经 TimeAttention 做逐元素加权（Filter 型）
        【保留用于对比】论文版 2-1 会在下方以新的类名实现。
        """
        super(ImprovedLSTMWithAttention, self).__init__()
        
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.bidirectional = bidirectional
        
        self.lstm = nn.LSTM(
            input_dim,
            hidden_dim,
            num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=bidirectional
        )
        
        lstm_output_dim = hidden_dim * 2 if bidirectional else hidden_dim
        self.time_attention = TimeAttention(lstm_output_dim)
        self.use_residual = True
        self.attention_temperature = 1.0
        
        self.fc = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(lstm_output_dim, output_dim)
        )
        
    def forward(self, x, peak_indices=None):
        lstm_out, (h_n, c_n) = self.lstm(x)
        hidden_state = None if peak_indices is not None else h_n[-1]
        attn_out, attention_weights = self.time_attention(
            lstm_output=lstm_out,
            hidden_state=hidden_state,
            peak_indices=peak_indices,
            temperature=self.attention_temperature
        )
        if self.use_residual:
            fused_out = lstm_out + attn_out
        else:
            fused_out = attn_out
        output = self.fc(fused_out)
        return output


class ImprovedLSTMWithAttentionPaperVision(nn.Module):
    """
    修正版 2-1: Encoder-Decoder with Global Attention（Paper Vision 版本）
    
    架构逻辑:
    1. Encoder: 提取局部时序特征
    2. Attention: 基于峰值/全局视角，计算一个全局上下文向量 (Context Vector)
    3. Decoder: 接收 [Encoder输出 + Context向量] 的拼接，恢复全时程信号
    """
    def __init__(self, input_dim=1, hidden_dim=128, num_layers=3, output_dim=1, 
                 dropout=0.3, bidirectional=False, return_attention: bool = False):
        super(ImprovedLSTMWithAttentionPaperVision, self).__init__()
        
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.bidirectional = bidirectional
        # 若为 True，则 forward 返回 (prediction, attention_weights)
        self.return_attention = return_attention
        
        # 1. Encoder（与 Baseline 一致）
        self.encoder = nn.LSTM(
            input_dim,
            hidden_dim,
            num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=bidirectional
        )
        
        encoder_output_dim = hidden_dim * 2 if bidirectional else hidden_dim
        
        # 2. Attention 组件
        self.attn_fc = nn.Linear(encoder_output_dim, 1, bias=False)
        self.query_fc = nn.Linear(encoder_output_dim, encoder_output_dim, bias=False)
        self.tanh = nn.Tanh()
        
        # 3. Decoder：输入 = [Encoder 输出; Context]
        decoder_input_dim = encoder_output_dim * 2
        self.decoder = nn.LSTM(
            decoder_input_dim,
            hidden_dim,
            1,
            batch_first=True,
            dropout=dropout
        )
        
        # 4. 输出层
        self.fc = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, output_dim)
        )
        
    def forward(self, x, peak_indices=None):
        """
        Args:
            x: (batch, seq_len, 1)
            peak_indices: (batch,) 峰值所在的时间步索引
        """
        batch_size, seq_len, _ = x.size()
        
        # --- 1. Encoder ---
        encoder_out, (h_n, c_n) = self.encoder(x)  # (batch, seq, enc_hidden)
        
        # --- 2. Attention Mechanism ---
        encoder_hidden_dim = encoder_out.size(2)
        if peak_indices is not None:
            idx_expanded = peak_indices.view(batch_size, 1, 1).expand(-1, 1, encoder_hidden_dim)
            query = torch.gather(encoder_out, 1, idx_expanded).squeeze(1)  # (batch, enc_hidden)
        else:
            query = encoder_out[:, -1, :]  # (batch, enc_hidden)
        
        query_proj = self.query_fc(query).unsqueeze(1)  # (batch, 1, enc_hidden)
        energy = self.tanh(encoder_out + query_proj)    # (batch, seq, enc_hidden)
        attention_scores = self.attn_fc(energy)         # (batch, seq, 1)
        attention_weights = torch.softmax(attention_scores, dim=1)  # (batch, seq, 1)
        
        # --- 3. Context Vector ---
        context_vector = torch.sum(encoder_out * attention_weights, dim=1)  # (batch, enc_hidden)
        
        # --- 4. Decoder Input ---
        context_repeated = context_vector.unsqueeze(1).expand(-1, seq_len, -1)  # (batch, seq, enc_hidden)
        decoder_input = torch.cat((encoder_out, context_repeated), dim=2)       # (batch, seq, enc_hidden*2)
        
        # --- 5. Decoder & Output ---
        decoder_out, _ = self.decoder(decoder_input)  # (batch, seq, hidden_dim)
        prediction = self.fc(decoder_out)             # (batch, seq, output_dim)
        
        if self.return_attention:
            # 返回 (预测, 注意力权重(去掉最后一维))
            return prediction, attention_weights.squeeze(-1)  # (batch, seq)
        return prediction


class CNNAttnLSTM_PaperVersion(nn.Module):
    """
    SCI Proposed Model: CNN-Attention-LSTM (CAL-Net)
    
    Architecture Design for Seismic Response Prediction:
    1. [Local Feature Extraction]: 1D-CNN captures high-frequency local patterns (peaks/jerks) 
       from earthquake excitation.
    2. [Global Temporal Modeling]: LSTM Encoder captures long-term dependencies and structural dynamics.
    3. [Feature Fusion]: Global Attention aggregates critical context vectors.
    4. [Signal Reconstruction]: LSTM Decoder regenerates the displacement history using 
       concatenated [Local Features + Global Context].
       
    Note: Padding is used in CNN to preserve temporal resolution (Sequence Length), 
    ensuring perfect alignment for Physics-Informed Loss calculation.
    """
    def __init__(self, input_dim=1, cnn_channels=32, hidden_dim=128, num_layers=3, 
                 output_dim=1, dropout=0.3, bidirectional=False):
        super(CNNAttnLSTM_PaperVersion, self).__init__()
        
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.bidirectional = bidirectional
        
        # --- 1. CNN Feature Extractor (New Component) ---
        # input: (Batch, input_dim, Seq_Len)
        # We use a stack of Conv1d to increase receptive field without losing resolution
        self.cnn = nn.Sequential(
            # Layer 1: Expand features
            nn.Conv1d(in_channels=input_dim, out_channels=cnn_channels, 
                      kernel_size=5, padding=2), # padding=2 keeps length same for k=5
            nn.BatchNorm1d(cnn_channels),
            nn.ReLU(),
            nn.Dropout(0.1),
            
            # Layer 2: Deepen features
            nn.Conv1d(in_channels=cnn_channels, out_channels=cnn_channels*2, 
                      kernel_size=3, padding=1), # padding=1 keeps length same for k=3
            nn.BatchNorm1d(cnn_channels*2),
            nn.ReLU(),
            nn.Dropout(0.1)
        )
        
        # The LSTM input size is now the output channels of CNN
        lstm_input_size = cnn_channels * 2
        
        # --- 2. LSTM Encoder ---
        self.encoder = nn.LSTM(
            input_size=lstm_input_size,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=bidirectional
        )
        
        encoder_output_dim = hidden_dim * 2 if bidirectional else hidden_dim
        
        # --- 3. Attention Mechanism ---
        self.attn_fc = nn.Linear(encoder_output_dim, 1, bias=False)
        self.query_fc = nn.Linear(encoder_output_dim, encoder_output_dim, bias=False)
        self.tanh = nn.Tanh()
        
        # --- 4. LSTM Decoder ---
        # Input = [Encoder_Output (Local) ; Context_Vector (Global)]
        # Concatenation Strategy
        decoder_input_dim = encoder_output_dim * 2
        self.decoder = nn.LSTM(
            decoder_input_dim,
            hidden_dim,
            1, # Decoder depth
            batch_first=True,
            dropout=dropout
        )
        
        # --- 5. Output Layer ---
        self.fc = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, output_dim)
        )
        
    def forward(self, x, peak_indices=None):
        """
        x: (Batch, Seq_Len, Input_Dim)
        """
        batch_size, seq_len, _ = x.size()
        
        # --- Step 1: CNN Extraction ---
        # Permute for Conv1d: (Batch, Seq, Dim) -> (Batch, Dim, Seq)
        x_permuted = x.permute(0, 2, 1)
        cnn_feat = self.cnn(x_permuted)
        # Permute back for LSTM: (Batch, Dim, Seq) -> (Batch, Seq, Dim)
        cnn_feat = cnn_feat.permute(0, 2, 1) 
        
        # --- Step 2: Encoder ---
        # input: CNN features
        encoder_out, (h_n, c_n) = self.encoder(cnn_feat)
        
        # --- Step 3: Attention ---
        encoder_hidden_dim = encoder_out.size(2)
        if peak_indices is not None:
            # Gather peak hidden state as query
            idx_expanded = peak_indices.view(batch_size, 1, 1).expand(-1, 1, encoder_hidden_dim)
            query = torch.gather(encoder_out, 1, idx_expanded).squeeze(1)
        else:
            query = encoder_out[:, -1, :] # Fallback to last state
            
        # Standard Global Attention Calculation
        query_proj = self.query_fc(query).unsqueeze(1)
        energy = self.tanh(encoder_out + query_proj)
        attention_scores = self.attn_fc(energy)
        attention_weights = torch.softmax(attention_scores, dim=1)
        
        # Context Vector (Weighted Sum)
        context_vector = torch.sum(encoder_out * attention_weights, dim=1)
        
        # --- Step 4: Decoder (Concat Strategy) ---
        # Expand context to match sequence length
        context_repeated = context_vector.unsqueeze(1).expand(-1, seq_len, -1)
        
        # Concat: [Encoder_Output (Local Context) ; Global_Context]
        # This preserves local details extracted by CNN+LSTM while adding global guidance
        decoder_input = torch.cat((encoder_out, context_repeated), dim=2)
        
        decoder_out, _ = self.decoder(decoder_input)
        
        # --- Step 5: Prediction ---
        prediction = self.fc(decoder_out)
        
        return prediction


class CNNAttnLSTM_Residual_Version(nn.Module):
    """
    SCI Proposed Model: Residual CNN-Attention-LSTM (Res-CAL-Net)
    
    Improvements over M3:
    1. [Residual Connection]: Concatenates Raw Input with CNN Features. 
       Ensures the model performs at least as well as the Baseline LSTM.
    2. [Lightweight CNN]: Reduces channel size to prevent overfitting on small datasets.
    """
    def __init__(self, input_dim=1, cnn_channels=16, hidden_dim=128, num_layers=3, 
                 output_dim=1, dropout=0.3, bidirectional=False):
        super(CNNAttnLSTM_Residual_Version, self).__init__()
        
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.bidirectional = bidirectional
        
        # --- 1. Lightweight CNN Feature Extractor ---
        # Reduced complexity: 32 -> 16 channels, single conv layer
        self.cnn = nn.Sequential(
            nn.Conv1d(in_channels=input_dim, out_channels=cnn_channels, 
                      kernel_size=5, padding=2),
            nn.BatchNorm1d(cnn_channels),
            nn.ReLU(),
            nn.Dropout(0.1)
        )
        
        # --- Key Change: Input Fusion ---
        # LSTM input = Raw Input (1) + CNN Features (cnn_channels)
        lstm_input_size = input_dim + cnn_channels
        
        # --- 2. LSTM Encoder ---
        self.encoder = nn.LSTM(
            input_size=lstm_input_size,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=bidirectional
        )
        
        encoder_output_dim = hidden_dim * 2 if bidirectional else hidden_dim
        
        # --- 3. Attention (Same as PaperVision 2-1) ---
        self.attn_fc = nn.Linear(encoder_output_dim, 1, bias=False)
        self.query_fc = nn.Linear(encoder_output_dim, encoder_output_dim, bias=False)
        self.tanh = nn.Tanh()
        
        # --- 4. Decoder (Same as PaperVision 2-1) ---
        decoder_input_dim = encoder_output_dim * 2
        self.decoder = nn.LSTM(
            decoder_input_dim,
            hidden_dim,
            1,
            batch_first=True,
            dropout=dropout
        )
        
        # --- 5. Output ---
        self.fc = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, output_dim)
        )
        
    def forward(self, x, peak_indices=None):
        """
        x: (batch, seq_len, input_dim)
        """
        batch_size, seq_len, _ = x.size()
        
        # --- Step 1: CNN Extraction ---
        x_permuted = x.permute(0, 2, 1)  # (batch, 1, seq)
        cnn_feat = self.cnn(x_permuted)  # (batch, cnn_channels, seq)
        cnn_feat = cnn_feat.permute(0, 2, 1)  # (batch, seq, cnn_channels)
        
        # --- Step 1.5: Residual Fusion (Concatenation) ---
        # combined_input: (batch, seq, input_dim + cnn_channels)
        combined_input = torch.cat((x, cnn_feat), dim=2)
        
        # --- Step 2: Encoder ---
        encoder_out, (h_n, c_n) = self.encoder(combined_input)
        
        # --- Step 3: Attention ---
        encoder_hidden_dim = encoder_out.size(2)
        if peak_indices is not None:
            idx_expanded = peak_indices.view(batch_size, 1, 1).expand(-1, 1, encoder_hidden_dim)
            query = torch.gather(encoder_out, 1, idx_expanded).squeeze(1)
        else:
            query = encoder_out[:, -1, :]
            
        query_proj = self.query_fc(query).unsqueeze(1)
        energy = self.tanh(encoder_out + query_proj)
        attention_scores = self.attn_fc(energy)
        attention_weights = torch.softmax(attention_scores, dim=1)
        
        context_vector = torch.sum(encoder_out * attention_weights, dim=1)
        
        # --- Step 4: Decoder ---
        context_repeated = context_vector.unsqueeze(1).expand(-1, seq_len, -1)
        decoder_input = torch.cat((encoder_out, context_repeated), dim=2)
        
        decoder_out, _ = self.decoder(decoder_input)
        prediction = self.fc(decoder_out)
        
        return prediction


class CNNAttnLSTM_Residual_Version_K3(nn.Module):
    """
    M3-3核版本: Residual CNN-Attention-LSTM (Res-CAL-Net, k=3)
    
    与 M3（CNNAttnLSTM_Residual_Version）的唯一区别：
    - CNN 的卷积核从 kernel_size=5 改为 kernel_size=3（padding=1 保持序列长度不变）
    
    动机：
    - 更小卷积核更偏向提取“更局部”的高频细节，可能减少平滑效应，从而改善 Peak RMSE。
    """
    def __init__(self, input_dim=1, cnn_channels=16, hidden_dim=128, num_layers=3,
                 output_dim=1, dropout=0.3, bidirectional=False):
        super(CNNAttnLSTM_Residual_Version_K3, self).__init__()
        
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.bidirectional = bidirectional
        
        # --- 1. Lightweight CNN Feature Extractor (k=3) ---
        self.cnn = nn.Sequential(
            nn.Conv1d(in_channels=input_dim, out_channels=cnn_channels,
                      kernel_size=3, padding=1),
            nn.BatchNorm1d(cnn_channels),
            nn.ReLU(),
            nn.Dropout(0.1)
        )
        
        # --- Residual Fusion ---
        lstm_input_size = input_dim + cnn_channels
        
        # --- 2. LSTM Encoder ---
        self.encoder = nn.LSTM(
            input_size=lstm_input_size,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=bidirectional
        )
        
        encoder_output_dim = hidden_dim * 2 if bidirectional else hidden_dim
        
        # --- 3. Attention ---
        self.attn_fc = nn.Linear(encoder_output_dim, 1, bias=False)
        self.query_fc = nn.Linear(encoder_output_dim, encoder_output_dim, bias=False)
        self.tanh = nn.Tanh()
        
        # --- 4. Decoder (Concat Strategy) ---
        decoder_input_dim = encoder_output_dim * 2
        self.decoder = nn.LSTM(
            decoder_input_dim,
            hidden_dim,
            1,
            batch_first=True,
            dropout=dropout
        )
        
        # --- 5. Output ---
        self.fc = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, output_dim)
        )
    
    def forward(self, x, peak_indices=None):
        """
        x: (batch, seq_len, input_dim)
        """
        batch_size, seq_len, _ = x.size()
        
        # CNN features
        x_permuted = x.permute(0, 2, 1)  # (batch, input_dim, seq)
        cnn_feat = self.cnn(x_permuted)  # (batch, cnn_channels, seq)
        cnn_feat = cnn_feat.permute(0, 2, 1)  # (batch, seq, cnn_channels)
        
        # Residual fusion
        combined_input = torch.cat((x, cnn_feat), dim=2)  # (batch, seq, input_dim+cnn_channels)
        
        # Encoder
        encoder_out, _ = self.encoder(combined_input)
        
        # Attention (peak query or last state)
        encoder_hidden_dim = encoder_out.size(2)
        if peak_indices is not None:
            idx_expanded = peak_indices.view(batch_size, 1, 1).expand(-1, 1, encoder_hidden_dim)
            query = torch.gather(encoder_out, 1, idx_expanded).squeeze(1)
        else:
            query = encoder_out[:, -1, :]
        
        query_proj = self.query_fc(query).unsqueeze(1)
        energy = self.tanh(encoder_out + query_proj)
        attention_scores = self.attn_fc(energy)
        attention_weights = torch.softmax(attention_scores, dim=1)
        context_vector = torch.sum(encoder_out * attention_weights, dim=1)
        
        # Decoder
        context_repeated = context_vector.unsqueeze(1).expand(-1, seq_len, -1)
        decoder_input = torch.cat((encoder_out, context_repeated), dim=2)
        decoder_out, _ = self.decoder(decoder_input)
        
        return self.fc(decoder_out)


class ModelM4_PhysicsPure(nn.Module):
    """
    M4: Physics-Informed Residual LSTM without CNN
    
    Architecture:
    1. Input: 3 channels [ü_g (base accel), u̇_g (integrated), u_g (integrated)]
    2. No CNN: Direct Linear projection to LSTM hidden dimension
    3. LSTM + Attention: Same as M2/M3 (Encoder-Decoder Global Attention)
    4. Residual Connection: Output = Prior_Projected + Delta_Y
    
    Key Innovation:
    - Scale Alignment Layer: Learnable affine transformation to align the integrated
      ground-motion displacement prior (u_g) with the target's normalized space
    - Preserves high-frequency peak information by avoiding CNN smoothing
    """
    def __init__(self, input_dim=3, hidden_dim=128, num_layers=3, output_dim=1, 
                 dropout=0.3, bidirectional=False, dt=0.02):
        super(ModelM4_PhysicsPure, self).__init__()
        
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.bidirectional = bidirectional
        self.dt = dt
        
        # --- 1. Input Projection (No CNN) ---
        # Project 3-channel input to LSTM hidden dimension
        encoder_input_dim = hidden_dim * 2 if bidirectional else hidden_dim
        self.input_projection = nn.Linear(input_dim, encoder_input_dim)
        
        # --- 2. LSTM Encoder (Same as M2/M3) ---
        self.encoder = nn.LSTM(
            input_size=encoder_input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=bidirectional
        )
        
        encoder_output_dim = hidden_dim * 2 if bidirectional else hidden_dim
        
        # --- 3. Attention (Same as M2/M3 Paper Vision) ---
        self.attn_fc = nn.Linear(encoder_output_dim, 1, bias=False)
        self.query_fc = nn.Linear(encoder_output_dim, encoder_output_dim, bias=False)
        self.tanh = nn.Tanh()
        
        # --- 4. Decoder (Same as M2/M3) ---
        decoder_input_dim = encoder_output_dim * 2
        self.decoder = nn.LSTM(
            decoder_input_dim,
            hidden_dim,
            1,
            batch_first=True,
            dropout=dropout
        )
        
        # --- 5. Delta Predictor (Correction Term) ---
        self.delta_predictor = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, output_dim)
        )
        
        # --- 6. Scale Alignment Layer (Critical for Physics Input) ---
        # Learnable affine transformation: x_phys_projected = x_phys * scale + bias
        # Initialize with small values to start from identity-like transformation
        self.phys_scale = nn.Parameter(torch.ones(1))
        self.phys_bias = nn.Parameter(torch.zeros(1))
        
    def forward(self, x, peak_indices=None):
        """
        Args:
            x: (batch, seq_len, 3) - [ü_g, u̇_g, u_g] (ground-motion-derived kinematic prior)
            peak_indices: (batch,) - Peak time step indices (optional)
        Returns:
            output: (batch, seq_len, 1) - Final displacement prediction
        """
        batch_size, seq_len, _ = x.size()
        
        # --- 1. Separate prior baseline (Channel 2: u_g) ---
        x_phys_raw = x[:, :, 2:3]  # (batch, seq_len, 1)
        
        # --- 2. Scale Alignment: Project prior to target space ---
        x_phys_projected = x_phys_raw * self.phys_scale + self.phys_bias
        
        # --- 3. Main Network: Data-Driven Residual (Delta) ---
        # Project 3-channel input to LSTM dimension
        x_projected = self.input_projection(x)  # (batch, seq_len, encoder_input_dim)
        
        # Encoder
        encoder_out, (h_n, c_n) = self.encoder(x_projected)  # (batch, seq, enc_hidden)
        
        # Attention Mechanism (Same as M2/M3)
        encoder_hidden_dim = encoder_out.size(2)
        if peak_indices is not None:
            idx_expanded = peak_indices.view(batch_size, 1, 1).expand(-1, 1, encoder_hidden_dim)
            query = torch.gather(encoder_out, 1, idx_expanded).squeeze(1)  # (batch, enc_hidden)
        else:
            query = encoder_out[:, -1, :]  # (batch, enc_hidden)
        
        query_proj = self.query_fc(query).unsqueeze(1)  # (batch, 1, enc_hidden)
        energy = self.tanh(encoder_out + query_proj)    # (batch, seq, enc_hidden)
        attention_scores = self.attn_fc(energy)         # (batch, seq, 1)
        attention_weights = torch.softmax(attention_scores, dim=1)  # (batch, seq, 1)
        
        # Context Vector
        context_vector = torch.sum(encoder_out * attention_weights, dim=1)  # (batch, enc_hidden)
        
        # Decoder Input
        context_repeated = context_vector.unsqueeze(1).expand(-1, seq_len, -1)  # (batch, seq, enc_hidden)
        decoder_input = torch.cat((encoder_out, context_repeated), dim=2)       # (batch, seq, enc_hidden*2)
        
        # Decoder
        decoder_out, _ = self.decoder(decoder_input)  # (batch, seq, hidden_dim)
        
        # Delta Prediction (Correction Term)
        delta_y = self.delta_predictor(decoder_out)  # (batch, seq, 1)
        
        # --- 4. Final Residual Sum ---
        output = x_phys_projected + delta_y  # (batch, seq, 1)
        
        return output

