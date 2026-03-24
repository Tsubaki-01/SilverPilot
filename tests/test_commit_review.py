from __future__ import annotations

import unittest
from pathlib import Path

from silver_pilot.server.commit_review import build_commit_review_report


class CommitReviewReportTests(unittest.TestCase):
    def test_build_report_contains_required_sections(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        report = build_commit_review_report(
            repo_root,
            [
                "6732a4c21320d9904e649f1f13c44764e02fd614",
                "57700ee9f1d910a8427f44097826453fe8d99de8",
            ],
        )

        self.assertIn("📝 **变更摘要**", report)
        self.assertIn("🔄 **兼容性报告**", report)
        self.assertIn("⚠️ **潜在冲突**", report)
        self.assertIn("🚀 **优化建议**", report)
        self.assertIn("❓ **需要明确的疑问**", report)
        self.assertIn("6732a4c", report)
        self.assertIn("57700ee", report)

    def test_invalid_commit_hash_raises(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with self.assertRaises(ValueError):
            build_commit_review_report(repo_root, ["not-a-commit"])


if __name__ == "__main__":
    unittest.main()
