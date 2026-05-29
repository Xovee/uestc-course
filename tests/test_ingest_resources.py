from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "ingest_resources.py"
SPEC = importlib.util.spec_from_file_location("ingest_resources", SCRIPT)
assert SPEC and SPEC.loader
ingest = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ingest
SPEC.loader.exec_module(ingest)


class IngestResourcesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.incoming = self.root / "_incoming"
        self.repo.mkdir()
        self.incoming.mkdir()
        self.course_root = self.repo / "课程目录"
        self.course_root.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_course(self, name: str, category: str, readme: str | None = None) -> Path:
        category_dir = self.course_root / name / category
        category_dir.mkdir(parents=True)
        if readme is not None:
            (category_dir / "README.md").write_text(readme, encoding="utf-8")
        return category_dir

    def touch_file(self, name: str, content: bytes = b"x", mtime: datetime | None = None) -> Path:
        path = self.incoming / name
        path.write_bytes(content)
        if mtime is not None:
            stamp = mtime.timestamp()
            os.utime(path, (stamp, stamp))
        return path

    def touch_text(self, name: str, content: str, mtime: datetime | None = None) -> Path:
        return self.touch_file(name, content.encode("utf-8"), mtime)

    def test_scan_uses_file_mtime_and_infers_categories(self) -> None:
        self.make_course(
            "网络计算模式",
            "复习资料",
            "# 复习资料\n\n文件名|作者|来源|文件类型|文件大小|最近更新时间|备注\n---|---|---|---|---|---|---\n",
        )
        self.make_course(
            "组合数学",
            "历年试题",
            "# 历年试题\n\n文件名|来源|文件类型|文件大小|备注\n---|---|---|---|---\n",
        )
        self.make_course(
            "数字逻辑",
            "作业",
            "# 作业\n\n文件名|文件类型|文件大小|备注\n---|---|---|---\n",
        )
        expected_mtime = datetime(2024, 3, 4, 12, 0, 0)
        self.touch_file("网络计算模式-复习重点.pdf", b"x" * 2048, expected_mtime)
        self.touch_file("组合数学-2025年秋-期中考试-无答案.docx")
        self.touch_file("数字逻辑-第一次作业.pdf")

        plan = ingest.scan_resources(self.incoming, self.repo)
        by_source = {entry["source"]: entry for entry in plan["entries"]}

        review = by_source["网络计算模式-复习重点.pdf"]
        self.assertEqual(review["destination"]["course"], "网络计算模式")
        self.assertEqual(review["destination"]["category"], "复习资料")
        self.assertEqual(review["metadata"]["file_type"], "PDF")
        self.assertEqual(review["metadata"]["file_size"], "2 KB")
        self.assertEqual(review["metadata"]["updated_at"], "2024年3月4日")
        self.assertTrue(review["apply"])

        exam = by_source["组合数学-2025年秋-期中考试-无答案.docx"]
        self.assertEqual(exam["destination"]["category"], "历年试题")

        assignment = by_source["数字逻辑-第一次作业.pdf"]
        self.assertEqual(assignment["destination"]["category"], "作业")

    def test_multiple_course_matches_need_review(self) -> None:
        self.make_course("操作系统", "复习资料", "# 复习资料\n")
        self.make_course("计算机操作系统", "复习资料", "# 复习资料\n")
        self.touch_file("计算机操作系统-复习.pdf")

        plan = ingest.scan_resources(self.incoming, self.repo)
        entry = plan["entries"][0]

        self.assertEqual(entry["status"], "needs_review")
        self.assertFalse(entry["apply"])
        self.assertIn("multiple_course_matches", entry["warnings"])
        self.assertEqual(entry["destination"]["course"], None)

    def test_scan_marks_existing_destination_as_conflict(self) -> None:
        category_dir = self.make_course(
            "网络计算模式",
            "复习资料",
            "# 复习资料\n\n文件名|作者|来源|文件类型|文件大小|最近更新时间|备注\n---|---|---|---|---|---|---\n",
        )
        (category_dir / "网络计算模式-复习重点.pdf").write_bytes(b"existing")
        self.touch_file("网络计算模式-复习重点.pdf")

        plan = ingest.scan_resources(self.incoming, self.repo)
        entry = plan["entries"][0]

        self.assertEqual(entry["status"], "conflict")
        self.assertFalse(entry["apply"])
        self.assertIn("destination_file_exists", entry["warnings"])

    def test_scan_uses_existing_exam_category_alias(self) -> None:
        self.make_course(
            "计算机系统结构",
            "历年真题",
            "# 历年真题\n\n文件名|来源|文件类型|文件大小|备注\n---|---|---|---|---\n",
        )
        self.touch_file("计算机系统结构-2022秋-期末考试-无答案.pdf")

        plan = ingest.scan_resources(self.incoming, self.repo)
        entry = plan["entries"][0]

        self.assertEqual(entry["destination"]["category"], "历年真题")
        self.assertTrue(entry["apply"])

    def test_scan_requires_review_when_readme_has_multiple_file_tables(self) -> None:
        self.make_course(
            "大学物理",
            "历年试题",
            (
                "# 历年试题\n\n"
                "文件名|来源|文件类型|文件大小|备注\n"
                "---|---|---|---|---\n"
                "A|Local|PDF|1 KB|\n\n"
                "文件名|来源|文件类型|文件大小|备注\n"
                "---|---|---|---|---\n"
                "B|Local|PDF|1 KB|\n"
            ),
        )
        self.touch_file("大学物理-2024年春-期末考试-无答案.pdf")

        plan = ingest.scan_resources(self.incoming, self.repo)
        entry = plan["entries"][0]

        self.assertEqual(entry["status"], "needs_review")
        self.assertFalse(entry["apply"])
        self.assertIn("multiple_readme_file_tables", entry["warnings"])

    def test_apply_copies_file_updates_readme_and_keeps_incoming(self) -> None:
        self.make_course(
            "网络计算模式",
            "复习资料",
            "# 复习资料\n\n文件名|作者|来源|文件类型|文件大小|最近更新时间|备注\n---|---|---|---|---|---|---\n旧资料|Unknown|Local|PDF|1 KB|2020年1月1日|\n",
        )
        source = self.touch_file("网络计算模式-新资料.pdf", b"x" * 1024, datetime(2024, 5, 6, 8, 0, 0))
        plan = ingest.scan_resources(self.incoming, self.repo)

        report = ingest.apply_plan(self.incoming, self.repo, plan)

        target = self.course_root / "网络计算模式" / "复习资料" / "网络计算模式-新资料.pdf"
        readme = target.parent / "README.md"
        self.assertTrue(target.exists())
        self.assertTrue(source.exists())
        self.assertEqual(len(report["applied"]), 1)

        content = readme.read_text(encoding="utf-8")
        self.assertIn("网络计算模式-新资料|Unknown|Local|PDF|1 KB|2024年5月6日|", content)
        self.assertLess(
            content.index("网络计算模式-新资料"),
            content.index("旧资料"),
        )

    def test_prepare_normalizes_filename_and_screens_safe_text(self) -> None:
        self.make_course(
            "网络计算模式",
            "复习资料",
            "# 复习资料\n\n文件名|作者|来源|文件类型|文件大小|最近更新时间|备注\n---|---|---|---|---|---|---\n",
        )
        self.touch_text("网络计算模式 期末 复习.txt", "普通复习重点")

        plan = ingest.prepare_resources(self.incoming, self.repo)
        entry = plan["entries"][0]

        self.assertEqual(plan["schema_version"], 2)
        self.assertEqual(entry["destination"]["filename"], "网络计算模式-期末-复习.txt")
        self.assertEqual(entry["metadata"]["display_name"], "网络计算模式-期末-复习")
        self.assertEqual(entry["content_screening"]["risk_level"], "low")
        self.assertTrue(entry["apply"])

    def test_prepare_blocks_privacy_risk_for_manual_review(self) -> None:
        self.make_course(
            "网络计算模式",
            "复习资料",
            "# 复习资料\n\n文件名|作者|来源|文件类型|文件大小|最近更新时间|备注\n---|---|---|---|---|---|---\n",
        )
        self.touch_text("网络计算模式-名单.txt", "姓名：张三\n手机号：13800138000")

        plan = ingest.prepare_resources(self.incoming, self.repo)
        entry = plan["entries"][0]

        self.assertEqual(entry["status"], "needs_review")
        self.assertFalse(entry["apply"])
        self.assertIn("content_risk_found", entry["warnings"])
        self.assertEqual(entry["content_screening"]["risk_level"], "high")

    def test_prepare_and_apply_can_create_new_course_after_confirmation(self) -> None:
        self.touch_text("新课程-复习重点.txt", "普通复习重点", datetime(2024, 7, 8, 9, 0, 0))
        plan = ingest.prepare_resources(self.incoming, self.repo)
        entry = plan["entries"][0]

        self.assertTrue(entry["new_course"])
        self.assertEqual(entry["destination"]["course"], "新课程")
        self.assertEqual(entry["destination"]["category"], "复习资料")
        self.assertEqual(entry["status"], "needs_review")
        self.assertFalse(entry["apply"])

        entry["apply"] = True
        report = ingest.apply_plan(self.incoming, self.repo, plan)

        course_dir = self.course_root / "新课程"
        target = course_dir / "复习资料" / "新课程-复习重点.txt"
        self.assertTrue(target.exists())
        self.assertEqual(len(report["applied"]), 1)
        self.assertIn("# 新课程", (course_dir / "README.md").read_text(encoding="utf-8"))
        self.assertIn(
            "新课程-复习重点|Unknown|Local|Text|18 B|2024年7月8日|",
            (course_dir / "复习资料" / "README.md").read_text(encoding="utf-8"),
        )

    def test_cli_scan_writes_json_output(self) -> None:
        self.make_course(
            "网络计算模式",
            "复习资料",
            "# 复习资料\n\n文件名|作者|来源|文件类型|文件大小|最近更新时间|备注\n---|---|---|---|---|---|---\n",
        )
        self.touch_file("网络计算模式-复习重点.pdf")
        output = self.root / "plan.json"

        stdout = StringIO()
        with redirect_stdout(stdout):
            exit_code = ingest.main([
                "--repo-root",
                str(self.repo),
                "scan",
                "--incoming",
                str(self.incoming),
                "--output",
                str(output),
            ])

        self.assertEqual(exit_code, 0)
        self.assertIn("网络计算模式-复习重点.pdf", stdout.getvalue())
        data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(data["entries"][0]["destination"]["course"], "网络计算模式")

    def test_cli_prepare_writes_json_output(self) -> None:
        self.make_course(
            "网络计算模式",
            "复习资料",
            "# 复习资料\n\n文件名|作者|来源|文件类型|文件大小|最近更新时间|备注\n---|---|---|---|---|---|---\n",
        )
        self.touch_text("网络计算模式 复习.txt", "普通复习重点")
        output = self.root / "plan.json"

        stdout = StringIO()
        with redirect_stdout(stdout):
            exit_code = ingest.main([
                "--repo-root",
                str(self.repo),
                "prepare",
                "--incoming",
                str(self.incoming),
                "--output",
                str(output),
            ])

        self.assertEqual(exit_code, 0)
        self.assertIn('"mode": "prepare"', stdout.getvalue())
        data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 2)


if __name__ == "__main__":
    unittest.main()
