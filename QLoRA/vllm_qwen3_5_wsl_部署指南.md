# WSL + vLLM 部署 Qwen3.5 QLoRA 模型全流程

> 环境：Windows 11 + WSL2 Ubuntu + CUDA GPU + Python / OpenAI SDK

---

## 一、环境说明

| 项目 | 版本 / 路径 |
|------|------------|
| 运行环境 | WSL2 Ubuntu |
| conda 环境 | `vllm` |
| 模型路径（WSL） | `/mnt/c/Users/{user}/.lora_models/qwen3_5_0_8B` |
| 模型架构 | Qwen3.5-0.8B |
| GPU | 8GB 显存（RTX 系列） |

---

## 二、启动 vLLM 服务

### 完整启动命令

```bash
conda activate vllm

VLLM_DISABLE_COMPILE_CACHE=1 \
TORCH_COMPILE_DISABLE=1 \
python -m vllm.entrypoints.openai.api_server \
  --model /mnt/c/Users/tsubaki/.lora_models/qwen3_5_0_8B \
  --served-model-name elderly-care-assistant \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype bfloat16 \
  --max-model-len 2048 \
  --trust-remote-code \
  --gpu-memory-utilization 0.60 \
  --enforce-eager
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `--served-model-name` | API 调用时使用的模型名，需与代码中一致 |
| `--host 0.0.0.0` | 绑定所有网卡，Windows 才能访问 |
| `--dtype bfloat16` | 与模型训练精度一致 |
| `--trust-remote-code` | Qwen 系列必须加，否则 tokenizer 报错 |
| `--gpu-memory-utilization 0.80` | 限制显存占用比例，避免 OOM |
| `--enforce-eager` | 禁用 torch.compile / cuda graph，WSL 下必须加 |
| `TORCH_COMPILE_DISABLE=1` | 彻底禁用编译，解决 WSL 下 `nvcc` 权限问题 |

### 启动成功标志

看到以下日志即表示服务正常运行：

```
INFO  Starting vLLM server on http://0.0.0.0:8000
INFO  Application startup complete.
```

---

## 三、坑点与解决方案

### 坑1：TokenizersBackend 不存在

**报错：**
```
ValueError: Tokenizer class TokenizersBackend does not exist
```

**原因：** `tokenizer_config.json` 中写了自定义 tokenizer 类名，transformers 不认识。

**解决：** 修改 `tokenizer_config.json`，将 tokenizer_class 改为标准类名：

```bash
sed -i 's/"tokenizer_class": "TokenizersBackend"/"tokenizer_class": "Qwen2TokenizerFast"/' \
  '/mnt/c/Users/tsubaki/.lora_models/qwen3_5_0_8B/tokenizer_config.json'
```

---

### 坑2：显存不足

**报错：**

```
ValueError: Free memory on device cuda:0 (6.89/8.0 GiB) is less than desired GPU memory utilization (0.9, 7.2 GiB)
```

**原因：** vLLM 默认要求 90% 显存，但其他进程已占用部分。

**解决：** 加 `--gpu-memory-utilization 0.60` 降低要求，或先 kill 占用 GPU 的进程：

```bash
nvidia-smi          # 查看占用进程
sudo kill -9 <PID>  # 释放显存
```

---

### 坑3：nvcc 权限错误（torch.compile 失败）

**报错：**

```
PermissionError: [Errno 13] Permission denied: 'nvcc'
torch._inductor.exc.InductorError
```

**原因：** WSL 环境下无法执行 `nvcc`，而 vLLM v1 引擎默认启用 torch.compile。

**解决：** 启动时加 `--enforce-eager` 和环境变量，完全跳过编译：

```bash
VLLM_DISABLE_COMPILE_CACHE=1 TORCH_COMPILE_DISABLE=1 \
python -m vllm.entrypoints.openai.api_server ... --enforce-eager
```

> `--compilation-config '{"level": 0}'` 在新版 vLLM 中已不支持此写法，改用 `--enforce-eager`。

---

## 四、Windows 端调用

### 获取 WSL IP

方法一：WSL 日志中直接查看

方法二：WSL  ubuntu内执行：
```bash
hostname -I | awk '{print $1}'
```

方法三：Windows PowerShell 自动获取：
```python
import subprocess
result = subprocess.run(
    ["wsl", "-d", "Ubuntu", "hostname", "-I"],
    capture_output=True, text=True
)
WSL_IP = result.stdout.strip() or "127.0.0.1"
```

> WSL IP 每次重启可能变化，建议用代码自动获取。

---

### test_api.py（OpenAI SDK 版）

```python
"""
测试 vLLM 部署的模型 — 验证语气风格是否符合预期
使用 OpenAI SDK 调用
"""
import subprocess
from openai import OpenAI

# 自动获取 WSL IP
def get_wsl_ip():
    result = subprocess.run(
        ["wsl", "-d", "Ubuntu", "hostname", "-I"],
        capture_output=True, text=True
    )
    ip = result.stdout.strip()
    return ip if ip else "127.0.0.1"

WSL_IP = get_wsl_ip()
print(f"连接到: {WSL_IP}:8000")

client = OpenAI(
    base_url=f"http://{WSL_IP}:8000/v1",
    api_key="dummy",  # 本地部署不需要真实 key
)

SYSTEM_PROMPT = (
    "你是一个专门为老年人设计的AI看护助手。"
    "你的语气必须像家里耐心懂事的晚辈，或者贴心的社区工作人员。"
    "必须使用大白话、接地气的口语，绝不使用复杂术语，用生活化比喻耐心引导；"
    "但在遇到紧急情况时，你必须立刻收起所有寒暄与情绪安抚，"
    "迅速、简明扼要、语气坚决地给出保命或止损的行动指令。"
)

TEST_CASES = [
    "有人打电话说我中了大奖，让我先交两千块手续费，我该交吗？",
    "我胸口闷得慌，喘不上气来，是不是天气太热了？",
    "我孙子教我用微信发红包，可我怎么也找不到那个按钮。",
    "老伴走了三年了，我一个人在家越来越没意思，饭也懒得做。",
]

def test():
    for q in TEST_CASES:
        print(f"\n{'='*60}")
        print(f"问: {q}")
        response = client.chat.completions.create(
            model="elderly-care-assistant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": q},
            ],
            temperature=0.7,
            max_tokens=512,
        )
        print(f"答: {response.choices[0].message.content}")

if __name__ == "__main__":
    test()
```

安装依赖：
```cmd
pip install openai
```

---

## 五、快速启动脚本

将以下内容保存为 `start_vllm.sh`，下次直接运行：

```bash
#!/bin/bash
conda activate vllm

VLLM_DISABLE_COMPILE_CACHE=1 \
TORCH_COMPILE_DISABLE=1 \
python -m vllm.entrypoints.openai.api_server \
  --model /mnt/c/Users/tsubaki/.lora_models/qwen3_5_0_8B \
  --served-model-name elderly-care-assistant \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype bfloat16 \
  --max-model-len 2048 \
  --trust-remote-code \
  --gpu-memory-utilization 0.60 \
  --enforce-eager
```

```bash
chmod +x start_vllm.sh
./start_vllm.sh
```

---

## 六、模型说明

本次部署的模型为 **Qwen3.5-0.8B**，架构为 `Qwen3_5ForConditionalGeneration`，包含：

- 文本模型：24层，混合 linear attention + full attention
- 视觉编码器：12层 ViT，patch_size=16
- 参数规模：约 0.8B
