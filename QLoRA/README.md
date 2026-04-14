# 老年人AI看护助手 — LoRA微调 & vLLM部署

## 项目概述

针对老年人日常交互痛点（防诈骗、手机使用、健康引导、情绪陪伴），基于 **Qwen3.5-0.8B** 使用 LLaMA Factory 进行 LoRA 微调，使模型输出具备"耐心晚辈"式的语气风格，并通过 vLLM 本地部署。

## 环境准备

```bash
# 1. 创建虚拟环境
conda create -n elderly_care python=3.12 -y
conda activate elderly_care

# 2. 安装 LLaMA Factory
git clone --depth 1 https://github.com/hiyouga/LLaMA-Factory.git
cd LLaMA-Factory
pip install -e ".[torch,metrics]"

# 3. 安装 vLLM（部署用）
pip install vllm
```

## 步骤

### Step 1: 准备 LLaMA Factory 配置

将清洗后的数据和 `dataset_info.json` 放入 LLaMA Factory 的 `data/` 目录：

```bash
cp cleaned_train.jsonl /path/to/LLaMA-Factory/data/elderly_care_train.jsonl
cp cleaned_val.jsonl   /path/to/LLaMA-Factory/data/elderly_care_val.jsonl
cp dataset_info.json   /path/to/LLaMA-Factory/data/dataset_info.json
```

### Step 2: 开始训练

```bash
cd /path/to/LLaMA-Factory
llamafactory-cli train train_config.yaml
```

### Step 3: 合并 LoRA 权重

```bash
llamafactory-cli export merge_config.yaml
```

### Step 4: vLLM 部署

```bash
详见vllm_qwen3_5_wsl_部署指南.md
```

### Step 5: 测试

```bash
python test_api.py
```
