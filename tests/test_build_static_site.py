from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "build_static_site.py"
SPEC = importlib.util.spec_from_file_location("build_static_site", SCRIPT)
assert SPEC and SPEC.loader
site_builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = site_builder
SPEC.loader.exec_module(site_builder)


class BuildStaticSiteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.course_root = self.root / "课程目录"
        self.course_root.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_build_site_index_reads_readme_tables_and_matches_local_files(self) -> None:
        review_dir = self.course_root / "图论" / "复习资料"
        exam_dir = self.course_root / "图论" / "历年试题"
        review_dir.mkdir(parents=True)
        exam_dir.mkdir()
        (review_dir / "图论-复习重点.pdf").write_bytes(b"x")
        (exam_dir / "2025年春-期末考试-无答案.pdf").write_bytes(b"x")
        (review_dir / "README.md").write_text(
            "# 复习资料\n\n"
            "文件名|作者|来源|文件类型|文件大小|最近更新时间|备注\n"
            "---|---|---|---|---|---|---\n"
            "图论-复习重点|Alice|Local|PDF|1 KB|2025年1月1日|\n",
            encoding="utf-8",
        )
        (exam_dir / "README.md").write_text(
            "# 历年试题\n\n"
            "文件名|来源 | 文件类型|文件大小|备注\n"
            "---|--|------|-------|---\n"
            "2025年春-期末考试-无答案|GitHub Issue|PDF|1 KB|闭卷\n",
            encoding="utf-8",
        )

        index = site_builder.build_site_index(self.root)

        self.assertEqual(index["course_count"], 1)
        self.assertEqual(index["resource_count"], 2)
        course = index["courses"][0]
        self.assertEqual(course["name"], "图论")
        self.assertEqual(course["category_counts"]["复习资料"], 1)
        resources = {resource["name"]: resource for resource in index["resources"]}
        self.assertEqual(resources["图论-复习重点"]["path"], "课程目录/图论/复习资料/图论-复习重点.pdf")
        self.assertTrue(resources["2025年春-期末考试-无答案"]["is_local"])
        self.assertEqual(resources["2025年春-期末考试-无答案"]["remark"], "闭卷")

    def test_write_site_index_outputs_utf8_json(self) -> None:
        course_dir = self.course_root / "数据库原理及应用" / "作业"
        course_dir.mkdir(parents=True)
        (course_dir / "README.md").write_text(
            "# 作业\n\n文件名|文件类型|文件大小|备注\n---|---|---|---\n实验一|PDF|2 KB|\n",
            encoding="utf-8",
        )
        output = self.root / "site" / "data" / "resources.json"

        site_builder.write_site_index(self.root, output)

        data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(data["courses"][0]["name"], "数据库原理及应用")
        self.assertEqual(data["resources"][0]["name"], "实验一")


if __name__ == "__main__":
    unittest.main()
