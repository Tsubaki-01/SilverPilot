"""
测试 vLLM 部署的模型
使用 OpenAI SDK 调用
"""

import subprocess

from openai import OpenAI


# 自动获取 WSL IP
def get_wsl_ip() -> str:
    result = subprocess.run(
        ["wsl", "-d", "Ubuntu", "hostname", "-I"],
        capture_output=True,
        text=True,
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


def test() -> None:
    for q in TEST_CASES:
        print(f"\n{'=' * 60}")
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
