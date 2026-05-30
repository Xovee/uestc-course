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
        self.make_templates()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_templates(self) -> None:
        template_root = self.course_root / "0-模板"
        (template_root / "作业").mkdir(parents=True)
        (template_root / "历年试题").mkdir()
        (template_root / "复习资料").mkdir()
        (template_root / "README.md").write_text(
            "# 模板\n\n"
            "课程介绍。\n\n"
            "## 下载\n\n"
            "[点击链接，下载文件夹内所有内容]"
            "(https://xovee.github.io/gitzip/?https://github.com/Xovee/uestc-course/tree/main/课程目录/【替换为文件夹名】)\n",
            encoding="utf-8",
        )
        (template_root / "作业" / "README.md").write_text(
            "# 作业\n\n文件名|文件类型|文件大小|备注\n---|---|---|---\n模板作业|PDF|1 KB|\n",
            encoding="utf-8",
        )
        (template_root / "历年试题" / "README.md").write_text(
            "# 历年试题\n\n文件名|来源 | 文件类型|文件大小|备注\n---|--|------|-------|---\n模板试题|河畔|PDF|1 KB|\n",
            encoding="utf-8",
        )
        (template_root / "复习资料" / "README.md").write_text(
            "# 复习资料\n\n文件名|作者|来源|文件类型|文件大小|最近更新时间|备注\n---|---|---|---|---|---|---\n模板复习|Unknown|Local|PDF|1 KB||\n",
            encoding="utf-8",
        )

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
        self.make_course(
            "数据库原理及应用",
            "复习资料",
            "# 复习资料\n\n文件名|来源|文件类型|文件大小|备注\n---|---|---|---|---\n",
        )
        expected_mtime = datetime(2024, 3, 4, 12, 0, 0)
        self.touch_file("网络计算模式-复习重点.pdf", b"x" * 2048, expected_mtime)
        self.touch_file("组合数学-2025年秋-期中考试-无答案.docx")
        self.touch_file("数字逻辑-第一次作业.pdf")
        self.touch_file("数据库原理及应用-软院SQL机考题.zip")

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

        sql_machine_test = by_source["数据库原理及应用-软院SQL机考题.zip"]
        self.assertEqual(sql_machine_test["destination"]["category"], "复习资料")

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

    def test_scan_uses_canonical_exam_category_even_if_legacy_exists(self) -> None:
        self.make_course(
            "计算机系统结构",
            "历年真题",
            "# 历年真题\n\n文件名|来源|文件类型|文件大小|备注\n---|---|---|---|---\n",
        )
        self.touch_file("计算机系统结构-2022秋-期末考试-无答案.pdf")

        plan = ingest.scan_resources(self.incoming, self.repo)
        entry = plan["entries"][0]

        self.assertEqual(entry["destination"]["category"], "历年试题")
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

    def test_apply_uses_category_template_and_keeps_author_in_remarks(self) -> None:
        self.make_course("数据库原理及应用", "历年试题")
        self.touch_file("数据库-2026年-期中考试.docx", b"x" * 512)
        plan = {
            "entries": [
                {
                    "source": "数据库-2026年-期中考试.docx",
                    "apply": True,
                    "destination": {
                        "course": "数据库原理及应用",
                        "category": "历年试题",
                        "filename": "2026年-期中考试-无答案.docx",
                    },
                    "metadata": {
                        "display_name": "2026年-期中考试-无答案",
                        "author": "woohaixi",
                        "source": "GitHub Issue",
                        "file_type": "Word",
                        "file_size": "512 B",
                        "remark": "闭卷",
                    },
                }
            ]
        }

        ingest.apply_plan(self.incoming, self.repo, plan)

        content = (self.course_root / "数据库原理及应用" / "历年试题" / "README.md").read_text(encoding="utf-8")
        self.assertIn("文件名|来源 | 文件类型|文件大小|备注", content)
        self.assertNotIn("模板试题", content)
        self.assertIn("2026年-期中考试-无答案|GitHub Issue|Word|512 B|闭卷；作者：woohaixi", content)

    def test_prepare_marks_exam_archives_for_extraction(self) -> None:
        self.make_course(
            "数据库原理及应用",
            "历年试题",
            "# 历年试题\n\n文件名|来源|文件类型|文件大小|备注\n---|---|---|---|---\n",
        )
        self.touch_file("数据库原理及应用-期末真题.zip")

        plan = ingest.prepare_resources(self.incoming, self.repo)
        entry = plan["entries"][0]

        self.assertEqual(entry["destination"]["category"], "历年试题")
        self.assertIn("exam_metadata_requires_content_review", entry["warnings"])
        self.assertIn("exam_archive_should_be_extracted", entry["warnings"])
        self.assertFalse(entry["apply"])

    def test_prepare_requires_exam_metadata_content_review(self) -> None:
        self.make_course(
            "数据库原理及应用",
            "历年试题",
            "# 历年试题\n\n文件名|来源|文件类型|文件大小|备注\n---|---|---|---|---\n",
        )
        self.touch_file("数据库原理及应用-2007年-期末考试.docx", b"safe text")

        plan = ingest.prepare_resources(self.incoming, self.repo)
        entry = plan["entries"][0]

        self.assertEqual(entry["status"], "needs_review")
        self.assertFalse(entry["apply"])
        self.assertIn("exam_metadata_requires_content_review", entry["warnings"])

    def test_apply_rejects_exam_zip_without_explicit_override(self) -> None:
        self.make_course(
            "数据库原理及应用",
            "历年试题",
            "# 历年试题\n\n文件名|来源|文件类型|文件大小|备注\n---|---|---|---|---\n",
        )
        self.touch_file("数据库原理及应用-期末真题.zip")
        plan = {
            "entries": [
                {
                    "source": "数据库原理及应用-期末真题.zip",
                    "apply": True,
                    "destination": {
                        "course": "数据库原理及应用",
                        "category": "历年试题",
                        "filename": "数据库原理及应用-期末真题.zip",
                    },
                    "metadata": {
                        "display_name": "数据库原理及应用-期末真题",
                        "source": "Issue",
                        "file_type": "ZIP",
                        "file_size": "1 B",
                    },
                }
            ]
        }

        with self.assertRaisesRegex(ValueError, "Exam archives must be extracted"):
            ingest.apply_plan(self.incoming, self.repo, plan)

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
        self.assertEqual(entry["destination"]["category"], "复习资料")
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

    def test_load_json_accepts_utf8_bom(self) -> None:
        path = self.root / "bom.json"
        path.write_text('\ufeff{"entries": []}', encoding="utf-8")

        data = ingest.load_json(path)

        self.assertEqual(data, {"entries": []})

    def test_audit_reports_category_readme_template_mismatch(self) -> None:
        self.make_course(
            "数据库原理及应用",
            "历年试题",
            "# 历年试题\n\n文件名|科目|考试形式|答案|文件类型|文件大小\n---|---|---|---|---|---\n",
        )

        report = ingest.audit_repository(self.repo)
        mismatch_paths = {
            Path(item["path"]).as_posix()
            for item in report["category_readme_template_mismatches"]
        }

        self.assertIn(
            (self.course_root / "数据库原理及应用" / "历年试题" / "README.md").as_posix(),
            mismatch_paths,
        )

    def test_resource_date_key_understands_ranges_and_academic_codes(self) -> None:
        self.assertEqual(ingest.resource_date_key("2018年秋至2021年春-期末考试"), (2021, 1))
        self.assertEqual(ingest.resource_date_key("2000年到2009年-期末考试"), (2009, None))
        self.assertEqual(ingest.resource_date_key("2023-2024-2-第四章-补充作业"), (2024, 1))
        self.assertEqual(ingest.resource_date_key("2024上-第五次测试"), (2024, 1))
        self.assertEqual(ingest.resource_date_key("202501-随机过程-期末自救指南"), (2025, None))
        self.assertEqual(ingest.resource_date_key("2007-2008学年第一学期"), (2007, 3))
        self.assertEqual(ingest.resource_date_key("2007-2008学年第二学期"), (2008, 1))
        self.assertIsNone(ingest.resource_date_key("ISO_IEC_IEEE.42010-2011"))

    def test_audit_reports_readme_file_inventory_issues(self) -> None:
        category_dir = self.make_course(
            "矩阵理论",
            "历年试题",
            (
                "# 历年试题\n\n"
                "文件名|来源 | 文件类型|文件大小|备注\n"
                "---|--|------|-------|---\n"
                "2023年春-期末考试-无答案|Local|PDF|1 KB|\n"
                "2024年春-期末考试-无答案|Local|PDF|1 KB|\n"
                "2024年春-期末考试-无答案|Local|PDF|1 KB|\n"
                "矩阵理论-2025年春-作业1|Local|Word|1 KB|\n"
                "课程测试1-答案|Local|PDF|1 KB|\n"
                "高级网络计算-秦臻|Local|Word|1 KB|\n"
                "Anki牌组|Local|APKG|1 KB|\n"
                "GET-2016年春|Local|Folder|1 KB|\n"
                "复习提纲2014|Local|PPT|1 KB|\n"
                "不存在资源|Local|PDF|1 KB|\n"
                "在线文档|Local|Online Doc|-|语雀文档\n"
                "暂无试题|Local|-|-|暂无资源\n"
                "2025年秋-期末考试-回忆版|河畔|在线|-|地址：https://example.com/thread/1\n"
            ),
        )
        (category_dir / "2023年春-期末考试-无答案.pdf").write_bytes(b"x")
        (category_dir / "2024年春-期末考试-无答案.pdf").write_bytes(b"x")
        (category_dir / "2025年春-作业1.docx").write_bytes(b"x")
        (category_dir / "课程测试1答案.pdf").write_bytes(b"x")
        (category_dir / "高级网络计算—秦臻.docx").write_bytes(b"x")
        (category_dir / "Anki牌组.apkg").write_bytes(b"x")
        (category_dir / "GET-2016春").mkdir()
        (category_dir / "复习题纲2014.ppt").write_bytes(b"x")
        (category_dir / "assets").mkdir()
        (category_dir / "未登记.pdf").write_bytes(b"x")
        (category_dir / "重复扩展.pdf.pdf").write_bytes(b"x")

        report = ingest.audit_repository(self.repo)

        self.assertEqual(
            [item["name"] for item in report["readme_entries_without_files"]],
            ["不存在资源"],
        )
        missing_paths = {Path(item["path"]).name for item in report["files_missing_readme_entries"]}
        self.assertEqual(missing_paths, {"未登记.pdf", "重复扩展.pdf.pdf"})
        duplicate_names = {item["name"] for item in report["duplicate_readme_resource_names"]}
        self.assertEqual(duplicate_names, {"2024年春-期末考试-无答案"})
        order_issues = {item["issue"] for item in report["readme_resource_order_issues"]}
        self.assertIn("dated_rows_not_descending", order_issues)
        duplicate_extension_paths = {
            Path(item["path"]).name for item in report["suspicious_duplicate_extensions"]
        }
        self.assertEqual(duplicate_extension_paths, {"重复扩展.pdf.pdf"})

    def test_audit_matches_leading_date_prefix_for_non_exam_resources(self) -> None:
        category_dir = self.make_course(
            "金融衍生工具",
            "作业",
            (
                "# 作业\n\n"
                "文件名|文件类型|文件大小|备注\n"
                "---|---|---|---\n"
                "2024春-课程实验|XLSX|1 KB|\n"
            ),
        )
        (category_dir / "课程实验.xlsx").write_bytes(b"x")

        report = ingest.audit_repository(self.repo)

        self.assertEqual(report["readme_entries_without_files"], [])
        self.assertEqual(report["files_missing_readme_entries"], [])

    def test_audit_reports_legacy_exam_category_and_empty_resource_dirs(self) -> None:
        legacy_dir = self.make_course(
            "计算机系统结构",
            "历年真题",
            "# 历年真题\n\n文件名|来源 | 文件类型|文件大小|备注\n---|--|------|-------|---\n",
        )
        empty_dir = self.make_course(
            "网络计算模式",
            "复习资料",
            "# 复习资料\n\n文件名|作者|来源|文件类型|文件大小|最近更新时间|备注\n---|---|---|---|---|---|---\n",
        )

        report = ingest.audit_repository(self.repo)

        self.assertIn(str(legacy_dir), report["legacy_exam_category_dirs"])
        self.assertIn(str(empty_dir), report["empty_resource_directories"])

    def test_audit_old_master_links_only_flags_this_repo(self) -> None:
        readme = self.repo / "README.md"
        readme.write_text(
            "[old self](https://github.com/Xovee/uestc-course/tree/master/课程目录)\n"
            "[external](https://github.com/example/project/tree/master/docs)\n",
            encoding="utf-8",
        )

        report = ingest.audit_repository(self.repo)

        self.assertEqual(len(report["old_master_links"]), 1)
        self.assertEqual(Path(report["old_master_links"][0]["path"]), readme)

    def test_audit_placeholder_download_links_ignores_template_course(self) -> None:
        report = ingest.audit_repository(self.repo)

        self.assertEqual(report["placeholder_download_links"], [])

    def test_cli_audit_writes_json_output(self) -> None:
        stdout = StringIO()
        with redirect_stdout(stdout):
            exit_code = ingest.main([
                "--repo-root",
                str(self.repo),
                "audit",
            ])

        self.assertEqual(exit_code, 0)
        data = json.loads(stdout.getvalue())
        self.assertIn("category_readme_template_mismatches", data)


if __name__ == "__main__":
    unittest.main()
