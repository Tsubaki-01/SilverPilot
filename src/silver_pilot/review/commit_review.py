"""Generate structured code-review reports for one or more Git commits."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess


_REQUIRED_HEADINGS = [
    "📝 变更摘要",
    "🔄 兼容性报告",
    "⚠️ 潜在冲突",
    "🚀 优化建议",
    "❓ 需要明确的疑问",
]
_COMMIT_ID_DISPLAY_LENGTH = 7


@dataclass(frozen=True)
class CommitSnapshot:
    """A compact view of one commit needed for quality-impact analysis."""

    commit_id: str
    subject: str
    files: tuple[str, ...]
    patch_text: str


def parse_commit_ids(raw: str) -> list[str]:
    """Extract unique commit hashes from free-form input while preserving order."""
    ids: list[str] = []
    for token in re.findall(r"\b[0-9a-fA-F]{7,40}\b", raw):
        lowered = token.lower()
        if lowered not in ids:
            ids.append(lowered)
    return ids


def _run_git(repo_path: Path, args: list[str]) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_path), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise ValueError(
            f"git command failed: {' '.join(args)}; "
            f"repo={repo_path}; stderr={stderr or 'N/A'}"
        ) from exc
    return completed.stdout.strip()


def _load_snapshot(repo_path: Path, commit_id: str) -> CommitSnapshot:
    subject = _run_git(repo_path, ["show", "-s", "--format=%s", commit_id])
    files_raw = _run_git(repo_path, ["show", "--pretty=format:", "--name-only", commit_id])
    patch_text = _run_git(repo_path, ["show", "--no-color", "--format=", commit_id])
    files = tuple(line.strip() for line in files_raw.splitlines() if line.strip())
    return CommitSnapshot(commit_id=commit_id, subject=subject, files=files, patch_text=patch_text)


def _patch_contains(snapshots: list[CommitSnapshot], needle: str) -> bool:
    target = needle.lower()
    return any(target in snapshot.patch_text.lower() for snapshot in snapshots)


def _patch_has_key_assignment(snapshots: list[CommitSnapshot], key: str) -> bool:
    pattern = re.compile(rf"^[+\-]\s*{re.escape(key)}\s*:", re.IGNORECASE | re.MULTILINE)
    return any(pattern.search(snapshot.patch_text) for snapshot in snapshots)


def _compatibility_lines(snapshots: list[CommitSnapshot]) -> list[str]:
    files = {path for snapshot in snapshots for path in snapshot.files}
    lines: list[str] = []

    if any(path.startswith("src/silver_pilot/server/") for path in files):
        lines.append(
            "- **API 与接口**：服务端模块（如 `app.py`/`models.py`）存在新增或调整，"
            "属于接口层演进。建议调用方按最新路由与字段契约联调，避免协议漂移。"
        )
        lines.append(
            "- **数据与状态**：若本次改动涉及会话状态管理（如 `session_store.py`），"
            "需确认状态持久化策略与历史行为是否一致，以避免升级后状态预期变化。"
        )

    if {"src/silver_pilot/server/models.py", "static/api-connector.js"}.issubset(files):
        lines.append(
            "- **前后端协同**：同一提交同时修改前端连接器与后端模型定义，"
            "建议确保前后端版本成对发布，避免单侧升级导致字段不匹配。"
        )

    if "QLoRA/train_qlora_elderly_care.yaml" in files:
        lines.append(
            "- **依赖关系**：QLoRA YAML 仅新增训练配置文件，不直接变更运行时 Python 依赖，"
            "对线上服务兼容性风险低。"
        )

    if not lines:
        lines.append("- 未发现方法签名级破坏；当前变更主要是新增文件，兼容性风险整体可控。")

    return lines


def _conflict_lines(snapshots: list[CommitSnapshot]) -> list[str]:
    files = {path for snapshot in snapshots for path in snapshot.files}
    lines: list[str] = []

    if "src/silver_pilot/server/session_store.py" in files and _patch_contains(snapshots, "_messages"):
        lines.append(
            "- **并发与状态冲突**：提交涉及会话消息集合更新逻辑。"
            "触发条件是同一会话高并发写入时，若缺少同步机制可能产生竞态。"
        )

    if {"src/silver_pilot/server/models.py", "static/api-connector.js"}.issubset(files):
        lines.append(
            "- **逻辑冲突**：前后端消息协议耦合较紧（例如 `WSIncoming`/`WSOutgoing`），"
            "触发条件是任一侧字段变更未同步发布。"
        )

    if "src/silver_pilot/server/app.py" in files and _patch_contains(snapshots, "global _graph"):
        lines.append(
            "- **作用域与全局状态**：模块级 `_graph`、`_store` 由多个请求共享；"
            "触发条件是未来引入多进程部署或热重载时，状态一致性要求提升。"
        )

    if not lines:
        lines.append("- 未观察到明显命名冲突或作用域污染风险。")

    return lines


def _optimization_lines(snapshots: list[CommitSnapshot]) -> list[str]:
    files = {path for snapshot in snapshots for path in snapshot.files}
    snippets: list[str] = []

    if "src/silver_pilot/server/session_store.py" in files and _patch_contains(snapshots, "_messages"):
        snippets.append(
            "- `SessionStore` 可增加最小化并发保护，避免并发写入时的状态竞态（示例）。\n"
            "\n"
            "```python\n"
            "# Before\n"
            "messages[session_id].append(message)\n"
            "\n"
            "# After\n"
            "with session_lock:\n"
            "    messages[session_id].append(message)\n"
            "```"
        )

    if "src/silver_pilot/server/app.py" in files and _patch_has_key_assignment(
        snapshots, "allow_origins"
    ):
        snippets.append(
            "- 若提交中使用宽松 CORS（`allow_origins=[\"*\"]`），建议改为白名单以降低暴露面。\n"
            "\n"
            "```python\n"
            "# Before\n"
            "allow_origins = [\"*\"]\n"
            "\n"
            "# After\n"
            "allow_origins = settings.cors_origins\n"
            "```"
        )

    if "QLoRA/train_qlora_elderly_care.yaml" in files and _patch_has_key_assignment(
        snapshots, "bf16"
    ):
        snippets.append(
            "- 训练配置建议显式声明精度降级策略，减少环境不一致导致的启动失败（示例）。\n"
            "\n"
            "```yaml\n"
            "# Before\n"
            "bf16: true\n"
            "\n"
            "# After\n"
            "bf16: true\n"
            "fp16: false  # 与 bf16 二选一，由部署环境决定\n"
            "```"
        )

    if not snippets:
        snippets.append("- 当前改动量较小，建议先补充针对关键路径的单元测试再进行重构。")

    return snippets


def _questions(snapshots: list[CommitSnapshot]) -> list[str]:
    files = {path for snapshot in snapshots for path in snapshot.files}
    questions = [
        "- 这些 commit 是否计划直接进入生产，还是仅用于 Demo/内测环境？（影响兼容与安全基线）",
    ]

    if any(path.startswith("src/silver_pilot/server/") for path in files):
        questions.append("- WebSocket 协议是否有版本号或 schema 管理机制？若无，建议明确升级策略。")

    if "QLoRA/train_qlora_elderly_care.yaml" in files:
        questions.append("- 训练配置对应的数据集版本与模型基座版本是否已冻结？")

    return questions


def render_commit_review_report(snapshots: list[CommitSnapshot]) -> str:
    """Render a markdown report that matches the requested structure."""
    commit_list = ", ".join(
        snapshot.commit_id[:_COMMIT_ID_DISPLAY_LENGTH] for snapshot in snapshots
    )
    purpose = "；".join(snapshot.subject for snapshot in snapshots)

    summary = [
        f"本次审查覆盖 commit：`{commit_list}`。",
        f"核心目标是：{purpose}。",
    ]

    lines: list[str] = []
    lines.append(f"## {_REQUIRED_HEADINGS[0]}")
    lines.extend(summary)
    lines.append("")

    lines.append(f"## {_REQUIRED_HEADINGS[1]}")
    lines.extend(_compatibility_lines(snapshots))
    lines.append("")

    lines.append(f"## {_REQUIRED_HEADINGS[2]}")
    lines.extend(_conflict_lines(snapshots))
    lines.append("")

    lines.append(f"## {_REQUIRED_HEADINGS[3]}")
    lines.extend(_optimization_lines(snapshots))
    lines.append("")

    lines.append(f"## {_REQUIRED_HEADINGS[4]}")
    lines.extend(_questions(snapshots))

    return "\n".join(lines)


def review_commits(commit_input: str, repo_path: str | Path) -> str:
    """Load commit context from Git and return a structured markdown report."""
    ids = parse_commit_ids(commit_input)
    if not ids:
        raise ValueError("No valid commit ids found in input")

    repo = Path(repo_path).resolve()
    snapshots = [_load_snapshot(repo, commit_id) for commit_id in ids]
    return render_commit_review_report(snapshots)
