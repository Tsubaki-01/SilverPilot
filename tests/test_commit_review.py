import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from silver_pilot.review.commit_review import (
    CommitSnapshot,
    parse_commit_ids,
    render_commit_review_report,
    review_commits,
)


class CommitReviewTests(unittest.TestCase):
    def test_parse_commit_ids_from_multiline_input(self) -> None:
        raw = "请基于以下commit进行分析： 6732a4c\n 8d664f7\n 6732A4C"
        self.assertEqual(parse_commit_ids(raw), ["6732a4c", "8d664f7"])

    def test_render_report_has_required_sections_and_snippets(self) -> None:
        snapshots = [
            CommitSnapshot(
                commit_id="6732a4c",
                subject="初始化前后端接口",
                files=(
                    "src/silver_pilot/server/app.py",
                    "src/silver_pilot/server/models.py",
                    "src/silver_pilot/server/session_store.py",
                    "static/api-connector.js",
                ),
                patch_text="+global _graph\n+allow_origins=[\"*\"]\n+_messages",
            ),
            CommitSnapshot(
                commit_id="8d664f7",
                subject="新增QLoRA配置",
                files=("QLoRA/train_qlora_elderly_care.yaml",),
                patch_text="+bf16: true",
            ),
        ]

        report = render_commit_review_report(snapshots)

        self.assertIn("## 📝 变更摘要", report)
        self.assertIn("## 🔄 兼容性报告", report)
        self.assertIn("## ⚠️ 潜在冲突", report)
        self.assertIn("## 🚀 优化建议", report)
        self.assertIn("## ❓ 需要明确的疑问", report)
        self.assertIn("```python", report)
        self.assertIn("```yaml", report)

    def test_review_commits_loads_real_commit_metadata(self) -> None:
        # 使用仓库历史中的已知提交，验证与真实 git 历史的集成行为。
        repo = Path(__file__).resolve().parent.parent
        report = review_commits("6732a4c 8d664f7", repo)

        self.assertIn("`6732a4c, 8d664f7`", report)
        self.assertIn("## 📝 变更摘要", report)

    def test_review_commits_raises_clear_error_on_git_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            git_error = subprocess.CalledProcessError(1, ["git", "show"])
            git_error.stderr = "fatal: bad revision"
            with patch(
                "silver_pilot.review.commit_review.subprocess.run",
                side_effect=git_error,
            ):
                with self.assertRaises(ValueError) as ctx:
                    review_commits("6732a4c", tmp)
        self.assertIn("git command failed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
