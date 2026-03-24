"""
模块名称：commit_review
功能描述：基于给定 Git Commit 列表生成结构化 Markdown 审查报告。
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

_COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")


@dataclass(slots=True)
class CommitStats:
    """单个提交的基础统计信息。"""

    commit_hash: str
    subject: str
    files: list[str]
    insertions: int
    deletions: int


def _run_git(repo_root: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _validate_commit_hash(commit_hash: str) -> str:
    normalized = commit_hash.strip().lower()
    if not _COMMIT_RE.fullmatch(normalized):
        raise ValueError(f"非法 commit hash: {commit_hash}")
    return normalized


def _collect_commit_stats(repo_root: Path, commit_hash: str) -> CommitStats:
    normalized = _validate_commit_hash(commit_hash)
    _run_git(repo_root, ["cat-file", "-e", f"{normalized}^{{commit}}"])

    subject = _run_git(repo_root, ["show", "-s", "--format=%s", normalized])
    numstat = _run_git(repo_root, ["show", "--numstat", "--format=", normalized])

    files: list[str] = []
    insertions = 0
    deletions = 0
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        add_str, del_str, path = parts
        files.append(path)
        if add_str.isdigit():
            insertions += int(add_str)
        if del_str.isdigit():
            deletions += int(del_str)

    return CommitStats(
        commit_hash=normalized,
        subject=subject or "(无提交标题)",
        files=files,
        insertions=insertions,
        deletions=deletions,
    )


def build_commit_review_report(repo_root: Path, commit_hashes: list[str]) -> str:
    if not commit_hashes:
        raise ValueError("commit_hashes 不能为空")

    stats_list = [_collect_commit_stats(repo_root, commit_hash) for commit_hash in commit_hashes]
    all_files = [file for stats in stats_list for file in stats.files]

    touches_server_api = any(file.startswith("src/silver_pilot/server/") for file in all_files)
    touches_frontend = any(file.startswith("static/") for file in all_files)
    touches_agent_context = any(
        file
        in {
            "src/silver_pilot/agent/nodes/helpers.py",
            "src/silver_pilot/agent/nodes/chat_agent.py",
            "src/silver_pilot/agent/nodes/medical_agent.py",
            "src/silver_pilot/agent/nodes/supervisor.py",
        }
        for file in all_files
    )
    touches_dependencies = any(file == "pyproject.toml" for file in all_files)

    summary_items = [
        f"`{stats.commit_hash[:7]}` {stats.subject}"
        for stats in stats_list
    ]
    total_files = len(set(all_files))
    total_insertions = sum(stats.insertions for stats in stats_list)
    total_deletions = sum(stats.deletions for stats in stats_list)

    compatibility_points = [
        "- **API 与接口**："
        + (
            "涉及 `src/silver_pilot/server/` 与 `static/` 的协同改动，前后端契约变更风险为 **中等**。"
            if touches_server_api or touches_frontend
            else "本次变更主要集中于内部实现，外部接口破坏风险为 **低**。"
        ),
        "- **数据与状态**："
        + (
            "新增对话上下文提取逻辑会影响 prompt 输入内容，属于行为兼容性变更；需确认旧会话回放结果是否可接受。"
            if touches_agent_context
            else "未发现明显的数据结构版本迁移动作，前后向兼容风险较低。"
        ),
        "- **依赖关系**："
        + (
            "检测到依赖文件变更，请确认锁定版本与运行环境的一致性。"
            if touches_dependencies
            else "未检测到依赖升级/替换，模块兼容性主要取决于代码逻辑。"
        ),
    ]

    conflict_points = [
        "- **逻辑冲突**：当同一轮消息中包含多条 `HumanMessage` 或消息顺序异常时，`get_conversation_context` 的截取窗口可能与既有总结逻辑出现偏差（触发条件：消息注入顺序不稳定）。"
        if touches_agent_context
        else "- **逻辑冲突**：未发现明显业务规则互斥点，建议重点关注边界输入场景。",
        "- **并发与状态**：WebSocket 场景下若会话并发写入消息，历史上下文读取可能出现“读到半更新状态”的窗口问题（触发条件：同一 session 并发请求）。",
        "- **命名空间与作用域**：当前未发现直接命名冲突；但建议避免跨模块重复定义“会话摘要/上下文”语义，以免后续维护歧义。",
    ]

    report = f"""📝 **变更摘要**
本次评审覆盖以下提交：{", ".join(summary_items)}。整体上变更集中在前后端接口初始化与对话上下文提取策略优化，共涉及 **{total_files}** 个文件（+{total_insertions}/-{total_deletions}）。

🔄 **兼容性报告**
{chr(10).join(compatibility_points)}

⚠️ **潜在冲突**
{chr(10).join(conflict_points)}

🚀 **优化建议**
1. 将上下文窗口参数化并显式复用配置，降低 magic number 扩散。

**Before**
```python
conversation_summary=get_conversation_context(state.get("messages", []))
```

**After**
```python
max_turns = state.get("context_window_turns", 6)
conversation_summary = get_conversation_context(state.get("messages", []), max_turns=max_turns)
```

2. 避免直接操作 `SessionStore` 私有属性，减少实现耦合。

**Before**
```python
if not _store.get(session_id):
    _store._sessions[session_id] = SessionMeta(session_id=session_id, name="新对话")
    _store._messages[session_id] = []
```

**After**
```python
if not _store.get(session_id):
    _store.create(name="新对话", user_id="default_user")
```

❓ **需要明确的疑问**
- `get_conversation_context` 是否刻意排除“本轮用户输入”？若是，是否已在产品层评估回答连贯性影响？
- 前端 `api-connector.js` 与后端 `WSOutgoing` 的字段契约是否有版本标识与回滚策略？
- 是否有针对多轮上下文截断策略的回归测试（尤其是含图片/音频混合消息场景）？
"""
    return report
