from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "repository_size_report.py"
SPEC = importlib.util.spec_from_file_location("repository_size_report", SCRIPT)
assert SPEC and SPEC.loader
size_report = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = size_report
SPEC.loader.exec_module(size_report)


class RepositorySizeReportTest(unittest.TestCase):
    def test_human_size_formats_binary_units(self) -> None:
        self.assertEqual(size_report.human_size(512), "512 B")
        self.assertEqual(size_report.human_size(1536), "1.5 KB")
        self.assertEqual(size_report.human_size(2 * 1024 * 1024), "2.0 MB")

    def test_build_report_flags_large_files_and_exam_archives(self) -> None:
        mb = 1024 * 1024
        records = [
            size_report.FileRecord("README.md", 1024),
            size_report.FileRecord("课程目录/课程A/复习资料/notes.pdf", 2 * mb),
            size_report.FileRecord("课程目录/课程A/历年试题/2025年春.zip", 90 * mb),
            size_report.FileRecord("课程目录/课程A/历年试题/images/page1.png", 3 * mb),
            size_report.FileRecord("assets/img/banner.png", mb),
        ]

        report = size_report.build_report(records, limit=2, threshold_bytes=50 * mb)

        self.assertEqual(report["total_files"], 5)
        self.assertEqual(report["largest_files"][0]["path"], "课程目录/课程A/历年试题/2025年春.zip")
        self.assertEqual([row["path"] for row in report["large_files"]], ["课程目录/课程A/历年试题/2025年春.zip"])
        self.assertEqual([row["path"] for row in report["exam_archives"]], ["课程目录/课程A/历年试题/2025年春.zip"])
        self.assertEqual(report["by_top_level"][0]["name"], "课程目录")

        extension_rows = {row["name"]: row for row in report["by_extension"]}
        self.assertEqual(extension_rows[".zip"]["files"], 1)
        self.assertEqual(extension_rows[".png"]["files"], 2)

    def test_format_report_includes_empty_sections(self) -> None:
        report = size_report.build_report([], limit=5, threshold_bytes=10)

        text = size_report.format_report(report, limit=5, threshold_mb=10)

        self.assertIn("Tracked files: 0", text)
        self.assertIn("## Exam archives\n(none)", text)


if __name__ == "__main__":
    unittest.main()
